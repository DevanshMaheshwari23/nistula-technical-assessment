"""
POST /webhook/message — full message processing pipeline.
"""
from __future__ import annotations
import logging
import uuid
import anthropic
from fastapi import APIRouter, HTTPException, status
from src.models.schemas import (
    ActionType, ErrorDetail, InboundMessagePayload,
    QueryType, WebhookResponse,
)
from src.services.ai_service import generate_reply
from src.services.normaliser import normalise
from src.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhook", tags=["Webhook"])


def _determine_action(confidence: float, query_type: QueryType) -> ActionType:
    s = get_settings()
    if query_type == QueryType.COMPLAINT:
        return ActionType.ESCALATE
    if confidence >= s.confidence_auto_send_threshold:
        return ActionType.AUTO_SEND
    if confidence >= s.confidence_escalate_threshold:
        return ActionType.AGENT_REVIEW
    return ActionType.ESCALATE


@router.post(
    "/message",
    response_model=WebhookResponse,
    status_code=200,
    summary="Receive inbound guest message",
)
async def handle_message(payload: InboundMessagePayload) -> WebhookResponse:
    tag = str(uuid.uuid4())[:8]
    logger.info("[%s] Inbound — source=%s guest=%r", tag, payload.source.value, payload.guest_name)

    # Step 1: Normalise
    try:
        msg = normalise(payload)
        logger.info("[%s] Classified as %s — message_id=%s", tag, msg.query_type.value, msg.message_id)
    except Exception as exc:
        logger.exception("[%s] Normalisation error: %s", tag, exc)
        raise HTTPException(status_code=500,
            detail=ErrorDetail(error="normalisation_failed", detail=str(exc)).model_dump())

    # Step 2: AI reply
    try:
        ai = await generate_reply(msg)
    except (anthropic.RateLimitError, anthropic.APIError) as exc:
        raise HTTPException(status_code=503,
            detail=ErrorDetail(
                error="ai_service_unavailable",
                detail="Claude API temporarily unavailable. Please retry.",
                message_id=msg.message_id,
            ).model_dump())
    except Exception as exc:
        logger.exception("[%s] AI service error: %s", tag, exc)
        raise HTTPException(status_code=500,
            detail=ErrorDetail(error="ai_error", detail=str(exc),
                               message_id=msg.message_id).model_dump())

    # Step 3: Route
    action = _determine_action(ai.confidence_score, msg.query_type)
    logger.info("[%s] Done — confidence=%.2f action=%s", tag, ai.confidence_score, action.value)

    return WebhookResponse(
        message_id=msg.message_id,
        query_type=msg.query_type,
        drafted_reply=ai.drafted_reply,
        confidence_score=ai.confidence_score,
        action=action,
    )