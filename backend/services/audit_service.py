"""
审计日志服务

对外暴露 `record_action(...)` 一个函数：
- 独立 AsyncSession 写入（不挂在请求 db 上，业务回滚不带走审计行）
- 进程内 5 分钟去重（同 actor + target + action）
- result=fail 不去重（失败事件全留，便于排障）
- 写入失败不影响主业务
"""
from __future__ import annotations

import time
from typing import Any
from fastapi import Request
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import AsyncSessionLocal
from backend.models.audit_log import AuditLog


# ——— 配置 ———
DEDUP_WINDOW_SECONDS = 300  # 5 分钟

# ——— 进程内去重表 ———
# key: (actor_loginid, action, target_type, target_id)
# value: 上次记录时间戳（time.time()）
_recent_dedup: dict[tuple, float] = {}
_last_gc_ts: float = 0.0
_GC_INTERVAL_SECONDS = 60  # 每 60 秒 lazy 清理一次过期 key


def _gc_dedup_lockal(now: float) -> None:
    """惰性清理过期的去重 key，控制字典大小"""
    global _last_gc_ts
    if now - _last_gc_ts < _GC_INTERVAL_SECONDS:
        return
    _last_gc_ts = now
    cutoff = now - DEDUP_WINDOW_SECONDS
    expired = [k for k, t in _recent_dedup.items() if t < cutoff]
    for k in expired:
        _recent_dedup.pop(k, None)


def _is_duplicate(actor: str, action: str, target_type: str | None, target_id: str | None) -> bool:
    """同 actor + 同 target + 同 action 在 DEDUP_WINDOW_SECONDS 内只记一次"""
    now = time.time()
    _gc_dedup_lockal(now)
    key = (actor, action, target_type or "", target_id or "")
    last = _recent_dedup.get(key)
    if last is not None and now - last < DEDUP_WINDOW_SECONDS:
        return True
    _recent_dedup[key] = now
    return False


def _extract_actor_role(actor: dict | None) -> str | None:
    """从 user_info 推断角色"""
    if not actor:
        return None
    if actor.get("loginid") == "admin":
        return "admin"
    loginid = actor.get("loginid") or ""
    if loginid.startswith("k"):
        return "k_user"
    return "oa_user"


def _extract_ip(request: Request | None) -> str | None:
    if request is None:
        return None
    # 优先 X-Forwarded-For（反代后），其次 client.host
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    if request.client:
        return request.client.host
    return None


def _extract_ua(request: Request | None) -> str | None:
    if request is None:
        return None
    ua = request.headers.get("user-agent")
    if ua:
        return ua[:255]
    return None


async def record_action(
    *,
    actor: dict | None,
    action: str,
    target_type: str | None = None,
    target_id: str | None = None,
    target_label: str | None = None,
    request: Request | None = None,
    result: str = "success",
    detail: dict[str, Any] | None = None,
) -> None:
    """写入一行审计日志。

    用法（典型）：
        await record_action(
            actor=current_user_dict,
            action="recording.score",
            target_type="recording",
            target_id=str(recording_id),
            request=request,
            detail={"score": 88.5},
        )

    行为约定：
    - actor 为空 → 不记（未登录的请求一般是健康检查等）
    - result=fail 不去重（失败事件全留）
    - 写入异常仅 logger.warning，不抛
    """
    try:
        if not actor or not actor.get("loginid"):
            return

        actor_loginid = actor["loginid"]

        # 失败事件不去重；其他走 5 分钟去重
        if result != "fail" and _is_duplicate(actor_loginid, action, target_type, target_id):
            return

        log = AuditLog(
            actor_loginid=actor_loginid,
            actor_name=actor.get("姓名") or actor.get("name"),
            actor_role=_extract_actor_role(actor),
            action=action,
            target_type=target_type,
            target_id=str(target_id) if target_id is not None else None,
            target_label=target_label,
            ip=_extract_ip(request),
            user_agent=_extract_ua(request),
            result=result,
            detail=detail,
        )

        async with AsyncSessionLocal() as session:
            session.add(log)
            await session.commit()
    except Exception as e:
        # 写入失败不能影响主业务
        logger.warning(f"audit_service.record_action 写入失败: {e}")