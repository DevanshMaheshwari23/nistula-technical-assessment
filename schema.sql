-- ============================================================
-- NISTULA UNIFIED MESSAGING PLATFORM — PostgreSQL Schema
-- Version: 1.0 | Author: Devansh Maheshwari
-- ============================================================
-- Design Principles:
--   1. One guest profile across all channels (deduplication via
--      guest_channel_identities — the guest's unique ID per channel)
--   2. All messages in a single append-only messages table
--   3. Conversations group messages per guest+property context
--      and can exist BEFORE a booking_ref is known (pre-sales)
--   4. Full AI audit trail: draft → agent edit → sent all tracked
--   5. Confidence score, query_type, and model version stored per message
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ─── ENUMS ────────────────────────────────────────────────────────────────────

CREATE TYPE source_channel AS ENUM (
    'whatsapp', 'booking_com', 'airbnb', 'instagram', 'direct'
);

CREATE TYPE query_type AS ENUM (
    'pre_sales_availability',
    'pre_sales_pricing',
    'post_sales_checkin',
    'special_request',
    'complaint',
    'general_enquiry'
);

CREATE TYPE reply_action AS ENUM (
    'auto_send',      -- confidence >= 0.85
    'agent_review',   -- confidence 0.60–0.85
    'escalate'        -- confidence < 0.60 OR complaint
);

CREATE TYPE message_status AS ENUM (
    'received',
    'processing',
    'draft_ready',
    'agent_editing',
    'sent',
    'escalated',
    'resolved'
);


-- ─── PROPERTIES ───────────────────────────────────────────────────────────────
-- Single source of truth for all managed villas/properties.
-- In production this would be the authoritative record that
-- feeds the AI context registry — not hardcoded in prompts.

CREATE TABLE properties (
    id                   VARCHAR(50)  PRIMARY KEY,        -- e.g. 'villa-b1'
    name                 VARCHAR(200) NOT NULL,
    location             TEXT         NOT NULL,
    max_guests           SMALLINT     NOT NULL DEFAULT 6,
    bedrooms             SMALLINT     NOT NULL DEFAULT 3,
    has_private_pool     BOOLEAN      NOT NULL DEFAULT FALSE,
    base_rate_inr        INTEGER      NOT NULL,
    extra_guest_rate_inr INTEGER      NOT NULL DEFAULT 2000,
    wifi_password        VARCHAR(100),
    check_in_time        VARCHAR(10)  NOT NULL DEFAULT '14:00',
    check_out_time       VARCHAR(10)  NOT NULL DEFAULT '11:00',
    caretaker_name       VARCHAR(100),
    caretaker_available  VARCHAR(50)  DEFAULT '8am to 10pm',
    chef_on_call         BOOLEAN      NOT NULL DEFAULT FALSE,
    cancellation_policy  TEXT,
    is_active            BOOLEAN      NOT NULL DEFAULT TRUE,
    metadata             JSONB        NOT NULL DEFAULT '{}',
    created_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- Seed Villa B1 from the assessment brief
INSERT INTO properties (
    id, name, location, max_guests, bedrooms, has_private_pool,
    base_rate_inr, extra_guest_rate_inr, wifi_password,
    check_in_time, check_out_time, caretaker_available,
    chef_on_call, cancellation_policy
) VALUES (
    'villa-b1',
    'Villa B1',
    'Assagao, North Goa',
    6, 3, TRUE,
    18000, 2000, 'Nistula@2024',
    '14:00', '11:00', '8am to 10pm',
    TRUE,
    'Free cancellation up to 7 days before check-in'
);


-- ─── GUESTS ───────────────────────────────────────────────────────────────────
-- ONE record per real-world guest, regardless of how many channels
-- they use to contact us. Deduplication logic lives in application
-- layer — on inbound message, match by phone/email before creating new.

CREATE TABLE guests (
    id                UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    full_name         VARCHAR(200) NOT NULL,
    email             VARCHAR(255) UNIQUE,
    phone             VARCHAR(30),
    nationality       VARCHAR(60),
    preferred_channel source_channel,
    total_stays       SMALLINT     NOT NULL DEFAULT 0,
    is_vip            BOOLEAN      NOT NULL DEFAULT FALSE,
    notes             TEXT,                               -- internal agent notes
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- gin index enables fast fuzzy name search (e.g. "Rahul" matches "Rahul Sharma")
CREATE INDEX idx_guests_name_trgm ON guests USING gin (full_name gin_trgm_ops);
CREATE INDEX idx_guests_email     ON guests (email) WHERE email IS NOT NULL;
CREATE INDEX idx_guests_phone     ON guests (phone) WHERE phone IS NOT NULL;


-- ─── GUEST CHANNEL IDENTITIES ─────────────────────────────────────────────────
-- Maps one guest to their identity on each channel.
-- e.g. same Rahul Sharma may be +919876543210 on WhatsApp,
-- "rahulsharma91" on Airbnb, and r.sharma@email.com on Booking.com.
-- This table is the deduplication bridge.

CREATE TABLE guest_channel_identities (
    id                 UUID           PRIMARY KEY DEFAULT uuid_generate_v4(),
    guest_id           UUID           NOT NULL REFERENCES guests(id) ON DELETE CASCADE,
    channel            source_channel NOT NULL,
    channel_identifier VARCHAR(255)   NOT NULL,           -- phone / username / booking platform ID
    display_name       VARCHAR(200),                      -- name as it appears on that channel
    verified           BOOLEAN        NOT NULL DEFAULT FALSE,
    created_at         TIMESTAMPTZ    NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_channel_identity UNIQUE (channel, channel_identifier)
);

CREATE INDEX idx_channel_identity_lookup
    ON guest_channel_identities (channel, channel_identifier);


-- ─── RESERVATIONS ─────────────────────────────────────────────────────────────
-- Actual bookings. Messages are linked to reservations where possible.
-- A reservation can have messages from BEFORE it was confirmed
-- (linked retroactively via conversation.reservation_id).

CREATE TABLE reservations (
    id               UUID           PRIMARY KEY DEFAULT uuid_generate_v4(),
    booking_ref      VARCHAR(50)    UNIQUE NOT NULL,      -- e.g. 'NIS-2024-0891'
    guest_id         UUID           NOT NULL REFERENCES guests(id),
    property_id      VARCHAR(50)    NOT NULL REFERENCES properties(id),
    channel          source_channel NOT NULL,
    check_in_date    DATE           NOT NULL,
    check_out_date   DATE           NOT NULL,
    num_guests       SMALLINT       NOT NULL DEFAULT 1,
    total_amount_inr INTEGER,
    status           VARCHAR(30)    NOT NULL DEFAULT 'confirmed',
    external_ref     VARCHAR(100),                        -- Airbnb / Booking.com reference
    special_requests TEXT,
    created_at       TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ    NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_reservations_booking_ref ON reservations (booking_ref);
CREATE INDEX idx_reservations_guest       ON reservations (guest_id);
CREATE INDEX idx_reservations_property_dates
    ON reservations (property_id, check_in_date, check_out_date);


-- ─── CONVERSATIONS ────────────────────────────────────────────────────────────
-- Groups all messages for a guest+property context into one thread.
--
-- HARDEST DESIGN DECISION: Should a conversation be tied to a reservation?
-- Decision: NO — not at creation time. Pre-sales enquiries arrive before any
-- booking_ref exists. The conversation is opened with just guest_id + property_id,
-- and reservation_id is linked AFTER a booking is confirmed. This means the full
-- message history (enquiry → booking → stay → checkout) lives in one conversation
-- thread, which is far more useful for agents than two disconnected threads.

CREATE TABLE conversations (
    id              UUID           PRIMARY KEY DEFAULT uuid_generate_v4(),
    guest_id        UUID           NOT NULL REFERENCES guests(id),
    property_id     VARCHAR(50)    REFERENCES properties(id),
    reservation_id  UUID           REFERENCES reservations(id),   -- NULL until booking confirmed
    channel         source_channel NOT NULL,
    subject         VARCHAR(255),                                  -- derived from first message
    is_open         BOOLEAN        NOT NULL DEFAULT TRUE,
    assigned_agent  VARCHAR(100),
    last_message_at TIMESTAMPTZ,
    opened_at       TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    closed_at       TIMESTAMPTZ,
    total_messages  INTEGER        NOT NULL DEFAULT 0,
    complaint_count SMALLINT       NOT NULL DEFAULT 0
);

CREATE INDEX idx_conversations_guest
    ON conversations (guest_id);
CREATE INDEX idx_conversations_open
    ON conversations (is_open, last_message_at DESC) WHERE is_open = TRUE;
CREATE INDEX idx_conversations_property
    ON conversations (property_id, opened_at DESC);
CREATE INDEX idx_conversations_reservation
    ON conversations (reservation_id) WHERE reservation_id IS NOT NULL;


-- ─── MESSAGES ─────────────────────────────────────────────────────────────────
-- The core append-only table. Every inbound message AND outbound reply
-- is a row here. Nothing is ever updated or deleted — only inserted.
-- The full lifecycle of a message (received → AI drafted → agent edited
-- → sent) is tracked via status + timestamps on the same row.

CREATE TABLE messages (
    id                   UUID           PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id      UUID           NOT NULL REFERENCES conversations(id),
    guest_id             UUID           NOT NULL REFERENCES guests(id),
    property_id          VARCHAR(50)    REFERENCES properties(id),
    booking_ref          VARCHAR(50),                             -- denormalised for fast lookup

    -- Content
    direction            VARCHAR(10)    NOT NULL CHECK (direction IN ('inbound', 'outbound')),
    source_channel       source_channel NOT NULL,
    raw_payload          JSONB          NOT NULL DEFAULT '{}',    -- original webhook JSON
    message_text         TEXT           NOT NULL,
    received_at          TIMESTAMPTZ    NOT NULL,                 -- original message timestamp

    -- Classification (inbound only)
    query_type           query_type,

    -- AI processing (inbound only)
    ai_drafted_reply     TEXT,
    ai_confidence_score  DECIMAL(4,3)   CHECK (ai_confidence_score BETWEEN 0 AND 1),
    ai_model_used        VARCHAR(60),                            -- e.g. 'claude-sonnet-4-20250514'
    ai_processed_at      TIMESTAMPTZ,
    confidence_breakdown JSONB,                                  -- per-signal scores

    -- Action routing
    action               reply_action,
    status               message_status NOT NULL DEFAULT 'received',

    -- Agent workflow
    agent_edited_reply   TEXT,                                   -- if agent changed the AI draft
    agent_id             VARCHAR(100),
    agent_actioned_at    TIMESTAMPTZ,

    -- Final sent state
    sent_reply           TEXT,                                   -- what was actually sent
    sent_at              TIMESTAMPTZ,

    created_at           TIMESTAMPTZ    NOT NULL DEFAULT NOW()
);

-- Optimised for most common query patterns
CREATE INDEX idx_messages_conversation
    ON messages (conversation_id, received_at);
CREATE INDEX idx_messages_booking_ref
    ON messages (booking_ref) WHERE booking_ref IS NOT NULL;
CREATE INDEX idx_messages_guest
    ON messages (guest_id, received_at DESC);
CREATE INDEX idx_messages_action_status
    ON messages (action, status)
    WHERE status IN ('draft_ready', 'agent_editing');
CREATE INDEX idx_messages_complaints
    ON messages (property_id, received_at DESC)
    WHERE query_type = 'complaint';
CREATE INDEX idx_messages_query_type
    ON messages (query_type, received_at DESC);


-- ─── AI AUDIT LOG ─────────────────────────────────────────────────────────────
-- Immutable record of every Claude API call. Used for:
--   - Model performance monitoring (confidence vs actual outcome)
--   - Cost tracking (input/output tokens)
--   - Fine-tuning data collection
--   - Compliance and debugging

CREATE TABLE ai_audit_log (
    id                  UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    message_id          UUID        NOT NULL REFERENCES messages(id),
    model               VARCHAR(60) NOT NULL,
    system_prompt_hash  VARCHAR(64) NOT NULL,                    -- SHA-256 of system prompt used
    input_tokens        INTEGER,
    output_tokens       INTEGER,
    latency_ms          INTEGER,
    confidence_score    DECIMAL(4,3),
    query_type          query_type,
    action_taken        reply_action,
    error               TEXT,                                    -- NULL on success
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_ai_audit_message   ON ai_audit_log (message_id);
CREATE INDEX idx_ai_audit_date      ON ai_audit_log (created_at DESC);
CREATE INDEX idx_ai_audit_errors    ON ai_audit_log (created_at DESC) WHERE error IS NOT NULL;


-- ─── ESCALATION LOG ───────────────────────────────────────────────────────────
-- Every escalation event with full notification trail.
-- Supports the 30-min watchdog pattern from Part 3:
--   1. Complaint arrives → escalation_log row inserted (auto_escalated = FALSE)
--   2. Background job checks acknowledged_at every 5 min
--   3. If NULL after 30 min → new row with auto_escalated = TRUE, wider audience

CREATE TABLE escalation_log (
    id               UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    message_id       UUID        NOT NULL REFERENCES messages(id),
    property_id      VARCHAR(50) REFERENCES properties(id),
    escalation_type  VARCHAR(50) NOT NULL,                       -- 'complaint', 'no_response_30min', 'critical'
    notified_roles   TEXT[]      NOT NULL DEFAULT '{}',          -- ['caretaker', 'operations', 'management']
    notified_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    acknowledged_at  TIMESTAMPTZ,
    acknowledged_by  VARCHAR(100),
    resolution_notes TEXT,
    resolved_at      TIMESTAMPTZ,
    auto_escalated   BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_escalation_message    ON escalation_log (message_id);
CREATE INDEX idx_escalation_unresolved ON escalation_log (notified_at DESC)
    WHERE resolved_at IS NULL;
CREATE INDEX idx_escalation_property   ON escalation_log (property_id, notified_at DESC);


-- ─── PROPERTY ISSUE PATTERNS ──────────────────────────────────────────────────
-- Aggregates recurring issues per property to enable preventive maintenance.
-- Powers the "3rd hot water complaint" detection from Part 3.
-- On every complaint insert, the application layer upserts this table.
-- When occurrence_count hits threshold (e.g. 3), a maintenance alert fires.

CREATE TABLE property_issue_patterns (
    id                      UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    property_id             VARCHAR(50) NOT NULL REFERENCES properties(id),
    issue_tag               VARCHAR(100) NOT NULL,               -- 'hot_water', 'ac', 'wifi', 'pool'
    occurrence_count        INTEGER     NOT NULL DEFAULT 1,
    first_reported_at       TIMESTAMPTZ NOT NULL,
    last_reported_at        TIMESTAMPTZ NOT NULL,
    is_resolved             BOOLEAN     NOT NULL DEFAULT FALSE,
    resolution_notes        TEXT,
    maintenance_ticket_ref  VARCHAR(100),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_property_issue UNIQUE (property_id, issue_tag)
);

CREATE INDEX idx_issue_patterns_property
    ON property_issue_patterns (property_id, last_reported_at DESC);
CREATE INDEX idx_issue_patterns_unresolved
    ON property_issue_patterns (is_resolved, occurrence_count DESC)
    WHERE is_resolved = FALSE;


-- ─── TRIGGERS ─────────────────────────────────────────────────────────────────

-- Auto-update updated_at on any UPDATE
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_properties_updated_at
    BEFORE UPDATE ON properties
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_guests_updated_at
    BEFORE UPDATE ON guests
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_reservations_updated_at
    BEFORE UPDATE ON reservations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_issue_patterns_updated_at
    BEFORE UPDATE ON property_issue_patterns
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- Keep conversation stats in sync on every new message
CREATE OR REPLACE FUNCTION sync_conversation_stats()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE conversations
    SET
        total_messages  = total_messages + 1,
        last_message_at = NOW(),
        complaint_count = complaint_count + (
            CASE WHEN NEW.query_type = 'complaint' THEN 1 ELSE 0 END
        )
    WHERE id = NEW.conversation_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_message_inserted
    AFTER INSERT ON messages
    FOR EACH ROW EXECUTE FUNCTION sync_conversation_stats();
