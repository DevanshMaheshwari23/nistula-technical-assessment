"""
Normaliser — InboundMessagePayload → UnifiedMessage.
Pure function: no I/O, no side effects, fully unit-testable.
"""
from __future__ import annotations
import html
import re
from src.models.schemas import InboundMessagePayload, UnifiedMessage, SourceChannel
from src.services.classifier import classify


def _clean_whatsapp(text: str) -> str:
    return re.sub(r"[*_~]", "", text).strip()

def _clean_booking_com(text: str) -> str:
    text = html.unescape(text)
    return re.sub(r"<[^>]+>", "", text).strip()

def _clean_airbnb(text: str) -> str:
    return re.sub(r"^Guest\s+message\s*:\s*", "", text, flags=re.IGNORECASE).strip()

def _clean_instagram(text: str) -> str:
    return re.sub(r"\s{2,}", " ", text).strip()

def _clean_direct(text: str) -> str:
    return text.strip()


_CLEANERS = {
    SourceChannel.WHATSAPP:    _clean_whatsapp,
    SourceChannel.BOOKING_COM: _clean_booking_com,
    SourceChannel.AIRBNB:      _clean_airbnb,
    SourceChannel.INSTAGRAM:   _clean_instagram,
    SourceChannel.DIRECT:      _clean_direct,
}


def normalise(payload: InboundMessagePayload) -> UnifiedMessage:
    """Convert raw payload → UnifiedMessage with cleaned text and query type."""
    cleaner = _CLEANERS.get(payload.source, _clean_direct)
    clean_text = cleaner(payload.message)
    return UnifiedMessage(
        source=payload.source,
        guest_name=payload.guest_name,
        message_text=clean_text,
        timestamp=payload.timestamp,
        booking_ref=payload.booking_ref,
        property_id=payload.property_id,
        query_type=classify(clean_text),
    )