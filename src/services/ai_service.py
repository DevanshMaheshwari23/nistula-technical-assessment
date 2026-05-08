"""
AI Service — Claude API integration.
Client created once via lru_cache — reused across all requests.
"""
from __future__ import annotations
import logging
from functools import lru_cache
import anthropic
from src.config import get_settings
from src.models.schemas import UnifiedMessage, QueryType, AIResponse
from src.services.property_context import format_for_prompt
from src.services.confidence import compute_confidence

logger = logging.getLogger(__name__)

BASE_SYSTEM = """\
You are a warm, professional guest relations specialist for Nistula Villas,
a boutique luxury villa collection in Assagao, North Goa.

YOUR TONE:
- Warm, personal, genuinely helpful — never robotic
- Confident and factual — use exact figures from PROPERTY CONTEXT
- 3 to 6 sentences maximum — guests message on WhatsApp, not email
- Address the guest by first name
- Never use corporate phrases like "we apologise for any inconvenience"

HARD RULES:
- Only state facts present in PROPERTY CONTEXT below
- If unsure: say "I will confirm and come back to you shortly"
- Never promise a refund without management approval
- Never share caretaker personal phone numbers

{property_context}

QUERY TYPE: {query_type}
"""

_OVERLAYS = {
    QueryType.PRE_SALES_AVAILABILITY: """
TASK: Confirm availability. Give the nightly rate. Mention cancellation policy.
End with: "Shall I hold these dates for you?"
""",
    QueryType.PRE_SALES_PRICING: """
TASK: Give exact price breakdown (base rate + extra guest charges x nights).
Show the calculation. Mention what is included (pool, caretaker, WiFi).
End with: "Would you like to check availability for these dates?"
""",
    QueryType.POST_SALES_CHECKIN: """
TASK: Answer the logistics question directly.
For WiFi — give the exact password. For check-in — be precise.
Mention caretaker is available 8am-10pm as reassurance.
""",
    QueryType.SPECIAL_REQUEST: """
TASK: Acknowledge the request warmly. Give clear yes/no with conditions.
For chef: pre-booking required. For early check-in: depends on occupancy.
""",
    QueryType.COMPLAINT: """
TASK — CRITICAL: Guest is upset. Empathy first, solutions second.
1. Acknowledge the problem genuinely — do NOT minimise
2. Commit to immediate action (caretaker alerted / team notified)
3. Say manager will follow up — do NOT promise a specific refund
4. Ask: "Is there anything I can do for you right now?"
""",
    QueryType.GENERAL_ENQUIRY: """
TASK: Answer clearly. Add one useful piece of extra info. Invite further questions.
""",
}

_USER_TEMPLATE = """\
Guest: {guest_name}
Channel: {source}
Booking Reference: {booking_ref}
Message: "{message_text}"

Please draft a reply to this guest.
"""


@lru_cache(maxsize=1)
def _get_client() -> anthropic.AsyncAnthropic:
    return anthropic.AsyncAnthropic(api_key=get_settings().anthropic_api_key)


async def generate_reply(msg: UnifiedMessage) -> AIResponse:
    settings = get_settings()
    system = (
        BASE_SYSTEM.format(
            property_context=format_for_prompt(msg.property_id),
            query_type=msg.query_type.value,
        )
        + _OVERLAYS.get(msg.query_type, "")
    )
    user = _USER_TEMPLATE.format(
        guest_name=msg.guest_name,
        source=msg.source.value,
        booking_ref=msg.booking_ref or "Not provided",
        message_text=msg.message_text,
    )

    logger.info("Claude API call — message_id=%s query_type=%s",
                msg.message_id, msg.query_type.value)

    try:
        response = await _get_client().messages.create(
            model=settings.claude_model,
            max_tokens=600,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
    except anthropic.AuthenticationError:
        logger.error("Authentication failed — check ANTHROPIC_API_KEY in .env")
        raise
    except anthropic.RateLimitError:
        logger.error("Rate limit hit — message_id=%s", msg.message_id)
        raise
    except anthropic.APIError as e:
        logger.error("Claude API error — %s", str(e))
        raise

    reply = response.content[0].text.strip()
    confidence = compute_confidence(msg)

    logger.info("Reply generated — message_id=%s confidence=%.2f",
                msg.message_id, confidence.final_score)

    return AIResponse(
        drafted_reply=reply,
        confidence_score=confidence.final_score,
        confidence_breakdown=confidence,
        model_used=settings.claude_model,
    )