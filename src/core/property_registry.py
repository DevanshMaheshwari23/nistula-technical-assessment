from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from src.core.exceptions import PropertyNotFoundError


@dataclass(frozen=True)
class PropertyContext:
    property_id:           str
    name:                  str
    location:              str
    region:                str
    bedrooms:              int
    max_guests:            int
    has_private_pool:      bool
    check_in_time:         str
    check_out_time:        str
    base_rate_inr:         int
    base_guest_count:      int
    extra_guest_rate_inr:  int
    wifi_password:         str
    caretaker_hours:       str
    caretaker_contact:     str
    chef_on_call:          bool
    chef_notice_hours:     int
    nearest_beach_km:      float
    nearest_airport:       str
    nearest_airport_km:    float
    cancellation_policy:   str
    house_rules:           list[str] = field(default_factory=list)
    amenities:             list[str] = field(default_factory=list)
    nearby_attractions:    list[str] = field(default_factory=list)
    availability_notes:    str = ""

    def rate_for_guests(self, num_guests: int, nights: int = 1) -> int:
        extra = max(0, num_guests - self.base_guest_count)
        return (self.base_rate_inr + extra * self.extra_guest_rate_inr) * nights

    def rate_breakdown(self, num_guests: int, nights: int = 1) -> dict:
        extra     = max(0, num_guests - self.base_guest_count)
        per_night = self.base_rate_inr + extra * self.extra_guest_rate_inr
        return {
            "base_rate_inr":       self.base_rate_inr,
            "extra_guests":        extra,
            "extra_charge_inr":    extra * self.extra_guest_rate_inr,
            "per_night_total_inr": per_night,
            "nights":              nights,
            "total_inr":           per_night * nights,
        }


PROPERTIES_DB: dict[str, PropertyContext] = {
    "villa-b1": PropertyContext(
        property_id          = "villa-b1",
        name                 = "Nistula Villa B1",
        location             = "Amado Vista, Near Assagao Grampanchayat, Assagao, Bardez",
        region               = "North Goa",
        bedrooms             = 3,
        max_guests           = 6,
        has_private_pool     = True,
        check_in_time        = "14:00",
        check_out_time       = "11:00",
        base_rate_inr        = 18_000,
        base_guest_count     = 4,
        extra_guest_rate_inr = 2_000,
        wifi_password        = "Nistula@2024",
        caretaker_hours      = "8am to 10pm",
        caretaker_contact    = "+91-XXXXXXXXXX",
        chef_on_call         = True,
        chef_notice_hours    = 4,
        nearest_beach_km     = 4.7,
        nearest_airport      = "Mopa (GOX)",
        nearest_airport_km   = 25.5,
        cancellation_policy  = (
            "Free cancellation up to 7 days before check-in. "
            "50% charge within 7 days. Full charge within 48 hours."
        ),
        house_rules=[
            "No smoking inside the villa",
            "Pets not allowed",
            "No loud music after 10pm (Goa noise ordinance)",
            "Primary guest must be 18+, valid ID required at check-in",
            "Passport, Aadhaar, or Driving Licence accepted",
            "Maximum 6 guests including children",
        ],
        amenities=[
            "Private pool", "Air conditioning in all rooms", "High-speed WiFi",
            "Fully equipped kitchen", "Balcony", "Garden",
            "Daily housekeeping", "Caretaker on call 8am–10pm",
            "Chef on call (4hr notice)", "Airport transfers available",
            "Smart TV", "Power backup",
        ],
        nearby_attractions=[
            "Vagator Beach (4.7 km)", "Anjuna Flea Market (6 km)",
            "Chapora Fort (5 km)", "Saturday Night Market (8 km)",
            "Mapusa Friday Bazaar (5 km)", "Splashdown Waterpark (4 km)",
        ],
        availability_notes="Available April 20–24, 2026.",
    ),
    "villa-c1": PropertyContext(
        property_id          = "villa-c1",
        name                 = "Nistula Villa C1",
        location             = "Amado Vista, Near Assagao Grampanchayat, Assagao, Bardez",
        region               = "North Goa",
        bedrooms             = 3,
        max_guests           = 6,
        has_private_pool     = True,
        check_in_time        = "15:00",
        check_out_time       = "12:00",
        base_rate_inr        = 18_000,
        base_guest_count     = 4,
        extra_guest_rate_inr = 2_000,
        wifi_password        = "Nistula@2024",
        caretaker_hours      = "8am to 10pm",
        caretaker_contact    = "+91-XXXXXXXXXX",
        chef_on_call         = True,
        chef_notice_hours    = 4,
        nearest_beach_km     = 4.7,
        nearest_airport      = "Mopa (GOX)",
        nearest_airport_km   = 25.5,
        cancellation_policy  = (
            "Free cancellation up to 7 days before check-in. "
            "50% charge within 7 days. Full charge within 48 hours."
        ),
        house_rules=["No smoking", "Pets not allowed", "No loud music after 10pm"],
        amenities=["Private pool", "AC", "WiFi", "Kitchen", "Housekeeping", "Caretaker"],
        nearby_attractions=["Vagator Beach (4.7 km)", "Anjuna Market (6 km)"],
        availability_notes="Check with caretaker for current availability.",
    ),
}


def get_property(property_id: str) -> PropertyContext:
    key  = property_id.strip().lower()
    prop = PROPERTIES_DB.get(key)
    if not prop:
        known = ", ".join(sorted(PROPERTIES_DB.keys()))
        raise PropertyNotFoundError(f"Property '{key}' not found. Known: {known}")
    return prop

get_property_context = get_property 