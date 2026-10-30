# -*- coding: utf-8 -*-
"""
上游 CSP / ESCTerminal 4 步链路自检
（对照《录音请求.txt》里的真实 curl 样例，**逐字节**断言我们发出的请求）

链路：
  ① generate_mac  → POST {CSP}/v1/mac/generate
  ② 业务查询        → POST {ICP}  （带 X-GZB-mac = ①的结果）
  ③ verify_mac    → POST {CSP}/v1/mac/verify（X-CSP-MAC = ②响应头的 x-gzb-mac，body = ②的**原始字节**）
  ④ decrypt       → POST {CSP}/v1/password/decrypt（body = call_url_inner 裸串）

为什么强调「字节」：上游的 MAC 是对报文原文字节算的，
  - ① 和 ② 的请求体必须逐字节相同（样例是同一串 163 字节）
  - ③ 的 body 必须是 ② 收到的原始响应字节（重新序列化就验不过）
本文件里的断言全部比 bytes，不比解析后的对象。

跑法：
  python3 backend/tests/test_csp_flow.py     # 不依赖 pytest
  pytest backend/tests/test_csp_flow.py      # 装了 pytest 也能跑
"""
import asyncio
import json
import json as _json  # post() 的形参名是 json，会遮蔽 json 模块，这里留个别名
import os
import sys
from pathlib import Path

# —— 导入前先兜底必填配置（config 启动时会校验）——
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("ADMIN_PASSWORD", "test")
os.environ.setdefault("CSP_ADAPTER_BASE_URL", "http://csp-adapter:8081")
os.environ.setdefault("ICP_API_BASE_URL", "http://escterminal:10306/v1/icp/ICP1100010")

from backend.services import csp_service  # noqa: E402
from backend.services.csp_service import (  # noqa: E402
    CspApiError,
    decrypt_call_url,
    query_call_records,
)


# —— 《录音请求.txt》里的真实样例数据 ——
SAMPLE_MAC = "F4D7D9B6410F4444"          # ① generate 返回的 mac
SAMPLE_RESP_MAC = "904E4DF17CF35D42"     # ② escterminal 响应头 x-gzb-mac
SAMPLE_CIPHER = (
    "B386C21F11A12C2F44CEFEA082A859498CBBD54E88F5AE34D8DBF82B00F132EA56CFA5305CD0A2E0F1DD7E4D1CBF8"
    "FD1C09F6B24F13914C17E4A567B17C2A7238F5D43C7888FF840AD40B532ACC4F6D1A200BFDC79251EB28874AB7A7A1"
    "EFE40A9E6865531A3F8FC982BF3A74973B629"
)
SAMPLE_PLAINTEXT = (
    "http://172.25.166.137:8181/idp/file/get?filename=record/wav/25424493-1e45-4d14-bcb1-1b75865c88e4.wav"
)

# 样例里 ①②两次请求的 -d 请求体（**逐字节**，共 163 字节，与样例 Content-Length 一致）
SAMPLE_REQ_BODY = (
    '{"requestData": {"body": {"page": 1,"size": 10,"agent_id": "61038",'
    '"established_time_start": "2026-10-19 00:00:00",'
    '"established_time_end": "2026-10-20 00:00:00"}}}'
)

SAMPLE_ESC_RESPONSE = {
    "responseCode": "ICPAAAAAAA",
    "responseMessage": "处理成功",
    "responseDetail": "处理成功",
    "responseData": {
        "body": {
            "current": 1,
            "pages": 1,
            "size": 10,
            "total": 1,
            "records": [{
                "call_id": "aa828927-85a5-4396-b6fc-2da06f281c41",
                "agent_id": "61038",
                "agent_name": "61038",
                "dn_id": "1038",
                "calling_number": "135****9752",
                "phone_number": "1038",
                "established_time": "2026-10-19 14:40:40",
                "released_times": "2026-10-19 14:43:22",
                "handle_times": "162",
                "call_url": "F1813D881686C00E80FB231904DA0691AC6C7FD4831EB2626FAE5A0D49F31",
                "call_url_inner": SAMPLE_CIPHER,
                "reserve1": "", "reserve2": "", "reserve3": "", "reserve4": "", "reserve5": "",
            }],
        }
    },
}

# 样例里 ② 的响应体原文字节（紧凑格式，中文不转义）
SAMPLE_ESC_RAW = json.dumps(
    SAMPLE_ESC_RESPONSE, ensure_ascii=False, separators=(",", ":")
).encode("utf-8")


class _FakeResponse:
    def __init__(self, status_code=200, json_data=None, headers=None, text="", content=None):
        self.status_code = status_code
        self._json = json_data
        self.headers = headers or {}
        self.text = text or json.dumps(json_data, ensure_ascii=False)
        # content 模拟 httpx.Response.content：原始响应字节
        self.content = content if content is not None else self.text.encode("utf-8")

    def json(self):
        return self._json


class _FakeClient:
    """记录所有请求，按 URL 返回对应上游样例响应。"""

    calls: list = []
    esc_pages: dict = {}          # {page: _FakeResponse}，用于分页用例

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, json=None, content=None, headers=None):
        headers = {k.lower(): v for k, v in (headers or {}).items()}
        _FakeClient.calls.append({"url": url, "json": json, "content": content, "headers": headers})

        if url.endswith("/v1/mac/generate"):
            return _FakeResponse(json_data={
                "success": True, "responseCode": 0, "responseRemark": "Success",
                "responseDetail": None, "mac": SAMPLE_MAC,
            })
        if "/v1/icp/" in url:
            if _FakeClient.esc_pages:
                # 分页用例：按请求体里的 page 取对应响应
                body = _json.loads(content.decode("utf-8")) if content else {}
                page = body.get("requestData", {}).get("body", {}).get("page", 1)
                return _FakeClient.esc_pages[page]
            return _FakeResponse(json_data=SAMPLE_ESC_RESPONSE,
                                 headers={"x-gzb-mac": SAMPLE_RESP_MAC},
                                 content=SAMPLE_ESC_RAW)
        if url.endswith("/v1/mac/verify"):
            return _FakeResponse(json_data={
                "success": True, "responseCode": 0, "responseRemark": "Success",
                "responseDetail": None, "mac": None,
            })
        if url.endswith("/v1/password/decrypt"):
            return _FakeResponse(json_data={
                "success": True, "responseCode": 0, "responseRemark": "Success",
                "responseDetail": None, "plaintext": SAMPLE_PLAINTEXT,
            })
        raise AssertionError(f"未预期的请求 URL: {url}")


def _install_fake_client():
    import httpx
    httpx.AsyncClient = _FakeClient
    _FakeClient.calls = []
    _FakeClient.esc_pages = {}


def _restore_client():
    import httpx
    httpx.AsyncClient = _ORIGINAL_CLIENT


_ORIGINAL_CLIENT = None


def _run_query(**kwargs):
    """跑一次 query_call_records，返回 _FakeClient.calls"""
    global _ORIGINAL_CLIENT
    import httpx
    _ORIGINAL_CLIENT = httpx.AsyncClient
    _install_fake_client()
    try:
        records = asyncio.run(query_call_records(**kwargs))
    finally:
        _restore_client()
    return records, _FakeClient.calls


def test_query_call_records_matches_sample():
    """①②③ 三步的请求必须和《录音请求.txt》一致"""
    records, calls = _run_query(
        page=1, size=10, agent_id="61038",
        established_time_start="2026-10-19 00:00:00",
        established_time_end="2026-10-20 00:00:00",
    )

    assert len(calls) == 3, f"应有 3 次调用（generate/查询/verify），实际 {len(calls)}"
    gen, esc, verify = calls

    # —— ① generate ——
    assert gen["url"] == "http://csp-adapter:8081/v1/mac/generate"
    assert gen["headers"]["content-type"] == "application/octet-stream"
    assert gen["headers"]["x-csp-node-name"] == "ICPA"
    assert gen["headers"]["x-csp-global-service-no"] == "G202610130000000001"
    assert gen["headers"]["x-csp-source-journal-no"], "缺少 X-CSP-Source-Journal-No"
    # 请求体必须与样例逐字节一致（163 字节）
    assert gen["content"].decode("utf-8") == SAMPLE_REQ_BODY, "generate 请求体与样例不一致"
    assert len(gen["content"]) == 163, f"generate 请求体应为 163 字节，实际 {len(gen['content'])}"

    # —— ② 业务查询 ——
    assert esc["url"] == "http://escterminal:10306/v1/icp/ICP1100010"
    assert esc["headers"]["x-gzb-mac"] == SAMPLE_MAC, "X-GZB-mac 必须填 ① 生成的 mac"
    assert esc["headers"]["x-gzb-sourcesystemcode"] == "LMD"
    assert esc["headers"]["x-gzb-sinksystemcode"] == "ICP"
    assert esc["headers"]["x-gzb-actionid"] == "ICP1100010"
    assert esc["headers"]["x-gzb-macencrypttype"] == "4"
    assert esc["headers"]["content-type"] == "application/json"
    assert esc["headers"]["accept"] == "application/json"
    # 样例里的 escterminal 调用不带 X-CSP-* 头
    assert not any(k.startswith("x-csp-") for k in esc["headers"]), \
        "escterminal 请求不应带 X-CSP-* 头（与上游样例一致）"
    # 关键：② 的请求体必须与 ① 逐字节相同（上游按请求体原文算 MAC）
    assert esc["content"] == gen["content"], "查询请求体必须与 generate 逐字节一致"
    assert esc["content"].decode("utf-8") == SAMPLE_REQ_BODY, "查询请求体与样例不一致"

    # —— ③ verify ——
    assert verify["url"] == "http://csp-adapter:8081/v1/mac/verify"
    assert verify["headers"]["x-csp-mac"] == SAMPLE_RESP_MAC, \
        "X-CSP-MAC 必须填业务查询响应头返回的 x-gzb-mac"
    assert verify["headers"]["x-csp-node-name"] == "LMDA"
    assert verify["headers"]["content-type"] == "application/json"
    assert verify["headers"]["accept"] == "application/json"
    # 关键：③ 的 body 必须是 ② 的**原始响应字节**（不能重新序列化）
    assert verify["content"] == SAMPLE_ESC_RAW, "verify 的 body 必须是业务查询的原始响应字节"
    # 同一逻辑请求内，generate / verify 共用同一个 Source-Journal-No
    assert (verify["headers"]["x-csp-source-journal-no"]
            == gen["headers"]["x-csp-source-journal-no"]), \
        "generate / verify 必须共用同一个 X-CSP-Source-Journal-No"

    # —— 返回值 ——
    assert len(records) == 1
    r = records[0]
    assert r["call_id"] == "aa828927-85a5-4396-b6fc-2da06f281c41"
    assert r["call_url_inner"] == SAMPLE_CIPHER
    assert r["calling_number"] == "135****9752"
    assert r["phone_number"] == "1038"
    assert r["handle_times"] == 162, "handle_times 上游给字符串，必须转成 int"


def test_verify_sends_raw_bytes_not_reserialized():
    """上游若返回的响应体格式与「重新序列化」不同，verify 必须原样回传原始字节"""

    # 故意用「带空格 + \\uXXXX 转义」的响应体：重新序列化一定会变形
    raw = json.dumps(SAMPLE_ESC_RESPONSE, ensure_ascii=True, indent=None).encode("utf-8")
    assert raw != SAMPLE_ESC_RAW, "构造的原始字节应当与紧凑序列化不同"

    global _ORIGINAL_CLIENT
    import httpx
    _ORIGINAL_CLIENT = httpx.AsyncClient
    _install_fake_client()

    class _RawClient(_FakeClient):
        async def post(self, url, json=None, content=None, headers=None):
            headers = {k.lower(): v for k, v in (headers or {}).items()}
            _FakeClient.calls.append({"url": url, "json": json, "content": content, "headers": headers})
            if "/v1/icp/" in url:
                return _FakeResponse(json_data=SAMPLE_ESC_RESPONSE,
                                     headers={"x-gzb-mac": SAMPLE_RESP_MAC},
                                     content=raw)
            if url.endswith("/v1/mac/verify"):
                return _FakeResponse(json_data={
                    "success": True, "responseCode": 0, "responseRemark": "Success",
                    "responseDetail": None, "mac": None,
                })
            return await super().post(url, json=json, content=content, headers=headers)

    httpx.AsyncClient = _RawClient
    try:
        asyncio.run(query_call_records(
            page=1, size=10, agent_id="61038",
            established_time_start="2026-10-19 00:00:00",
            established_time_end="2026-10-20 00:00:00",
        ))
    finally:
        _restore_client()

    verify = _FakeClient.calls[-1]
    assert verify["url"].endswith("/v1/mac/verify")
    assert verify["content"] == raw, "verify 必须回传 ② 的原始响应字节，而不是重新序列化的 JSON"


def test_pagination_fetches_all_pages():
    """上游 pages>1 时自动翻页，每页各自走一遍 ①②③"""
    def _page_response(page, call_id):
        body = {
            "current": page, "pages": 2, "size": 10, "total": 2,
            "records": [{
                "call_id": call_id, "agent_id": "61038", "agent_name": "61038",
                "dn_id": "1038", "calling_number": "135****9752", "phone_number": "1038",
                "established_time": "2026-10-19 14:40:40",
                "released_times": "2026-10-19 14:43:22",
                "handle_times": "162",
                "call_url": "F1813D881686C00E80FB231904DA0691AC6C7FD4831EB2626FAE5A0D49F31",
                "call_url_inner": SAMPLE_CIPHER,
                "reserve1": "", "reserve2": "", "reserve3": "", "reserve4": "", "reserve5": "",
            }],
        }
        return _FakeResponse(
            json_data={"responseCode": "ICPAAAAAAA", "responseMessage": "处理成功",
                       "responseDetail": "处理成功", "responseData": {"body": body}},
            headers={"x-gzb-mac": SAMPLE_RESP_MAC},
        )

    global _ORIGINAL_CLIENT
    import httpx
    _ORIGINAL_CLIENT = httpx.AsyncClient
    _install_fake_client()
    _FakeClient.esc_pages = {1: _page_response(1, "call-1"), 2: _page_response(2, "call-2")}
    try:
        records = asyncio.run(query_call_records(
            page=1, size=10, agent_id="61038",
            established_time_start="2026-10-19 00:00:00",
            established_time_end="2026-10-20 00:00:00",
        ))
    finally:
        _restore_client()

    assert [r["call_id"] for r in records] == ["call-1", "call-2"], "两页都要取到"
    # 每页 3 步 = 6 次调用
    assert len(_FakeClient.calls) == 6, f"应为 6 次调用，实际 {len(_FakeClient.calls)}"
    # 两页的请求体不同（page 字段不同），但每页的 ①② 必须一致
    g1, e1, v1, g2, e2, v2 = _FakeClient.calls
    assert g1["content"] == e1["content"]
    assert g2["content"] == e2["content"]
    assert g1["content"] != g2["content"], "两页请求体应因 page 不同而不同"
    # 每页的 generate/verify 共用同一个 journal，两页之间 journal 不同
    assert v1["headers"]["x-csp-source-journal-no"] == g1["headers"]["x-csp-source-journal-no"]
    assert v2["headers"]["x-csp-source-journal-no"] == g2["headers"]["x-csp-source-journal-no"]
    assert v1["headers"]["x-csp-source-journal-no"] != v2["headers"]["x-csp-source-journal-no"]


def test_decrypt_matches_sample():
    """④ 解密：body 是裸密文串，头带 X-CSP-Key-Name"""
    global _ORIGINAL_CLIENT
    import httpx
    _ORIGINAL_CLIENT = httpx.AsyncClient
    _install_fake_client()
    try:
        plain = asyncio.run(decrypt_call_url(SAMPLE_CIPHER))
    finally:
        _restore_client()

    call = _FakeClient.calls[0]
    assert call["url"] == "http://csp-adapter:8081/v1/password/decrypt"
    assert call["headers"]["content-type"] == "text/plain; charset=us-ascii"
    assert call["headers"]["x-csp-key-name"] == "GZYH.LMDA_node.zek"
    assert call["content"] == SAMPLE_CIPHER.encode("ascii"), "解密 body 必须是裸密文串"
    assert plain == SAMPLE_PLAINTEXT


def test_verify_failure_aborts_batch():
    """MAC 校验失败 → 整批失败（不能拿着没校验过的数据去解密）"""
    global _ORIGINAL_CLIENT
    import httpx
    _ORIGINAL_CLIENT = httpx.AsyncClient

    class _BadVerifyClient(_FakeClient):
        async def post(self, url, json=None, content=None, headers=None):
            if url.endswith("/v1/mac/verify"):
                return _FakeResponse(json_data={
                    "success": True, "responseCode": 0, "mac": "SHOULD_BE_NULL",
                })
            return await super().post(url, json=json, content=content, headers=headers)

    httpx.AsyncClient = _BadVerifyClient
    _FakeClient.calls = []
    _FakeClient.esc_pages = {}
    try:
        try:
            asyncio.run(query_call_records(
                page=1, size=10, agent_id="61038",
                established_time_start="2026-10-19 00:00:00",
                established_time_end="2026-10-20 00:00:00",
            ))
        except CspApiError as e:
            assert "MAC 校验" in str(e), f"错误信息不对: {e}"
        else:
            raise AssertionError("MAC 校验失败时应当抛 CspApiError")
    finally:
        _restore_client()


def test_encode_body_matches_sample_bytes():
    """_encode_body 必须逐字节复现样例请求体（163 字节）"""
    from backend.services.csp_service import _common_body, _encode_body
    body = _common_body(
        page=1, size=10, agent_id="61038",
        established_time_start="2026-10-19 00:00:00",
        established_time_end="2026-10-20 00:00:00",
    )
    encoded = _encode_body(body)
    assert encoded.decode("utf-8") == SAMPLE_REQ_BODY
    assert len(encoded) == 163


def test_verify_accepts_echoed_mac():
    """有些环境在 verify 成功时会回显待校验的 mac（而不是 null）——只要与 X-CSP-MAC 一致就放行"""

    global _ORIGINAL_CLIENT
    import httpx
    _ORIGINAL_CLIENT = httpx.AsyncClient

    class _EchoClient(_FakeClient):
        async def post(self, url, json=None, content=None, headers=None):
            if url.endswith("/v1/mac/verify"):
                return _FakeResponse(json_data={
                    "success": True, "responseCode": 0, "responseRemark": "Success",
                    "responseDetail": None, "mac": SAMPLE_RESP_MAC,  # 回显
                })
            return await super().post(url, json=json, content=content, headers=headers)

    httpx.AsyncClient = _EchoClient
    _FakeClient.calls = []
    _FakeClient.esc_pages = {}
    try:
        records = asyncio.run(query_call_records(
            page=1, size=10, agent_id="61038",
            established_time_start="2026-10-19 00:00:00",
            established_time_end="2026-10-20 00:00:00",
        ))
    finally:
        _restore_client()
    assert len(records) == 1, "回显且与 X-CSP-MAC 一致时不应报错"


def main():
    tests = [
        test_query_call_records_matches_sample,
        test_encode_body_matches_sample_bytes,
        test_verify_sends_raw_bytes_not_reserialized,
        test_pagination_fetches_all_pages,
        test_decrypt_matches_sample,
        test_verify_failure_aborts_batch,
        test_verify_accepts_echoed_mac,
    ]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"✓ {t.__name__}")
        except Exception as e:
            failed += 1
            print(f"✗ {t.__name__}: {e!r}")
    print("\n全部通过" if not failed else f"\n{failed} 个用例失败")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
