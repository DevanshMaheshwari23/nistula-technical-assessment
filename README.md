# Nistula Guest Message Handler

A production-grade webhook API that receives inbound guest messages from multiple channels, classifies intent, normalises them into a unified schema, builds context-aware prompts, and returns AI-drafted replies with a confidence score and action routing decision.

Built for the **Nistula Summer Technology Internship 2026** technical assessment.

---

## Test Results

| Suite | Result | Duration |
|---|---|---|
| Unit + Edge Case Tests (132 tests) | ✅ 132/132 passed | 0.91s |
| Production Smoke Tests (28 assertions) | ✅ 28/28 passed | Live Claude API |
| Code Coverage | 77% overall | 100% on all critical paths |

---

## System Architecture

Every inbound message flows through a deterministic 7-stage pipeline before a single token is sent to Claude:

```
Inbound POST /webhook/message
│
▼
┌───────────────────────┐
│   Input Validation    │  Pydantic schema — rejects malformed payloads (422)
│     (schemas.py)      │  Validates: source channel, guest name, timestamp, property_id
└──────────┬────────────┘
           │
           ▼
┌───────────────────────┐
│      Normaliser       │  Channel-specific markup stripping (WhatsApp bold,
│   (normaliser.py)     │  Airbnb HTML, Booking.com prefixes, Instagram URLs)
│                       │  → Assigns UUID, title-cases guest name,
│                       │  attaches UTC timestamp, strips excess whitespace
└──────────┬────────────┘
           │
           ▼
┌───────────────────────┐
│      Classifier       │  Weighted regex scoring across 6 query types
│   (classifier.py)     │  3-phase: complaint gate → score all → tiebreaker
│                       │  → Outputs: QueryType enum value
└──────────┬────────────┘
           │
           ▼
┌───────────────────────┐
│  Confidence Engine    │  4-signal weighted formula (no Claude dependency)
│   (confidence.py)     │  → Outputs: float 0.0–1.0
└──────────┬────────────┘
           │
           ▼
┌───────────────────────┐
│    Prompt Builder     │  Selects base system prompt + query-type overlay
│ (prompt_builder.py)   │  Injects full property context block with
│                       │  pre-calculated rate examples
└──────────┬────────────┘
           │
           ▼
┌───────────────────────┐
│      AI Service       │  Async Claude Sonnet call via Anthropic SDK
│   (ai_service.py)     │  Maps SDK exceptions → typed HTTP errors
│                       │  Logs latency + token usage per request
└──────────┬────────────┘
           │
           ▼
┌───────────────────────┐
│    Action Router      │  Score ≥ 0.85  → auto_send
│    (webhook.py)       │  Score 0.60–0.849 → agent_review
│                       │  Score < 0.60 OR complaint → escalate
└───────────────────────┘
```

---

## Project Structure

```
nistula-technical-assessment/
├── src/
│   ├── core/
│   │   ├── config.py               # pydantic-settings — all config from .env
│   │   ├── exceptions.py           # Typed AI error hierarchy (Auth, RateLimit, Timeout...)
│   │   ├── logging.py              # Structured JSON logging with request context
│   │   └── property_registry.py   # In-memory property store + rate_breakdown() calculator
│   ├── models/
│   │   └── schemas.py              # All Pydantic v2 models: request, unified, response, enums
│   ├── routes/
│   │   └── webhook.py              # POST /webhook/message + GET /health handlers
│   └── services/
│       ├── ai_service.py           # Anthropic AsyncAnthropic client wrapper
│       ├── classifier.py           # Weighted regex query classifier (6 types)
│       ├── confidence.py           # 4-signal confidence scoring engine
│       ├── normaliser.py           # Channel-specific message normalisation
│       ├── prompt_builder.py       # System prompt + type overlay + context block builder
│       └── property_context.py    # Property data adapter layer
├── tests/
│   ├── conftest.py                 # Path setup + fake API key for test isolation
│   ├── test_edge_cases.py          # 58 unit + integration edge case tests
│   ├── test_advanced_edge_cases.py # 74 advanced robustness tests
│   └── test_classifier.py         # Classifier-specific unit tests
├── schema.sql                      # Part 2 — Full PostgreSQL schema with comments
├── thinking.md                     # Part 3 — 3am scenario written answers
├── design_decisions.md             # Architecture Decision Records (ADRs)
├── test_production.sh              # Live end-to-end production smoke test suite
├── requirements.txt
├── pytest.ini
├── conftest.py
└── .env.example
```

---

## Setup

### Prerequisites

- Python 3.11+
- An Anthropic API key (`claude-sonnet-4-20250514` model access)

### Installation

```bash
git clone https://github.com/DevanshMaheshwari23/nistula-technical-assessment.git
cd nistula-technical-assessment

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### Environment Configuration

```bash
cp .env.example .env
# Open .env and set your ANTHROPIC_API_KEY
```

Full `.env` reference:

```env
ANTHROPIC_API_KEY=sk-ant-...           # Required — your Anthropic key
CLAUDE_MODEL=claude-sonnet-4-20250514  # Model to use
CLAUDE_MAX_TOKENS=1024                 # Max reply length
CLAUDE_TIMEOUT_S=30                    # Request timeout in seconds
CLAUDE_MAX_RETRIES=2                   # SDK-level retry count

CONFIDENCE_AUTO_SEND_THRESHOLD=0.85    # Score >= this → auto_send
CONFIDENCE_ESCALATE_THRESHOLD=0.60     # Score < this → escalate

APP_ENV=development                    # development | production | test
LOG_LEVEL=INFO                         # DEBUG | INFO | WARNING | ERROR
WEBHOOK_SECRET=your-secret-here        # Optional — for webhook signature validation
```

### Run the Server

```bash
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:
- Swagger UI: http://localhost:8000/docs
- Health check: http://localhost:8000/health
- Webhook: POST http://localhost:8000/webhook/message

### Running Tests

```bash
# All tests
pytest tests/ -v

# With coverage report
pytest tests/ -v --cov=src --cov-report=term-missing

# Edge cases only
pytest tests/test_edge_cases.py tests/test_advanced_edge_cases.py -v
```

---

## API Reference

### `POST /webhook/message`

**Request payload:**

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

| Field | Type | Required | Notes |
|---|---|---|---|
| `source` | string | ✅ | One of: `whatsapp`, `booking_com`, `airbnb`, `instagram`, `direct` |
| `guest_name` | string | ✅ | Min 1 character |
| `message` | string | ✅ | Min 1 non-whitespace character |
| `timestamp` | ISO 8601 | ✅ | e.g. `2026-05-05T10:30:00Z` |
| `booking_ref` | string | ❌ | `null` accepted for pre-booking enquiries |
| `property_id` | string | ✅ | Must match a registered property (currently: `villa-b1`) |

**Response:**

```json
{
  "message_id": "c03c23e5-02d6-45d6-94a5-024fe844d070",
  "query_type": "pre_sales_availability",
  "drafted_reply": "Hi Rahul! Great news — Villa B1 is absolutely available from April 20–24, 2026...",
  "confidence_score": 0.93,
  "action": "auto_send"
}
```

**Action routing thresholds:**

| Confidence Score | Action | Meaning |
|---|---|---|
| ≥ 0.85 | `auto_send` | Reply goes directly to guest — no human needed |
| 0.60 – 0.849 | `agent_review` | Reply is drafted but held for agent approval |
| < 0.60 | `escalate` | Routed to human agent immediately |
| Any `complaint` | `escalate` | Hard override — complaints always escalate regardless of score |

**HTTP error codes:**

| Code | Reason |
|---|---|
| `422` | Invalid payload (missing field, bad source, blank message, bad timestamp) |
| `404` | Unknown `property_id` |
| `405` | Wrong HTTP method (only POST accepted at `/webhook/message`) |
| `500` | Claude API failure (timeout, auth error, connection error) |

---

## Part 1 — Message Normalisation

Every inbound message is normalised into a **Unified Message Schema** before any processing:

```json
{
  "message_id": "uuid4 — generated fresh per request",
  "source": "whatsapp",
  "guest_name": "Rahul Sharma",
  "message_text": "Is the villa available from April 20 to 24?",
  "timestamp": "2026-05-05T10:30:00Z",
  "booking_ref": "NIS-2024-0891",
  "property_id": "villa-b1",
  "query_type": "pre_sales_availability",
  "raw_payload": { "...original request..." }
}
```

### Channel-Specific Cleaning

| Channel | What Gets Stripped | Example |
|---|---|---|
| `whatsapp` | Bold/italic/strikethrough markdown (`*text*`, `_text_`, `~text~`), code blocks | `*hello*` → `hello` |
| `airbnb` | HTML tags, HTML entities, `---Airbnb` footers, "Reply above this line" trailers | `&amp;` → `&`, `<b>hi</b>` → `hi` |
| `booking_com` | `[Automated message from Booking.com]` prefix, `[Auto-translated]` tags | Strips platform boilerplate |
| `instagram` | URLs (`https://...`), mentions (`@username`) | Removes non-message noise |
| `direct` | No cleaning — passed through as-is | — |

After channel cleaning, all messages go through common normalisation:
- Collapse 3+ blank lines → 2, collapse 2+ spaces → 1
- Strip leading/trailing whitespace
- Guest name → `.title()` case (`RAHUL SHARMA` → `Rahul Sharma`)
- `property_id` → `.lower().strip()`
- Timezone-naive timestamps → UTC

---

## Part 1 — Query Classification

Every cleaned message is classified into one of 6 query types using a **3-phase weighted regex algorithm**.

### The 6 Query Types

| Type | Definition | Example Messages |
|---|---|---|
| `pre_sales_availability` | Guest asking if property is free on specific dates, before booking | *"Is the villa available April 20–24?"*, *"Kya villa free hai May mein?"* |
| `pre_sales_pricing` | Guest asking about rates or costs | *"What is the rate for 2 adults 3 nights?"*, *"How much for 5 people?"* |
| `post_sales_checkin` | Confirmed guest asking about check-in logistics, WiFi, access | *"What time can we check in?"*, *"What's the WiFi password?"* |
| `special_request` | Guest requesting something beyond standard stay | *"Can you arrange an airport transfer?"*, *"We'd like a chef for dinner"* |
| `complaint` | Guest expressing dissatisfaction or reporting a problem | *"The AC is not working"*, *"No hot water — this is unacceptable"* |
| `general_enquiry` | Everything else — policy questions, amenity queries | *"Do you allow pets?"*, *"Is there parking?"* |

### Classification Algorithm — 3 Phases

**Phase 1 — Complaint Gate (hard override)**
Complaint signal score computed using weighted regex patterns (`not working` = 3pts, `unacceptable` = 3pts, `terrible` = 2pts, `not happy` = 2pts). If total ≥ 2 → immediately classify as `complaint`. No further scoring.

**Phase 2 — Score All Types**
Every non-complaint type scored independently using its own weighted vocabulary:
- `pre_sales_availability`: `available`, `vacant`, `free on`, `can we book`, date patterns, month names
- `pre_sales_pricing`: `rate`, `price`, `cost`, `how much`, `per night`, `for N adults`
- `post_sales_checkin`: `check-in`, `wifi`, `password`, `keys`, `directions`, `gate code`
- `special_request`: `early check-in`, `late check-out`, `airport transfer`, `chef`, `birthday`
- `general_enquiry`: `pets`, `parking`, `smoking`, `do you allow`, `is there`

**Phase 3 — Tiebreaker (when top two scores are within 2 points)**
Priority ladder: `special_request` > `post_sales_checkin`; `pre_sales_availability` > `pre_sales_pricing` > `general_enquiry`. Wide gaps (> 2 points) resolve by raw score. Fallback: all-zero → `general_enquiry`.

**Language support:** All patterns cover English, Hinglish (`kya`, `kitna`, `kab`, `chahiye`), common typos (`availble`), emoji-only messages, ALL CAPS, and multi-line messages.

---

## Part 1 — Confidence Scoring

The confidence score is a **weighted sum of 4 independent signals**, computed entirely before the Claude API call — zero dependency on AI response quality.

### Formula

```
confidence = (query_type_signal   × 0.35)
           + (context_coverage    × 0.30)
           + (message_clarity     × 0.20)
           + (channel_reliability × 0.15)
```

### Signal 1 — Query Type Answerability (35%)

| Query Type | Score | Rationale |
|---|---|---|
| `post_sales_checkin` | 0.97 | WiFi password, check-in time — exact zero-ambiguity lookups |
| `pre_sales_pricing` | 0.90 | Rate formula is fully deterministic from property data |
| `pre_sales_availability` | 0.88 | Date availability is known and static |
| `general_enquiry` | 0.80 | Most property policy questions are directly answerable |
| `special_request` | 0.72 | Requires human judgement on feasibility |
| `complaint` | 0.30 | Never auto-send — always needs human involvement |

### Signal 2 — Context Keyword Coverage (30%)

Counts property-relevant keywords in the message: `available`, `rate`, `wifi`, `check-in`, `guest`, `adult`, `night`, `cancel`, `chef`, `pool`, date patterns, guest count patterns. Normalised over 3 — hitting 3+ keywords scores 1.0.

### Signal 3 — Message Clarity (20%)

Baseline 0.50, then adjusted:

| Condition | Adjustment |
|---|---|
| Message length 8–120 words | +0.20 |
| Message length < 8 words | −0.15 |
| Contains `?` | +0.15 |
| Contains a number | +0.10 |
| Each emotional charge word (`unacceptable`, `terrible`, `furious`, `urgent`) | −0.08 each |

Final value clamped to [0.0, 1.0].

### Signal 4 — Channel Reliability (15%)

| Channel | Base Score | Rationale |
|---|---|---|
| `direct` | 0.95 | Direct booking — verified guest, highest trust |
| `booking_com` | 0.88 | Authenticated OTA platform |
| `airbnb` | 0.85 | Authenticated OTA platform |
| `whatsapp` | 0.80 | Common channel, no formal verification |
| `instagram` | 0.65 | Public social channel, lowest trust |

**Booking ref bonus:** +0.08 when `booking_ref` is present.

### Override Rules

- **Complaint hard cap:** Any `complaint` is capped at ≤ 0.50, forcing `escalate` regardless of all other signals.
- **Post-sales checkin floor:** If query is `post_sales_checkin` AND message contains a directly-answerable keyword (wifi, password, check-in, pool), score is floored at 0.88.

### Real-World Score Examples

| Scenario | Channel | Booking Ref | Score | Action |
|---|---|---|---|---|
| "Is villa available Apr 20–24 for 2 adults?" | whatsapp | No | 0.93 | `auto_send` |
| "What's the WiFi password?" | direct | Yes | 0.94 | `auto_send` |
| "No hot water at 3am — unacceptable!" | whatsapp | Yes | 0.48 | `escalate` |
| "Can you arrange early check-in?" | airbnb | Yes | 0.67 | `agent_review` |
| "Do you allow pets?" | instagram | No | 0.73 | `agent_review` |

---

## Part 1 — Prompt Design

### System Prompt Structure

```
BASE SYSTEM PROMPT
→ Role: Nistula guest communication assistant
→ Tone: Warm, professional, specific — never generic
→ Rules: Only use facts from context, never invent numbers, never promise refunds

QUERY TYPE OVERLAY (appended per request type)
→ pre_sales_availability : Focus on dates, availability, offer to hold
→ pre_sales_pricing      : Show rate breakdown, all-inclusive, no hidden fees
→ post_sales_checkin     : Give WiFi password, check-in time, caretaker contact
→ special_request        : Acknowledge warmly, explain process, set expectations
→ complaint              : Empathise, commit to action, no refund promises
→ general_enquiry        : Answer directly from property facts only
```

### Property Context Block

```
Property: Villa B1, Assagao, North Goa
Bedrooms: 3 | Max guests: 6 | Private pool: Yes
Check-in: 2pm | Check-out: 11am
Base rate: ₹18,000/night for up to 4 guests
Extra guest: ₹2,000/person/night (guests 5–6 only)
WiFi password: Nistula@2024
Caretaker: Available 8am–10pm
Chef on call: Yes — minimum 4 hours advance notice required
Cancellation: Free up to 7 days before check-in

RATE EXAMPLES (pre-calculated):
2 guests, 1 night  : ₹18,000
5 guests, 3 nights : ₹60,000  (₹18,000 + ₹2,000 × 3 nights)

RULE: These are final all-inclusive totals. Do NOT add taxes, GST, or unlisted fees.
```

---

## Part 2 — Database Schema

See [`schema.sql`](./schema.sql) for full PostgreSQL `CREATE TABLE` statements with inline comments.

### Schema Overview

```
guests
└── reservations          ← One record per booking, linked to a property
    └── conversations     ← One thread per guest + reservation
        └── messages      ← Every inbound/outbound message
            └── ai_drafts ← AI response, confidence score, query type,
                             action taken, agent edit flag, latency
```

### Key Design Decisions

**`guests` is channel-agnostic:** The `guest_channel_identities` table maps each channel identity (WhatsApp number, Airbnb profile, Booking.com ID) to a single guest record, enabling unified history across channels.

**`ai_drafts` is a separate table:** Stores confidence breakdown, model used, latency, token counts, whether the agent edited before sending, and the final sent text — cleanly separated from the inbound message record.

**`conversations` scoped to reservation:** A guest's messages about a specific booking thread together regardless of channel — context is always property-stay-centric.

---

## Part 3 — Thinking Question Summary

See [`thinking.md`](./thinking.md) for the full written answers to all 3 questions.

**3am scenario — "No hot water, guests arriving for breakfast in 4 hours":**

- **Immediate reply (Q A):** Empathise specifically, commit to caretaker dispatch *right now*, promise manager callback within 30 minutes. The phrase "discuss tonight's stay" opens the refund conversation without making a 3am financial promise.
- **System response (Q B):** Flag → escalate → alert caretaker + property manager via SMS/WhatsApp (not email). Start 30-min SLA timer. No caretaker confirm in 10 min → secondary contact. No manager confirm in 20 min → ops on-call. At 30 min no response → auto follow-up to guest + emergency escalation to founder.
- **Pattern learning (Q C):** Third complaint in 60 days → SQL pattern detector auto-generates maintenance ticket, blocks `auto_send` for Villa B1 until resolved, adds "test hot water" to pre-stay caretaker checklist, sends post-resolution follow-up to guest next morning.

---

## Running Tests

```bash
# All 132 unit + edge case tests
pytest tests/test_edge_cases.py tests/test_advanced_edge_cases.py -v --tb=short

# With line-level coverage report
pytest tests/test_edge_cases.py tests/test_advanced_edge_cases.py -v --tb=short \
  --cov=src --cov-report=term-missing

# Full production smoke test (requires: server on :8000 + valid API key in .env)
bash test_production.sh
```

### What the Tests Cover

| Test Class | What It Tests |
|---|---|
| `TestClassifierEdgeCases` | Hinglish, typos, emoji, ALL CAPS, empty/whitespace, prompt injection |
| `TestConfidenceEdgeCases` | Score boundaries (0.85, 0.60), complaint cap, booking ref bonus, channel scoring |
| `TestNormaliserEdgeCases` | WhatsApp bold stripping, Airbnb HTML, name casing, UUID uniqueness |
| `TestWebhookEdgeCases` | All 5 channels, 404 on unknown property, 422 on bad input, 405 on wrong method |
| `TestActionRouting` | Exact boundary values: 0.85, 0.849, 0.60, 0.599, 0.0 |
| `TestInputValidation` | SQL injection, prompt injection, JSON injection in guest name, Unicode |
| `TestResponseSchema` | All 5 required fields, UUID format, valid enum values, unique message IDs |
| `TestConcurrency` | 10 parallel requests → all unique message IDs, all complaints escalate |
| `TestPromptSafetyRules` | WiFi not in pre-sales prompt, taxes blocked in pricing, refund blocked in complaint |
| `TestHTTPBoundaries` | Health OK, GET/PUT/DELETE → 405, malformed JSON → 422, empty body → 422 |

---

## Known Limitations & v2 Roadmap

### Current Limitations — Known and Intentional

- **`ai_service.py` unit coverage is 37%** — tested end-to-end via production smoke suite, but unit-level error path injection uses mocks at the boundary. Full coverage would use `respx` or `pytest-httpx`.
- **Special requests always go to `agent_review`** — intentional for safety. Known subtypes (airport transfer, chef booking, early check-in) could move to `auto_send` with a structured handler.
- **Cancellation policy goes to `agent_review`** — policy is static and fully known. Adding it to the auto-send knowledge base would cut agent queue with zero risk.
- **Single property in registry** — `villa-b1` only. Multi-property support requires a database-backed registry (schema already in `schema.sql`).

### Deliberately Scoped Out

- No database persistence — messages are stateless, no conversation history stored
- No conversation memory — each message treated in isolation, no guest sentiment tracking
- No async queue — synchronous processing bottlenecks under load
- No human-in-the-loop dashboard — `agent_review` messages flagged but no UI to approve/send
- No webhook signature validation, rate limiting, or replay protection
- No PII redaction in logs
- Several production concerns (distributed queues, persistence, observability, replay protection, and multi-turn conversation memory) are documented in the roadmap section but intentionally scoped out to prioritize core message-routing correctness.

### Design Weaknesses

- **Single intent per message** — classifier picks one winner. Real messages contain mixed intents (`complaint + logistics + special request`) requiring split routing.
- **Confidence ≠ correctness** — high score means safe to send, not factually accurate. Production needs retrieval verification on top of heuristic scoring.
- **Single-shot AI** — Claude drafts replies. It does not act. Production needs tool use: create tickets, look up reservations, dispatch alerts.
- **No metrics** — no measurement of auto-send rate, complaint recurrence, SLA breaches, or agent corrections.

### v2 Priorities

| # | What | Why |
|---|---|---|
| 1 | Conversation state engine | Prior complaints change routing regardless of confidence |
| 2 | Persistence layer | Enables multi-property registry and complaint pattern detection |
| 3 | Expand auto-send coverage | Cancellation policy + known special requests — zero safety tradeoff |
| 4 | Async queue | Webhook acknowledges instantly, retries automatically |
| 5 | Human-in-the-loop dashboard | What property managers actually use |
| 6 | Retrieval-based property context | Dynamic facts instead of static prompt injection |
| 7 | Webhook security hardening | HMAC, rate limiting, idempotency, PII redaction |
| 8 | Metrics dashboard | Complaint rate by property, SLA breach rate, auto-send distribution |

>The current implementation prioritizes deterministic routing and operational correctness. Future iterations would focus on persistence, orchestration, observability, and tooling integration.

---

## Design Decisions

See [`design_decisions.md`](./design_decisions.md) for the full ADR log.

| Decision | Choice | Why |
|---|---|---|
| When to compute confidence | Before Claude call | Score reflects message quality not AI quality — prevents circular reasoning, fast and deterministic |
| Complaint routing | Hard escalate always | No confidence score can override a complaint — guest safety requires human review unconditionally |
| Anthropic client lifecycle | Module-level singleton, not `lru_cache` | `AsyncAnthropic` holds an `httpx.AsyncClient` bound to the event loop — `lru_cache` breaks test isolation after event loop restart |
| Classifier approach | Weighted regex, not ML | 6-class problem with well-defined vocabulary — faster, fully debuggable, needs no training data |
| Prompt structure | Base + type overlay | Single base enforces tone/safety globally; per-type overlays customise without duplication |
| Rate examples in prompt | Pre-calculated in Python | Prevents Claude from re-deriving pricing and introducing rounding errors or hallucinated fees |
