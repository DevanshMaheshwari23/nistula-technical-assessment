"""
Property Context Registry.
In production: replace get_property_context() with a DB call.
No other code changes needed — interface stays the same.
"""
from __future__ import annotations
from typing import Optional

PROPERTIES: dict[str, dict] = {
    "villa-b1": {
        "id":                    "villa-b1",
        "name":                  "Villa B1",
        "location":              "Assagao, North Goa",
        "bedrooms":              3,
        "max_guests":            6,
        "private_pool":          True,
        "check_in_time":         "2:00 PM",
        "check_out_time":        "11:00 AM",
        "base_rate_inr":         18000,
        "base_rate_guest_limit": 4,
        "extra_guest_rate_inr":  2000,
        "wifi_password":         "Nistula@2024",
        "caretaker_hours":       "8:00 AM to 10:00 PM",
        "chef_on_call":          True,
        "cancellation_policy":   (
            "Free cancellation up to 7 days before check-in. "
            "50% charge within 7 days. No refund within 48 hours."
        ),
        "pets_allowed":          False,
        "smoking_policy":        "Outdoor areas only",
        "parking":               "Yes — 2 cars",
        "extra_bed":             "Available on request — INR 1,500/night",
        "infant_cot":            "Available at no charge — pre-booking required",
        "availability_notes":    "Available April 20–24, 2026",
    }
}

DEFAULT_PROPERTY_ID = "villa-b1"


def get_property_context(property_id: Optional[str]) -> dict:
    pid = (property_id or DEFAULT_PROPERTY_ID).lower().strip()
    return PROPERTIES.get(pid, PROPERTIES[DEFAULT_PROPERTY_ID])


def format_for_prompt(property_id: Optional[str]) -> str:
    """
    Render property data as a structured block for Claude.
    Scannable layout so Claude locates exact values quickly.
    """
    p = get_property_context(property_id)
    return f"""
PROPERTY CONTEXT
================
Name          : {p['name']}, {p['location']}
Bedrooms      : {p['bedrooms']}  |  Max Guests : {p['max_guests']}
Private Pool  : {'Yes' if p['private_pool'] else 'No'}

CHECK-IN / CHECK-OUT
Check-in      : {p['check_in_time']}
Check-out     : {p['check_out_time']}

PRICING (INR)
Base rate     : INR {p['base_rate_inr']:,} per night (up to {p['base_rate_guest_limit']} guests)
Extra guest   : INR {p['extra_guest_rate_inr']:,} per night per additional person
Example       : 5 guests x 2 nights = (18,000 + 2,000) x 2 = INR 40,000

CONNECTIVITY
WiFi password : {p['wifi_password']}

SERVICES
Caretaker     : Available {p['caretaker_hours']}
Chef on call  : {'Yes — must pre-book at least 24 hours in advance' if p['chef_on_call'] else 'No'}

CANCELLATION
{p['cancellation_policy']}

AVAILABILITY
{p['availability_notes']}

POLICIES
Pets          : {'Allowed' if p['pets_allowed'] else 'Not permitted'}
Smoking       : {p['smoking_policy']}
Parking       : {p['parking']}
Extra bed     : {p['extra_bed']}
Infant cot    : {p['infant_cot']}
""".strip()