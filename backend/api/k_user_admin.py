"""
k 账号管理 API（admin 专用）

- 列表：列出全部 k 账号、是否需强制改密、最后改密时间等
- 重置密码：把指定 k 账号密码重置为默认密码，并强制下次登录必须改密
"""
import time
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from pydantic import BaseModel
from loguru import logger

from backend.core.config import settings
from backend.core.database import get_db
from backend.core.datetime_utils import get_current_time
from backend.models.k_user import KUser
from backend.models.recording import Recording, TranscriptSegment, ScoringResult
from backend.models.rule import ScoringRule
from backend.services.oss_service import oss_service
from backend.api.auth import hash_password, _k_login_state, get_current_user_required

router = APIRouter(prefix="/admin/k-users", tags=["客服账号管理"])


def _require_admin(user_info: dict) -> None:
    """仅 admin 可访问"""
    if user_info.get("loginid") != settings.ADMIN_USER:
        raise HTTPException(status_code=403, detail="仅管理员可访问")


def _serialize_k_user(k_user: KUser) -> dict:
    """把 KUser ORM 行序列化为前端展示用的字典"""
    must_change, expire_at = _k_login_state(k_user)
    return {
        "loginid": k_user.loginid,
        "name": k_user.name,
        "department": k_user.department,
        "must_change": bool(k_user.must_change),
        "needs_change": must_change,
        "password_changed_at": (
            k_user.password_changed_at.isoformat() if k_user.password_changed_at else None
        ),
        "password_expire_at": expire_at,
        "created_at": k_user.created_at.isoformat() if k_user.created_at else None,
        "updated_at": k_user.updated_at.isoformat() if k_user.updated_at else None,
    }


class CreateKUserRequest(BaseModel):
    """添加客服白名单请求体"""
    loginid: str
    name: str | None = None
    department: str | None = None


class UpdateKUserRequest(BaseModel):
    """修改客服白名单请求体（仅可改姓名/部门）"""
    name: str | None = None
    department: str | None = None


@router.put("/{loginid}")
async def update_k_user(
    loginid: str,
    payload: UpdateKUserRequest,
    db: AsyncSession = Depends(get_db),
    user_info: dict = Depends(get_current_user_required),
):
    """修改客服白名单的姓名/部门（admin，工号与密码不可改）"""
    _require_admin(user_info)

    if not loginid.startswith("k"):
        raise HTTPException(status_code=400, detail="仅支持 k 开头账号")

    result = await db.execute(select(KUser).where(KUser.loginid == loginid))
    k_user = result.scalar_one_or_none()
    if k_user is None:
        raise HTTPException(status_code=404, detail=f"账号 {loginid} 不存在")

    # 入参允许为 null/空字符串：null 视为"保持原值"，空字符串视为"清空"
    if payload.name is not None:
        k_user.name = payload.name.strip() or None
    if payload.department is not None:
        k_user.department = payload.department.strip() or None

    await db.commit()
    await db.refresh(k_user)

    logger.info(
        f"admin {user_info.get('loginid')} 修改 k 账号 {loginid}: "
        f"name={k_user.name}, department={k_user.department}"
    )
    return {
        "success": True,
        "message": f"已修改 {loginid} 的信息",
        "item": _serialize_k_user(k_user),
    }


@router.post("")
async def create_k_user(
    payload: CreateKUserRequest,
    db: AsyncSession = Depends(get_db),
    user_info: dict = Depends(get_current_user_required),
):
    """添加一条客服白名单（admin）：预创建账号并写入姓名/部门，
    首次登录即用默认密码 kefu123456，并强制改密。"""
    _require_admin(user_info)

    loginid = (payload.loginid or "").strip()
    if not loginid.startswith("k"):
        raise HTTPException(status_code=400, detail="工号必须以 k 开头")
    if not loginid:
        raise HTTPException(status_code=400, detail="工号不能为空")
    if len(loginid) > 50:
        raise HTTPException(status_code=400, detail="工号长度不能超过 50")

    existing = await db.execute(select(KUser).where(KUser.loginid == loginid))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail=f"工号 {loginid} 已存在")

    name = (payload.name or "").strip() or None
    department = (payload.department or "").strip() or None

    salt_hex, hash_hex = hash_password(settings.K_USER_DEFAULT_PASSWORD)
    k_user = KUser(
        loginid=loginid,
        password_hash=hash_hex,
        salt=salt_hex,
        must_change=True,
        name=name,
        department=department,
        password_changed_at=None,
    )
    db.add(k_user)
    await db.commit()
    await db.refresh(k_user)

    logger.info(
        f"admin {user_info.get('loginid')} 添加客服白名单 {loginid} "
        f"(name={name}, department={department})"
    )
    return {
        "success": True,
        "message": (
            f"已添加客服白名单 {loginid}，默认密码 {settings.K_USER_DEFAULT_PASSWORD}，"
            f"首次登录需强制改密"
        ),
        "item": _serialize_k_user(k_user),
    }


@router.get("")
async def list_k_users(
    db: AsyncSession = Depends(get_db),
    user_info: dict = Depends(get_current_user_required),
):
    """列出全部 k 账号（admin）"""
    _require_admin(user_info)
    result = await db.execute(select(KUser).order_by(KUser.created_at.desc()))
    items = [_serialize_k_user(u) for u in result.scalars().all()]
    return {"success": True, "items": items, "total": len(items)}


@router.post("/{loginid}/reset-password")
async def reset_k_user_password(
    loginid: str,
    db: AsyncSession = Depends(get_db),
    user_info: dict = Depends(get_current_user_required),
):
    """把指定 k 账号密码重置为默认密码，并强制下次登录必须改密（admin）"""
    _require_admin(user_info)

    if not loginid.startswith("k"):
        raise HTTPException(status_code=400, detail="仅支持 k 开头账号")

    result = await db.execute(select(KUser).where(KUser.loginid == loginid))
    k_user = result.scalar_one_or_none()
    if k_user is None:
        raise HTTPException(status_code=404, detail=f"账号 {loginid} 不存在")

    salt_hex, hash_hex = hash_password(settings.K_USER_DEFAULT_PASSWORD)
    k_user.salt = salt_hex
    k_user.password_hash = hash_hex
    k_user.must_change = True
    k_user.password_changed_at = None  # 关键：清空，否则下次登录会被当作"刚改密"
    await db.commit()
    await db.refresh(k_user)

    logger.info(f"admin {user_info.get('loginid')} 重置 k 账号 {loginid} 的密码")
    return {
        "success": True,
        "message": f"已重置 {loginid} 的密码为默认密码，下次登录需强制改密",
        "item": _serialize_k_user(k_user),
    }


async def _purge_k_user_business_data(
    db: AsyncSession, loginid: str
) -> dict:
    """清空 k 账号的全部业务数据（不 commit；返回删除条数与待清理的 OSS 对象键列表）。
    删除顺序：transcript_segments / scoring_results（子表）→ scoring_rules / recordings（主表）。
    """
    rec_rows = (
        await db.execute(
            select(Recording.id, Recording.oss_bucket, Recording.oss_object_key)
            .where(Recording.user_id == loginid)
        )
    ).all()
    rec_ids = [r[0] for r in rec_rows]
    object_keys = [(r[1], r[2]) for r in rec_rows if r[2]]

    transcript_deleted = 0
    scoring_results_deleted = 0
    if rec_ids:
        ts_res = await db.execute(
            delete(TranscriptSegment).where(TranscriptSegment.recording_id.in_(rec_ids))
        )
        transcript_deleted = ts_res.rowcount or 0
        sr_res = await db.execute(
            delete(ScoringResult).where(ScoringResult.recording_id.in_(rec_ids))
        )
        scoring_results_deleted = sr_res.rowcount or 0

    rules_res = await db.execute(
        delete(ScoringRule).where(ScoringRule.user_id == loginid)
    )
    rules_deleted = rules_res.rowcount or 0

    rec_res = await db.execute(
        delete(Recording).where(Recording.user_id == loginid)
    )
    recordings_deleted = rec_res.rowcount or 0

    return {
        "recordings_deleted": recordings_deleted,
        "rules_deleted": rules_deleted,
        "transcripts_deleted": transcript_deleted,
        "scoring_results_deleted": scoring_results_deleted,
        "object_keys": object_keys,
    }


async def _delete_oss_objects(object_keys: list[tuple[str, str]]) -> tuple[int, int]:
    """best-effort 删除 MinIO 对象；返回 (files_deleted, files_failed)"""
    files_deleted = 0
    files_failed = 0
    for bucket, key in object_keys:
        try:
            await oss_service.delete_file(key, bucket)
            files_deleted += 1
        except Exception:
            files_failed += 1
    return files_deleted, files_failed


@router.post("/{loginid}/clear-data")
async def clear_k_user_data(
    loginid: str,
    db: AsyncSession = Depends(get_db),
    user_info: dict = Depends(get_current_user_required),
):
    """清除指定 k 账号的全部业务数据（admin，密码不变）：
    - recordings（含 transcript_segments / scoring_results 子表）
    - scoring_rules
    - MinIO 上的录音文件
    账号本身（k_users 行）保留，密码、姓名、部门不动。
    """
    _require_admin(user_info)

    if not loginid.startswith("k"):
        raise HTTPException(status_code=400, detail="仅支持 k 开头账号")

    k_user = (
        await db.execute(select(KUser).where(KUser.loginid == loginid))
    ).scalar_one_or_none()
    if k_user is None:
        raise HTTPException(status_code=404, detail=f"账号 {loginid} 不存在")

    counts = await _purge_k_user_business_data(db, loginid)
    await db.commit()

    files_deleted, files_failed = await _delete_oss_objects(counts["object_keys"])

    logger.info(
        f"admin {user_info.get('loginid')} 清除 k 账号 {loginid} 数据："
        f"recordings={counts['recordings_deleted']}, rules={counts['rules_deleted']}, "
        f"transcripts={counts['transcripts_deleted']}, "
        f"scoring_results={counts['scoring_results_deleted']}, "
        f"files_deleted={files_deleted}, files_failed={files_failed}"
    )

    msg = (
        f"已清除 {loginid} 的数据：{counts['recordings_deleted']} 条录音、"
        f"{counts['rules_deleted']} 条评分规则、{files_deleted} 个文件"
    )
    if files_failed:
        msg += f"，{files_failed} 个文件删除失败"

    return {
        "success": True,
        "message": msg,
        "recordings_deleted": counts["recordings_deleted"],
        "rules_deleted": counts["rules_deleted"],
        "transcripts_deleted": counts["transcripts_deleted"],
        "scoring_results_deleted": counts["scoring_results_deleted"],
        "files_deleted": files_deleted,
        "files_failed": files_failed,
        # 账号行仍然存在，密码不变
        "item": _serialize_k_user(k_user),
    }


@router.post("/{loginid}/remove")
async def remove_k_user(
    loginid: str,
    db: AsyncSession = Depends(get_db),
    user_info: dict = Depends(get_current_user_required),
):
    """剔除 k 账号白名单（admin）：
    1) 清除该账号的全部业务数据（同 clear-data）
    2) 删除 k_users 行（账号从此无法登录，除非再次被 admin 添加）
    """
    _require_admin(user_info)

    if not loginid.startswith("k"):
        raise HTTPException(status_code=400, detail="仅支持 k 开头账号")
    if loginid == settings.ADMIN_USER:
        # 防御性：理论上 ADMIN_USER='admin' 不以 k 开头已被上面拦截，但保留双重保护
        raise HTTPException(status_code=400, detail="不允许剔除系统管理员")

    k_user = (
        await db.execute(select(KUser).where(KUser.loginid == loginid))
    ).scalar_one_or_none()
    if k_user is None:
        raise HTTPException(status_code=404, detail=f"账号 {loginid} 不存在")

    counts = await _purge_k_user_business_data(db, loginid)

    # 删除白名单行
    await db.delete(k_user)
    await db.commit()

    files_deleted, files_failed = await _delete_oss_objects(counts["object_keys"])

    logger.info(
        f"admin {user_info.get('loginid')} 剔除 k 账号白名单 {loginid}："
        f"recordings={counts['recordings_deleted']}, rules={counts['rules_deleted']}, "
        f"transcripts={counts['transcripts_deleted']}, "
        f"scoring_results={counts['scoring_results_deleted']}, "
        f"files_deleted={files_deleted}, files_failed={files_failed}"
    )

    msg = (
        f"已剔除 {loginid}：清除 {counts['recordings_deleted']} 条录音、"
        f"{counts['rules_deleted']} 条评分规则、{files_deleted} 个文件，账号不再能登录"
    )
    if files_failed:
        msg += f"，{files_failed} 个文件删除失败"

    return {
        "success": True,
        "message": msg,
        "recordings_deleted": counts["recordings_deleted"],
        "rules_deleted": counts["rules_deleted"],
        "transcripts_deleted": counts["transcripts_deleted"],
        "scoring_results_deleted": counts["scoring_results_deleted"],
        "files_deleted": files_deleted,
        "files_failed": files_failed,
        "removed_loginid": loginid,
    }
