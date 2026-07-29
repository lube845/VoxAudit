"""
录音相关Schema
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class RecordingBase(BaseModel):
    file_name: str
    file_size: int
    file_md5: Optional[str] = None
    file_type: str


class RecordingInitUpload(BaseModel):
    file_name: str
    file_size: int
    file_md5: Optional[str] = None
    file_type: str
    agent_name: Optional[str] = None
    agent_id: Optional[str] = None
    customer_phone: Optional[str] = None
    call_time: Optional[datetime] = None
    # 说话人检测方式
    speaker_detection_method: Optional[str] = "channel"  # "channel" | "llm"
    left_channel_role: Optional[str] = "agent"  # 左声道角色
    right_channel_role: Optional[str] = "customer"  # 右声道角色


class RecordingUploadResponse(BaseModel):
    id: int
    file_name: str
    oss_object_key: str
    status: str


class RecordingResponse(BaseModel):
    id: int
    file_name: str
    file_size: int
    file_type: str
    status: str
    duration: Optional[float] = None
    transcript: Optional[str] = None
    total_score: Optional[float] = None
    bonus_score: float = 0
    deduction_score: float = 0
    agent_id: Optional[str] = None
    agent_name: Optional[str] = None
    customer_phone: Optional[str] = None
    remark: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    is_rejected: bool = False  # 是否被否决（是否命中否决规则）

    class Config:
        from_attributes = True


class TranscriptSegmentResponse(BaseModel):
    id: Optional[int] = None
    speaker: Optional[str] = None
    speaker_name: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    text: Optional[str] = None
    confidence: Optional[float] = None

    class Config:
        from_attributes = True


class ScoringDetailResponse(BaseModel):
    id: Optional[int] = None
    item_name: str
    item_type: str
    status: str
    score: float
    max_score: float
    matched_text: Optional[str] = None
    is_veto: bool = False  # 是否否决项

    class Config:
        from_attributes = True


class ScoringResultResponse(BaseModel):
    id: int
    total_score: float
    bonus_score: float = 0
    deduction_score: float = 0
    passed: bool = False
    is_rejected: bool = False
    is_auto_scored: bool = True
    ai_model: Optional[str] = None
    scored_by: Optional[int] = None
    scored_at: Optional[datetime] = None
    remark: Optional[str] = None
    rule_ids: Optional[List[int]] = None  # 参与评分的规则ID列表
    details: List[ScoringDetailResponse] = []
    created_at: datetime

    class Config:
        from_attributes = True


class RecordingDetailResponse(BaseModel):
    id: int
    file_name: str
    file_size: int
    file_type: str
    status: str
    duration: Optional[float] = None
    transcript: Optional[str] = None
    total_score: Optional[float] = None
    bonus_score: float = 0
    deduction_score: float = 0
    agent_name: Optional[str] = None
    customer_phone: Optional[str] = None
    remark: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    is_rejected: bool = False  # 是否被否决（是否命中否决规则）
    transcript_segments: Optional[List[TranscriptSegmentResponse]] = None
    scoring_results: Optional[List[ScoringResultResponse]] = None

    class Config:
        from_attributes = True


class RecordingScoreResponse(BaseModel):
    recording: RecordingDetailResponse
    scoring_result: Optional[ScoringResultResponse] = None


class RecordingListResponse(BaseModel):
    items: List[RecordingResponse]
    total: int
    page: int
    page_size: int