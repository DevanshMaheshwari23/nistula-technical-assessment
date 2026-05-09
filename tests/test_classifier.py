from src.services.classifier import classify
from src.models.schemas import QueryType

def test_ac_not_working():      assert classify("The AC is not working") == QueryType.COMPLAINT
def test_unacceptable():        assert classify("This is unacceptable I want a refund") == QueryType.COMPLAINT
def test_no_hot_water():        assert classify("There is no hot water this is terrible") == QueryType.COMPLAINT
def test_wifi_not_working():    assert classify("WiFi not working since morning") == QueryType.COMPLAINT
def test_availability():        assert classify("Is villa available April 20 to 24?") == QueryType.PRE_SALES_AVAILABILITY
def test_booking():             assert classify("Can we book from 20 Apr to 24 Apr?") == QueryType.PRE_SALES_AVAILABILITY
def test_rate():                assert classify("What is the rate for 2 adults 3 nights?") == QueryType.PRE_SALES_PRICING
def test_how_much():            assert classify("How much does it cost for 5 guests?") == QueryType.PRE_SALES_PRICING
def test_wifi_password():       assert classify("What is the WiFi password?") == QueryType.POST_SALES_CHECKIN
def test_checkin_time():        assert classify("What time can we check in tomorrow?") == QueryType.POST_SALES_CHECKIN
def test_airport_transfer():    assert classify("Can you arrange an airport transfer?") == QueryType.SPECIAL_REQUEST
def test_birthday():            assert classify("It is my wife birthday can you arrange a surprise?") == QueryType.SPECIAL_REQUEST
def test_pets():                assert classify("Do you allow pets at the villa?") == QueryType.GENERAL_ENQUIRY
def test_parking():             assert classify("Is there parking available?") == QueryType.GENERAL_ENQUIRY
def test_empty_general():       assert classify("Hello I have a question") == QueryType.GENERAL_ENQUIRY