"""
上游 CSP 适配器 + ESCTerminal 链路服务（催记管理数据源）

刷新通话记录的链路 = 4 步（顺序与《录音请求.txt》样例一致）：
  ① 生成 MAC    POST csp-adapter/v1/mac/generate
  ② 业务查询    POST escterminal/v1/icp/ICP1100010 （带 X-GZB-* + X-GZB-mac 头）
                 → 响应头里带 x-gzb-mac（用于第 ③ 步校验）
  ③ 校验 MAC    POST csp-adapter/v1/mac/verify
                 → X-CSP-MAC 填第 ② 步响应头返回的 x-gzb-mac，
                   请求 body 放第 ② 步的**完整响应内容**
  ④ 逐条解密    POST csp-adapter/v1/password/decrypt （用 X-CSP-Key-Name 头）

注意：第 ③ 步的校验对象是「②的响应」，不是「①生成的 mac」。
      ① 生成的 mac 只作为第 ② 步的 X-GZB-mac 请求头使用。

请求/响应形态（参考《语音获取接口说明.xlsx》+《录音请求.txt》curl 样例）：

  POST {CSP_ADAPTER_BASE_URL}/v1/mac/generate
  Headers: Content-Type: application/octet-stream
           X-CSP-Global-Service-No / X-CSP-Source-Journal-No / X-CSP-Node-Name: ICPA
  Body: {"requestData": {"body": {page, size, agent_id, established_time_start/end}}}
  Resp: {"success":true,"responseCode":0,"mac":"F4D7D9B6410F4444"}

  POST {ESCTERMINAL_BASE_URL}   （配置里已含 /v1/icp/ICP1100010 路径）
  Headers: Content-Type: application/json
           Accept: application/json
           X-GZB-sourceSystemCode: LMD / X-GZB-sinkSystemCode: ICP / X-GZB-actionId
           X-GZB-macEncryptType: 4 / X-GZB-mac: <①的 mac>
  Body: 同 generate
  Resp: 响应头 x-gzb-mac: <待校验的 mac>
        响应体 responseCode == "ICPAAAAAAA"，数据在 responseData.body.records[]

  POST {CSP_ADAPTER_BASE_URL}/v1/mac/verify
  Headers: Content-Type: application/json
           Accept: application/json
           X-CSP-Global-Service-No / X-CSP-Source-Journal-No / X-CSP-Node-Name: LMDA
           X-CSP-MAC: <②响应头的 x-gzb-mac>
  Body: ② 的完整响应内容（原样透传）
  Resp: {success:true, responseCode:0, mac:null} — 成功时 mac 必须为 None

  POST {CSP_ADAPTER_BASE_URL}/v1/password/decrypt
  Headers: Content-Type: text/plain; charset=us-ascii
           X-CSP-Key-Name: GZYH.LMDA_node.zek
  Body: 单条 call_url_inner 密文字符串（裸串，非 JSON）
  Resp: {success:true, responseCode:0, plaintext:"http://.../可下载URL"}

错误处理：
- 步骤 1-3 任一环节失败 → 整批 refresh 失败（raise CspApiError）
- 步骤 4 单条失败 → 由调用方决定是否跳过该条

【字节级铁律】（踩过的坑，勿改）
上游的 MAC 是对**报文原文字节**算的，因此：
  1) ① generate 与 ② 业务查询必须发**完全相同**的请求体字节（样例是同一串 163 字节）；
     两者序列化方式必须一致（见 _encode_body）。
  2) ③ verify 的 body 必须是 ② 收到的**原始响应字节**（resp.content），
     不能把 JSON 解析后再重新序列化——转义、空格、数字格式稍有差异 MAC 就对不上，
     上游会返回「验证mac失败」。
"""
from __future__ import annotations

import asyncio
import json
import time
from typing import Any
import httpx
from loguru import logger

from backend.core.config import settings


class CspApiError(Exception):
    """上游 CSP / ESCTerminal 链路失败（MAC / decrypt / 业务码 / 解析）"""


# ——— 公开常量 ———

# csp-adapter /v1/mac/* 与 /v1/password/decrypt 的业务成功码
CSP_SUCCESS_CODE = 0

# ESCTerminal 的业务成功码（兼容旧 icp_service 常量名）
ICP_SUCCESS_CODE = "ICPAAAAAAA"

# ESCTerminal 的接口事务码（路径末段）
ICP_TRX_CODE = "ICP1100010"

# 单次刷新最多翻多少页（防御上游 pages 字段异常导致死循环）
MAX_PAGES = 20


# ——— 内部工具 ———

_journal_counter = 0


def _new_journal_no() -> str:
    """生成一次逻辑请求（一次刷新）共用的 Source-Journal-No。

    上游样例形如 'DEMO202610130000000001'：前缀 DEMO + yyyyMMdd + 9 位毫秒序号。
    同一个逻辑请求里的 generate / verify 必须用同一个值。
    """
    global _journal_counter
    now = time.localtime()
    # 毫秒 + 自增计数：同一毫秒内多次调用（如翻页）也不会撞号
    _journal_counter = (_journal_counter + 1) % 1_000_000_000
    seq = (int(time.time() * 1000) + _journal_counter) % 1_000_000_000
    return f"DEMO{now.tm_year:04d}{now.tm_mon:02d}{now.tm_mday:02d}{seq:09d}"


def _journal_no() -> str:
    """取本次逻辑请求的 Source-Journal-No：优先用配置，留空则自动生成。"""
    return (settings.X_CSP_SOURCE_JOURNAL_NO or "").strip() or _new_journal_no()


def _csp_headers(*, node_name: str, journal_no: str, extra: dict | None = None) -> dict[str, str]:
    """构造 csp-adapter 通用头（带 X-CSP-* 标识）。

    X-CSP-Global-Service-No：同一逻辑请求的所有 HTTP 调用共享，从配置取；
    X-CSP-Source-Journal-No：同一逻辑请求的所有 HTTP 调用共享（generate / verify 同值）；
    X-CSP-Node-Name：本次调用的节点身份（generate=ICPA，verify=LMDA），从配置取。
    """
    h = {
        "X-CSP-Global-Service-No":  settings.X_CSP_GLOBAL_SERVICE_NO,
        "X-CSP-Source-Journal-No":  journal_no,
        "X-CSP-Node-Name":          node_name,
    }
    if extra:
        h.update(extra)
    return h


def _gzb_headers(mac: str) -> dict[str, str]:
    """构造 ESCTerminal 调用头（只有 X-GZB-*，与上游样例一致，不带 X-CSP-* 头）。

    X-GZB-mac 填的是第 ① 步 generate 拿到的 mac。
    """
    return {
        "Content-Type":           "application/json",
        "Accept":                 "application/json",
        "X-GZB-sourceSystemCode": settings.X_GZB_SOURCE_SYSTEM_CODE,
        "X-GZB-sinkSystemCode":   settings.X_GZB_SINK_SYSTEM_CODE,
        "X-GZB-actionId":         settings.X_GZB_ACTION_ID,
        "X-GZB-macEncryptType":   str(settings.X_GZB_MAC_ENCRYPT_TYPE),
        "X-GZB-mac":              mac,
    }


def _common_body(
    page: int,
    size: int,
    agent_id: str | None,
    established_time_start: str,
    established_time_end: str,
) -> dict:
    """generate 与业务查询共用的请求体（两者必须完全一致，MAC 才校验得过）。"""
    inner: dict[str, Any] = {
        "page": page,
        "size": size,
    }
    if agent_id:
        inner["agent_id"] = agent_id
    inner["established_time_start"] = established_time_start
    inner["established_time_end"] = established_time_end
    return {"requestData": {"body": inner}}


def _encode_body(body: dict) -> bytes:
    """把请求体序列化成**固定的字节串**（①②两步共用同一份字节）。

    格式严格对齐《录音请求.txt》样例：
        separators=(",", ": ")  →  键后有空格、逗号后无空格
        ensure_ascii=False      →  中文按 UTF-8 原样发出
    样例请求体正好 163 字节（样例里 Content-Length: 163），可用于自检。

    ⚠️ 不要用 httpx 的 json= 参数：它用的是紧凑分隔符（","/":"），与本函数结果差 7 字节，
       会导致 ① 和 ② 的请求体不一致 → 上游 MAC 校验失败。
    """
    return json.dumps(body, ensure_ascii=False, separators=(",", ": ")).encode("utf-8")


def _wrap_csp(path: str) -> str:
    """拼出 csp-adapter 完整 URL；base 未配置时抛 CspApiError"""
    base = (settings.CSP_ADAPTER_BASE_URL or "").rstrip("/")
    if not base:
        raise CspApiError("未配置 CSP_ADAPTER_BASE_URL，请在 docker/.env 中设置后再刷新")
    return f"{base}{path}"


def _wrap_escterminal() -> str:
    """返回 ESCTerminal 完整 URL（从 settings.ICP_API_BASE_URL 读取，已含 /v1/icp/ICP1100010 路径）。"""
    url = (settings.ICP_API_BASE_URL or "").strip()
    if not url:
        raise CspApiError("未配置 ICP_API_BASE_URL，请在 docker/.env 中设置后再刷新")
    return url


def _format_dt(value: str | None) -> str | None:
    """ESCTerminal 返回的 established_time / released_times 形如 '2026-01-01 00:00:00'，
    直接原样返回；不合法时回 None，避免下游解析报错。"""
    if not value:
        return None
    s = str(value).strip()
    return s or None


def _to_int(value: Any) -> int | None:
    """handle_times 是秒数；上游可能给数字也可能给字符串"""
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(value))
        except Exception:
            return None


def _normalize_record(raw: dict) -> dict:
    """把 ESCTerminal 单条记录规整为后端统一字段（snake_case，与 call_records 表一致）。

    上游同时返回 call_url 和 call_url_inner 两个字段，都原样入库；
    解密、下载只认 call_url_inner（密文可解的那一份）。

    号码口径（上游实际返回）：
      - calling_number：对端客户号码（上游已做 135****9752 脱敏）
      - phone_number  ：主叫号码，实际上与 dn_id 相同（分机号）
    """
    return {
        "call_id":          (raw.get("call_id") or "").strip() or None,
        "agent_id":         (raw.get("agent_id") or "").strip() or None,
        "agent_name":       (raw.get("agent_name") or "").strip() or None,
        "dn_id":            (raw.get("dn_id") or "").strip() or None,
        "phone_number":     (raw.get("phone_number") or "").strip() or None,
        "calling_number":   (raw.get("calling_number") or "").strip() or None,
        "established_time": _format_dt(raw.get("established_time")),
        "released_times":   _format_dt(raw.get("released_times")),
        "handle_times":     _to_int(raw.get("handle_times")),
        "call_url":         (raw.get("call_url") or "").strip() or None,
        "call_url_inner":   (raw.get("call_url_inner") or "").strip() or None,
        "reserve1":         raw.get("reserve1") or None,
        "reserve2":         raw.get("reserve2") or None,
        "reserve3":         raw.get("reserve3") or None,
        "reserve4":         raw.get("reserve4") or None,
        "reserve5":         raw.get("reserve5") or None,
    }


def _check_csp_success(data: dict, op: str) -> None:
    """校验 csp-adapter 响应（success==true 且 responseCode==0），否则 raise"""
    if data.get("success") is not True or data.get("responseCode") != CSP_SUCCESS_CODE:
        msg = data.get("responseRemark") or data.get("responseDetail") or "未知错误"
        raise CspApiError(f"CSP {op} 失败：{msg}")


# ——— 公共 API ———

async def generate_mac(
    *,
    page: int,
    size: int,
    agent_id: str | None,
    established_time_start: str,
    established_time_end: str,
    journal_no: str | None = None,
) -> str:
    """调用 csp-adapter /v1/mac/generate，返回 mac 字符串（后续填入 X-GZB-mac）"""
    url = _wrap_csp("/v1/mac/generate")
    body = _common_body(page, size, agent_id, established_time_start, established_time_end)
    body_bytes = _encode_body(body)  # 与第②步业务查询逐字节一致
    timeout = max(1, int(settings.CSP_ADAPTER_TIMEOUT or 10))
    journal_no = journal_no or _journal_no()

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                url,
                content=body_bytes,  # spec octet-stream
                headers=_csp_headers(
                    node_name=settings.X_CSP_NODE_NAME_GENERATE,
                    journal_no=journal_no,
                    extra={"Content-Type": "application/octet-stream"},
                ),
            )
    except httpx.TimeoutException as e:
        logger.error(f"[CSP] MAC 生成超时 ({timeout}s): {url}")
        raise CspApiError(f"CSP MAC 生成超时（>{timeout}s）") from e
    except httpx.HTTPError as e:
        logger.error(f"[CSP] MAC 生成网络错误: {e!r}")
        raise CspApiError(f"CSP MAC 生成网络错误：{e!s}") from e

    if resp.status_code != 200:
        logger.error(f"[CSP] MAC 生成 HTTP {resp.status_code}: {resp.text[:300]}")
        raise CspApiError(f"CSP MAC 生成返回 HTTP {resp.status_code}")

    try:
        data = resp.json()
    except Exception as e:
        raise CspApiError("CSP MAC 生成响应不是合法 JSON") from e

    _check_csp_success(data, "MAC 生成")

    mac = (data.get("mac") or "").strip()
    if not mac:
        raise CspApiError("CSP MAC 生成响应缺少 mac 字段")
    return mac


async def verify_mac(*, mac: str, raw_body: bytes, journal_no: str | None = None) -> None:
    """调用 csp-adapter /v1/mac/verify 校验**业务查询响应**的 mac。

    Args:
        mac:      业务查询（ESCTerminal）响应头里的 x-gzb-mac
        raw_body: 业务查询的**原始响应字节**（resp.content，原样透传，不能重新序列化）
    Raises:
        CspApiError: 网络异常 / 业务码失败 / mac 字段异常
    """
    if not mac:
        raise CspApiError("MAC 校验缺少 mac 参数（业务查询响应头未返回 x-gzb-mac）")
    if not raw_body:
        raise CspApiError("MAC 校验缺少待校验的响应内容")

    url = _wrap_csp("/v1/mac/verify")
    timeout = max(1, int(settings.CSP_ADAPTER_TIMEOUT or 10))
    journal_no = journal_no or _journal_no()

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                url,
                content=raw_body,  # 原始响应字节原样透传（重新序列化会验不过）
                headers=_csp_headers(
                    node_name=settings.X_CSP_NODE_NAME_VERIFY,
                    journal_no=journal_no,
                    extra={
                        "Content-Type": "application/json",
                        "Accept":       "application/json",
                        "X-CSP-MAC":    mac,
                    },
                ),
            )
    except httpx.TimeoutException as e:
        logger.error(f"[CSP] MAC 校验超时 ({timeout}s): {url}")
        raise CspApiError(f"CSP MAC 校验超时（>{timeout}s）") from e
    except httpx.HTTPError as e:
        logger.error(f"[CSP] MAC 校验网络错误: {e!r}")
        raise CspApiError(f"CSP MAC 校验网络错误：{e!s}") from e

    if resp.status_code != 200:
        logger.error(f"[CSP] MAC 校验 HTTP {resp.status_code}: {resp.text[:300]}")
        raise CspApiError(f"CSP MAC 校验返回 HTTP {resp.status_code}")

    try:
        result = resp.json()
    except Exception as e:
        raise CspApiError("CSP MAC 校验响应不是合法 JSON") from e

    _check_csp_success(result, "MAC 校验")

    # 成功时上游的 mac 字段应为 null（见《录音请求.txt》样例）。
    # 少数环境会回显待校验的 mac —— 只要与 X-CSP-MAC 一致就视为通过；
    # 不一致则说明校验结果对不上，判失败（fail closed）。
    returned_mac = result.get("mac")
    if returned_mac is not None:
        if str(returned_mac).strip() == mac.strip():
            logger.warning(
                f"[CSP] MAC 校验成功但响应回显了 mac={returned_mac!r}（非 null），已按通过处理"
            )
        else:
            raise CspApiError(
                f"CSP MAC 校验异常：响应 mac 字段应为 null，实际={returned_mac!r}（与 X-CSP-MAC 不一致）"
            )


async def _query_page(
    *,
    page: int,
    size: int,
    agent_id: str | None,
    established_time_start: str,
    established_time_end: str,
    journal_no: str,
) -> dict:
    """执行**一页**的 ①②③ 链路，返回 ESCTerminal 的完整响应 dict（已通过 MAC 校验）。

    ① generate 的请求体与 ② 业务查询的请求体逐字节一致；③ verify 回传 ② 的原始响应字节。

    Raises:
        CspApiError: 网络异常 / 业务码失败 / MAC 校验失败 / 解析失败（步骤 1-3 任一失败）
    """
    # —— 1) 生成 MAC（后续填入 X-GZB-mac 请求头）——
    mac = await generate_mac(
        page=page, size=size, agent_id=agent_id,
        established_time_start=established_time_start,
        established_time_end=established_time_end,
        journal_no=journal_no,
    )

    # —— 2) 业务查询（请求体与 ① 逐字节一致）——
    body = _common_body(page, size, agent_id, established_time_start, established_time_end)
    body_bytes = _encode_body(body)
    url = _wrap_escterminal()
    timeout = max(1, int(settings.ICP_API_TIMEOUT or 15))

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, content=body_bytes, headers=_gzb_headers(mac))
    except httpx.TimeoutException as e:
        logger.error(f"[ESCTerminal] 查询超时 ({timeout}s): {url}")
        raise CspApiError(f"ESCTerminal 查询超时（>{timeout}s）") from e
    except httpx.HTTPError as e:
        logger.error(f"[ESCTerminal] 查询网络错误: {e!r}")
        raise CspApiError(f"ESCTerminal 查询网络错误：{e!s}") from e

    if resp.status_code != 200:
        logger.error(f"[ESCTerminal] HTTP {resp.status_code}: {resp.text[:300]}")
        raise CspApiError(f"ESCTerminal 返回 HTTP {resp.status_code}")

    try:
        data = resp.json()
    except Exception as e:
        raise CspApiError("ESCTerminal 响应不是合法 JSON") from e

    # —— 3) 校验 MAC ——
    #    校验对象是**②的响应**：X-CSP-MAC 填响应头返回的 x-gzb-mac，
    #    body 放**原始响应字节**（resp.content，不能重新序列化）
    resp_mac = (resp.headers.get("x-gzb-mac") or "").strip()
    if not resp_mac:
        logger.error(f"[ESCTerminal] 响应头缺少 x-gzb-mac: {dict(resp.headers)}")
        raise CspApiError("ESCTerminal 响应头缺少 x-gzb-mac，无法校验 MAC")
    await verify_mac(mac=resp_mac, raw_body=resp.content, journal_no=journal_no)

    # —— 4) MAC 校验通过 → 校验业务码 ——
    if data.get("responseCode") != ICP_SUCCESS_CODE:
        msg = data.get("responseMessage") or data.get("responseDetail") or "未知错误"
        logger.warning(f"[ESCTerminal] 业务失败: code={data.get('responseCode')}, msg={msg}")
        raise CspApiError(f"ESCTerminal 业务失败：{msg}")

    return data


async def query_call_records(
    *,
    page: int = 1,
    size: int = 100,
    agent_id: str | None = None,
    agent_name: str | None = None,
    dn_id: str | None = None,
    phone_number: str | None = None,
    established_time_start: str,
    established_time_end: str,
) -> list[dict]:
    """完整链路：generate_mac → ESCTerminal 查询 → verify_mac（校验查询响应）

    超过一页时自动翻页（每页走一遍完整的 ①②③）。

    Returns:
        标准化后的 records 列表（_normalize_record 处理，含 call_url_inner）

    Raises:
        CspApiError: 网络异常 / 业务码失败 / MAC 校验失败 / 解析失败（步骤 1-3 任一失败）
    """
    # 兼容调用方传入 agent_name / dn_id / phone_number 筛选条件
    def _age_pred(item: dict) -> bool:
        if agent_name and agent_name not in (item.get("agent_name") or ""):
            return False
        if dn_id and (item.get("dn_id") or "") != dn_id:
            return False
        if phone_number:
            haystack = f"{item.get('phone_number') or ''}{item.get('calling_number') or ''}"
            if phone_number not in haystack:
                return False
        return True

    # 无录音地址的记录直接丢弃（call_url_inner 为空 → 无法解密下载）
    def _has_url(item: dict) -> bool:
        return bool((item.get("call_url_inner") or "").strip())

    records: list[dict] = []
    cur_page = max(1, int(page or 1))
    total_pages = 1

    while True:
        # 每一页是一个逻辑请求：generate / verify 共用同一个 Source-Journal-No
        journal_no = _journal_no()
        data = await _query_page(
            page=cur_page,
            size=size,
            agent_id=agent_id,
            established_time_start=established_time_start,
            established_time_end=established_time_end,
            journal_no=journal_no,
        )

        body_obj = (data.get("responseData") or {}).get("body") or {}
        records_raw = body_obj.get("records") or []
        if not isinstance(records_raw, list):
            raise CspApiError("ESCTerminal 响应 records 不是数组")

        page_records = [
            _normalize_record(r)
            for r in records_raw
            if isinstance(r, dict) and _age_pred(r) and _has_url(r)
        ]
        dropped = len(records_raw) - len(page_records)
        if dropped > 0:
            logger.info(
                f"[ESCTerminal] 第 {cur_page} 页过滤掉 {dropped} 条无录音地址"
                f"(call_url_inner 为空)的记录"
            )
        records.extend(page_records)

        total_pages = _to_int(body_obj.get("pages")) or 1
        if cur_page >= total_pages:
            break
        if cur_page >= MAX_PAGES:
            logger.warning(
                f"[ESCTerminal] 命中分页上限 MAX_PAGES={MAX_PAGES}，"
                f"上游共 {total_pages} 页，第 {cur_page + 1} 页及之后未拉取"
            )
            break
        cur_page += 1

    logger.info(f"[ESCTerminal] 拉取完成：{total_pages} 页，共取到 {len(records)} 条可用记录")
    return records


async def decrypt_call_url(cipher: str, *, client: httpx.AsyncClient | None = None) -> str:
    """解密单条 call_url 密文 → 可下载的明文 URL

    Args:
        cipher: 上游返回的 call_url 原始密文（十六进制/Base64 串等）
        client: 复用已有连接（批量解密时传入，避免每条都新建连接）
    Returns:
        解密后的明文 URL（http://...）
    Raises:
        CspApiError: 网络 / 业务码 / 解析失败
    """
    if not cipher or not str(cipher).strip():
        raise CspApiError("待解密的 call_url 为空")

    # 上游密文是 ASCII 十六进制串；出现非 ASCII 说明数据异常，
    # 这里直接报错而不是静默丢字符（否则解出来的是错的东西）
    raw_cipher = str(cipher).strip()
    try:
        cipher_bytes = raw_cipher.encode("us-ascii")
    except UnicodeEncodeError as e:
        raise CspApiError(f"待解密的 call_url 含非 ASCII 字符，无法按 us-ascii 发送：{raw_cipher[:64]!r}") from e

    url = _wrap_csp("/v1/password/decrypt")
    timeout = max(1, int(settings.CSP_ADAPTER_TIMEOUT or 10))

    async def _post(c: httpx.AsyncClient) -> httpx.Response:
        return await c.post(
            url,
            content=cipher_bytes,
            headers={
                "Content-Type":   "text/plain; charset=us-ascii",
                "X-CSP-Key-Name": settings.CSP_KEY_NAME,
            },
        )

    try:
        if client is not None:
            resp = await _post(client)
        else:
            async with httpx.AsyncClient(timeout=timeout) as c:
                resp = await _post(c)
    except httpx.TimeoutException as e:
        logger.error(f"[CSP] URL 解密超时 ({timeout}s): {url}")
        raise CspApiError(f"CSP URL 解密超时（>{timeout}s）") from e
    except httpx.HTTPError as e:
        logger.error(f"[CSP] URL 解密网络错误: {e!r}")
        raise CspApiError(f"CSP URL 解密网络错误：{e!s}") from e
    except Exception as e:
        # httpx.InvalidURL / UnsupportedProtocol 等不继承 HTTPError，这里统一包成 CspApiError
        logger.error(f"[CSP] URL 解密请求异常: {e!r}")
        raise CspApiError(f"CSP URL 解密请求异常：{e!s}") from e

    if resp.status_code != 200:
        logger.error(f"[CSP] URL 解密 HTTP {resp.status_code}: {resp.text[:300]}")
        raise CspApiError(f"CSP URL 解密返回 HTTP {resp.status_code}")

    try:
        data = resp.json()
    except Exception as e:
        raise CspApiError("CSP URL 解密响应不是合法 JSON") from e

    _check_csp_success(data, "URL 解密")

    plaintext = (data.get("plaintext") or "").strip()
    if not plaintext:
        raise CspApiError("CSP URL 解密响应 plaintext 为空")
    return plaintext


async def decrypt_call_urls(
    ciphers: list[str],
    *,
    concurrency: int = 8,
) -> list[tuple[str | None, str | None]]:
    """批量解密（并发），返回 [(明文 URL, 错误信息)]，顺序与输入一一对应。

    - 单条失败不抛异常：错误信息放在对应位置，调用方决定跳过还是重试
    - 复用一个 AsyncClient + Semaphore 限流，避免每条都新建连接
    """
    if not ciphers:
        return []
    timeout = max(1, int(settings.CSP_ADAPTER_TIMEOUT or 10))
    sem = asyncio.Semaphore(max(1, concurrency))

    async with httpx.AsyncClient(timeout=timeout) as client:
        async def _one(cipher: str) -> tuple[str | None, str | None]:
            async with sem:
                try:
                    return await decrypt_call_url(cipher, client=client), None
                except CspApiError as e:
                    return None, str(e)
                except Exception as e:  # 兜底：绝不让单条异常掀翻整批
                    return None, repr(e)

        return list(await asyncio.gather(*(_one(c) for c in ciphers)))