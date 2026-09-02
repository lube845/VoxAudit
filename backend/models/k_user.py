"""
k 前缀本地账号数据模型
- 首次用默认密码登录即落库，must_change=1，强制改密
- 改密后写入新 hash + 新 salt，must_change=0
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
    must_change = Column(Boolean, default=True, nullable=False, comment="是否仍为默认密码，需强制改密")
    password_changed_at = Column(DateTime, nullable=True, comment="最近一次改密时间；NULL 表示仍在用默认密码")
    created_at = Column(DateTime, default=get_current_time, comment="创建时间")
    updated_at = Column(DateTime, default=get_current_time, onupdate=get_current_time, comment="更新时间")