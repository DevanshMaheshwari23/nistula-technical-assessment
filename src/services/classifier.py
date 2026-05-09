from __future__ import annotations
import re
from src.models.schemas import QueryType


COMPLAINT_SIGNALS: list[tuple[str, int]] = [
    (r"\bnot\s+working\b",          3),
    (r"\bbroken\b",                 3),
    (r"\bno\s+(hot\s+)?water\b",    3),
    (r"\bac\s+(is\s+)?not\b",       3),
    (r"\bunacceptable\b",           3),
    (r"\bwant\s+a?\s*refund\b",     3),
    (r"\bI\s+am\s+not\s+happy\b",   3),
    (r"\bnot\s+as\s+described\b",   3),
    (r"\bfraud\b",                  3),
    (r"\bscam\b",                   3),
    (r"\bcockroach\b",              3),
    (r"\bno\s+electricity\b",       3),
    (r"\bwifi\s+not\s+working\b",   3),
    (r"\bpool\s+(is\s+)?dirty\b",   3),
    (r"\broom\s+(is\s+)?dirty\b",   3),
    (r"\bterrible\b",               2),
    (r"\bhorrible\b",               2),
    (r"\bnot\s+happy\b",            2),
    (r"\bunhappy\b",                2),
    (r"\bdisgusting\b",             2),
    (r"\bdirty\b",                  2),
    (r"\bvery\s+disappointed\b",    2),
    (r"\bnot\s+what\s+we\s+expected\b",  2),
(r"\bnot\s+(?:very\s+)?happy\b",      2),
]
COMPLAINT_THRESHOLD = 2

# Tiebreaker only fires when competing scores are within this gap.
_TIEBREAK_GAP = 2

_VOCAB: dict[QueryType, list[tuple[str, int]]] = {

    QueryType.PRE_SALES_AVAILABILITY: [
        (r"\bavailab\w*\s+(from|on|for|between|in\s+\w+\s*\d)", 4),
        (r"\b(is|are)\s+(the\s+)?(villa|property|dates?)\s+\w*\s*availab", 4),
        (r"\bavailab\w*\b",                                       1),
        (r"\bvacant\b",                                           4),
        (r"\bfree\s+(on|from)\b",                                 3),
        (r"\bcan\s+we\s+book\b",                                  3),
        (r"\blong\s+weekend\b",                                   3),
        (r"\bfrom\s+\d",                                          2),
        (r"\bto\s+\d",                                            2),
        (r"\b(apr|may|jun|jul|aug|sep|oct|nov|dec|jan|feb|mar)\w*\b", 1),
        (r"\bdates?\b",                                           1),
        (r"\bslots?\b",                                           3),
    ],

    QueryType.PRE_SALES_PRICING: [
        (r"\brates?\b",                                           4),
        (r"\bpric\w*\b",                                          4),
        (r"\bcost\b",                                             4),
        (r"\bhow\s+much\b",                                       4),
        (r"\btariff\b",                                           4),
        (r"\bper\s+night\b",                                      3),
        (r"\bquote\b",                                            2),
        (r"\bcharges?\b",                                         2),
        (r"\bfor\s+\d+\s+(adult|guest|person|people|night)\b",    3),
    ],

    QueryType.POST_SALES_CHECKIN: [
        (r"\bcheck.?in\s*(time|at|from|procedure)?\b",            2),
        (r"\bwifi\b",                                             3),
        (r"\bwi.?fi\b",                                           3),
        (r"\bpassword\b",                                         3),
        (r"\bkeys?\b",                                            2),
        (r"\baccess\b",                                           1),
        (r"\bdirections?\b",                                      1),
        (r"\bgate\b",                                             1),
        (r"\bwhat\s+time\b",                                      1),
    ],

    QueryType.SPECIAL_REQUEST: [
        (r"\bearly\s+check.?in\b",                                6),
        (r"\blate\s+check.?out\b",                                6),
        (r"\bairport\s+transfer\b",                               4),
        (r"\bpick.?up\b",                                         2),
        (r"\bchef\b",                                             3),
        (r"\bcook\b",                                             2),
        (r"\bbirthday\b",                                         3),
        (r"\banniversary\b",                                      3),
        (r"\bsurprise\b",                                         2),
        (r"\bcan\s+you\s+arrange\b",                              3),
        (r"\bextra\s+bed\b",                                      2),
        (r"\bbaby\b",                                             2),
        (r"\bhoneymoon\b",                                        3),
    ],

    QueryType.GENERAL_ENQUIRY: [
        (r"\bpets?\b",                                            3),
        (r"\bdogs?\b",                                            3),
        (r"\bsmok\w*\b",                                          3),
        (r"\bdo\s+you\s+(allow|have|provide|offer)\b",            2),
        (r"\bis\s+there\b",                                       1),
        (r"\bparking\b",                                          4),
        (r"\bpool\b",                                             1),
        (r"\bbeach\b",                                            1),
        (r"\brestaurant\b",                                       1),
    ],
}

# Pre-compile all patterns once at import time
_CC = [(re.compile(p, re.I), s) for p, s in COMPLAINT_SIGNALS]
_CV = {qt: [(re.compile(p, re.I), s) for p, s in pats] for qt, pats in _VOCAB.items()}

_PRIORITY: list[tuple[QueryType, QueryType]] = [
    (QueryType.SPECIAL_REQUEST,        QueryType.POST_SALES_CHECKIN),
    (QueryType.PRE_SALES_AVAILABILITY, QueryType.PRE_SALES_PRICING),
    (QueryType.PRE_SALES_PRICING,      QueryType.GENERAL_ENQUIRY),
    (QueryType.PRE_SALES_AVAILABILITY, QueryType.GENERAL_ENQUIRY),
]


def classify(message: str) -> QueryType:
    """
    1. Complaint gate — score >= COMPLAINT_THRESHOLD → COMPLAINT (hard override)
    2. Score all types via weighted keyword matching
    3. Tiebreaker ONLY when gap between competing scores <= _TIEBREAK_GAP
       Wide gaps resolve by raw score — no artificial promotion
    4. Fallback → GENERAL_ENQUIRY
    """
    text = message.strip()
    if not text:
        return QueryType.GENERAL_ENQUIRY

    # Phase 1 — Complaint gate
    complaint_score = sum(s for pat, s in _CC if pat.search(text))
    if complaint_score >= COMPLAINT_THRESHOLD:
        return QueryType.COMPLAINT

    # Phase 2 — Score every type
    scores: dict[QueryType, int] = {
        qt: sum(s for pat, s in pats if pat.search(text))
        for qt, pats in _CV.items()
    }

    if max(scores.values()) == 0:
        return QueryType.GENERAL_ENQUIRY

    best = max(scores, key=lambda qt: scores[qt])

    # Phase 3 — Tiebreaker (only when scores are close)
    for winner, loser in _PRIORITY:
        if (
            scores[winner] > 0
            and scores[loser] > 0
            and best == loser
            and (scores[loser] - scores[winner]) <= _TIEBREAK_GAP
        ):
            return winner

    return best