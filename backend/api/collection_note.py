"""
催记管理 API

当前状态：**占位实现**。上游通话数据接口还在开发中（call_records 表暂不建），
所以本接口暂以"最小骨架"形式提供：
- GET 列表 / 详情：返回 mock 数据，让前端能跑通流程
- POST 6 个动作（view/edit/save ×2）：只记录审计日志，不修改任何持久化数据

上游就绪后，把下面 TODO 替换为真实 DB 操作即可。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from loguru import logger

from backend.api.auth import get_current_user_required
from backend.services.audit_service import record_action


router = APIRouter(prefix="/collection-notes", tags=["催记管理"])


# ——— 临时 mock 数据 ———
# 上游未接期间给前端 UI 跑流程用；call_id 唯一即可
_MOCK_CALLS = [
    {
        "call_id": "CALL20250914001",
        "agent_id": "CS001",
        "agent_name": "张明",
        "extension": "8001",
        "phone": "13888885678",
        "start_time": "2026-09-14 09:32:15",
        "end_time": "2026-09-14 09:35:48",
        "duration_sec": 213,
        "duration_text": "3分33秒",
        "transcript": "座席：您好，请问是13888885678机主本人吗？\n客户：是的，您是哪里？\n座席：您好，我是xx银行催收中心的张明，工号CS001……",
        "structured_note": "【客户身份】确认本人\n【欠款情况】尾号5678信用卡，逾期15天，金额4500.00元\n【客户反馈】资金紧张，要求缓期\n【承诺情况】承诺下周三发工资后全额还款\n【后续跟进】2026-09-20 跟进还款情况",
        "unstructured_note": "本次通话由座席张明（工号CS001）于 2026-09-14 09:32 外呼尾号5678 用户，确认本人身份后告知其信用卡已逾期、欠款情况。客户表示近期资金紧张、请求缓期；经沟通最终承诺下周三发工资后全额还款。后续将于 2026-09-20 跟进还款情况。",
    },
    {
        "call_id": "CALL20250914002",
        "agent_id": "CS002",
        "agent_name": "李婷",
        "extension": "8002",
        "phone": "13912341234",
        "start_time": "2026-09-14 10:15:32",
        "end_time": "2026-09-14 10:18:45",
        "duration_sec": 193,
        "duration_text": "3分13秒",
        "transcript": "座席：您好，请问是13912341234机主本人吗？……",
        "structured_note": "【客户身份】确认本人\n【欠款情况】尾号1234信用卡，逾期8天，金额2300.00元\n【客户反馈】本周可还款\n【承诺情况】承诺本周五前还款\n【后续跟进】2026-09-19 跟进还款情况",
        "unstructured_note": "本次通话由座席李婷（工号CS002）于 2026-09-14 10:15 外呼尾号1234 用户，确认本人身份后告知其信用卡已逾期、欠款情况。客户表示本周可还款，并承诺本周五前还款。后续将于 2026-09-19 跟进还款情况。",
    },
]


def _phone_tail(phone: str | None) -> str | None:
    """脱敏：取尾号 4 位"""
    if not phone:
        return None
    s = str(phone)[-4:]
    return f"尾号{s}"


def _calc_metrics(text: str | None) -> dict:
    """统计催记内容的字符数与行数（不入库原文）"""
    if not text:
        return {"chars": 0, "lines": 0}
    return {
        "chars": len(text),
        "lines": text.count("\n") + 1 if text else 0,
    }


# ——— 入参 ———
class SaveNoteRequest(BaseModel):
    content: str  # 前端送来用于审计统计（不入库原文 → 服务端不持久化）
    is_final: bool = False


# ——— 接口 ———
@router.get("/calls")
async def list_calls(
    agent_id: str | None = None,
    agent_name: str | None = None,
    extension: str | None = None,
    phone: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    user_info: dict = Depends(get_current_user_required),
):
    """通话列表（占位）"""
    items = []
    for c in _MOCK_CALLS:
        if agent_id and c["agent_id"] != agent_id:
            continue
        if agent_name and agent_name not in (c["agent_name"] or ""):
            continue
        if extension and c["extension"] != extension:
            continue
        if phone and phone not in c["phone"]:
            continue
        items.append({
            "call_id": c["call_id"],
            "agent_id": c["agent_id"],
            "agent_name": c["agent_name"],
            "extension": c["extension"],
            "phone": c["phone"],
            "start_time": c["start_time"],
            "end_time": c["end_time"],
            "duration_sec": c["duration_sec"],
            "duration_text": c["duration_text"],
        })
    return {"success": True, "items": items, "total": len(items)}


@router.get("/calls/{call_id}")
async def get_call(
    call_id: str,
    user_info: dict = Depends(get_current_user_required),
):
    """单个通话详情（占位）"""
    c = next((x for x in _MOCK_CALLS if x["call_id"] == call_id), None)
    if c is None:
        raise HTTPException(status_code=404, detail=f"通话 {call_id} 不存在")
    return {
        "success": True,
        "item": {
            **c,
            # 详情返回时再算一次 metrics，前端可以直接展示
        },
    }


@router.post("/calls/{call_id}/view-structured")
async def view_structured(
    call_id: str,
    http_request: Request,
    user_info: dict = Depends(get_current_user_required),
):
    """标记"查看结构化催记"。仅记审计。"""
    c = next((x for x in _MOCK_CALLS if x["call_id"] == call_id), None)
    if c is None:
        raise HTTPException(status_code=404, detail=f"通话 {call_id} 不存在")
    metrics = _calc_metrics(c["structured_note"])
    await record_action(
        actor=user_info,
        action="collection_note.view_structured",
        target_type="collection_note",
        target_id=call_id,
        request=http_request,
        detail={
            "call_id": call_id,
            "agent_id": c["agent_id"],
            "phone_tail": _phone_tail(c["phone"]),
            **metrics,
        },
    )
    return {"success": True, "message": "ok"}


@router.post("/calls/{call_id}/view-unstructured")
async def view_unstructured(
    call_id: str,
    http_request: Request,
    user_info: dict = Depends(get_current_user_required),
):
    """标记"查看非结构化催记"。仅记审计。"""
    c = next((x for x in _MOCK_CALLS if x["call_id"] == call_id), None)
    if c is None:
        raise HTTPException(status_code=404, detail=f"通话 {call_id} 不存在")
    metrics = _calc_metrics(c["unstructured_note"])
    await record_action(
        actor=user_info,
        action="collection_note.view_unstructured",
        target_type="collection_note",
        target_id=call_id,
        request=http_request,
        detail={
            "call_id": call_id,
            "agent_id": c["agent_id"],
            "phone_tail": _phone_tail(c["phone"]),
            **metrics,
        },
    )
    return {"success": True, "message": "ok"}


@router.post("/calls/{call_id}/edit-structured")
async def edit_structured(
    call_id: str,
    payload: SaveNoteRequest,
    http_request: Request,
    user_info: dict = Depends(get_current_user_required),
):
    """上报"编辑过结构化催记"（textarea blur 时触发）。仅记审计。"""
    metrics = _calc_metrics(payload.content)
    await record_action(
        actor=user_info,
        action="collection_note.edit_structured",
        target_type="collection_note",
        target_id=call_id,
        request=http_request,
        detail={
            "call_id": call_id,
            "is_final": payload.is_final,
            **metrics,  # chars/lines，不存原文
        },
    )
    return {"success": True, "message": "ok"}


@router.post("/calls/{call_id}/edit-unstructured")
async def edit_unstructured(
    call_id: str,
    payload: SaveNoteRequest,
    http_request: Request,
    user_info: dict = Depends(get_current_user_required),
):
    """上报"编辑过非结构化催记"（textarea blur 时触发）。仅记审计。"""
    metrics = _calc_metrics(payload.content)
    await record_action(
        actor=user_info,
        action="collection_note.edit_unstructured",
        target_type="collection_note",
        target_id=call_id,
        request=http_request,
        detail={
            "call_id": call_id,
            "is_final": payload.is_final,
            **metrics,
        },
    )
    return {"success": True, "message": "ok"}


@router.post("/calls/{call_id}/save-structured")
async def save_structured(
    call_id: str,
    payload: SaveNoteRequest,
    http_request: Request,
    user_info: dict = Depends(get_current_user_required),
):
    """保存结构化催记。当前 mock 实现：不持久化（上游未接），仅记审计。"""
    metrics = _calc_metrics(payload.content)
    await record_action(
        actor=user_info,
        action="collection_note.save_structured",
        target_type="collection_note",
        target_id=call_id,
        request=http_request,
        detail={
            "call_id": call_id,
            "is_final": payload.is_final,
            **metrics,
        },
    )
    return {"success": True, "message": "已保存（mock）"}


@router.post("/calls/{call_id}/save-unstructured")
async def save_unstructured(
    call_id: str,
    payload: SaveNoteRequest,
    http_request: Request,
    user_info: dict = Depends(get_current_user_required),
):
    """保存非结构化催记。当前 mock 实现：不持久化（上游未接），仅记审计。"""
    metrics = _calc_metrics(payload.content)
    await record_action(
        actor=user_info,
        action="collection_note.save_unstructured",
        target_type="collection_note",
        target_id=call_id,
        request=http_request,
        detail={
            "call_id": call_id,
            "is_final": payload.is_final,
            **metrics,
        },
    )
    return {"success": True, "message": "已保存（mock）"}