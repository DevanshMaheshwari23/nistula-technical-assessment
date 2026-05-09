# Part 3 — Thinking Question

## The Scenario

It is 3am. A guest at Villa B1 sends a WhatsApp message:
> "There is no hot water and we have guests arriving for breakfast in 4 hours. This is unacceptable. I want a refund for tonight."

***

## Question A — The Immediate Response

**The message sent at 3am:**

> Hi [Guest name], I'm truly sorry — no hot water at 3am with guests arriving is completely unacceptable and I understand how stressful this is. Our caretaker has been alerted right now and is on their way to Villa B1 to fix this urgently. I'll also have our manager call you within 30 minutes to discuss tonight's charges. You have my word we will resolve this before your guests arrive.

**Why this wording:**
The guest is angry and time-pressured — they need to know three things immediately: their problem is being acted on *right now*, a real human is coming, and the refund question will be addressed (not dismissed). The reply avoids hollow apologies ("sorry for the inconvenience"), makes a concrete commitment ("on their way now"), and closes with a direct promise on the refund rather than deflecting it — because deflection at 3am turns a fixable situation into a review.

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

***

## Question C — The Learning Loop

This is the third hot water complaint at Villa B1 in two months. The pattern is the data — the system should surface it, act on it, and prevent it.

**What the system should do with the pattern:**

1. **Automatic pattern detection** — a recurring complaint detector that flags when the same complaint type (mapped by classifier query + keyword cluster) fires ≥ 2 times at the same property within a rolling 60-day window. This is a simple SQL aggregation, not ML.

2. **Generate a maintenance alert** — when the pattern is detected, automatically create a maintenance ticket: *"Hot water system at Villa B1 has generated 3 guest complaints in 60 days. Scheduled inspection required before next check-in."*

3. **Block auto-send for this property** — until the maintenance ticket is resolved, all post-sales messages for Villa B1 should default to `agent_review` (not `auto_send`) so a human sees every message from this property.

**What I would build to prevent the fourth complaint:**

- A **pre-stay checklist** sent to the caretaker 24 hours before every check-in, with property-specific items based on past complaint history. Villa B1's list would include "Test hot water in all bathrooms."
- A **post-resolution follow-up** sent to the guest the morning after any complaint: *"Good morning — I wanted to check that the hot water issue was fully resolved and that you had a good breakfast with your guests. Please let me know if anything else needs attention."* This converts a 1-star experience into a recoverable one.
- A **dashboard view for founders** showing complaint frequency by property and type, so maintenance patterns are visible without manual log-reading.