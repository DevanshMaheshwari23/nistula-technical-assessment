# Nistula Guest Message Handler

A production-grade webhook API that receives inbound guest messages from multiple channels, classifies intent, builds context-aware prompts, and returns AI-drafted replies with a confidence score — built for the Nistula Summer Technology Internship 2026 assessment.

***

## Results

| Suite | Result | Time |
|---|---|---|
| Unit + Edge Case Tests (132 tests) | ✅ 132/132 passed | 0.91s |
| Production Smoke Tests (28 assertions) | ✅ 28/28 passed | Live Claude API |
| Code Coverage | 77% | 100% on critical paths |

***

## Architecture

```
Inbound Webhook
      │
      ▼
┌─────────────────┐
│  normaliser.py  │  Strip markup, unify schema, assign message_id (UUID)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  classifier.py  │  Weighted keyword scoring → QueryType (6 types)
└────────┬────────┘
         │
         ▼
┌──────────────────┐
│  confidence.py   │  4-signal weighted formula → confidence score (0–1)
└────────┬─────────┘
         │
         ▼
┌──────────────────────┐
│  prompt_builder.py   │  Type-aware system prompt + property context block
└────────┬─────────────┘
         │
         ▼
┌──────────────────┐
│  ai_service.py   │  Claude Sonnet API call (async, error-mapped)
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  webhook.py      │  Action routing → auto_send / agent_review / escalate
└──────────────────┘
```

***

## Project Structure

```
nistula-technical-assessment/
├── src/
│   ├── core/
│   │   ├── config.py              # Settings (pydantic-settings, .env)
│   │   ├── exceptions.py          # Typed AI error hierarchy
│   │   ├── logging.py             # Structured JSON logging
│   │   └── property_registry.py  # In-memory property store + rate calc
│   ├── models/
│   │   └── schemas.py             # All Pydantic models (request / response)
│   ├── routes/
│   │   └── webhook.py             # POST /webhook/message handler
│   └── services/
│       ├── ai_service.py          # Anthropic async client wrapper
│       ├── classifier.py          # Weighted regex query classifier
│       ├── confidence.py          # 4-signal confidence scoring engine
│       ├── normaliser.py          # Channel-specific message normalisation
│       ├── prompt_builder.py      # System prompt + overlay builder
│       └── property_context.py   # Property data adapter layer
├── tests/
│   ├── conftest.py
│   ├── test_edge_cases.py         # 58 unit + integration tests
│   ├── test_advanced_edge_cases.py # 74 advanced edge case tests
│   └── test_classifier.py
├── schema.sql                     # Part 2 — PostgreSQL schema
├── thinking.md                    # Part 3 — Written answers
├── design_decisions.md            # Architecture decision log
├── test_production.sh             # Live production smoke test suite
├── requirements.txt
├── .env.example
└── pytest.ini
```

***

## Setup

### Prerequisites

- Python 3.11+
- An Anthropic API key

### Installation

```bash
git clone https://github.com/DevanshMaheshwari23/nistula-technical-assessment.git
cd nistula-technical-assessment

python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### Environment

```bash
cp .env.example .env
# Edit .env and set your ANTHROPIC_API_KEY
```

`.env.example`:
```
ANTHROPIC_API_KEY=sk-ant-...
CLAUDE_MODEL=claude-sonnet-4-20250514
CLAUDE_MAX_TOKENS=1024
CLAUDE_TIMEOUT_S=30
CLAUDE_MAX_RETRIES=2
LOG_LEVEL=INFO
```

### Run the Server

```bash
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

API is live at: `http://localhost:8000`
Health check: `GET http://localhost:8000/health`

***

## API Reference

### `POST /webhook/message`

**Request**
```json
{
  "source": "whatsapp",
  "guest_name": "Rahul Sharma",
  "message": "Is the villa available from April 20 to 24? What is the rate for 2 adults?",
  "timestamp": "2026-05-05T10:30:00Z",
  "booking_ref": "NIS-2024-0891",
  "property_id": "villa-b1"
}
```

`source` must be one of: `whatsapp`, `booking_com`, `airbnb`, `instagram`, `direct`

**Response**
```json
{
  "message_id": "c03c23e5-02d6-45d6-94a5-024fe844d070",
  "query_type": "pre_sales_availability",
  "drafted_reply": "Hi Rahul! Great news — Villa B1 is available from April 20–24...",
  "confidence_score": 0.93,
  "action": "auto_send"
}
```

**Action routing:**
| Score | Action |
|---|---|
| ≥ 0.85 | `auto_send` |
| 0.60 – 0.849 | `agent_review` |
| < 0.60 or `complaint` | `escalate` |

**Query types:** `pre_sales_availability`, `pre_sales_pricing`, `post_sales_checkin`, `special_request`, `complaint`, `general_enquiry`

***

## Confidence Scoring Logic

The confidence score is a **weighted sum of 4 independent signals**, computed before any Claude API call (zero dependency on the AI response).

### Formula

```
score = (query_type_signal × 0.35)
      + (context_coverage  × 0.30)
      + (message_clarity   × 0.20)
      + (channel_reliability × 0.15)
```

### Signal 1 — Query Type Answerability (35%)

How directly can we answer this type from static property context?

| Query Type | Score | Rationale |
|---|---|---|
| `post_sales_checkin` | 0.97 | WiFi password, check-in time — exact lookups |
| `pre_sales_pricing` | 0.90 | Rate formula is deterministic |
| `pre_sales_availability` | 0.88 | Dates are known |
| `general_enquiry` | 0.80 | Usually answerable from property facts |
| `special_request` | 0.72 | Requires human judgement |
| `complaint` | 0.30 | Always escalate — hard cap applied |

### Signal 2 — Context Keyword Coverage (30%)

Counts how many property-relevant keywords appear in the message (availability, rate, wifi, check-in, guest count, dates, chef, pool, etc.). Normalised over 3: hitting 3+ scores 1.0. This measures whether the message contains enough detail to answer accurately.

### Signal 3 — Message Clarity (20%)

Starts at 0.50, then adjusted:
- `+0.20` for well-formed length (8–120 words)
- `-0.15` for very short messages (< 8 words — likely incomplete)
- `+0.15` if message contains a `?` (explicit question)
- `+0.10` if message contains a number (dates, guest counts)
- `-0.08` per emotional charge word (unacceptable, terrible, furious, urgent) — these signal escalation risk

### Signal 4 — Channel Reliability (15%)

| Channel | Base Score | Rationale |
|---|---|---|
| `direct` | 0.95 | Verified guest, highest trust |
| `booking_com` | 0.88 | Authenticated platform |
| `airbnb` | 0.85 | Authenticated platform |
| `whatsapp` | 0.80 | Common channel, less verification |
| `instagram` | 0.65 | Public channel, lowest verification |

**Booking ref bonus:** `+0.08` when a booking reference is present (confirms the guest is post-booking).

### Special Rules

- **Complaint hard cap:** Any `complaint` query is capped at `≤ 0.50`, forcing `escalate` regardless of other signals.
- **Post-sales checkin floor:** If the message contains a directly-answerable property fact (WiFi, pool, check-in time), the score is floored at `0.88` to prevent under-confidence on zero-ambiguity lookups.

***

## Query Classification

The classifier uses **weighted regex pattern matching** with a 3-phase algorithm:

1. **Complaint gate** — if complaint signal score ≥ 2, classify as `complaint` immediately (hard override before any other scoring)
2. **Score all types** — each type has a vocabulary of weighted regex patterns; the total weighted score is computed for every type
3. **Tiebreaker** — when two types score within 2 points of each other, a priority ladder resolves the tie (e.g. `special_request` beats `post_sales_checkin` on overlap; `availability` beats `pricing` when both fire)

**Language support:** Patterns cover English, Hinglish (`kya`, `kitna`, `kab`, `chahiye`), common typos (`availble`), emoji-only messages, ALL CAPS, and multi-line messages.

***

## Running Tests

```bash
# All 132 unit + edge case tests
pytest tests/test_edge_cases.py tests/test_advanced_edge_cases.py -v --tb=short

# With coverage report
pytest tests/test_edge_cases.py tests/test_advanced_edge_cases.py -v --tb=short --cov=src --cov-report=term-missing

# Production smoke test (requires live server on :8000 + valid API key)
bash test_production.sh
```

***

## Known Limitations & Next Steps

1. **`ai_service.py` coverage is 37%** — the Anthropic client path is tested via the production smoke suite against the live API, but unit-level error injection (rate limits, connection drops) uses mocks at the boundary. Deeper unit tests with `respx`/`pytest-httpx` are the natural next step.

2. **Special requests always go to `agent_review`** — this is intentional for safety. A structured special-request handler (early check-in availability check, airport transfer booking flow) would move a subset of these to `auto_send`.

3. **Cancellation policy is `general_enquiry → agent_review`** — the policy is static and fully known. Adding it to the auto-send knowledge base would reduce agent load at no risk.

4. **Single property** — the registry supports multiple properties but only `villa-b1` is seeded. Extending to multi-property requires a database-backed registry.

***

## Design Decisions

See `design_decisions.md` for the full ADR log. Key decisions:

- **Confidence computed before Claude** — the score reflects message quality and query type, not AI response quality. This prevents circular reasoning and makes the score fast and deterministic.
- **Hard complaint escalation** — no confidence score can override a complaint. Guest safety and satisfaction always require human review.
- **Module-level Anthropic client** — not `lru_cache` because `AsyncAnthropic` holds an `httpx.AsyncClient` bound to the event loop. `lru_cache` would break test isolation after event loop restarts.
- **Weighted regex over ML classifier** — for a 6-class problem with well-defined vocabulary, a tuned regex classifier is faster, more debuggable, and requires no training data. The weighted scoring + tiebreaker handles edge cases cleanly.