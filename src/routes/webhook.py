from __future__ import annotations
import logging
from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from src.core.config import get_settings
from src.core.exceptions import (
    AIAuthenticationError, AIRateLimitError, AIServiceError,
    AITimeoutError, PropertyNotFoundError,
)
from src.models.schemas import (
    ActionType, ErrorResponse, InboundMessagePayload, QueryType, WebhookResponse,
)
from src.services.ai_service import generate_reply
from src.services.normaliser import normalise


router = APIRouter(prefix="/webhook", tags=["Webhook"])
logger = logging.getLogger(__name__)


def determine_action(confidence: float, query_type: QueryType) -> ActionType:
    s = get_settings()
    if query_type == QueryType.COMPLAINT:              return ActionType.ESCALATE
    if confidence >= s.confidence_auto_send_threshold: return ActionType.AUTO_SEND
    if confidence >= s.confidence_escalate_threshold:  return ActionType.AGENT_REVIEW
    return ActionType.ESCALATE

# Keep private alias so existing internal callers don't break
_action = determine_action


@router.post("/message", response_model=WebhookResponse, status_code=200,
             summary="Process an inbound guest message")
async def handle_message(payload: InboundMessagePayload, request: Request):
    req_id = None
    try:
        unified = normalise(payload)
        req_id  = str(unified.message_id)[:8]
        logger.info(f"[{req_id}] {unified.source.value} | {unified.guest_name} | {unified.query_type.value}")

        ai     = await generate_reply(unified)
        action = determine_action(ai.confidence_score, unified.query_type)
        logger.info(f"[{req_id}] conf={ai.confidence_score} action={action.value} {ai.latency_ms}ms")

        return WebhookResponse(
            message_id=unified.message_id, query_type=unified.query_type,
            drafted_reply=ai.drafted_reply, confidence_score=ai.confidence_score,
            action=action,
            metadata={
                "model": ai.model_used, "latency_ms": ai.latency_ms,
                "tokens": {"input": ai.input_tokens, "output": ai.output_tokens},
                "confidence_breakdown": ai.confidence_breakdown.model_dump(),
                "property_id": unified.property_id, "channel": unified.source.value,
            },
        )
    except PropertyNotFoundError as e:
        return JSONResponse(status_code=404, content={"error": "property_not_found", "detail": str(e)})
    except AIAuthenticationError:
        return JSONResponse(status_code=503, content={"error": "ai_auth_error", "detail": "API key invalid."})
    except AIRateLimitError:
        return JSONResponse(status_code=429, content={"error": "rate_limit", "detail": "Retry after 60s."})
    except AITimeoutError:
        return JSONResponse(status_code=504, content={"error": "ai_timeout", "detail": "AI timed out."})
    except AIServiceError as e:
        return JSONResponse(status_code=503, content={"error": "ai_unavailable", "detail": str(e)})
    except Exception as e:
        logger.exception(f"[{req_id}] {e}")
        return JSONResponse(status_code=500, content={"error": "internal_error", "detail": "Unexpected error."})