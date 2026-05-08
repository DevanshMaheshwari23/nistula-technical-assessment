"""
Nistula Guest Message Handler — Integration Tests
Tests 5 message scenarios as required by the assessment.
"""
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from src.main import app
from src.models.schemas import ActionType, QueryType, ConfidenceBreakdown, AIResponse

client = TestClient(app)


# ─── Shared mock helper ───────────────────────────────────────────────────────

def make_mock_ai(confidence: float = 0.91, reply: str = "Hi! Great news about your query."):
    """Returns an async mock for generate_reply with configurable confidence."""
    breakdown = ConfidenceBreakdown(
        query_type_signal=0.90,
        context_coverage_signal=0.90,
        message_clarity_signal=0.92,
        channel_reliability_signal=0.95,
        complaint_cap_applied=False,
        final_score=confidence,
    )
    mock_response = AIResponse(
        drafted_reply=reply,
        confidence_score=confidence,
        confidence_breakdown=breakdown,
        model_used="claude-sonnet-4-20250514",
    )
    async def _mock(msg):
        return mock_response
    return _mock


# ─── Test 1: Availability query via WhatsApp ─────────────────────────────────

def test_availability_whatsapp():
    with patch("src.routes.webhook.generate_reply", make_mock_ai(0.91)):
        response = client.post("/webhook/message", json={
            "source": "whatsapp",
            "guest_name": "Rahul Sharma",
            "message": "Is the villa available from April 20 to 24? What is the rate for 2 adults?",
            "timestamp": "2026-05-05T10:30:00Z",
            "booking_ref": "NIS-2024-0891",
            "property_id": "villa-b1",
        })
    assert response.status_code == 200
    data = response.json()
    assert data["query_type"] == "pre_sales_availability"
    assert data["action"] == "auto_send"           # 0.91 >= 0.85
    assert "message_id" in data
    assert 0.0 <= data["confidence_score"] <= 1.0
    assert len(data["drafted_reply"]) > 0
    print(f"\n✅ Test 1 passed — action: {data['action']}, confidence: {data['confidence_score']}")


# ─── Test 2: Complaint always escalates regardless of confidence ──────────────

def test_complaint_always_escalates():
    # Even with very high mock confidence, complaint must → escalate
    with patch("src.routes.webhook.generate_reply", make_mock_ai(0.99)):
        response = client.post("/webhook/message", json={
            "source": "whatsapp",
            "guest_name": "Priya Menon",
            "message": "The AC is not working. It is 38 degrees and this is unacceptable!",
            "timestamp": "2026-05-05T02:00:00Z",
            "booking_ref": "NIS-2024-0910",
            "property_id": "villa-b1",
        })
    assert response.status_code == 200
    data = response.json()
    assert data["query_type"] == "complaint"
    assert data["action"] == "escalate"            # complaint always escalates
    print(f"\n✅ Test 2 passed — complaint correctly escalated")


# ─── Test 3: Pricing query via Airbnb ────────────────────────────────────────

def test_pricing_airbnb():
    with patch("src.routes.webhook.generate_reply", make_mock_ai(0.88)):
        response = client.post("/webhook/message", json={
            "source": "airbnb",
            "guest_name": "Ananya Roy",
            "message": "What is the rate for 5 guests for 3 nights?",
            "timestamp": "2026-05-06T14:00:00Z",
            "property_id": "villa-b1",
        })
    assert response.status_code == 200
    data = response.json()
    assert data["query_type"] == "pre_sales_pricing"
    assert data["action"] == "auto_send"
    print(f"\n✅ Test 3 passed — pricing classified correctly")


# ─── Test 4: Check-in / WiFi query (post-sales) ───────────────────────────────

def test_checkin_wifi_direct():
    with patch("src.routes.webhook.generate_reply", make_mock_ai(0.96)):
        response = client.post("/webhook/message", json={
            "source": "direct",
            "guest_name": "Vikram Shah",
            "message": "Hi what time can we check in? Also what is the WiFi password?",
            "timestamp": "2026-05-07T09:00:00Z",
            "booking_ref": "NIS-2024-0905",
            "property_id": "villa-b1",
        })
    assert response.status_code == 200
    data = response.json()
    assert data["query_type"] == "post_sales_checkin"
    assert data["action"] == "auto_send"
    print(f"\n✅ Test 4 passed — check-in/WiFi classified correctly")


# ─── Test 5: Low confidence → agent_review ───────────────────────────────────

def test_low_confidence_agent_review():
    with patch("src.routes.webhook.generate_reply", make_mock_ai(0.72)):
        response = client.post("/webhook/message", json={
            "source": "instagram",
            "guest_name": "Neha Kapoor",
            "message": "Hey can you help me with something?",
            "timestamp": "2026-05-08T11:00:00Z",
            "property_id": "villa-b1",
        })
    assert response.status_code == 200
    data = response.json()
    assert data["action"] == "agent_review"        # 0.72 is between 0.60 and 0.85
    print(f"\n✅ Test 5 passed — low confidence → agent_review")


# ─── Test 6: Validation error — missing required field ───────────────────────

def test_validation_error_missing_source():
    response = client.post("/webhook/message", json={
        "guest_name": "Test User",
        "message": "Hello there",
        "timestamp": "2026-05-05T10:00:00Z",
    })
    assert response.status_code == 422
    print(f"\n✅ Test 6 passed — validation error on missing 'source' field")


# ─── Test 7: Validation error — blank message ────────────────────────────────

def test_validation_error_blank_message():
    response = client.post("/webhook/message", json={
        "source": "whatsapp",
        "guest_name": "Test User",
        "message": "   ",
        "timestamp": "2026-05-05T10:00:00Z",
    })
    assert response.status_code == 422
    print(f"\n✅ Test 7 passed — validation error on blank message")