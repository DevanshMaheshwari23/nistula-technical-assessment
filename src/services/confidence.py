from __future__ import annotations
import re
from src.models.schemas import UnifiedMessage, ConfidenceBreakdown, QueryType, SourceChannel


_QT_SCORES = {
    QueryType.POST_SALES_CHECKIN:     0.97,
    QueryType.PRE_SALES_PRICING:      0.90,
    QueryType.PRE_SALES_AVAILABILITY: 0.88,
    QueryType.GENERAL_ENQUIRY:        0.80,
    QueryType.SPECIAL_REQUEST:        0.72,
    QueryType.COMPLAINT:              0.30,
}

_CH_SCORES = {
    SourceChannel.DIRECT:      0.95,
    SourceChannel.BOOKING_COM: 0.88,
    SourceChannel.AIRBNB:      0.85,
    SourceChannel.WHATSAPP:    0.80,
    SourceChannel.INSTAGRAM:   0.65,
}
BOOKING_REF_BONUS = 0.08

_CTX_KW = [re.compile(p, re.I) for p in [
    r"\bavailab\w*", r"\brate[s]?", r"\bpric\w*", r"\bcost",
    r"\bcheck.?in", r"\bcheck.?out", r"\bwifi", r"\bpassword",
    r"\bguest[s]?", r"\badult[s]?", r"\bnight[s]?", r"\bcancell?\w*",
    r"\bchef", r"\btransfer", r"\bairport", r"\bpool", r"\bcaretaker",
    r"\b\d{1,2}\s*(apr|may|jun|jul|aug|sep|oct|nov|dec|jan|feb|mar)\b",
    r"\bfor\s+\d+\s*(adult|guest|person|people)\b",
]]

_CHARGE = [re.compile(p, re.I) for p in [
    r"\bunacceptable", r"\bterrible", r"\bhorrible", r"\bfurious",
    r"\bangry", r"\bdemand", r"\burgent", r"\basap",
]]

_DIRECT_ANSWER_KW = [re.compile(p, re.I) for p in [
    r"\bwifi\b", r"\bpassword\b", r"\bcheck.?in\b", r"\bcheck.?out\b",
    r"\bpool\b", r"\bcaretaker\b", r"\bchef\b",
]]


def _compute_confidence_internal(
    query_type: QueryType,
    source: SourceChannel,
    message: str,
    booking_ref: str | None,
) -> ConfidenceBreakdown:
    qt  = _QT_SCORES[query_type]
    ctx = min(1.0, sum(1 for p in _CTX_KW if p.search(message)) / 3.0)

    words = message.split()
    wc    = len(words)
    clr   = 0.50
    if 8 <= wc <= 120:
        clr += 0.20
    elif wc < 8:
        clr -= 0.15
    if "?" in message and wc >= 3:
        clr += 0.15
    if re.search(r"\b\d+\b", message):
        clr += 0.10
    clr -= sum(1 for p in _CHARGE if p.search(message)) * 0.08
    clr  = max(0.0, min(1.0, clr))

    ch = min(1.0, _CH_SCORES[source] + (BOOKING_REF_BONUS if booking_ref else 0.0))
    w  = qt * 0.35 + ctx * 0.30 + clr * 0.20 + ch * 0.15

    if (
        query_type == QueryType.POST_SALES_CHECKIN
        and any(p.search(message) for p in _DIRECT_ANSWER_KW)
    ):
        w = max(w, 0.88)

    capped = query_type == QueryType.COMPLAINT
    if capped:
        w = min(w, 0.50)

    return ConfidenceBreakdown(
        query_type_signal     = round(qt,  3),
        context_coverage      = round(ctx, 3),
        message_clarity       = round(clr, 3),
        channel_reliability   = round(ch,  3),
        complaint_cap_applied = capped,
        final_score           = round(max(0.0, min(1.0, w)), 3),
    )


def _build_breakdown(msg: UnifiedMessage) -> ConfidenceBreakdown:
    return _compute_confidence_internal(
        msg.query_type, msg.source, msg.message_text, msg.booking_ref
    )


def compute_confidence(
    query_type_or_msg,
    source: SourceChannel | None = None,
    message: str | None = None,
    booking_ref: str | None = None,
) -> ConfidenceBreakdown:
    if source is None:
        msg = query_type_or_msg
        return _compute_confidence_internal(
            msg.query_type, msg.source, msg.message_text, msg.booking_ref
        )
    return _compute_confidence_internal(query_type_or_msg, source, message, booking_ref)


def compute_confidence_breakdown(msg: UnifiedMessage) -> ConfidenceBreakdown:
    return _build_breakdown(msg)