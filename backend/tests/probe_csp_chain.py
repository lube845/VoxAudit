# -*- coding: utf-8 -*-
"""
内网自检脚本：照着《录音请求.txt》跑一遍 4 步链路，并把**每一步的原文**打出来。

用途：部署到内网后，先跑这个脚本确认「协议层」没问题（再排查业务层）。
它不碰数据库、不调 ASR/LLM，只跑 CSP 链路。

用法（在能访问 csp-adapter / escterminal 的机器上跑）：
    cd <项目根目录>
    set -a && . docker/.env && set +a
    python3 backend/tests/probe_csp_chain.py

    # 可选：指定工号和时间窗（默认用 .env 里的配置 + 最近 1 天）
    python3 backend/tests/probe_csp_chain.py --agent-id 61038 \
        --start "2026-10-19 00:00:00" --end "2026-10-20 00:00:00"

输出里带 [curl] 开头的行可以直接复制到内网机器上执行，用于和样例逐字对比。
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import httpx  # noqa: E402

from backend.core.config import settings  # noqa: E402
from backend.services.csp_service import (  # noqa: E402
    _common_body,
    _encode_body,
    _journal_no,
)


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()[:16]


def _curl(url: str, headers: dict, body: bytes | None = None, *, raw: bool = False) -> str:
    """拼一条可复制的 curl 命令"""
    parts = [f"curl -v '{url}'"]
    for k, v in headers.items():
        parts.append(f"  -H '{k}: {v}'")
    if body is not None:
        if raw:
            parts.append(f"  --data-binary '{body.decode('utf-8', 'replace')}'")
        else:
            parts.append(f"  -d '{body.decode('utf-8', 'replace')}'")
    return "\n".join(parts)


def _dump(title: str, resp: httpx.Response, *, show_body: bool = True) -> None:
    print(f"\n===== {title} =====")
    print(f"HTTP {resp.status_code}")
    for k, v in resp.headers.items():
        print(f"  < {k}: {v}")
    print(f"  响应体 {len(resp.content)} 字节  sha256[:16]={_sha(resp.content)}")
    if show_body:
        txt = resp.text
        print("  响应体前 400 字符：")
        print("   ", txt[:400].replace("\n", "\n    "))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent-id", default="", help="纯工号，如 61038（不带 k 前缀）")
    ap.add_argument("--start", default="", help="established_time_start，如 '2026-10-19 00:00:00'")
    ap.add_argument("--end", default="", help="established_time_end，如 '2026-10-20 00:00:00'")
    ap.add_argument("--size", type=int, default=10)
    ap.add_argument("--page", type=int, default=1)
    ap.add_argument("--no-decrypt", action="store_true", help="跳过第④步解密")
    args = ap.parse_args()

    csp = (settings.CSP_ADAPTER_BASE_URL or "").rstrip("/")
    icp = (settings.ICP_API_BASE_URL or "").strip()
    if not csp or not icp:
        print("✗ CSP_ADAPTER_BASE_URL / ICP_API_BASE_URL 未配置，请先 source docker/.env")
        return 2

    # 时间窗：默认取「昨天 00:00 → 今天 00:00」这样的完整一天（和样例一致）
    now = time.localtime()
    today = dt.date(now.tm_year, now.tm_mon, now.tm_mday)
    end = args.end or (today - dt.timedelta(days=1)).strftime("%Y-%m-%d 00:00:00")
    start = args.start or (today - dt.timedelta(days=2)).strftime("%Y-%m-%d 00:00:00")

    body = _common_body(args.page, args.size, args.agent_id or None, start, end)
    body_bytes = _encode_body(body)
    journal_no = _journal_no()

    print("### 本次请求参数")
    print(f"  agent_id           = {args.agent_id or '(空)'}")
    print(f"  时间窗             = {start} ~ {end}")
    print(f"  page/size          = {args.page}/{args.size}")
    print(f"  Source-Journal-No  = {journal_no}")
    print(f"  Global-Service-No  = {settings.X_CSP_GLOBAL_SERVICE_NO}")
    print(f"  ①②请求体 {len(body_bytes)} 字节 sha256[:16]={_sha(body_bytes)}")

    ok = True
    with httpx.Client(timeout=30) as client:
        # ——— ① 生成 MAC ———
        gen_headers = {
            "Content-Type": "application/octet-stream",
            "X-CSP-Global-Service-No": settings.X_CSP_GLOBAL_SERVICE_NO,
            "X-CSP-Source-Journal-No": journal_no,
            "X-CSP-Node-Name": settings.X_CSP_NODE_NAME_GENERATE,
        }
        print("\n[curl] ① generate：")
        print(_curl(f"{csp}/v1/mac/generate", gen_headers, body_bytes))
        try:
            r1 = client.post(f"{csp}/v1/mac/generate", content=body_bytes, headers=gen_headers)
        except Exception as e:
            print(f"✗ ① 网络错误：{e!r}")
            return 1
        _dump("① generate 响应", r1)
        try:
            d1 = r1.json()
        except Exception:
            print("✗ ① 响应不是合法 JSON")
            return 1
        mac = (d1.get("mac") or "").strip()
        if d1.get("success") is not True or d1.get("responseCode") != 0 or not mac:
            print(f"✗ ① generate 失败：{d1.get('responseRemark') or d1.get('responseDetail')}")
            return 1
        print(f"✓ ① 拿到 mac = {mac}")

        # ——— ② 业务查询 ———
        gzb_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-GZB-sourceSystemCode": settings.X_GZB_SOURCE_SYSTEM_CODE,
            "X-GZB-sinkSystemCode": settings.X_GZB_SINK_SYSTEM_CODE,
            "X-GZB-actionId": settings.X_GZB_ACTION_ID,
            "X-GZB-macEncryptType": str(settings.X_GZB_MAC_ENCRYPT_TYPE),
            "X-GZB-mac": mac,
        }
        print("\n[curl] ② 业务查询（请求体与 ① 逐字节相同）：")
        print(_curl(icp, gzb_headers, body_bytes))
        try:
            r2 = client.post(icp, content=body_bytes, headers=gzb_headers)
        except Exception as e:
            print(f"✗ ② 网络错误：{e!r}")
            return 1
        _dump("② 业务查询响应", r2)
        resp_mac = (r2.headers.get("x-gzb-mac") or "").strip()
        if not resp_mac:
            print("✗ ② 响应头缺少 x-gzb-mac（若中间有网关/代理，检查是否透传自定义响应头）")
            ok = False
        else:
            print(f"✓ ② 拿到待校验 mac = {resp_mac}")

        # ——— ③ 校验 MAC ———
        if resp_mac:
            verify_headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-CSP-Global-Service-No": settings.X_CSP_GLOBAL_SERVICE_NO,
                "X-CSP-Source-Journal-No": journal_no,
                "X-CSP-Node-Name": settings.X_CSP_NODE_NAME_VERIFY,
                "X-CSP-MAC": resp_mac,
            }
            print("\n[curl] ③ 校验 MAC（body = ②的原始响应字节，原样回传）：")
            print(_curl(f"{csp}/v1/mac/verify", verify_headers, r2.content, raw=True))
            try:
                r3 = client.post(f"{csp}/v1/mac/verify", content=r2.content, headers=verify_headers)
            except Exception as e:
                print(f"✗ ③ 网络错误：{e!r}")
                return 1
            _dump("③ verify 响应", r3)
            try:
                d3 = r3.json()
            except Exception:
                print("✗ ③ 响应不是合法 JSON")
                return 1
            if d3.get("success") is True and d3.get("responseCode") == 0 and d3.get("mac") is None:
                print("✓ ③ MAC 校验通过")
            else:
                print(f"✗ ③ MAC 校验失败：{d3.get('responseRemark') or d3.get('responseDetail') or d3}")
                ok = False

        # ——— ④ 解密第一条 ———
        try:
            d2 = r2.json()
        except Exception:
            d2 = {}
        records = (((d2.get("responseData") or {}).get("body") or {}).get("records") or [])
        print(f"\n② 共返回 {len(records)} 条记录")
        if records and not args.no_decrypt:
            cipher = (records[0].get("call_url_inner") or "").strip()
            if cipher:
                dec_headers = {
                    "Content-Type": "text/plain; charset=us-ascii",
                    "X-CSP-Key-Name": settings.CSP_KEY_NAME,
                }
                print("\n[curl] ④ 解密 call_url_inner：")
                print(_curl(f"{csp}/v1/password/decrypt", dec_headers, cipher.encode("ascii"), raw=True))
                try:
                    r4 = client.post(f"{csp}/v1/password/decrypt", content=cipher.encode("ascii"),
                                     headers=dec_headers)
                except Exception as e:
                    print(f"✗ ④ 网络错误：{e!r}")
                    return 1
                _dump("④ decrypt 响应", r4)
                d4 = r4.json()
                if d4.get("success") is True and d4.get("plaintext"):
                    print(f"✓ ④ 解密成功：{d4['plaintext']}")
                else:
                    print(f"✗ ④ 解密失败：{d4.get('responseRemark') or d4.get('responseDetail') or d4}")
                    ok = False

    print("\n" + ("=== 全部通过：链路与《录音请求.txt》一致 ===" if ok
                  else "=== 有步骤失败，见上面的 ✗ ==="))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
