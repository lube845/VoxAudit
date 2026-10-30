"""
催记管理 - 单条通话的处理结果

与 call_records 1:1：通过 call_id 关联。
- call_records：来源数据（ICP 拉到的字段）
- call_notes：   处理结果（转写 / 原始催记 / 校对催记 / 各步状态）

字段级状态：ASR / 结构化催记 / 非结构化催记 三步独立；
任一步失败时只标自己的 *_status='failed' + 写 *_error，不影响其他字段。
"""
from sqlalchemy import (
    Column, BigInteger, String, DateTime, Text, Index,
)
from sqlalchemy.dialects.mysql import JSON

from backend.core.database import Base
from backend.core.datetime_utils import get_current_time


class CallNote(Base):
    """催记处理结果表（1:1 对应 call_records）"""
    __tablename__ = "call_notes"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="自增ID")
    call_id = Column(String(64), nullable=False, unique=True, comment="业务主键（对应 call_records.call_id）")

    # —— AI 处理结果 ——
    transcript = Column(Text, nullable=True, comment="录音转写原文")
    transcript_segments = Column(JSON, nullable=True, comment="转写片段（带时间戳、说话人）")
    structured_note = Column(Text, nullable=True, comment="原始结构化催记（AI 生成）")
    unstructured_note = Column(Text, nullable=True, comment="原始非结构化催记（AI 生成）")

    # —— 人工编辑 ——
    edited_structured_note = Column(Text, nullable=True, comment="校对结构化催记")
    edited_unstructured_note = Column(Text, nullable=True, comment="校对非结构化催记")

    # —— 字段级状态（每步独立：pending/processing/done/failed） ——
    asr_status = Column(String(20), nullable=False, default="pending", comment="ASR 转写状态")
    structured_status = Column(String(20), nullable=False, default="pending", comment="结构化催记状态")
    unstructured_status = Column(String(20), nullable=False, default="pending", comment="非结构化催记状态")

    asr_error = Column(Text, nullable=True, comment="ASR 失败原因")
    structured_error = Column(Text, nullable=True, comment="结构化催记失败原因")
    unstructured_error = Column(Text, nullable=True, comment="非结构化催记失败原因")

    # —— 元信息 ——
    last_processed_at = Column(DateTime, nullable=True, comment="任一步最近一次完成时间，用于启动恢复判定")
    created_at = Column(DateTime, default=get_current_time, nullable=False, comment="创建时间")
    updated_at = Column(DateTime, default=get_current_time, onupdate=get_current_time, comment="更新时间")

    __table_args__ = (
        Index("idx_call_notes_asr_status", "asr_status"),
        Index("idx_call_notes_structured_status", "structured_status"),
        Index("idx_call_notes_unstructured_status", "unstructured_status"),
        Index("idx_call_notes_call_id", "call_id"),
    )
