"""
src/services/property_context.py

Thin adapter — all property data lives in src.core.property_registry.
This module provides the prompt-formatting layer on top of it.
Import get_property_context() for raw data, format_for_prompt() for Claude.
"""
from __future__ import annotations
from typing import Optional

from src.core.property_registry import PropertyContext, get_property, PROPERTIES_DB
from src.core.exceptions import PropertyNotFoundError


# Re-export for convenience so callers don't need two imports
__all__ = ["get_property_context", "format_for_prompt", "PropertyNotFoundError"]


def get_property_context(property_id: Optional[str]) -> PropertyContext:
    """
    Returns the PropertyContext for the given property_id.
    Raises PropertyNotFoundError if the ID is unknown.
    Falls back to 'villa-b1' only if property_id is None/empty.
    """
    pid = (property_id or "villa-b1").lower().strip()
    return get_property(pid)


def format_for_prompt(prop: PropertyContext) -> str:
    """
    Render a PropertyContext as a structured block for Claude.
    Scannable layout so Claude locates exact values quickly.
    All values come from the single PropertyContext source — no duplication.
    """
    house_rules_text    = "\n".join(f"  • {r}" for r in prop.house_rules)
    amenities_text      = ", ".join(prop.amenities)
    attractions_text    = "\n".join(f"  • {a}" for a in prop.nearby_attractions)

    check_in_display    = _format_time(prop.check_in_time)
    check_out_display   = _format_time(prop.check_out_time)

    return f"""
PROPERTY CONTEXT — USE ONLY THE FACTS LISTED HERE. DO NOT INVENT ANYTHING NOT PRESENT.
========================================================================================
Name          : {prop.name}
Location      : {prop.location}, {prop.region}
Bedrooms      : {prop.bedrooms}  |  Max Guests : {prop.max_guests}
Private Pool  : {'Yes' if prop.has_private_pool else 'No'}

CHECK-IN / CHECK-OUT
Check-in      : {check_in_display}
Check-out     : {check_out_display}

PRICING (INR)
Base rate     : INR {prop.base_rate_inr:,} per night (up to {prop.base_guest_count} guests)
Extra guest   : INR {prop.extra_guest_rate_inr:,} per night per additional person
               (applies to guest #{prop.base_guest_count + 1} through #{prop.max_guests})
Example       : {prop.max_guests} guests × 2 nights
               = (INR {prop.base_rate_inr:,} + {prop.max_guests - prop.base_guest_count} × INR {prop.extra_guest_rate_inr:,}) × 2
               = INR {prop.rate_for_guests(prop.max_guests, 2):,}

CONNECTIVITY
WiFi password : {prop.wifi_password}

SERVICES
Caretaker     : Available {prop.caretaker_hours} (contact in booking confirmation)
Chef on call  : {'Yes — must pre-book at least ' + str(prop.chef_notice_hours) + ' hours in advance' if prop.chef_on_call else 'No'}

LOCATION
Nearest beach : {prop.nearest_beach_km} km
Airport       : {prop.nearest_airport} — {prop.nearest_airport_km} km

CANCELLATION
{prop.cancellation_policy}

AVAILABILITY
{prop.availability_notes}
Note: ONLY confirm dates listed as "Available" above. For all other dates say:
      "Let me check our calendar and confirm shortly."

AMENITIES
{amenities_text}

NEARBY ATTRACTIONS
{attractions_text}

HOUSE RULES
{house_rules_text}
========================================================================================
CRITICAL RULES FOR THIS RESPONSE:
  1. Do NOT invent caretaker's name — it is not provided here.
  2. Do NOT invent cancellation tiers beyond what is written above.
  3. Do NOT confirm availability for dates not listed above.
  4. Do NOT quote specific refund amounts — say the manager will confirm.
  5. Parking details not listed above — say "I'll confirm shortly."
""".strip()


def _format_time(t: str) -> str:
    """Convert '14:00' → '2:00 PM', pass through if already formatted."""
    if ":" not in t or t[0].isalpha():
        return t
    try:
        h, m = map(int, t.split(":"))
        suffix = "AM" if h < 12 else "PM"
        h12    = h % 12 or 12
        return f"{h12}:{m:02d} {suffix}"
    except ValueError:
        return t