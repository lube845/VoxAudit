"""
系统设置数据模型
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime
from backend.core.database import Base


class SystemSettings(Base):
    """系统配置表"""
    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False, index=True, comment="配置键")
    value = Column(Text, nullable=True, comment="配置值")
    description = Column(String(255), nullable=True, comment="配置描述")
    is_secret = Column(Boolean, default=False, comment="是否敏感信息（如密码、密钥）")
    is_system = Column(Boolean, default=False, comment="是否为系统级配置")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")
