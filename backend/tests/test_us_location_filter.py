from app.services.discovery import is_probably_non_us_user, is_probably_us_user, us_confidence_for_user


def test_us_profile_locations_are_accepted():
    assert is_probably_us_user({"location": "New York, NY"})
    assert is_probably_us_user({"location": "San Francisco, CA"})
    assert is_probably_us_user({"location": "USA"})
    assert is_probably_us_user({"location": "Austin, Texas"})
    assert us_confidence_for_user({"location": "New York, NY"}) == "high"


def test_empty_location_is_unknown_not_us():
    assert not is_probably_us_user({"location": ""})
    assert not is_probably_non_us_user({"location": ""})
    assert us_confidence_for_user({"location": ""}) == "unknown"


def test_non_us_profile_locations_are_rejected():
    assert not is_probably_us_user({"location": "Ho Chi Minh City, Vietnam"})
    assert not is_probably_us_user({"location": "London, UK"})
    assert is_probably_non_us_user({"location": "Ho Chi Minh City, Vietnam"})
    assert is_probably_non_us_user({"location": "London, UK"})
    assert us_confidence_for_user({"location": "London, UK"}) == "non_us"


def test_us_location_takes_precedence_over_short_state_tokens():
    assert is_probably_us_user({"location": "Portland, OR"})
    assert not is_probably_non_us_user({"location": "Portland, OR"})
