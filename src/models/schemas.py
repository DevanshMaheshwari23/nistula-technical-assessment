"""
All Pydantic v2 schemas — single source of truth for data contracts.
Validate at the boundary, trust internally.
"""
from __future__ import annotations
import uuid
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class SourceChannel(str, Enum):
    WHATSAPP    = "whatsapp"
    BOOKING_COM = "booking_com"
    AIRBNB      = "airbnb"
    INSTAGRAM   = "instagram"
    DIRECT      = "direct"


class QueryType(str, Enum):
    PRE_SALES_AVAILABILITY = "pre_sales_availability"
    PRE_SALES_PRICING      = "pre_sales_pricing"
    POST_SALES_CHECKIN     = "post_sales_checkin"
    SPECIAL_REQUEST        = "special_request"
    COMPLAINT              = "complaint"
    GENERAL_ENQUIRY        = "general_enquiry"


class ActionType(str, Enum):
    AUTO_SEND    = "auto_send"     # confidence >= 0.85
    AGENT_REVIEW = "agent_review"  # 0.60 <= confidence < 0.85
    ESCALATE     = "escalate"      # < 0.60 or complaint


class InboundMessagePayload(BaseModel):
    source:      SourceChannel
    guest_name:  str           = Field(..., min_length=1, max_length=200)
    message:     str           = Field(..., min_length=1, max_length=5000)
    timestamp:   datetime
    booking_ref: Optional[str] = Field(None, max_length=50)
    property_id: Optional[str] = Field(None, max_length=50)

    @field_validator("guest_name", "message", mode="before")
    @classmethod
    def strip_and_reject_blank(cls, v: str) -> str:
        if isinstance(v, str):
            v = v.strip()
        if not v:
            raise ValueError("Field cannot be blank or whitespace-only")
        return v

    model_config = {"str_strip_whitespace": True}


class UnifiedMessage(BaseModel):
    message_id:   str           = Field(default_factory=lambda: str(uuid.uuid4()))
    source:       SourceChannel
    guest_name:   str
    message_text: str
    timestamp:    datetime
    booking_ref:  Optional[str] = None
    property_id:  Optional[str] = None
    query_type:   QueryType


class ConfidenceBreakdown(BaseModel):
    query_type_signal:           float = Field(..., ge=0.0, le=1.0)
    context_coverage_signal:     float = Field(..., ge=0.0, le=1.0)
    message_clarity_signal:      float = Field(..., ge=0.0, le=1.0)
    channel_reliability_signal:  float = Field(..., ge=0.0, le=1.0)
    complaint_cap_applied:       bool  = False
    final_score:                 float = Field(..., ge=0.0, le=1.0)


class AIResponse(BaseModel):
    drafted_reply:        str
    confidence_score:     float              = Field(..., ge=0.0, le=1.0)
    confidence_breakdown: ConfidenceBreakdown
    model_used:           str


class WebhookResponse(BaseModel):
    message_id:       str
    query_type:       QueryType
    drafted_reply:    str
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    action:           ActionType


class ErrorDetail(BaseModel):
    error:      str
    detail:     Optional[str] = None
    message_id: Optional[str] = None