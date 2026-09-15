"""
审计日志自动埋点中间件

职责：对所有非 GET 请求自动从 URL 推断 action / target_type / target_id，
      调 record_action(...) 写入审计日志。

设计原则：
- 拿不到业务上下文（中间件看不到路由函数里的变量）；关键接口（登录、催记 6 动作、管理员）
  仍在路由函数里手动 record_action(...) 以补充 detail。
- 推断规则：先用 FINE_RULES 精确匹配；未命中走 COARSE_FALLBACK 兜底。
"""
from __future__ import annotations

import re
import time
from typing import Any
from fastapi import Request, Response
from loguru import logger

from backend.services.audit_service import record_action


# ——— 精确规则 ———
# 每条: (method, regex, action, target_type, id_group_name)
FINE_RULES: list[tuple[str, re.Pattern, str, str | None, str | None]] = [
    # —— 规则管理 ——
    ("POST",   re.compile(r"^/api/v1/rules$"),                                    "rule.create",     None, None),
    ("PUT",    re.compile(r"^/api/v1/rules/(?P<id>[^/]+)$"),                       "rule.update",     "rule", "id"),
    ("DELETE", re.compile(r"^/api/v1/rules/(?P<id>[^/]+)$"),                       "rule.delete",     "rule", "id"),
    ("PATCH",  re.compile(r"^/api/v1/rules/(?P<id>[^/]+)/toggle-enabled$"),        "rule.toggle",     "rule", "id"),
    ("POST",   re.compile(r"^/api/v1/rules/(?P<id>[^/]+)/rollback/(?P<ver>[^/]+)$"), "rule.rollback",  "rule", "id"),
    ("POST",   re.compile(r"^/api/v1/rules/ruleimport$"),                          "rule.import",     None, None),
    ("GET",    re.compile(r"^/api/v1/rules/ruleexport$"),                          "rule.export",     None, None),
    ("DELETE", re.compile(r"^/api/v1/rules/history/(?P<id>[^/]+)$"),               "rule.delete_version", "rule", "id"),

    # —— 录音管理 ——
    ("POST",   re.compile(r"^/api/v1/recordings/init-upload$"),                    "recording.upload",         None, None),
    ("POST",   re.compile(r"^/api/v1/recordings/(?P<id>[^/]+)/upload$"),           "recording.upload",         "recording", "id"),
    ("POST",   re.compile(r"^/api/v1/recordings/(?P<id>[^/]+)/transcribe$"),       "recording.transcribe",     "recording", "id"),
    ("POST",   re.compile(r"^/api/v1/recordings/(?P<id>[^/]+)/score$"),           "recording.score",          "recording", "id"),
    ("POST",   re.compile(r"^/api/v1/recordings/(?P<id>[^/]+)/retry-transcribe$"), "recording.retry_transcribe", "recording", "id"),
    ("POST",   re.compile(r"^/api/v1/recordings/(?P<id>[^/]+)/retry-score$"),      "recording.retry_score",    "recording", "id"),
    ("DELETE", re.compile(r"^/api/v1/recordings/(?P<id>[^/]+)$"),                  "recording.delete",         "recording", "id"),
    ("POST",   re.compile(r"^/api/v1/recordings/batch-retry$"),                    "recording.batch_retry",    None, None),

    # —— 催记管理 ——
    ("POST",   re.compile(r"^/api/v1/collection-notes/calls/(?P<id>[^/]+)/view-structured$"),   "collection_note.view_structured",   "collection_note", "id"),
    ("POST",   re.compile(r"^/api/v1/collection-notes/calls/(?P<id>[^/]+)/view-unstructured$"), "collection_note.view_unstructured", "collection_note", "id"),
    ("POST",   re.compile(r"^/api/v1/collection-notes/calls/(?P<id>[^/]+)/edit-structured$"),   "collection_note.edit_structured",   "collection_note", "id"),
    ("POST",   re.compile(r"^/api/v1/collection-notes/calls/(?P<id>[^/]+)/edit-unstructured$"), "collection_note.edit_unstructured", "collection_note", "id"),
    ("POST",   re.compile(r"^/api/v1/collection-notes/calls/(?P<id>[^/]+)/save-structured$"),   "collection_note.save_structured",   "collection_note", "id"),
    ("POST",   re.compile(r"^/api/v1/collection-notes/calls/(?P<id>[^/]+)/save-unstructured$"), "collection_note.save_unstructured", "collection_note", "id"),

    # —— k 账号管理 ——
    ("POST",   re.compile(r"^/api/v1/admin/k-users$"),                             "kuser.create",         None, None),
    ("PUT",    re.compile(r"^/api/v1/admin/k-users/(?P<id>[^/]+)$"),               "kuser.update",         "kuser", "id"),
    ("POST",   re.compile(r"^/api/v1/admin/k-users/(?P<id>[^/]+)/reset-password$"), "kuser.reset_password", "kuser", "id"),
    ("POST",   re.compile(r"^/api/v1/admin/k-users/(?P<id>[^/]+)/clear-data$"),    "kuser.clear_data",     "kuser", "id"),
    ("POST",   re.compile(r"^/api/v1/admin/k-users/(?P<id>[^/]+)/remove$"),        "kuser.remove",         "kuser", "id"),

    # —— 存储清理 ——
    ("POST",   re.compile(r"^/api/v1/storage/delete$"),        "storage.delete",      None, None),
    ("POST",   re.compile(r"^/api/v1/storage/cache/clear$"),   "storage.clear_cache", None, None),

    # —— 系统设置 ——
    ("PUT",    re.compile(r"^/api/v1/system-settings/config/llm$"),     "system_settings.update_llm",     None, None),
    ("PUT",    re.compile(r"^/api/v1/system-settings/config/asr$"),     "system_settings.update_asr",     None, None),
    ("PUT",    re.compile(r"^/api/v1/system-settings/prompts$"),        "system_settings.update_prompts",  None, None),
    ("POST",   re.compile(r"^/api/v1/system-settings/prompts/reset$"),  "system_settings.reset_prompts",  None, None),
    ("POST",   re.compile(r"^/api/v1/system-settings/config/llm/test$"), "system_settings.test",          None, None),
    ("POST",   re.compile(r"^/api/v1/system-settings/config/asr/test$"), "system_settings.test",          None, None),

    # —— 导出 ——
    ("GET",    re.compile(r"^/api/v1/export/report$"),                   "export.report",            None, None),
    ("GET",    re.compile(r"^/api/v1/export/recording/(?P<id>[^/]+)$"),  "export.single_recording",  "recording", "id"),

    # —— 审计日志（自身） ——
    # 注：/admin/audit-logs/export 是 GET，由 handler 内部 record_action() 显式落库，
    #     中间件只处理非 GET，且此处也不需要再做 URL 推断。
    # —— 审计日志自身 list/actions/actors/record 都是 GET/已记，无需中间件覆盖 ——
]


# ——— 中间件跳过的路径前缀 ———
# 这些接口由路由函数手动 record_action(...) 写入更详细的审计行，
# 中间件跳过避免重复/丢失上下文。
_SKIP_PATH_PREFIXES = (
    "/api/v1/auth/",  # 登录/改密/登出：拿不到已认证用户，需手动记
    "/api/v1/admin/audit-logs/",  # 审计日志自身的写入入口，避免自审计
)


# ——— 粗粒度兜底：URL 第一段 → target_type；method → action 后缀 ——
_COARSE_TARGET_TYPE = {
    "rules": "rule",
    "recordings": "recording",
    "collection-notes": "collection_note",
    "admin": None,          # 兜底时 admin/k-users 等二段还要再细分
    "storage": "storage",
    "export": "export",
    "system-settings": "system_settings",
    "statistics": "statistics",
    "auth": "auth",
    "audit-logs": "audit_log",
}

_METHOD_TO_VERB = {
    "POST": "create",
    "PUT": "update",
    "DELETE": "delete",
    "PATCH": "update",
}


def _try_fine_rule(method: str, path: str) -> tuple[str | None, str | None, str | None]:
    """优先用精确规则匹配；返回 (action, target_type, target_id)"""
    for m, regex, action, target_type, id_group in FINE_RULES:
        if m != method:
            continue
        m_obj = regex.match(path)
        if not m_obj:
            continue
        target_id = m_obj.group(id_group) if id_group else None
        return action, target_type, target_id
    return None, None, None


def _coarse_fallback(method: str, path: str) -> tuple[str | None, str | None, str | None]:
    """未命中精确规则时的兜底：用 method + 第一段拼粗粒度 action"""
    if method not in _METHOD_TO_VERB:
        return None, None, None

    # 去掉前缀 /api/v1
    sub = path[len("/api/v1"):] if path.startswith("/api/v1") else path
    sub = sub.lstrip("/")
    if not sub:
        return None, None, None
    segments = sub.split("/")

    first = segments[0]
    target_type = _COARSE_TARGET_TYPE.get(first)

    # admin 段下要再细分：admin/k-users → kuser
    if first == "admin" and len(segments) >= 2:
        sub_map = {
            "k-users": "kuser",
            "audit-logs": "audit_log",
        }
        target_type = sub_map.get(segments[1], "admin")

    # 最后一段如果是数字/字符串，作为 target_id
    target_id = segments[-1] if len(segments) > 1 else None

    action_verb = _METHOD_TO_VERB[method]
    if target_type:
        action = f"{target_type}.{action_verb}"
    else:
        action = action_verb

    return action, target_type, target_id


def _infer(method: str, path: str) -> tuple[str | None, str | None, str | None]:
    action, target_type, target_id = _try_fine_rule(method, path)
    if action:
        return action, target_type, target_id
    return _coarse_fallback(method, path)


async def _try_get_actor(request: Request) -> dict | None:
    """从 X-User-Info 头解出 actor；失败返回 None"""
    try:
        import base64
        import json
        encoded = request.headers.get("x-user-info")
        if not encoded:
            return None
        decoded = base64.b64decode(encoded)
        info = json.loads(decoded)
        if not info.get("loginid"):
            return None
        return info
    except Exception:
        return None


async def audit_middleware(request: Request, call_next):
    """FastAPI 中间件：对所有非 GET 自动埋点审计日志"""
    method = request.method

    # 1) 先处理业务，拿到 response（确保不影响业务）
    response: Response = await call_next(request)

    # 2) GET / HEAD / OPTIONS 不记（页面访问由前端路由守卫记）
    if method in ("GET", "HEAD", "OPTIONS"):
        return response

    # 3) 跳过静态资源/文档
    path = request.url.path
    if path.startswith("/docs") or path.startswith("/openapi") or path == "/health":
        return response

    # 3.1) 跳过需要手动埋点的接口
    if any(path.startswith(p) for p in _SKIP_PATH_PREFIXES):
        return response

    # 4) 推断 action
    action, target_type, target_id = _infer(method, path)
    if not action:
        return response

    # 5) 取 actor（未登录则不记）
    actor = await _try_get_actor(request)
    if not actor:
        return response

    # 6) 写审计（异步、不阻塞 response）
    result = "success" if response.status_code < 400 else "fail"
    try:
        await record_action(
            actor=actor,
            action=action,
            target_type=target_type,
            target_id=target_id,
            request=request,
            result=result,
        )
    except Exception as e:
        logger.warning(f"audit_middleware 写入失败: {e}")

    return response