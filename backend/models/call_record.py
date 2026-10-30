"""
催记管理 - 通话记录数据模型

来源：上游 ICP 接口 ICP1100010。
用途：把上游拉到的数据落到本系统自己的库里，做"历史数据"持久化。
- k 账号只查自己 agent_id 的数据；
- admin 可以查所有；
- oa_user 不允许进入催记管理页面（前端隐藏 + 后端 403 双层防护）。

策略：
- 业务主键 call_id 唯一约束；重复拉取走 UPSERT（以最新一次拉到的字段为准）。
- fetched_at / fetched_by 记录最近一次入库时间和触发人，便于追溯。
"""
from sqlalchemy import (
    Column, BigInteger, String, DateTime, Integer, Text, Index,
)
from backend.core.database import Base
from backend.core.datetime_utils import get_current_time


class CallRecord(Base):
    """通话记录表（来源于上游 ICP）"""
    __tablename__ = "call_records"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="自增ID")

    # —— 业务字段（与上游 ICP ICP1100010 返回一致）——
    call_id = Column(String(64), nullable=False, unique=True, comment="通话ID（业务主键）")
    agent_id = Column(String(50), nullable=False, comment="座席工号")
    agent_name = Column(String(100), nullable=True, comment="座席姓名")
    dn_id = Column(String(50), nullable=True, comment="分机号")
    phone_number = Column(String(50), nullable=True, comment="主叫号码（上游 phone_number，实为分机号）")
    calling_number = Column(String(50), nullable=True, comment="对端客户号码（上游 calling_number，上游已脱敏 135****9752）")
    established_time = Column(DateTime, nullable=True, comment="通话开始时间")
    released_times = Column(DateTime, nullable=True, comment="通话挂断时间")
    handle_times = Column(Integer, nullable=True, comment="通话时长（秒）")
    call_url = Column(Text, nullable=True, comment="通话录音地址（上游 call_url 原样存；不作解密源）")
    call_url_inner = Column(Text, nullable=True, comment="通话录音地址密文（上游 call_url_inner 原值，解密/下载的唯一来源）")
    call_url_decrypted = Column(Text, nullable=True, comment="通话录音地址明文（csp-adapter 解密后，用于 ASR 下载）")
    reserve1 = Column(String(255), nullable=True, comment="备用字段1")
    reserve2 = Column(String(255), nullable=True, comment="备用字段2")
    reserve3 = Column(String(255), nullable=True, comment="备用字段3")
    reserve4 = Column(String(255), nullable=True, comment="备用字段4")
    reserve5 = Column(String(255), nullable=True, comment="备用字段5")

    # —— 入库元信息 ——
    fetched_at = Column(DateTime, default=get_current_time, nullable=False, comment="入库时间")
    fetched_by = Column(String(50), nullable=False, comment="触发刷新的 loginid")

    __table_args__ = (
        Index("idx_call_records_agent_id", "agent_id"),
        Index("idx_call_records_established_time", "established_time"),
        Index("idx_call_records_phone", "phone_number"),
    )
