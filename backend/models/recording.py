"""
录音文件相关数据模型
"""
import enum
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Text, Float, ForeignKey, JSON, Enum
)

from backend.core.database import Base
from backend.core.datetime_utils import get_current_time


class RecordingStatus(enum.Enum):
    UPLOADING = "uploading"
    UPLOADED = "uploaded"
    UPLOAD_FAILED = "upload_failed"
    TRANSCRIBING = "transcribing"
    TRANSCRIBED = "transcribed"
    TRANSCRIBE_FAILED = "transcribe_failed"
    SCORING = "scoring"
    SCORED = "scored"
    SCORE_FAILED = "score_failed"


class Recording(Base):
    """录音文件表"""
    __tablename__ = "recordings"

    id = Column(Integer, primary_key=True, index=True)
    file_name = Column(String(255), nullable=False, comment="文件名")
    file_size = Column(Integer, nullable=False, comment="文件大小(字节)")
    file_md5 = Column(String(32), nullable=True, index=True, comment="文件MD5")
    file_type = Column(String(20), nullable=False, comment="文件类型(mp3/wav/amr/zip)")

    # 存储信息
    oss_object_key = Column(String(500), nullable=False, comment="OSS对象键")
    oss_bucket = Column(String(100), nullable=False, comment="OSS Bucket")

    # 业务信息
    agent_id = Column(String(50), nullable=True, comment="坐席工号")
    agent_name = Column(String(100), nullable=True, comment="坐席姓名")
    customer_phone = Column(String(20), nullable=True, comment="客户电话")
    call_id = Column(String(100), nullable=True, comment="通话ID")
    call_time = Column(DateTime, nullable=True, comment="通话时间")

    # 状态
    status = Column(Enum(RecordingStatus), default=RecordingStatus.UPLOADING, comment="状态")
    duration = Column(Float, nullable=True, comment="录音时长(秒)")

    # 用户归属（admin=超级管理员）
    user_id = Column(String(50), nullable=True, index=True, comment="所属用户loginid")

    # 转写结果
    transcript = Column(Text, nullable=True, comment="转写全文")
    transcript_segments = Column(JSON, nullable=True, comment="转写片段(带时间戳)")

    # 评分结果
    total_score = Column(Float, nullable=True, comment="总分")
    bonus_score = Column(Float, default=0, comment="加分总分")
    deduction_score = Column(Float, default=0, comment="扣分总分")
    rule_version = Column(String(20), nullable=True, comment="规则版本")
    remark = Column(Text, nullable=True, comment="备注/错误信息")

    created_at = Column(DateTime, default=get_current_time, comment="创建时间")
    updated_at = Column(DateTime, default=get_current_time, onupdate=get_current_time, comment="更新时间")


class TranscriptSegment(Base):
    """转写片段表（带时间戳的对话）"""
    __tablename__ = "transcript_segments"

    id = Column(Integer, primary_key=True)
    recording_id = Column(Integer, ForeignKey("recordings.id"), nullable=False)
    speaker = Column(String(20), nullable=True, comment="说话人(agent/customer)")
    speaker_name = Column(String(100), nullable=True, comment="说话人名称")
    start_time = Column(Float, nullable=True, comment="开始时间(秒)")
    end_time = Column(Float, nullable=True, comment="结束时间(秒)")
    text = Column(Text, nullable=True, comment="文本内容")
    confidence = Column(Float, nullable=True, comment="置信度")


class ScoringResult(Base):
    """评分结果表"""
    __tablename__ = "scoring_results"

    id = Column(Integer, primary_key=True, index=True)
    recording_id = Column(Integer, ForeignKey("recordings.id"), nullable=False)
    rule_ids = Column(JSON, nullable=True, comment="参与评分的规则ID列表")

    # 评分详情
    total_score = Column(Float, default=0, comment="该规则得分")
    bonus_score = Column(Float, default=0, comment="加分")
    deduction_score = Column(Float, default=0, comment="扣分")
    scoring_details = Column(JSON, nullable=True, comment="评分详情JSON")
    matched_text = Column(Text, nullable=True, comment="匹配的原文")

    # 状态
    is_auto_scored = Column(Boolean, default=True, comment="是否自动评分")
    is_rejected = Column(Boolean, default=False, comment="是否驳回")
    ai_model = Column(String(100), nullable=True, comment="使用的AI模型")
    scored_by = Column(Integer, nullable=True, comment="评分人")
    scored_at = Column(DateTime, nullable=True, comment="评分时间")
    remark = Column(Text, nullable=True, comment="备注")

    # 用户归属（admin=超级管理员）
    user_id = Column(String(50), nullable=True, index=True, comment="所属用户loginid")

    created_at = Column(DateTime, default=get_current_time, comment="创建时间")
