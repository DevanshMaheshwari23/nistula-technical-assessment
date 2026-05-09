from unittest.mock import patch
from fastapi.testclient import TestClient
from src.main import app
from src.models.schemas import AIResponse, ConfidenceBreakdown

client = TestClient(app)

def _ai(conf=0.91):
    bd = ConfidenceBreakdown(query_type_signal=0.9, context_coverage=0.85,
                             message_clarity=0.90, channel_reliability=0.95,
                             complaint_cap_applied=False, final_score=conf)
    async def inner(msg): return AIResponse(drafted_reply="Test reply.", confidence_score=conf,
                                            confidence_breakdown=bd, model_used="claude-sonnet-4-20250514",
                                            input_tokens=120, output_tokens=80, latency_ms=900)
    return inner

def test_availability_auto_send():
    with patch("src.routes.webhook.generate_reply", _ai(0.93)):
        r = client.post("/webhook/message", json={"source":"whatsapp","guest_name":"Rahul Sharma",
            "message":"Is villa available April 20 to 24?","timestamp":"2026-05-05T10:30:00Z",
            "booking_ref":"NIS-2024-0891","property_id":"villa-b1"})
    assert r.status_code == 200
    assert r.json()["action"] == "auto_send"
    assert r.json()["query_type"] == "pre_sales_availability"

def test_complaint_always_escalates():
    with patch("src.routes.webhook.generate_reply", _ai(0.99)):
        r = client.post("/webhook/message", json={"source":"whatsapp","guest_name":"Priya Menon",
            "message":"The AC is not working this is unacceptable",
            "timestamp":"2026-05-05T02:00:00Z","property_id":"villa-b1"})
    assert r.json()["action"] == "escalate"

def test_pricing_query():
    with patch("src.routes.webhook.generate_reply", _ai(0.88)):
        r = client.post("/webhook/message", json={"source":"booking_com","guest_name":"Ananya Roy",
            "message":"What is the rate for 5 guests 3 nights?","timestamp":"2026-05-06T14:00:00Z",
            "property_id":"villa-b1"})
    assert r.json()["query_type"] == "pre_sales_pricing"

def test_low_confidence_agent_review():
    with patch("src.routes.webhook.generate_reply", _ai(0.72)):
        r = client.post("/webhook/message", json={"source":"instagram","guest_name":"Neha K",
            "message":"Hey can you help me?","timestamp":"2026-05-08T11:00:00Z","property_id":"villa-b1"})
    assert r.json()["action"] == "agent_review"

def test_unknown_property_404():
    with patch("src.routes.webhook.generate_reply", _ai()):
        r = client.post("/webhook/message", json={"source":"whatsapp","guest_name":"Test",
            "message":"Is it available?","timestamp":"2026-05-05T10:00:00Z","property_id":"villa-xyz"})
    assert r.status_code == 404

def test_missing_source_422():
    r = client.post("/webhook/message", json={"guest_name":"Test","message":"Hello","timestamp":"2026-05-05T10:00:00Z"})
    assert r.status_code == 422

def test_blank_message_422():
    r = client.post("/webhook/message", json={"source":"whatsapp","guest_name":"Test",
        "message":"   ","timestamp":"2026-05-05T10:00:00Z","property_id":"villa-b1"})
    assert r.status_code == 422

def test_metadata_complete():
    with patch("src.routes.webhook.generate_reply", _ai(0.91)):
        r = client.post("/webhook/message", json={"source":"direct","guest_name":"Vikram Shah",
            "message":"What time is check in and what is the WiFi password?",
            "timestamp":"2026-05-07T09:00:00Z","booking_ref":"NIS-2024-0905","property_id":"villa-b1"})
    meta = r.json()["metadata"]
    for k in ["model","latency_ms","tokens","confidence_breakdown","property_id","channel"]:
        assert k in meta