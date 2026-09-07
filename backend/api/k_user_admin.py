"""
k 账号管理 API（admin 专用）

- 列表：列出全部 k 账号、是否需强制改密、最后改密时间等
- 重置密码：把指定 k 账号密码重置为默认密码，并强制下次登录必须改密
"""
import time
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from loguru import logger

from backend.core.config import settings
from backend.core.database import get_db
from backend.core.datetime_utils import get_current_time
from backend.models.k_user import KUser
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
        "must_change": bool(k_user.must_change),
        "needs_change": must_change,
        "password_changed_at": (
            k_user.password_changed_at.isoformat() if k_user.password_changed_at else None
        ),
        "password_expire_at": expire_at,
        "created_at": k_user.created_at.isoformat() if k_user.created_at else None,
        "updated_at": k_user.updated_at.isoformat() if k_user.updated_at else None,
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
