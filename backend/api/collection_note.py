"""
催记管理 API

数据流：
  1. 用户点"刷新" → POST /collection-notes/calls/refresh
     → 后端调上游 4 步链路（见 csp_service）：
       generate_mac → ESCTerminal 查询 → verify_mac（校验查询响应）→ 逐条解密
     → 拉到的 records UPSERT 进 call_records
     → 为新 call_id 插 call_notes（三步全 pending）
     → 触发后台异步处理（asr + 两份 LLM 催记）
     → 立即返回新拉到的 call_records 列表

  2. 用户点开详情 → GET /collection-notes/calls/{call_id}
     → 返回 call_record + call_note（含三步状态、转写、原始/校对催记、错误）
     → 前端按字段级状态显示；processing 字段轮询等待

  3. 用户编辑"校对" → POST /calls/{id}/save-structured (或 -unstructured)
     → 写入 call_notes.edited_*_note，记审计

  4. 用户点"重新处理" → POST /calls/{id}/process 或 /transcribe 或 /note/{structured|unstructured}
     → 同步处理对应步骤

角色与权限：
  - k_user：agent_id = "k+工号"（= loginid 本身），只查/改自己工号
  - admin  ：刷新时填了工号 → 走上游拉该工号数据；没填 → 只读本地库
  - oa_user：403 屏蔽

agent_id 口径（两套，别混）：
  - 落库 / 鉴权："k+工号"（如 k63001），与本系统 k 账号 loginid 对齐
  - 请求上游 ESCTerminal：纯工号（如 63001）——上游 agent_id 是精确匹配，
    带 "k" 前缀会查不到任何记录（见 _to_plain_agent_id）
  查询侧额外兼容历史的纯工号形态（_agent_id_variants）。
"""
from __future__ import annotations

import asyncio
import datetime as _dt
import time
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from loguru import logger
from sqlalchemy import and_, or_, select
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.auth import get_current_user_required
from backend.core.config import settings
from backend.core.database import AsyncSessionLocal, get_db
from backend.core.datetime_utils import get_current_time
from backend.models.call_note import CallNote
from backend.models.call_record import CallRecord
from backend.models.k_user import KUser
from backend.services.audit_service import record_action
from backend.services.collection_note_service import collection_note_service
from backend.services.csp_service import (
    CspApiError,
    decrypt_call_urls,
    query_call_records,
)


router = APIRouter(prefix="/collection-notes", tags=["催记管理"])


# ——— 角色工具 ———

def _extract_role(user_info: dict) -> str:
    if not user_info:
        return "oa_user"
    if user_info.get("loginid") == "admin":
        return "admin"
    loginid = user_info.get("loginid") or ""
    if loginid.startswith("k"):
        return "k_user"
    return "oa_user"


def _to_agent_id(value: str | None) -> str:
    """把工号归一化成 "k+工号" 形式（对齐账号体系）。

    - "63001"  → "k63001"
    - "k63001" → "k63001"
    - "K63001" → "k63001"
    """
    s = (value or "").strip()
    if not s:
        return ""
    if s[0] == "k":
        return s
    if s[0].lower() == "k":
        return "k" + s[1:]
    return "k" + s


def _to_plain_agent_id(value: str | None) -> str:
    """把工号还原成上游 ESCTerminal 认的纯工号（去掉 k 前缀）。

    上游 ICP1100010 的 agent_id 是坐席工号本身（如 "61038"，精确匹配），
    不带我们本地的 "k" 前缀；带上前缀会查不到任何记录。
    """
    s = (value or "").strip()
    if not s:
        return ""
    if s[0].lower() == "k":
        return s[1:]
    return s


def _agent_id_variants(value: str | None) -> set[str]:
    """agent_id 的可能入库形态：{"k+工号", "工号"}，用于兼容历史数据。"""
    s = (value or "").strip()
    if not s:
        return set()
    variants = {_to_agent_id(s)}
    plain = s[1:] if s[0].lower() == "k" else s
    if plain:
        variants.add(plain)
    return variants


def _k_user_agent_id(loginid: str) -> str:
    """k 账号的 agent_id = "k+工号"（loginid 本身就是这个形式）。"""
    return _to_agent_id(loginid)


def _reject_oa(user_info: dict) -> None:
    if _extract_role(user_info) == "oa_user":
        raise HTTPException(status_code=403, detail="无访问权限")


# ——— 刷新频控（per-loginid 进程内时间窗）———
# 记录每个 loginid 上次刷新的时间戳；同 loginid 在冷却窗口内重复刷新 → 429
_refresh_last_call: dict[str, float] = {}


def _enforce_refresh_cooldown(loginid: str) -> None:
    """按 loginid 频控刷新。冷却窗口内 → 抛 429（前端可用 Retry-After 自动倒计时）"""
    cooldown = max(0, int(getattr(settings, "COLLECTION_NOTE_REFRESH_COOLDOWN_SECONDS", 5)))
    if cooldown <= 0:
        return  # 关闭频控
    last = _refresh_last_call.get(loginid)
    now_ts = time.time()
    if last and (now_ts - last) < cooldown:
        wait = int(cooldown - (now_ts - last)) + 1
        raise HTTPException(
            status_code=429,
            detail=f"刷新频控中，请 {wait} 秒后再试",
            headers={"Retry-After": str(wait)},
        )
    _refresh_last_call[loginid] = now_ts


def _clear_refresh_cooldown(loginid: str) -> None:
    """清掉该 loginid 的频控时间戳（仅供测试 / 调试使用）"""
    _refresh_last_call.pop(loginid, None)


def _format_duration(sec) -> str:
    if not isinstance(sec, int) or sec < 0:
        return ""
    m, s = divmod(int(sec), 60)
    return f"{m}分{s:02d}秒"


def _to_dt(s: str | None) -> _dt.datetime | None:
    if not s:
        return None
    try:
        return _dt.datetime.strptime(s.strip(), "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


# ——— 字段映射 ——

def _row_to_list_item(row: CallRecord) -> dict:
    return {
        "call_id":       row.call_id,
        "agent_id":      row.agent_id,
        "agent_name":    row.agent_name,
        "extension":     row.dn_id,
        "phone":         row.phone_number,
        "calling_number": row.calling_number,
        "start_time":    row.established_time.strftime("%Y-%m-%d %H:%M:%S") if row.established_time else None,
        "end_time":      row.released_times.strftime("%Y-%m-%d %H:%M:%S") if row.released_times else None,
        "duration_sec":  row.handle_times,
        "duration_text": _format_duration(row.handle_times),
    }


def _note_to_dict(note: CallNote | None) -> dict | None:
    if not note:
        return None
    return {
        "asr_status":              note.asr_status,
        "structured_status":       note.structured_status,
        "unstructured_status":     note.unstructured_status,
        "asr_error":               note.asr_error,
        "structured_error":        note.structured_error,
        "unstructured_error":      note.unstructured_error,
        "transcript":              note.transcript,
        "structured_note":         note.structured_note,
        "unstructured_note":       note.unstructured_note,
        "edited_structured_note":   note.edited_structured_note,
        "edited_unstructured_note": note.edited_unstructured_note,
        "last_processed_at":       note.last_processed_at.strftime("%Y-%m-%d %H:%M:%S") if note.last_processed_at else None,
    }


# ——— 入参 ———

class SaveNoteRequest(BaseModel):
    """save-* 端点：保存用户编辑的"校对"催记"""
    content: str
    is_final: bool = False


class RefreshRequest(BaseModel):
    """refresh 端点"""
    agent_id: Optional[str] = Field(default=None, description="已废弃：admin 刷新固定刷白名单里所有工号坐席，不再按单个工号刷；k 账号忽略")
    page: int = Field(default=1, ge=1)
    size: int = Field(default=100, ge=1, le=100)
    established_time_start: Optional[str] = None
    established_time_end:   Optional[str] = None


# ——— 列表 ———

@router.get("/calls")
async def list_calls(
    agent_id: Optional[str] = None,
    agent_name: Optional[str] = None,
    extension: Optional[str] = None,
    phone: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    user_info: dict = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
):
    """通话列表（从 call_records 读取）"""
    _reject_oa(user_info)
    role = _extract_role(user_info)
    loginid = user_info.get("loginid", "")

    if role == "k_user":
        agent_id = _k_user_agent_id(loginid)

    stmt = select(CallRecord)
    conditions = [
        # 无录音地址（call_url_inner 为空）的记录不展示：无法解密下载
        CallRecord.call_url_inner.isnot(None),
        CallRecord.call_url_inner != "",
    ]
    if agent_id:
        # 兼容历史数据：'k+工号' 与 '工号' 两种入库形态都能匹配
        conditions.append(CallRecord.agent_id.in_(_agent_id_variants(agent_id)))
    if agent_name:
        conditions.append(CallRecord.agent_name.like(f"%{agent_name}%"))
    if extension:
        conditions.append(CallRecord.dn_id == extension)
    if phone:
        # 号码有两个来源：phone_number（主叫/分机）与 calling_number（对端客户号，上游已脱敏）
        # 搜任一命中即可
        conditions.append(
            or_(
                CallRecord.phone_number.like(f"%{phone}%"),
                CallRecord.calling_number.like(f"%{phone}%"),
            )
        )
    dt_start = _to_dt(start_time)
    dt_end = _to_dt(end_time)
    if dt_start:
        conditions.append(CallRecord.established_time >= dt_start)
    if dt_end:
        conditions.append(CallRecord.established_time <= dt_end)

    if conditions:
        stmt = stmt.where(and_(*conditions))
    stmt = stmt.order_by(CallRecord.established_time.desc())

    result = await db.execute(stmt)
    rows = result.scalars().all()
    items = [_row_to_list_item(r) for r in rows]

    # —— 顶部统计：今日通话 / 平均通话时长 / AI 催记生成数 ——
    # 1) 今日通话：established_time 落在"今天 00:00 ~ 明天 00:00"（按配置 TZ）
    now_dt = get_current_time()
    today_start = now_dt.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + _dt.timedelta(days=1)
    # DB 字段是 naive datetime，比较时去掉 tzinfo 避免 SQLAlchemy 触发隐式转时区
    today_start_naive = today_start.replace(tzinfo=None)
    today_end_naive = today_end.replace(tzinfo=None)
    today_count = sum(
        1 for r in rows
        if r.established_time is not None
        and today_start_naive <= r.established_time < today_end_naive
    )

    # 2) 平均通话时长：handle_times 的均值（跳过 None / 0 以免把未接通通话拉低）
    durations = [r.handle_times for r in rows if isinstance(r.handle_times, int) and r.handle_times > 0]
    avg_duration_sec = int(sum(durations) / len(durations)) if durations else 0

    # 3) AI 催记生成数 = 三步全 done 的条数
    if items:
        call_ids = [r["call_id"] for r in items]
        notes_q = await db.execute(
            select(CallNote).where(
                CallNote.call_id.in_(call_ids),
                CallNote.asr_status == "done",
                CallNote.structured_status == "done",
                CallNote.unstructured_status == "done",
            )
        )
        ai_done_count = len(notes_q.scalars().all())
    else:
        ai_done_count = 0

    return {
        "success": True,
        "items": items,
        "total": len(items),
        "today_count": today_count,
        "avg_duration_sec": avg_duration_sec,
        "ai_done_count": ai_done_count,
    }


# ——— 详情 ———

@router.get("/calls/{call_id}")
async def get_call(
    call_id: str,
    user_info: dict = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
):
    """单条详情：返回 call_record + call_note（字段级状态）"""
    _reject_oa(user_info)
    role = _extract_role(user_info)
    loginid = user_info.get("loginid", "")

    rec = await db.execute(select(CallRecord).where(CallRecord.call_id == call_id))
    row = rec.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail=f"通话 {call_id} 不存在")
    if role == "k_user" and row.agent_id not in _agent_id_variants(loginid):
        raise HTTPException(status_code=403, detail="无访问该通话的权限")

    note_res = await db.execute(select(CallNote).where(CallNote.call_id == call_id))
    note = note_res.scalar_one_or_none()

    return {
        "success": True,
        "item": _row_to_list_item(row) | {"call_url": row.call_url},
        "note": _note_to_dict(note),
    }


# ——— 刷新（调上游 ICP） ———

@router.post("/calls/refresh")
async def refresh_calls(
    payload: RefreshRequest | None = None,
    http_request: Request = None,
    user_info: dict = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
):
    """刷新（从上游拉数据入库）：
      - admin：**客服白名单里所有工号坐席**逐个从上游拉 → UPSERT call_records
                → 插 call_notes(pending) → 触发后台处理（ASR + LLM）
                （与筛选框无关；筛选框只影响"查询"）
      - k_user：只拉自己的工号

    body 可选（前端可能不发 body）；缺省时所有字段视为 None / 默认值
    """
    if payload is None:
        payload = RefreshRequest()
    _reject_oa(user_info)
    loginid = user_info.get("loginid", "")
    # 频控：同一 loginid 在冷却窗口内只允许一次刷新
    _enforce_refresh_cooldown(loginid)
    role = _extract_role(user_info)

    # 时间窗口：由后端按 RECORDING_REQUEST_DURATION_DAYS 自动计算
    # start = (今天结束 + 1 天) - N 天 = 明天 00:00 - N 天  => [start, 明天 00:00)
    # end   = 明天 00:00:00 （= 今天 23:59:59 的下一个整点）
    now_dt = get_current_time()
    today_end = (now_dt + _dt.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    duration_days = max(1, int(settings.RECORDING_REQUEST_DURATION_DAYS))
    start_dt = today_end - _dt.timedelta(days=duration_days)
    start_str = start_dt.strftime("%Y-%m-%d %H:%M:%S")
    end_str   = today_end.strftime("%Y-%m-%d %H:%M:%S")

    # 1) 上一次刷新还在跑？直接拒绝（别再白跑一遍上游查询）
    running_job_id = _REFRESH_RUNNING_BY_USER.get(loginid)
    if running_job_id:
        running = _REFRESH_JOBS.get(running_job_id)
        if running and running.get("status") == "running":
            raise HTTPException(status_code=409, detail="上一次刷新还在进行中，请等待完成后再试")

    # 2) 定目标座席
    #    落库 / 鉴权口径 = "k+工号"；请求上游口径 = 纯工号（上游 agent_id 精确匹配，不带 k 前缀）
    if role == "admin":
        targets = await _whitelist_agent_targets(db)
        if not targets:
            raise HTTPException(
                status_code=400,
                detail="客服管理白名单里还没有工号坐席，无法刷新",
            )
    else:
        own = _k_user_agent_id(loginid)
        targets = [{
            "target_agent_id": own,
            "upstream_agent_id": _to_plain_agent_id(own),
        }]

    # 3) admin 要刷的座席可能很多，上游查询全部放进后台任务（同步做必然超时）；
    #    k_user 只有一个座席，上游查询留在同步：上游报错（如「验证mac失败」）要立刻回给用户，
    #    不能变成"转后台后再失败"。
    raw_records: list[dict] | None = None
    if role != "admin":
        try:
            raw_records = await query_call_records(
                page=payload.page,
                size=payload.size,
                agent_id=targets[0]["upstream_agent_id"],
                established_time_start=start_str,
                established_time_end=end_str,
            )
        except CspApiError as e:
            await record_action(
                actor=user_info,
                action="collection_note.refresh",
                target_type="collection_note",
                target_id=targets[0]["target_agent_id"] or "all",
                request=http_request,
                result="fail",
                detail={
                    "mode": "csp_escterminal",
                    "agent_id": targets[0]["target_agent_id"],
                    "upstream_agent_id": targets[0]["upstream_agent_id"],
                    "start": start_str,
                    "end": end_str,
                    "duration_days": duration_days,
                    "error": str(e),
                },
            )
            raise HTTPException(status_code=502, detail=f"上游 CSP/ESCTerminal 拉取失败：{e}")

    # 4) 解密 + 落库转后台任务，接口立即返回（前端轮询 /calls/refresh/{job_id} 看进度）
    #    为什么放后台：解密是「每条记录一次 HTTP」的串行长活（几百条 = 几分钟），
    #    放在请求里必然超过前端 30s 超时，用户看到「刷新失败」但数据其实在慢慢入库。
    job = _new_refresh_job(
        total=len(raw_records) if raw_records is not None else 0,
        agent_id=targets[0]["target_agent_id"] if role != "admin" else "all_whitelist",
        upstream_agent_id=targets[0]["upstream_agent_id"] if role != "admin" else None,
        start=start_str,
        end=end_str,
        duration_days=duration_days,
        loginid=loginid,
        mode="csp_escterminal_whitelist" if role == "admin" else "csp_escterminal",
        agents=[
            {
                "agent_id": t["target_agent_id"],
                "upstream_agent_id": t["upstream_agent_id"],
                "status": "pending",
                "total": 0,
                "decrypted": 0,
                "inserted": 0,
                "updated": 0,
                "notes_inserted": 0,
                "error": None,
            }
            for t in targets
        ],
    )
    _REFRESH_RUNNING_BY_USER[loginid] = job["job_id"]
    _schedule_refresh_job(
        job,
        targets=targets,
        raw_records=raw_records,
        page=payload.page,
        size=payload.size,
        start_str=start_str,
        end_str=end_str,
        duration_days=duration_days,
        loginid=loginid,
        user_info=user_info,
        http_request=http_request,
    )

    if role == "admin":
        msg = f"正在后台刷新白名单里 {len(targets)} 个座席…"
    else:
        msg = f"已从上游拉取 {len(raw_records or [])} 条，正在后台解密入库…"
    return {
        "success": True,
        "status": "running",
        "job_id": job["job_id"],
        "message": msg,
        "agent_id": job["agent_id"],
        "start": start_str,
        "end": end_str,
        "duration_days": duration_days,
        "total": job["total"],
        "raw_returned": len(raw_records) if raw_records is not None else 0,
        "agent_count": len(targets),
        "mode": "csp_escterminal_whitelist" if role == "admin" else "csp_escterminal",
    }


async def _whitelist_agent_targets(db: AsyncSession) -> list[dict]:
    """客服白名单（k_users）里所有工号坐席的拉取目标。

    落库口径 = "k+工号"（与账号体系一致）；请求上游口径 = 纯工号
    （上游 ICP1100010 的 agent_id 精确匹配，带 k 前缀查不到任何记录）。
    """
    result = await db.execute(select(KUser.loginid).order_by(KUser.loginid))
    targets: list[dict] = []
    for (loginid,) in result.all():
        if not loginid or not loginid.lower().startswith("k"):
            continue
        targets.append({
            "target_agent_id": _to_agent_id(loginid),
            "upstream_agent_id": _to_plain_agent_id(loginid),
        })
    return targets


# ——— 刷新任务（进程内状态，前端轮询用）———
# 注意：任务状态存在**进程内存**里，所以后端要单进程跑（当前 compose 就是一个 uvicorn 进程）。
# 若改成多 worker，前端轮询可能落到不认识该 job 的 worker → 返回 404（前端会停止轮询并提示）。

_REFRESH_JOBS: dict[str, dict] = {}
_REFRESH_JOB_TTL_SECONDS = 1800   # 任务状态保留 30 分钟
_REFRESH_TASKS: set = set()       # 持有后台任务引用，避免被 GC 回收
_REFRESH_RUNNING_BY_USER: dict[str, str] = {}   # loginid -> job_id（防重复刷新）


def _gc_refresh_jobs() -> None:
    """清理已结束且过期的任务状态"""
    now = time.time()
    stale = [
        jid for jid, job in _REFRESH_JOBS.items()
        if job.get("finished_ts") and (now - job["finished_ts"]) > _REFRESH_JOB_TTL_SECONDS
    ]
    for jid in stale:
        _REFRESH_JOBS.pop(jid, None)


def _new_refresh_job(**fields) -> dict:
    _gc_refresh_jobs()
    job_id = f"rf_{int(time.time())}_{uuid.uuid4().hex[:8]}"
    job = {
        "job_id": job_id,
        "status": "running",          # running / done / failed
        "started_at": get_current_time().strftime("%Y-%m-%d %H:%M:%S"),
        "finished_at": None,
        "total": 0,
        "decrypted": 0,
        "decrypt_failed": 0,
        "skipped_already_decrypted": 0,
        "inserted": 0,
        "updated": 0,
        "dup_skipped": 0,
        "in_batch_dup_skipped": 0,
        "notes_inserted": 0,
        "message": "",
        "error": None,
    }
    job.update(fields)
    _REFRESH_JOBS[job_id] = job
    return job


def _schedule_refresh_job(job: dict, **kwargs) -> None:
    """把后台任务丢进事件循环（保留引用，防止任务被 GC）"""
    task = asyncio.create_task(_run_refresh_job(job, **kwargs))
    _REFRESH_TASKS.add(task)
    task.add_done_callback(_REFRESH_TASKS.discard)


async def _persist_refresh_records(
    db: AsyncSession,
    records: list[dict],
    *,
    target_agent_id: str,
    loginid: str,
) -> dict:
    """UPSERT call_records + 插 call_notes（复用请求内已有的去重/INSERT IGNORE 逻辑）"""
    # 去重口径：call_id 唯一约束（call_records.call_id / call_notes.call_id 均 unique）
    # - 批次内去重：上游翻页/重试可能把同一条返回多次，同一 call_id 只处理一次
    # - 跨请求去重：已入库的走 UPDATE（以本次拉到的字段为准）；
    #   未入库的走 INSERT IGNORE —— 并发刷新撞唯一键时安静跳过，不会把事务打成 500
    unique_records: dict[str, dict] = {}
    for r in records:
        cid = r.get("call_id")
        if cid and cid not in unique_records:
            unique_records[cid] = r
    in_batch_dup = len(records) - len(unique_records)

    inserted_count = 0
    updated_count = 0
    dup_skipped = 0

    existing_by_cid: dict[str, CallRecord] = {}
    if unique_records:
        q = await db.execute(
            select(CallRecord).where(CallRecord.call_id.in_(list(unique_records.keys())))
        )
        existing_by_cid = {row.call_id: row for row in q.scalars().all()}

    for cid, r in unique_records.items():
        row = existing_by_cid.get(cid)
        if row is not None:
            # 已入库 → 更新（以本次拉到的字段为准）
            row.agent_id           = _to_agent_id(r.get("agent_id")) or row.agent_id or target_agent_id
            row.agent_name         = r.get("agent_name")
            row.dn_id              = r.get("dn_id")
            row.phone_number       = r.get("phone_number")
            row.calling_number     = r.get("calling_number")
            row.established_time   = _to_dt(r.get("established_time"))
            row.released_times     = _to_dt(r.get("released_times"))
            row.handle_times       = r.get("handle_times")
            row.call_url           = r.get("call_url")
            row.call_url_inner     = r.get("call_url_inner")
            row.call_url_decrypted = r.get("call_url_decrypted")
            row.reserve1           = r.get("reserve1")
            row.reserve2           = r.get("reserve2")
            row.reserve3           = r.get("reserve3")
            row.reserve4           = r.get("reserve4")
            row.reserve5           = r.get("reserve5")
            row.fetched_at         = get_current_time()
            row.fetched_by         = loginid
            updated_count += 1
            continue

        # 未入库 → INSERT IGNORE（并发下若已被别人插入则跳过，不报错）
        res = await db.execute(
            mysql_insert(CallRecord)
            .values(
                call_id=cid,
                agent_id=_to_agent_id(r.get("agent_id")) or target_agent_id,
                agent_name=r.get("agent_name"),
                dn_id=r.get("dn_id"),
                phone_number=r.get("phone_number"),
                calling_number=r.get("calling_number"),
                established_time=_to_dt(r.get("established_time")),
                released_times=_to_dt(r.get("released_times")),
                handle_times=r.get("handle_times"),
                call_url=r.get("call_url"),
                call_url_inner=r.get("call_url_inner"),
                call_url_decrypted=r.get("call_url_decrypted"),
                reserve1=r.get("reserve1"),
                reserve2=r.get("reserve2"),
                reserve3=r.get("reserve3"),
                reserve4=r.get("reserve4"),
                reserve5=r.get("reserve5"),
                fetched_at=get_current_time(),
                fetched_by=loginid,
            )
            .prefix_with("IGNORE")
        )
        if res.rowcount == 1:
            inserted_count += 1
        else:
            # 并发下已被别的请求插入 → 跳过（不报错、不重复入库）
            dup_skipped += 1
    await db.commit()

    # 插 call_notes（仅新 call_id；已存在的一律不再插）
    pending_inserted = 0
    if unique_records:
        note_q = await db.execute(
            select(CallNote.call_id).where(CallNote.call_id.in_(list(unique_records.keys())))
        )
        existing_note_ids = {r[0] for r in note_q.all() if r[0]}
        new_note_ids = [cid for cid in unique_records if cid not in existing_note_ids]
        if new_note_ids:
            now_dt = get_current_time()
            await db.execute(
                mysql_insert(CallNote)
                .values([
                    {
                        "call_id": cid,
                        "asr_status": "pending",
                        "structured_status": "pending",
                        "unstructured_status": "pending",
                        "created_at": now_dt,
                        "updated_at": now_dt,
                    }
                    for cid in new_note_ids
                ])
                .prefix_with("IGNORE")
            )
            pending_inserted = len(new_note_ids)
    await db.commit()

    return {
        "inserted": inserted_count,
        "updated": updated_count,
        "dup_skipped": dup_skipped,
        "in_batch_dup_skipped": in_batch_dup,
        "pending_inserted": pending_inserted,
    }


async def _decrypt_and_persist(
    job: dict,
    state: dict,
    raw_records: list[dict],
    *,
    target_agent_id: str,
    loginid: str,
) -> dict:
    """单个座席：去重 → 并发解密 → 落库 → 插催记记录。返回统计。"""
    async with AsyncSessionLocal() as db:
        # 1) 去重：跳过已成功解密的 call_id（call_url_decrypted 非空）
        candidate_ids = [r.get("call_id") for r in raw_records if r.get("call_id")]
        already_decrypted_ids: set[str] = set()
        if candidate_ids:
            existing_q = await db.execute(
                select(CallRecord.call_id).where(
                    CallRecord.call_id.in_(candidate_ids),
                    CallRecord.call_url_decrypted.isnot(None),
                )
            )
            already_decrypted_ids = {r[0] for r in existing_q.all() if r[0]}

        if already_decrypted_ids:
            new_raw_records = [r for r in raw_records if r.get("call_id") not in already_decrypted_ids]
            logger.info(
                f"[催记] {target_agent_id} 跳过 {len(already_decrypted_ids)} 条已解密记录："
                f"{sorted(already_decrypted_ids)[:5]}" + ("..." if len(already_decrypted_ids) > 5 else "")
            )
        else:
            new_raw_records = raw_records

        # 2) 步骤 4：并发解密 call_url_inner → call_url_decrypted
        #    单条失败：warn + 跳过（不影响其他记录）
        ciphers = [(r.get("call_url_inner") or "").strip() for r in new_raw_records]
        results = await decrypt_call_urls(ciphers)
        records: list[dict] = []
        decrypt_failed = 0
        for r, (plain, err) in zip(new_raw_records, results):
            cid = r.get("call_id")
            if err:
                decrypt_failed += 1
                logger.warning(f"[催记] call_id={cid} URL 解密失败，跳过该条：{err}")
                continue
            r["call_url_decrypted"] = plain
            records.append(r)

        # 3) 落库 + 插催记记录
        stats = await _persist_refresh_records(
            db, records, target_agent_id=target_agent_id, loginid=loginid
        )

    state["decrypted"] = len(records)
    state["inserted"] = stats.get("inserted", 0)
    state["updated"] = stats.get("updated", 0)
    state["notes_inserted"] = stats.get("pending_inserted", 0)
    state["skipped_already_decrypted"] = len(already_decrypted_ids)
    state["decrypt_failed"] = decrypt_failed
    return {
        **stats,
        "decrypted": len(records),
        "decrypt_failed": decrypt_failed,
    }


async def _run_refresh_job(
    job: dict,
    *,
    targets: list[dict],
    raw_records: list[dict] | None = None,
    page: int = 1,
    size: int = 100,
    start_str: str = "",
    end_str: str = "",
    duration_days: int = 0,
    loginid: str = "",
    user_info: dict,
    http_request: Request,
) -> None:
    """后台任务：逐个座席拉上游 → 解密 → 落库 → 插催记 → 触发后台处理 → 审计

    - raw_records 非空（k_user 单座席）：上游已在请求里查好，这里只解密+落库
    - raw_records 为 None（admin 多座席）：在任务里逐个查上游，
      单个座席失败不影响其它座席，最后汇总
    """
    agent_states: list[dict] = job.get("agents") or []
    total = 0
    decrypted = 0
    decrypt_failed = 0
    inserted = 0
    updated = 0
    notes_inserted = 0
    skipped_already = 0
    dup_skipped = 0
    in_batch_dup = 0
    failed_agents: list[str] = []
    ok_agents = 0

    try:
        for idx, target in enumerate(targets):
            state = agent_states[idx] if idx < len(agent_states) else {}
            target_agent_id = target["target_agent_id"]
            upstream_agent_id = target["upstream_agent_id"]
            state["status"] = "running"

            records_raw = raw_records
            if records_raw is None:
                # admin 多座席：在后台任务里查上游
                try:
                    records_raw = await query_call_records(
                        page=page,
                        size=size,
                        agent_id=upstream_agent_id,
                        established_time_start=start_str,
                        established_time_end=end_str,
                    )
                except CspApiError as e:
                    state["status"] = "failed"
                    state["error"] = str(e)
                    failed_agents.append(f"{target_agent_id}({e})")
                    logger.error(f"[催记] 刷新座席 {target_agent_id} 上游拉取失败: {e}")
                    continue
                except Exception as e:
                    state["status"] = "failed"
                    state["error"] = str(e)
                    failed_agents.append(f"{target_agent_id}({e})")
                    logger.error(f"[催记] 刷新座席 {target_agent_id} 上游拉取异常: {e!r}")
                    continue

            state["total"] = len(records_raw)
            total += len(records_raw)

            stats = await _decrypt_and_persist(
                job, state, records_raw,
                target_agent_id=target_agent_id,
                loginid=loginid,
            )
            decrypted += stats.get("decrypted", 0)
            decrypt_failed += stats.get("decrypt_failed", 0)
            inserted += stats.get("inserted", 0)
            updated += stats.get("updated", 0)
            notes_inserted += stats.get("pending_inserted", 0)
            dup_skipped += stats.get("dup_skipped", 0)
            in_batch_dup += stats.get("in_batch_dup_skipped", 0)
            skipped_already += state.get("skipped_already_decrypted", 0)
            state["status"] = "done"
            ok_agents += 1

            # 汇总到 job（前端轮询看得到实时进度）
            job.update({
                "total": total,
                "decrypted": decrypted,
                "decrypt_failed": decrypt_failed,
                "inserted": inserted,
                "updated": updated,
                "notes_inserted": notes_inserted,
                "dup_skipped": dup_skipped,
                "in_batch_dup_skipped": in_batch_dup,
                "skipped_already_decrypted": skipped_already,
            })

        # 触发后台处理（非阻塞）
        if notes_inserted > 0:
            await collection_note_service.trigger_background_processing()

        # 汇总消息
        parts = []
        if skipped_already:
            parts.append(f"{skipped_already} 条已解密跳过")
        if decrypt_failed:
            parts.append(f"{decrypt_failed} 条解密失败已跳过")
        if in_batch_dup:
            parts.append(f"{in_batch_dup} 条批次内重复跳过")
        if dup_skipped:
            parts.append(f"{dup_skipped} 条并发重复跳过")
        skip_msg = f"；{', '.join(parts)}" if parts else ""

        if job.get("mode") == "csp_escterminal_whitelist":
            if ok_agents == 0:
                head = f"刷新失败（{len(targets)} 个座席全部失败）"
            else:
                head = f"已刷新 {ok_agents}/{len(targets)} 个座席"
        else:
            head = f"已从上游拉取 {total} 条"
        job["message"] = (
            f"{head}（解密成功 {decrypted}{skip_msg}，新增 {inserted}，更新 {updated}）；"
            f"后台正在处理 {notes_inserted} 条催记"
        )
        if failed_agents:
            job["message"] += f"；{len(failed_agents)} 个座席失败：{', '.join(failed_agents[:3])}"
        # 全部座席都失败才算任务失败；部分失败照常入库，消息里说明
        job["status"] = "done" if ok_agents > 0 else "failed"
        if job["status"] == "failed":
            job["error"] = failed_agents[0] if failed_agents else "全部座席刷新失败"

        # 审计
        await record_action(
            actor=user_info,
            action="collection_note.refresh",
            target_type="collection_note",
            target_id=job.get("agent_id") or "all",
            request=http_request,
            result="fail" if failed_agents else "success",
            detail={
                "mode": job.get("mode") or "csp_escterminal",
                "agent_id": job.get("agent_id"),
                "agent_count": len(targets),
                "agents_ok": ok_agents,
                "agents_failed": failed_agents,
                "start": job.get("start"),
                "end": job.get("end"),
                "duration_days": job.get("duration_days"),
                "raw_returned": total,
                "skipped_already_decrypted": skipped_already,
                "decrypted_ok": decrypted,
                "decrypt_failed": decrypt_failed,
                "records_inserted": inserted,
                "records_updated": updated,
                "records_dup_skipped": dup_skipped,
                "in_batch_dup_skipped": in_batch_dup,
                "notes_pending_inserted": notes_inserted,
            },
        )
    except Exception as e:
        logger.error(f"[催记] 后台刷新任务失败 job={job.get('job_id')}: {e!r}")
        job["status"] = "failed"
        job["error"] = str(e)
        job["message"] = f"刷新失败：{e}"
    finally:
        job["finished_at"] = get_current_time().strftime("%Y-%m-%d %H:%M:%S")
        job["finished_ts"] = time.time()
        _REFRESH_RUNNING_BY_USER.pop(job.get("loginid") or "", None)


@router.get("/calls/refresh/{job_id}")
async def get_refresh_status(
    job_id: str,
    user_info: dict = Depends(get_current_user_required),
):
    """刷新任务进度（前端轮询用）"""
    _reject_oa(user_info)
    role = _extract_role(user_info)
    job = _REFRESH_JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="刷新任务不存在或已过期")
    # 只能看自己的任务（admin 可看全部）
    if role != "admin" and job.get("loginid") != user_info.get("loginid"):
        raise HTTPException(status_code=403, detail="无权查看该刷新任务")
    return {
        "success": True,
        "job": {k: v for k, v in job.items() if k not in ("finished_ts", "loginid")},
    }


# ——— 处理 / 重试 ———

@router.post("/calls/{call_id}/process")
async def process_call(
    call_id: str,
    http_request: Request,
    user_info: dict = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
):
    """整体重新处理：三步全重置 + 走完整流程（同步）"""
    _reject_oa(user_info)
    role = _extract_role(user_info)
    loginid = user_info.get("loginid", "")

    rec = await db.execute(select(CallRecord).where(CallRecord.call_id == call_id))
    row = rec.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail=f"通话 {call_id} 不存在")
    if role == "k_user" and row.agent_id not in _agent_id_variants(loginid):
        raise HTTPException(status_code=403, detail="无访问该通话的权限")

    note_res = await db.execute(select(CallNote).where(CallNote.call_id == call_id))
    note = note_res.scalar_one_or_none()
    if note is None:
        note = CallNote(
            call_id=call_id,
            created_at=get_current_time(),
            updated_at=get_current_time(),
        )
        db.add(note)
        await db.commit()

    await record_action(
        actor=user_info, action="collection_note.process", target_type="collection_note",
        target_id=call_id, request=http_request,
    )

    result = await collection_note_service.reset_and_reprocess(call_id)
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("message", "处理失败"))

    # 取最新 note 返回
    note_res = await db.execute(select(CallNote).where(CallNote.call_id == call_id))
    note = note_res.scalar_one_or_none()
    return {"success": True, "message": "处理完成", "note": _note_to_dict(note)}


@router.post("/calls/{call_id}/transcribe")
async def transcribe_call(
    call_id: str,
    http_request: Request,
    user_info: dict = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
):
    """ASR 转写重试"""
    _reject_oa(user_info)
    role = _extract_role(user_info)
    loginid = user_info.get("loginid", "")

    rec = await db.execute(select(CallRecord).where(CallRecord.call_id == call_id))
    row = rec.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail=f"通话 {call_id} 不存在")
    if role == "k_user" and row.agent_id not in _agent_id_variants(loginid):
        raise HTTPException(status_code=403, detail="无访问该通话的权限")

    note_res = await db.execute(select(CallNote).where(CallNote.call_id == call_id))
    if note_res.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="该通话尚未生成催记记录，请先在刷新后重试")

    await record_action(
        actor=user_info, action="collection_note.transcribe", target_type="collection_note",
        target_id=call_id, request=http_request,
    )

    result = await collection_note_service.retry_transcribe(call_id)
    if not result.get("success") and not result.get("skipped"):
        raise HTTPException(status_code=500, detail=result.get("message", "转写失败"))

    note_res = await db.execute(select(CallNote).where(CallNote.call_id == call_id))
    note = note_res.scalar_one_or_none()
    return {
        "success": True,
        "message": result.get("message", "ok"),
        "skipped": result.get("skipped", False),
        "note": _note_to_dict(note),
    }


@router.post("/calls/{call_id}/note/structured")
async def retry_structured(
    call_id: str,
    http_request: Request,
    user_info: dict = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
):
    """结构化催记重试"""
    _reject_oa(user_info)
    role = _extract_role(user_info)
    loginid = user_info.get("loginid", "")

    rec = await db.execute(select(CallRecord).where(CallRecord.call_id == call_id))
    row = rec.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail=f"通话 {call_id} 不存在")
    if role == "k_user" and row.agent_id not in _agent_id_variants(loginid):
        raise HTTPException(status_code=403, detail="无访问该通话的权限")

    note_res = await db.execute(select(CallNote).where(CallNote.call_id == call_id))
    if note_res.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="该通话尚未生成催记记录，请先在刷新后重试")

    await record_action(
        actor=user_info, action="collection_note.note.structured", target_type="collection_note",
        target_id=call_id, request=http_request,
    )

    result = await collection_note_service.retry_structured_note(call_id)
    if not result.get("success") and not result.get("skipped"):
        raise HTTPException(status_code=500, detail=result.get("message", "重试失败"))

    note_res = await db.execute(select(CallNote).where(CallNote.call_id == call_id))
    note = note_res.scalar_one_or_none()
    return {
        "success": True,
        "message": result.get("message", "ok"),
        "skipped": result.get("skipped", False),
        "note": _note_to_dict(note),
    }


@router.post("/calls/{call_id}/note/unstructured")
async def retry_unstructured(
    call_id: str,
    http_request: Request,
    user_info: dict = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
):
    """非结构化催记重试"""
    _reject_oa(user_info)
    role = _extract_role(user_info)
    loginid = user_info.get("loginid", "")

    rec = await db.execute(select(CallRecord).where(CallRecord.call_id == call_id))
    row = rec.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail=f"通话 {call_id} 不存在")
    if role == "k_user" and row.agent_id not in _agent_id_variants(loginid):
        raise HTTPException(status_code=403, detail="无访问该通话的权限")

    note_res = await db.execute(select(CallNote).where(CallNote.call_id == call_id))
    if note_res.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="该通话尚未生成催记记录，请先在刷新后重试")

    await record_action(
        actor=user_info, action="collection_note.note.unstructured", target_type="collection_note",
        target_id=call_id, request=http_request,
    )

    result = await collection_note_service.retry_unstructured_note(call_id)
    if not result.get("success") and not result.get("skipped"):
        raise HTTPException(status_code=500, detail=result.get("message", "重试失败"))

    note_res = await db.execute(select(CallNote).where(CallNote.call_id == call_id))
    note = note_res.scalar_one_or_none()
    return {
        "success": True,
        "message": result.get("message", "ok"),
        "skipped": result.get("skipped", False),
        "note": _note_to_dict(note),
    }


# ——— 保存（真落库） ———

@router.post("/calls/{call_id}/save-structured")
async def save_structured(
    call_id: str,
    payload: SaveNoteRequest,
    http_request: Request,
    user_info: dict = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
):
    """保存校对结构化催记 → 写入 edited_structured_note"""
    _reject_oa(user_info)
    role = _extract_role(user_info)
    loginid = user_info.get("loginid", "")

    rec = await db.execute(select(CallRecord).where(CallRecord.call_id == call_id))
    row = rec.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail=f"通话 {call_id} 不存在")
    if role == "k_user" and row.agent_id not in _agent_id_variants(loginid):
        raise HTTPException(status_code=403, detail="无访问该通话的权限")

    note_res = await db.execute(select(CallNote).where(CallNote.call_id == call_id))
    note = note_res.scalar_one_or_none()
    if note is None:
        note = CallNote(call_id=call_id, created_at=get_current_time(), updated_at=get_current_time())
        db.add(note)

    note.edited_structured_note = payload.content
    note.updated_at = get_current_time()
    await db.commit()

    await record_action(
        actor=user_info, action="collection_note.save_structured", target_type="collection_note",
        target_id=call_id, request=http_request,
        detail={"call_id": call_id, "chars": len(payload.content or "")},
    )

    return {"success": True, "message": "保存成功", "note": _note_to_dict(note)}


@router.post("/calls/{call_id}/save-unstructured")
async def save_unstructured(
    call_id: str,
    payload: SaveNoteRequest,
    http_request: Request,
    user_info: dict = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
):
    """保存校对非结构化催记 → 写入 edited_unstructured_note"""
    _reject_oa(user_info)
    role = _extract_role(user_info)
    loginid = user_info.get("loginid", "")

    rec = await db.execute(select(CallRecord).where(CallRecord.call_id == call_id))
    row = rec.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail=f"通话 {call_id} 不存在")
    if role == "k_user" and row.agent_id not in _agent_id_variants(loginid):
        raise HTTPException(status_code=403, detail="无访问该通话的权限")

    note_res = await db.execute(select(CallNote).where(CallNote.call_id == call_id))
    note = note_res.scalar_one_or_none()
    if note is None:
        note = CallNote(call_id=call_id, created_at=get_current_time(), updated_at=get_current_time())
        db.add(note)

    note.edited_unstructured_note = payload.content
    note.updated_at = get_current_time()
    await db.commit()

    await record_action(
        actor=user_info, action="collection_note.save_unstructured", target_type="collection_note",
        target_id=call_id, request=http_request,
        detail={"call_id": call_id, "chars": len(payload.content or "")},
    )

    return {"success": True, "message": "保存成功", "note": _note_to_dict(note)}


# ——— view / edit 动作（仅审计） ———

def _phone_tail(phone: str | None) -> str | None:
    if not phone:
        return None
    s = str(phone)[-4:]
    return f"尾号{s}"


@router.post("/calls/{call_id}/view-structured")
async def view_structured(
    call_id: str,
    http_request: Request,
    user_info: dict = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
):
    _reject_oa(user_info)
    role = _extract_role(user_info)
    loginid = user_info.get("loginid", "")
    rec = await db.execute(select(CallRecord).where(CallRecord.call_id == call_id))
    row = rec.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail=f"通话 {call_id} 不存在")
    if role == "k_user" and row.agent_id not in _agent_id_variants(loginid):
        raise HTTPException(status_code=403, detail="无访问该通话的权限")
    await record_action(
        actor=user_info, action="collection_note.view_structured", target_type="collection_note",
        target_id=call_id, request=http_request,
        detail={"call_id": call_id, "agent_id": row.agent_id, "phone_tail": _phone_tail(row.phone_number)},
    )
    return {"success": True, "message": "ok"}


@router.post("/calls/{call_id}/view-unstructured")
async def view_unstructured(
    call_id: str,
    http_request: Request,
    user_info: dict = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
):
    _reject_oa(user_info)
    role = _extract_role(user_info)
    loginid = user_info.get("loginid", "")
    rec = await db.execute(select(CallRecord).where(CallRecord.call_id == call_id))
    row = rec.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail=f"通话 {call_id} 不存在")
    if role == "k_user" and row.agent_id not in _agent_id_variants(loginid):
        raise HTTPException(status_code=403, detail="无访问该通话的权限")
    await record_action(
        actor=user_info, action="collection_note.view_unstructured", target_type="collection_note",
        target_id=call_id, request=http_request,
        detail={"call_id": call_id, "agent_id": row.agent_id, "phone_tail": _phone_tail(row.phone_number)},
    )
    return {"success": True, "message": "ok"}


@router.post("/calls/{call_id}/edit-structured")
async def edit_structured(
    call_id: str,
    payload: SaveNoteRequest,
    http_request: Request,
    user_info: dict = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
):
    """textarea 失焦时上报编辑动作（仅审计）"""
    _reject_oa(user_info)
    role = _extract_role(user_info)
    loginid = user_info.get("loginid", "")
    rec = await db.execute(select(CallRecord).where(CallRecord.call_id == call_id))
    row = rec.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail=f"通话 {call_id} 不存在")
    if role == "k_user" and row.agent_id not in _agent_id_variants(loginid):
        raise HTTPException(status_code=403, detail="无访问该通话的权限")
    await record_action(
        actor=user_info, action="collection_note.edit_structured", target_type="collection_note",
        target_id=call_id, request=http_request,
        detail={"call_id": call_id, "chars": len(payload.content or "")},
    )
    return {"success": True, "message": "ok"}


@router.post("/calls/{call_id}/edit-unstructured")
async def edit_unstructured(
    call_id: str,
    payload: SaveNoteRequest,
    http_request: Request,
    user_info: dict = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
):
    _reject_oa(user_info)
    role = _extract_role(user_info)
    loginid = user_info.get("loginid", "")
    rec = await db.execute(select(CallRecord).where(CallRecord.call_id == call_id))
    row = rec.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail=f"通话 {call_id} 不存在")
    if role == "k_user" and row.agent_id not in _agent_id_variants(loginid):
        raise HTTPException(status_code=403, detail="无访问该通话的权限")
    await record_action(
        actor=user_info, action="collection_note.edit_unstructured", target_type="collection_note",
        target_id=call_id, request=http_request,
        detail={"call_id": call_id, "chars": len(payload.content or "")},
    )
    return {"success": True, "message": "ok"}
