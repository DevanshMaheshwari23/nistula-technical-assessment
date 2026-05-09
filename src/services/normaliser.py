from __future__ import annotations
import html, re, uuid
from datetime import timezone
from src.core.property_registry import get_property
from src.models.schemas import InboundMessagePayload, SourceChannel, UnifiedMessage
from src.services.classifier import classify                    # ← ADD THIS
classify_query_type = classify      

def _clean_whatsapp(t: str) -> str:
    t = re.sub(r"```.*?```", " ", t, flags=re.DOTALL)
    return re.sub(r"[*_~]{1,3}(.*?)[*_~]{1,3}", r"\1", t)


def _clean_airbnb(t: str) -> str:
    t = html.unescape(t)
    # Strip HTML tags
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"---+\s*Airbnb.*$", "", t, flags=re.I | re.DOTALL)
    return re.sub(r"Reply above this line.*$", "", t, flags=re.I | re.DOTALL)


def _clean_booking_com(t: str) -> str:
    # Strip [Automated message from Booking.com] prefix
    t = re.sub(r"^\[.*?Booking\.com.*?\]\s*", "", t, flags=re.I)
    t = re.sub(r"\[(?:Auto-)?[Tt]ranslated.*?\]\s*", "", t)
    t = re.sub(r"^(?:Guest\s+)?[Mm]essage\s*:\s*", "", t)
    # Strip "Guest asks:" prefix
    t = re.sub(r"^Guest\s+asks?:\s*", "", t, flags=re.I)
    return t


def _clean_instagram(t: str) -> str:
    t = re.sub(r"https?://\S+", "", t)
    return re.sub(r"@\w+", "", t)


_CLEANERS = {
    SourceChannel.WHATSAPP:    _clean_whatsapp,
    SourceChannel.AIRBNB:      _clean_airbnb,
    SourceChannel.BOOKING_COM: _clean_booking_com,
    SourceChannel.INSTAGRAM:   _clean_instagram,
    SourceChannel.DIRECT:      lambda t: t,
}


def normalise(payload: InboundMessagePayload) -> UnifiedMessage:
    prop_id = payload.property_id.strip().lower()
    get_property(prop_id)   # raises PropertyNotFoundError if unknown

    cleaned = _CLEANERS.get(payload.source, lambda t: t)(payload.message)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned).strip()

    ts = payload.timestamp
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)

    # ← These two lines MUST be outside and BEFORE the return
    raw = payload.guest_name.strip()
    guest_name = raw.title() if raw == raw.lower() else raw

    return UnifiedMessage(
        message_id = str(uuid.uuid4()),
        source       = payload.source,
        guest_name   = guest_name,          # ← use the variable, not inline logic
        message_text = cleaned,
        timestamp    = ts,
        booking_ref  = payload.booking_ref,
        property_id  = prop_id,
        query_type   = classify(cleaned),
        raw_payload  = payload.model_dump(mode="json"),
    )

__all__ = ["normalise", "classify_query_type"]