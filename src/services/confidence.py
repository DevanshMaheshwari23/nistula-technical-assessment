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

# Context keywords — property-relevant terms that indicate an answerable query
_CTX_KW = [re.compile(p, re.I) for p in [
    r"\bavailab\w*",
    r"\brate[s]?",
    r"\bpric\w*",
    r"\bcost",
    r"\bcheck.?in",
    r"\bcheck.?out",
    r"\bwifi",
    r"\bpassword",
    r"\bguest[s]?",
    r"\badult[s]?",
    r"\bnight[s]?",
    r"\bcancell?\w*",
    r"\bchef",
    r"\btransfer",
    r"\bairport",
    r"\bpool",
    r"\bcaretaker",
    r"\b\d{1,2}\s*(apr|may|jun|jul|aug|sep|oct|nov|dec|jan|feb|mar)\b",
    r"\bfor\s+\d+\s*(adult|guest|person|people)\b",
]]

# Emotional charge words — lower clarity, signal escalation risk
_CHARGE = [re.compile(p, re.I) for p in [
    r"\bunacceptable",
    r"\bterrible",
    r"\bhorrible",
    r"\bfurious",
    r"\bangry",
    r"\bdemand",
    r"\burgent",
    r"\basap",
]]

# Keywords we can answer directly from static property context (zero ambiguity)
_DIRECT_ANSWER_KW = [re.compile(p, re.I) for p in [
    r"\bwifi\b",
    r"\bpassword\b",
    r"\bcheck.?in\b",
    r"\bcheck.?out\b",
    r"\bpool\b",
    r"\bcaretaker\b",
    r"\bchef\b",
]]


def _build_breakdown(msg: UnifiedMessage) -> ConfidenceBreakdown:
    """Compute all four signals and return the full breakdown. Internal use only."""

    # Signal 1 — Query type answerability (35%)
    qt = _QT_SCORES[msg.query_type]

    # Signal 2 — Context keyword coverage (30%)
    # Normalised over 3: hitting 3+ relevant keywords scores 1.0
    ctx = min(1.0, sum(1 for p in _CTX_KW if p.search(msg.message_text)) / 3.0)

    # Signal 3 — Message clarity (20%)
    words = msg.message_text.split()
    wc    = len(words)
    clr   = 0.50
    if 8 <= wc <= 120:
        clr += 0.20    # well-formed message length
    elif wc < 8:
        clr -= 0.15    # too short, likely incomplete context
    if "?" in msg.message_text and wc >= 3: 
        clr += 0.15    # explicit question
    if re.search(r"\b\d\b", msg.message_text):
        clr += 0.10    # contains a number (dates, guest counts)
    clr -= sum(1 for p in _CHARGE if p.search(msg.message_text)) * 0.08
    clr   = max(0.0, min(1.0, clr))

    # Signal 4 — Channel reliability (15%)
    ch = min(1.0, _CH_SCORES[msg.source] + (BOOKING_REF_BONUS if msg.booking_ref else 0.0))

    # Weighted sum
    w = qt * 0.35 + ctx * 0.30 + clr * 0.20 + ch * 0.15

    # Direct-answer floor: POST_SALES_CHECKIN messages containing a property fact
    # we can answer exactly (WiFi password, check-in time, pool) get a minimum
    # score of 0.88 — these are zero-ambiguity lookups, confidence should reflect that.
    if (
        msg.query_type == QueryType.POST_SALES_CHECKIN
        and any(p.search(msg.message_text) for p in _DIRECT_ANSWER_KW)
    ):
        w = max(w, 0.88)

    # Complaint cap — always escalate regardless of computed score
    capped = msg.query_type == QueryType.COMPLAINT
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


def compute_confidence(msg: UnifiedMessage) -> float:
    """Return the final confidence score as a plain float. Used by tests and action router."""
    return _build_breakdown(msg).final_score


def compute_confidence_breakdown(msg: UnifiedMessage) -> ConfidenceBreakdown:
    """Return the full breakdown object. Used by ai_service to attach to AIResponse."""
    return _build_breakdown(msg)