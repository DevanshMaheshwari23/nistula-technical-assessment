"""
Confidence Scoring Engine — 4-signal weighted sum.

Signal              Weight  What it measures
query_type          0.35    How answerable from static context?
context_coverage    0.30    Does our data directly answer this?
message_clarity     0.20    Is the question clear and specific?
channel_reliability 0.15    How much metadata does this channel provide?

Hard rule: COMPLAINT always capped at 0.50 → always ESCALATE.
"""
from __future__ import annotations
import re
from src.models.schemas import UnifiedMessage, QueryType, SourceChannel, ConfidenceBreakdown

_QT_SCORES = {
    QueryType.POST_SALES_CHECKIN:     0.95,
    QueryType.PRE_SALES_PRICING:      0.92,
    QueryType.PRE_SALES_AVAILABILITY: 0.90,
    QueryType.GENERAL_ENQUIRY:        0.78,
    QueryType.SPECIAL_REQUEST:        0.68,
    QueryType.COMPLAINT:              0.40,
}

_CH_SCORES = {
    SourceChannel.DIRECT:      0.95,
    SourceChannel.BOOKING_COM: 0.90,
    SourceChannel.AIRBNB:      0.85,
    SourceChannel.WHATSAPP:    0.80,
    SourceChannel.INSTAGRAM:   0.65,
}

_CTX_INDICATORS = {
    QueryType.PRE_SALES_AVAILABILITY: [
        r"\bapr(il)?\b", r"\b2[0-4]\b", r"\bavailab\w+\b"],
    QueryType.PRE_SALES_PRICING: [
        r"\b\d+\s+adults?\b", r"\b\d+\s+guests?\b", r"\b\d+\s+nights?\b", r"\brate\b"],
    QueryType.POST_SALES_CHECKIN: [
        r"\bwi-?fi\b", r"\bpassword\b", r"\bcheck.?in\b", r"\bcaretaker\b"],
    QueryType.SPECIAL_REQUEST: [
        r"\bchef\b", r"\bearly\b", r"\blate\b", r"\btransfer\b"],
    QueryType.GENERAL_ENQUIRY: [
        r"\bpet\b", r"\bparking\b", r"\bpool\b", r"\bsmoking\b"],
    QueryType.COMPLAINT: [],
}


def _query_type_signal(msg: UnifiedMessage) -> float:
    return _QT_SCORES.get(msg.query_type, 0.70)


def _context_coverage_signal(msg: UnifiedMessage) -> float:
    indicators = _CTX_INDICATORS.get(msg.query_type, [])
    if not indicators:
        return 0.35
    t = msg.message_text.lower()
    matched = sum(1 for p in indicators if re.search(p, t))
    return round(max(0.50, 0.50 + (matched / len(indicators)) * 0.50), 3)


def _message_clarity_signal(msg: UnifiedMessage) -> float:
    text = msg.message_text
    wc = len(text.split())
    if wc < 4:       length = 0.45
    elif wc <= 80:   length = 1.00
    else:            length = max(0.55, 1.0 - (wc - 80) * 0.005)

    q_bonus = 0.05 if "?" in text else 0.0
    emotional = ["angry","furious","terrible","horrible","worst",
                 "disgusting","unacceptable","lawsuit","refund","compensation"]
    penalty = min(0.25, sum(1 for w in emotional if w in text.lower()) * 0.08)
    return round(max(0.20, min(1.0, length * 0.90 + q_bonus - penalty)), 3)


def _channel_reliability_signal(msg: UnifiedMessage) -> float:
    base = _CH_SCORES.get(msg.source, 0.75)
    if msg.booking_ref:
        base = min(1.0, base + 0.05)
    return round(base, 3)


def compute_confidence(msg: UnifiedMessage) -> ConfidenceBreakdown:
    qt  = _query_type_signal(msg)
    ctx = _context_coverage_signal(msg)
    clr = _message_clarity_signal(msg)
    chn = _channel_reliability_signal(msg)

    score = 0.35*qt + 0.30*ctx + 0.20*clr + 0.15*chn
    capped = msg.query_type == QueryType.COMPLAINT
    if capped:
        score = min(score, 0.50)

    return ConfidenceBreakdown(
        query_type_signal=qt,
        context_coverage_signal=ctx,
        message_clarity_signal=clr,
        channel_reliability_signal=chn,
        complaint_cap_applied=capped,
        final_score=round(score, 2),
    )