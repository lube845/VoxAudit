"""
规则相关Schema
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ScoringRuleBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    code: str = Field(..., min_length=1, max_length=50)
    version: str = Field(..., min_length=1, max_length=20)
    description: Optional[str] = Field(None, max_length=500)
    total_score: float = 100.0
    rule_type: str = "bonus"
    is_veto: bool = False
    is_enabled: bool = True


class ScoringRuleCreate(ScoringRuleBase):
    version: Optional[str] = None


class ScoringRuleUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    total_score: Optional[float] = Field(None, gt=0)
    is_veto: Optional[bool] = None
    is_enabled: Optional[bool] = None


class ScoringRuleResponse(ScoringRuleBase):
    id: int
    is_latest: bool
    parent_id: Optional[int]
    created_at: datetime
    updated_at: datetime
    published_at: Optional[datetime]

    class Config:
        from_attributes = True