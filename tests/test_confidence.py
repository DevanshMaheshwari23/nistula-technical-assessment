from src.services.confidence import compute_confidence
from src.models.schemas import QueryType, SourceChannel


def test_complaint_capped():
    bd = compute_confidence(QueryType.COMPLAINT, SourceChannel.DIRECT, "AC not working unacceptable", "NIS-001")
    assert bd.final_score <= 0.50
    assert bd.complaint_cap_applied is True


def test_direct_higher_than_instagram():
    d = compute_confidence(QueryType.GENERAL_ENQUIRY, SourceChannel.DIRECT, "Do you allow pets?", None)
    i = compute_confidence(QueryType.GENERAL_ENQUIRY, SourceChannel.INSTAGRAM, "Do you allow pets?", None)
    assert d.channel_reliability > i.channel_reliability


def test_booking_ref_boosts():
    # Use POST_SALES_CHECKIN but NO direct-answer keywords (no wifi/password/checkin/pool/caretaker/chef)
    # so the 0.88 floor is NOT triggered — only the BOOKING_REF_BONUS distinguishes scores
    with_ref    = compute_confidence(QueryType.POST_SALES_CHECKIN, SourceChannel.WHATSAPP, "What time is breakfast served?", "NIS-001")
    without_ref = compute_confidence(QueryType.POST_SALES_CHECKIN, SourceChannel.WHATSAPP, "What time is breakfast served?", None)
    assert with_ref.final_score > without_ref.final_score


def test_always_in_bounds():
    for qt in QueryType:
        for ch in SourceChannel:
            bd = compute_confidence(qt, ch, "test", None)
            assert 0.0 <= bd.final_score <= 1.0