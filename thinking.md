# Part 3 — Thinking Question

## The Scenario

It is 3am. A guest at Villa B1 sends a WhatsApp message:
> "There is no hot water and we have guests arriving for breakfast in 4 hours. This is unacceptable. I want a refund for tonight."

***

## Question A — The Immediate Response

**The message sent at 3am:**

> Hi [Guest name], I’m truly sorry — no hot water at this hour, especially with guests arriving in a few hours, is completely unacceptable. I’ve already alerted our caretaker and they are on the way to Villa B1 right now. Our property manager will also call you within 30 minutes to make sure this is resolved urgently and to discuss tonight’s stay with you. We will do everything we can to fix this before your guests arrive.

**Why this wording:**
A guest first needs to feel heard, not “processed.” The message acknowledges the seriousness of the failure, gives a concrete action already in motion, and sets a clear response timeline instead of offering vague reassurance. Hospitality guidance consistently emphasizes empathy, prompt action, and follow-up as the core of effective complaint handling.

***

## Question B — The System Design

Beyond sending the AI-drafted message, the platform should trigger a full escalation chain:

**Immediate (0–2 minutes):**
- Flag message as `complaint` → `escalate` in the database with `triggered_at` timestamp
- Send push alert to on-call caretaker with guest name, property, and issue summary
- Send SMS + WhatsApp alert to property manager (not just email — 3am email goes unread)
- Create an incident record linked to the reservation, message, and property

**Short-term (0–30 minutes):**
- Start a 30-minute countdown timer for human response acknowledgement
- If caretaker does not confirm dispatch within 10 minutes → escalate to secondary caretaker contact
- If property manager does not acknowledge within 20 minutes → alert Nistula ops on-call

**At the 30-minute mark (no human response):**
- Automatically send a follow-up message to the guest: *"Our team is actively working on this. Our manager will call you within the next 15 minutes."*
- Trigger an emergency escalation to the founder/ops lead
- Log the escalation failure as a separate incident for post-mortem

**Logging (everything, immediately):**
- Original message + timestamp + channel
- AI classification result and confidence score
- Every notification sent and to whom
- Caretaker dispatch confirmation time
- Resolution timestamp and outcome
- Whether the 30-minute SLA was met

**At 9am (post-resolution):**
- Send a personal follow-up regardless of outcome:
  "Good morning — I wanted to check the issue was fully resolved
  and that breakfast went well. Please let me know if anything
  still needs attention."
  A single genuine follow-up converts a near 1-star experience
  into a recoverable one. Guests who feel the problem was handled
  almost never leave a negative review.

***

## Question C — The Learning Loop

The third hot water complaint in two months means this is no
longer a guest-service issue — it is an asset-reliability issue.
In luxury stays, "service" is not just how well you respond after
failure — it is how rarely the guest ever sees failure.

Hot water is one symptom. The real question is: what kind of
platform turns *any* recurring property complaint into a resolved
maintenance issue before the next guest checks in? The same
system applies to every complaint type — AC failures, WiFi drops,
pool pump noise, generator outages, pest issues — every recurring
pattern gets the same treatment: detected → ticketed → checklist
item added → auto_send blocked until resolved. A complaint
addressed is a guest retained. A complaint pattern ignored is a
rating destroyed.

**What the system should do with the pattern:**

1. **Automatic pattern detection** — a recurring complaint
   detector flags when the same complaint cluster fires ≥ 2
   times at the same property in a rolling 60-day window.
   This is a simple SQL aggregation, not ML — and it catches
   every issue type.

2. **Root cause classification** — the third complaint triggers
   a mandatory manager investigation task: *why* is this
   recurring, not just *what* happened.An undersized geyser
   for 6 guests needs replacement. All guests showering 6–8am
   exhausting a small tank needs a pre-heat schedule. A periodic
   element failure needs a service contract. An AC freezing every
   3 weeks needs a filter-cleaning schedule. The platform surfaces
   the pattern and forces the investigation — rather than letting
   the same failure repeat silently until a guest catches it again.

3. **Generate a maintenance ticket** — auto-created when the
   threshold is hit:
   *"[Issue] at Villa B1 has generated [N] guest complaints in
   60 days. Inspection required before next check-in. auto_send
   blocked until resolved."*
   The ticket cannot be dismissed without adding resolution notes
   and a confirmation reference.

4. **Block auto-send for this property** — until the maintenance
   ticket is closed, all post-sales messages for Villa B1 default
   to `agent_review`. A human sees every message. This is not
   punishment — it is a signal that this property needs closer
   attention right now.

**What I would build to prevent the fourth complaint:**

- **Issue-seeded pre-stay checklist** generated automatically
  from `property_issue_patterns` and sent to the caretaker
  24 hours before every check-in. Items are driven by complaint
  history — not a generic standard list:
  - Hot water complaints → *"Run all showers 2 minutes and
    confirm hot water is flowing"*
  - AC complaints → *"Run AC in all bedrooms 15 minutes
    before guest arrival and confirm cooling"*
  - WiFi complaints → *"Connect a phone to the WiFi and run
    a speed test"*
  - Pool complaints → *"Check pump is running and water is
    clear at least 2 hours before check-in"*

  The caretaker cannot mark the checklist complete without
  ticking every item. This is logged and linked to the
  reservation. If the caretaker confirmed hot water was working
  24 hours before check-in and a guest still complains at 3am,
  the diagnosis scope is immediately narrower.

  **Scheduled preventive maintenance calendar** — every complaint
  pattern that fires ≥ 2 times in 60 days automatically adds a
  recurring inspection item to the property's maintenance calendar.
  Hot water complaints → plumber inspects geyser and checks
  element, thermostat, and tank capacity before the next check-in
  and again monthly. AC complaints → AC technician cleans filters
  and checks gas levels quarterly. WiFi complaints → router
  firmware updated and speed tested monthly.

- **Post-resolution follow-up** after every complaint
  with issue-specific templating:
  *"Good morning — I wanted to check that the [issue] was fully
  resolved and that you had a comfortable stay."*
  This single message has more review-recovery impact than any
  discount or partial refund.

- **Founder dashboard** (`v_complaint_frequency`) showing
  complaint frequency by property, by issue tag, and by week
  over a rolling 60-day window. When a founder opens this on
  Monday morning and sees 3 hot water rows for Villa B1 next
  to 2 AC rows for Villa C3, they do not need to read logs.
  The pattern is one number.

  **The core principle:** Every complaint the platform receives
is a maintenance ticket that arrived too late. The goal is to
move from reactive resolution to proactive prevention — because
in luxury hospitality, the best complaint handling is the
complaint that never gets sent.