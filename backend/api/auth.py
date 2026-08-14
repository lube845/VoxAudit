"""
登录认证API
"""
import time
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
from backend.core.config import settings
from backend.oa_auth import oa_login_with_password

router = APIRouter(prefix="/auth", tags=["认证"])


class LoginRequest(BaseModel):
    loginid: str
    password: str


class LoginResponse(BaseModel):
    success: bool
    message: str
    user_info: dict | None = None


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
async def login(request: LoginRequest):
    """
    登录接口
    - 如果登录ID是超级管理员，直接验证密码
    - 否则通过OA系统验证
    """
    # 超级管理员登录
    if request.loginid == settings.ADMIN_USER:
        if request.password != settings.ADMIN_PASSWORD:
            return LoginResponse(
                success=False,
                message="密码错误"
            )
        return LoginResponse(
            success=True,
            message="登录成功",
            user_info={
                "工号": "admin",
                "姓名": "超级管理员",
                "部门": "系统管理",
                "岗位": "管理员",
                "loginid": "admin",
                "login_time": time.time()
            }
        )

    # 普通用户OA登录
    success, user_info, message = oa_login_with_password(request.loginid, request.password)

    if not success:
        return LoginResponse(
            success=False,
            message=message
        )

    # 添加登录时间戳
    user_info["login_time"] = time.time()

    return LoginResponse(
        success=True,
        message=message,
        user_info=user_info
    )