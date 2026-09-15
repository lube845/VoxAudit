"""
审计日志数据模型

记录 admin / k_user / oa_user 三类用户的全部有副作用操作，用于后台审计查询。

设计要点：
- 仅增不改：admin 也只能查询
- 业务事务回滚不带走审计行：写入走独立 session
- 5 分钟内同 actor + target + action 去重（避免误点击刷屏）
- detail 不存原文，敏感字段脱敏（手机号只存尾号）
"""
from sqlalchemy import Column, BigInteger, String, DateTime, JSON, Text

from backend.core.database import Base
from backend.core.datetime_utils import get_current_time


class AuditLog(Base):
    """审计日志表"""
    __tablename__ = "audit_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="自增ID")

    created_at = Column(
        DateTime, default=get_current_time, nullable=False, index=True,
        comment="操作时间（带时区）",
    )

    # —— 操作人 ——
    actor_loginid = Column(String(50), nullable=False, index=True, comment="谁（loginid）")
    actor_name = Column(String(100), nullable=True, comment="姓名（冗余：人员变动后仍可读）")
    actor_role = Column(
        String(20), nullable=True,
        comment="admin / k_user / oa_user",
    )

    # —— 操作 ——
    action = Column(String(50), nullable=False, index=True, comment="事件类型，如 recording.score")
    target_type = Column(
        String(50), nullable=True, index=True,
        comment="对象类型，如 recording / rule / k_user / page",
    )
    target_id = Column(String(100), nullable=True, comment="对象ID（数值或 loginid 或路由路径）")
    target_label = Column(String(255), nullable=True, comment="给人看的对象描述")

    # —— 上下文 ——
    ip = Column(String(64), nullable=True, comment="客户端 IP")
    user_agent = Column(String(255), nullable=True)

    # —— 结果 ——
    result = Column(String(20), default="success", nullable=False, comment="success / fail")
    detail = Column(JSON, nullable=True, comment="业务上下文（不含原文、不含敏感字段原值）")