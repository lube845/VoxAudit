"""
评分规则相关数据模型
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Text, Float, ForeignKey
)

from backend.core.database import Base


class ScoringRule(Base):
    """评分规则表"""
    __tablename__ = "scoring_rules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, comment="规则名称")
    code = Column(String(50), nullable=False, comment="规则代码")
    version = Column(String(20), nullable=False, comment="规则版本号")
    description = Column(Text, nullable=True, comment="规则描述")

    total_score = Column(Float, default=100.0, comment="总分")
    rule_type = Column(String(20), default="bonus", comment="规则类型(bonus=加分, deduction=扣分)")

    is_veto = Column(Boolean, default=False, comment="是否否决项")
    is_latest = Column(Boolean, default=True, comment="是否为最新版本")

    parent_id = Column(Integer, nullable=True, comment="上一版本ID")

    # 用户归属（admin=超级管理员）
    user_id = Column(String(50), nullable=True, index=True, comment="所属用户loginid")

    remark = Column(Text, nullable=True, comment="备注")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")
    published_at = Column(DateTime, nullable=True, comment="发布时间")