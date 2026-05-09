from __future__ import annotations
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Optional
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
    AUTO_SEND    = "auto_send"
    AGENT_REVIEW = "agent_review"
    ESCALATE     = "escalate"


class InboundMessagePayload(BaseModel):
    source:      SourceChannel
    guest_name:  str  = Field(..., min_length=1, max_length=200)
    message:     str  = Field(..., min_length=1, max_length=5000)
    timestamp:   datetime
    booking_ref: Optional[str] = Field(default=None, max_length=50)
    property_id: str  = Field(..., min_length=1, max_length=50)

    @field_validator("message")
    @classmethod
    def not_whitespace(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("message must contain non-whitespace text")
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "source": "whatsapp",
                "guest_name": "Rahul Sharma",
                "message": "Is the villa available from April 20 to 24? What is the rate for 2 adults?",
                "timestamp": "2026-05-05T10:30:00Z",
                "booking_ref": "NIS-2024-0891",
                "property_id": "villa-b1",
            }
        }
    }


class UnifiedMessage(BaseModel):
    message_id:   uuid.UUID
    source:       SourceChannel
    guest_name:   str
    message_text: str
    timestamp:    datetime
    booking_ref:  Optional[str]
    property_id:  str
    query_type:   QueryType
    raw_payload:  dict[str, Any]


class ConfidenceBreakdown(BaseModel):
    query_type_signal:    float = Field(..., ge=0.0, le=1.0)
    context_coverage:     float = Field(..., ge=0.0, le=1.0)
    message_clarity:      float = Field(..., ge=0.0, le=1.0)
    channel_reliability:  float = Field(..., ge=0.0, le=1.0)
    complaint_cap_applied: bool = False
    final_score:          float = Field(..., ge=0.0, le=1.0)


class AIResponse(BaseModel):
    drafted_reply:        str
    confidence_score:     float = Field(..., ge=0.0, le=1.0)
    confidence_breakdown: ConfidenceBreakdown
    model_used:           str
    input_tokens:         int
    output_tokens:        int
    latency_ms:           int


class WebhookResponse(BaseModel):
    message_id:       uuid.UUID
    query_type:       QueryType
    drafted_reply:    str
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    action:           ActionType
    metadata:         dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error:  str
    detail: str