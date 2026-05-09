# Schema Design Decisions

## The Hardest Decision: When Does a Conversation Link to a Reservation?

**The problem:** Guests enquire about availability *before* they book. At the time of
the first message, there is no `booking_ref` yet. But after they book, you want the
full conversation history — enquiry, negotiation, confirmation, check-in questions —
in one place, not split across two disconnected threads.

**Decision:** `conversations.reservation_id` is nullable at creation. The conversation
opens with only `guest_id + property_id + channel`. Once a booking is confirmed and a
`booking_ref` exists, the application layer updates `reservation_id` on the existing
conversation. This means one continuous thread per guest stay, from first enquiry to
checkout — which is exactly what an agent needs when a guest calls with a question.

**Alternative considered:** Create a new conversation after booking. Rejected because
it loses the pre-sales context that often contains critical guest preferences and
special requests discussed before the booking was made.

---

## Guest Deduplication via `guest_channel_identities`

A guest named Rahul Sharma might contact via WhatsApp (+919876543210), Airbnb
("rahul_travels"), and Booking.com ("rahulsharma@email.com"). Without deduplication,
the platform creates 3 guest records and an agent has no view of the full relationship.

The `guest_channel_identities` table is the bridge: one `guests` row, multiple
`guest_channel_identities` rows. On every inbound message, the application looks up
`(channel, channel_identifier)` — if found, it maps to the existing `guest_id`. If not
found, a new identity is created (and potentially merged with an existing guest via
name/email fuzzy match using the `pg_trgm` index).

---

## Why `messages` is Append-Only

Every state transition (received → AI drafted → agent edited → sent) is recorded on the
*same row* via status updates, not as new rows. This is intentional: the single-row
lifecycle makes it trivial to answer "what was the AI's original draft vs what the agent
changed vs what was actually sent" — three columns, one query, no joins. The `ai_audit_log`
provides the deeper immutable record for compliance, while `messages` provides the
operational view.

---

## `property_issue_patterns` for Preventive Maintenance

Every time a `complaint` message is inserted, the application upserts
`property_issue_patterns` with the extracted `issue_tag`. When `occurrence_count`
crosses a threshold (default: 3), a maintenance alert fires. This turns complaint
data into actionable property maintenance intelligence — the system learns that
Villa B1's hot water geysers need inspection every 6 weeks, without a human having
to notice the pattern manually.

--  ─── FUTURE EXTENSIONS ─────────────────────────
-- The following tables are planned for v2 but intentionally excluded from v1
-- to keep the schema reviewable and focused on core requirements:
--
-- pre_stay_checklists       — caretaker checklists auto-generated 24h before check-in,
--                             seeded from property_issue_patterns (Part 3, Question C)
--
-- v_complaint_frequency     — founder dashboard view: complaint count per property
--                             over rolling 60-day window (Part 3, Question C)
--
-- escalation_severity ENUM  — severity levels (low/medium/high/critical) for
--                             the 30-min watchdog SLA timer (Part 3, Question B)
-- ─────────────────────────────────
