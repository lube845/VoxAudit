"""
登录认证API
"""
import time
import secrets
import hashlib
from fastapi import APIRouter, HTTPException, Header, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional

from backend.core.config import settings
from backend.core.database import get_db
from backend.models.k_user import KUser
from backend.core.datetime_utils import get_current_time
from backend.oa_auth import oa_login_with_password

router = APIRouter(prefix="/auth", tags=["认证"])


# PBKDF2 哈希参数（ponytail: 用 stdlib hashlib，不用 bcrypt/passlib；如需升级到 argon2 等再加）
_PBKDF2_ITERATIONS = 120_000
_PBKDF2_ALGO = "sha256"


def hash_password(password: str) -> tuple[str, str]:
    """生成 (salt_hex, hash_hex)。"""
    salt = secrets.token_bytes(16)
    h = hashlib.pbkdf2_hmac(_PBKDF2_ALGO, password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return salt.hex(), h.hex()


def verify_password(password: str, salt_hex: str, expected_hash_hex: str) -> bool:
    h = hashlib.pbkdf2_hmac(_PBKDF2_ALGO, password.encode("utf-8"), bytes.fromhex(salt_hex), _PBKDF2_ITERATIONS)
    return secrets.compare_digest(h.hex(), expected_hash_hex)


def _k_login_state(k_user: KUser) -> tuple[bool, float | None]:
    """根据 k_user 算出 (是否需强制改密, 密码过期 unix 时间戳)。

    - must_change=True 直接强制改密
    - 已改密且超过 K_USER_PASSWORD_EXPIRE_DAYS 天 → 强制改密
    - expire_at 始终返回，供前端做"提前提醒弹窗"
    """
    expire_at: float | None = None
    if k_user.password_changed_at:
        changed_ts = k_user.password_changed_at.timestamp()
        expire_at = changed_ts + settings.K_USER_PASSWORD_EXPIRE_DAYS * 86400
        expired = time.time() > expire_at
    else:
        expired = False
    return bool(k_user.must_change or expired), expire_at


class LoginRequest(BaseModel):
    loginid: str
    password: str


class LoginResponse(BaseModel):
    success: bool
    message: str
    user_info: dict | None = None
    must_change_password: bool = False


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class ChangePasswordResponse(BaseModel):
    success: bool
    message: str


async def get_current_user(x_user_info: Optional[str] = Header(None, alias="X-User-Info")) -> dict:
    """
    从请求头获取当前用户信息
    前端登录后将用户信息JSON编码后Base64编码放入X-User-Info头
    """
    if not x_user_info:
        raise HTTPException(status_code=401, detail="请先登录")

    import base64
    import json
    try:
        decoded = base64.b64decode(x_user_info)
        user_info = json.loads(decoded)
        if not user_info.get("loginid"):
            raise HTTPException(status_code=401, detail="无效的用户信息")

        # 检查会话是否过期
        login_time = user_info.get("login_time")
        if login_time:
            expire_seconds = settings.SESSION_EXPIRE_HOURS * 3600
            if time.time() - login_time > expire_seconds:
                raise HTTPException(status_code=401, detail="登录已过期，请重新登录")

        return user_info
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="无效的用户信息")


async def get_current_user_required(x_user_info: Optional[str] = Header(None, alias="X-User-Info")) -> dict:
    """
    获取当前用户信息（必须登录）
    """
    if not x_user_info:
        raise HTTPException(status_code=401, detail="请先登录")

    import base64
    import json
    try:
        decoded = base64.b64decode(x_user_info)
        user_info = json.loads(decoded)
        if not user_info.get("loginid"):
            raise HTTPException(status_code=401, detail="无效的用户信息")

        # 检查会话是否过期
        login_time = user_info.get("login_time")
        if login_time:
            expire_seconds = settings.SESSION_EXPIRE_HOURS * 3600
            if time.time() - login_time > expire_seconds:
                raise HTTPException(status_code=401, detail="登录已过期，请重新登录")

        return user_info
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="无效的用户信息")


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    登录接口
    - 超级管理员：直接验证密码
    - k 前缀账号：用本地 PBKDF2 hash 验证；首次登录强制改密
    - 其余用户：走 OA 验证
    """
    # 超级管理员登录
    if request.loginid == settings.ADMIN_USER:
        if request.password != settings.ADMIN_PASSWORD:
            return LoginResponse(success=False, message="密码错误")
        return LoginResponse(
            success=True,
            message="登录成功",
            user_info={
                "工号": "admin",
                "姓名": "超级管理员",
                "部门": "系统管理",
                "岗位": "管理员",
                "loginid": "admin",
                "login_time": time.time(),
            },
        )

    # k 前缀本地账号登录
    if request.loginid.startswith("k"):
        result = await db.execute(select(KUser).where(KUser.loginid == request.loginid))
        k_user = result.scalar_one_or_none()

        # 首次登录：用默认密码登录即落库，强制改密
        if k_user is None:
            if request.password != settings.K_USER_DEFAULT_PASSWORD:
                return LoginResponse(success=False, message="账号或密码错误")
            salt_hex, hash_hex = hash_password(settings.K_USER_DEFAULT_PASSWORD)
            k_user = KUser(
                loginid=request.loginid,
                password_hash=hash_hex,
                salt=salt_hex,
                must_change=True,
            )
            db.add(k_user)
            await db.commit()
            await db.refresh(k_user)
        else:
            if not verify_password(request.password, k_user.salt, k_user.password_hash):
                return LoginResponse(success=False, message="账号或密码错误")

        must_change, expire_at = _k_login_state(k_user)
        return LoginResponse(
            success=True,
            message="登录成功",
            must_change_password=must_change,
            user_info={
                "工号": k_user.loginid,
                "姓名": k_user.loginid,
                "部门": "客服",
                "岗位": "客服",
                "loginid": k_user.loginid,
                "login_time": time.time(),
                "password_expire_at": expire_at,
            },
        )

    # 普通用户OA登录
    success, user_info, message = oa_login_with_password(request.loginid, request.password)

    if not success:
        return LoginResponse(success=False, message=message)

    # 添加登录时间戳
    user_info["login_time"] = time.time()

    return LoginResponse(success=True, message=message, user_info=user_info)


@router.post("/change-password", response_model=ChangePasswordResponse)
async def change_password(
    request: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """改密接口：仅 k 前缀账号可用，需要旧密码。"""
    user_info = await get_current_user_required()
    loginid = user_info.get("loginid", "")

    if not loginid.startswith("k"):
        raise HTTPException(status_code=403, detail="仅 k 开头账号可改密")

    result = await db.execute(select(KUser).where(KUser.loginid == loginid))
    k_user = result.scalar_one_or_none()
    if k_user is None:
        raise HTTPException(status_code=404, detail="账号不存在")

    # 校验旧密码：可能是默认密码，也可能是上次改过的密码
    old_ok = False
    if k_user.must_change:
        old_ok = request.old_password == settings.K_USER_DEFAULT_PASSWORD
    else:
        old_ok = verify_password(request.old_password, k_user.salt, k_user.password_hash)
    if not old_ok:
        return ChangePasswordResponse(success=False, message="旧密码错误")

    if not request.new_password or len(request.new_password) < 6:
        return ChangePasswordResponse(success=False, message="新密码长度至少 6 位")

    salt_hex, hash_hex = hash_password(request.new_password)
    k_user.salt = salt_hex
    k_user.password_hash = hash_hex
    k_user.must_change = False
    k_user.password_changed_at = get_current_time()
    await db.commit()

    return ChangePasswordResponse(success=True, message="密码已修改")