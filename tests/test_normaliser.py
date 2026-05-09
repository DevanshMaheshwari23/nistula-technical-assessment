from datetime import datetime, timezone
from src.models.schemas import InboundMessagePayload, SourceChannel
from src.services.normaliser import normalise

def _p(**kw):
    defaults = dict(source=SourceChannel.WHATSAPP, guest_name="rahul sharma",
                    message="Is the villa available April 20 to 24?",
                    timestamp=datetime(2026,5,5,10,30,tzinfo=timezone.utc),
                    booking_ref=None, property_id="villa-b1")
    defaults.update(kw)
    return InboundMessagePayload(**defaults)

def test_title_case():         assert normalise(_p()).guest_name == "Rahul Sharma"
def test_property_lowercase(): assert normalise(_p(property_id="VILLA-B1")).property_id == "villa-b1"
def test_whatsapp_bold():       assert "*" not in normalise(_p(message="*Available* April 20?")).message_text
def test_airbnb_html():
    m = normalise(_p(source=SourceChannel.AIRBNB, message="Available April 20 &amp; 24?"))
    assert "&amp;" not in m.message_text and "&" in m.message_text
def test_booking_translation():
    m = normalise(_p(source=SourceChannel.BOOKING_COM, message="[Auto-translated] Is villa available?"))
    assert "[Auto-translated]" not in m.message_text
def test_unique_ids():          assert normalise(_p()).message_id != normalise(_p()).message_id
def test_query_type_set():      assert normalise(_p()).query_type is not None