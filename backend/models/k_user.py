"""
k 前缀本地账号数据模型

强制改密触发条件（任一为真即触发）：
- must_change=True：主动强制标志（管理员重置、首次落库默认 True）
- password_changed_at IS NULL：从未改密，仍在用默认密码
- 距 password_changed_at 已超过 K_USER_PASSWORD_EXPIRE_DAYS 天：密码过期

改密后写入新 hash + 新 salt，清 must_change=0，更新 password_changed_at。
"""
from sqlalchemy import Column, String, Boolean, DateTime
from backend.core.database import Base
from backend.core.datetime_utils import get_current_time


class KUser(Base):
    """k 前缀本地账号表"""
    __tablename__ = "k_users"

    loginid = Column(String(50), primary_key=True, comment="登录账号（k 开头）")
    password_hash = Column(String(255), nullable=False, comment="PBKDF2 摘要（hex）")
    salt = Column(String(64), nullable=False, comment="PBKDF2 盐（hex）")
    must_change = Column(Boolean, default=True, nullable=False, comment="是否需强制改密（管理员主动设置或首次登录落库为 True）")
    password_changed_at = Column(DateTime, nullable=True, comment="最近一次改密时间；NULL 表示从未改密，也会触发强制改密")
    created_at = Column(DateTime, default=get_current_time, comment="创建时间")
    updated_at = Column(DateTime, default=get_current_time, onupdate=get_current_time, comment="更新时间")