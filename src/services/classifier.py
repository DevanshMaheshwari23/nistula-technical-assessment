"""
Query Classifier — deterministic keyword matching, zero latency, zero cost.
Priority order: COMPLAINT > CHECKIN > SPECIAL > AVAILABILITY > PRICING > GENERAL
"""
from __future__ import annotations
import re
from src.models.schemas import QueryType

_COMPLAINT = [
    r"\bnot\s+working\b", r"\bbroken\b", r"\bnot\s+happy\b",
    r"\bunacceptable\b", r"\brefund\b", r"\bcompensation\b",
    r"\bterrible\b", r"\bhorrible\b", r"\bno\s+hot\s+water\b",
    r"\bno\s+water\b", r"\bac\s+(is\s+)?not\b", r"\bno\s+ac\b",
    r"\bdirty\b", r"\bcomplaint\b", r"\bcomplain\b",
    r"\bdisappointed\b", r"\bfrustrat(ed|ing)\b",
    r"\bwant\s+a\s+refund\b", r"\bnot\s+clean\b",
    r"\bpest\b", r"\bunhappy\b", r"\bpoor\s+service\b",
]

_CHECKIN = [
    r"\bwi-?fi\b", r"\bpassword\b", r"\bcheck.?in\s+time\b",
    r"\bcheck.?out\s+time\b", r"\bwhat\s+time\s+can\s+we\b",
    r"\barrival\s+instructions?\b", r"\bcaretaker\b",
    r"\baccess\s+(code|pin|key)\b", r"\bdirections?\s+to\b",
]

_SPECIAL = [
    r"\bearly\s+check.?in\b", r"\blate\s+check.?out\b",
    r"\bairport\s+(pick.?up|transfer|drop)\b", r"\bchef\b",
    r"\bcook\b", r"\bdecoration\b", r"\bcelebrat(e|ion)\b",
    r"\banniversary\b", r"\bbirthday\b", r"\bsurprise\b",
    r"\bmassage\b", r"\bspa\b", r"\bextra\s+bed\b",
    r"\bcot\b", r"\bflowers?\b", r"\bcake\b",
]

_AVAILABILITY = [
    r"\bavailab(le|ility)\b", r"\bbook(ing)?\s+(from|between|for)\b",
    r"\bfrom\s+\w+\s+\d+\s+to\b",
    r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s+\d{1,2}\b",
    r"\bvacant\b", r"\bopen\s+(slots?|dates?)\b",
    r"\bstill\s+free\b", r"\bcan\s+we\s+book\b",
]

_PRICING = [
    r"\brates?\b", r"\bprice\b", r"\bcost\b", r"\bcharge\b",
    r"\bhow\s+much\b", r"\bper\s+night\b", r"\btariff\b",
    r"\bquote\b", r"\b\d+\s+adults?\b", r"\b\d+\s+guests?\b",
    r"\bdiscount\b", r"\boffer\b", r"\bpayment\b",
]


def _match(text: str, patterns: list) -> bool:
    t = text.lower()
    return any(re.search(p, t) for p in patterns)


def classify(message: str) -> QueryType:
    if _match(message, _COMPLAINT):     return QueryType.COMPLAINT
    if _match(message, _CHECKIN):       return QueryType.POST_SALES_CHECKIN
    if _match(message, _SPECIAL):       return QueryType.SPECIAL_REQUEST
    if _match(message, _AVAILABILITY):  return QueryType.PRE_SALES_AVAILABILITY
    if _match(message, _PRICING):       return QueryType.PRE_SALES_PRICING
    return QueryType.GENERAL_ENQUIRY