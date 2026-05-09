from __future__ import annotations
import logging
import time

import anthropic

from src.core.config import get_settings
from src.core.exceptions import (
    AIAuthenticationError, AIRateLimitError, AIServiceError, AITimeoutError,
)
from src.core.property_registry import PropertyContext, get_property
from src.models.schemas import AIResponse, UnifiedMessage
from src.services.confidence import compute_confidence_breakdown
from src.services.prompt_builder import build_prompt

logger = logging.getLogger(__name__)

# Module-level client — instantiated once, reused across requests.
# NOT cached with lru_cache: AsyncAnthropic holds an httpx.AsyncClient
# that is bound to the event loop created at startup. lru_cache would
# return the same instance after an event-loop restart (e.g. in tests),
# causing "Event loop is closed" errors.
_client: anthropic.AsyncAnthropic | None = None


def _get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        s = get_settings()
        _client = anthropic.AsyncAnthropic(
            api_key     = s.anthropic_api_key,
            timeout     = float(s.claude_timeout_s),
            max_retries = s.claude_max_retries,
        )
    return _client


async def generate_reply(msg: UnifiedMessage) -> AIResponse:
    settings = get_settings()

    # Resolve property — raises PropertyNotFoundError (→ HTTP 404) if unknown
    prop: PropertyContext = get_property(msg.property_id)

    # Build prompt — build_prompt receives (UnifiedMessage, PropertyContext)
    # It calls format_for_prompt(prop) internally; no string IDs pass through.
    system, user = build_prompt(msg, prop)

    # Confidence is computed from the message alone — zero Claude dependency
    breakdown = compute_confidence_breakdown(msg)

    t0 = int(time.monotonic() * 1000)
    try:
        response = await _get_client().messages.create(
            model      = settings.claude_model,
            max_tokens = settings.claude_max_tokens,
            system     = system,
            messages   = [{"role": "user", "content": user}],
        )
    except anthropic.AuthenticationError as e:
        raise AIAuthenticationError(str(e)) from e
    except anthropic.RateLimitError as e:
        raise AIRateLimitError(str(e)) from e
    except anthropic.APITimeoutError as e:
        raise AITimeoutError(str(e)) from e
    except anthropic.APIStatusError as e:
        raise AIServiceError(f"{e.status_code}: {e.message}") from e
    except anthropic.APIError as e:
        raise AIServiceError(str(e)) from e

    latency = int(time.monotonic() * 1000) - t0
    logger.info(
        "Claude replied in %dms | in=%d out=%d | qt=%s conf=%.3f",
        latency,
        response.usage.input_tokens,
        response.usage.output_tokens,
        msg.query_type.value,
        breakdown.final_score,
    )

    return AIResponse(
        drafted_reply        = response.content[0].text.strip(),
        confidence_score     = breakdown.final_score,
        confidence_breakdown = breakdown,
        model_used           = settings.claude_model,
        input_tokens         = response.usage.input_tokens,
        output_tokens        = response.usage.output_tokens,
        latency_ms           = latency,
    )