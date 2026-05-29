from app.services.discovery import is_probably_us_user


def test_us_profile_locations_are_accepted():
    assert is_probably_us_user({"location": "New York, NY"})
    assert is_probably_us_user({"location": "San Francisco, CA"})
    assert is_probably_us_user({"location": "USA"})
    assert is_probably_us_user({"location": "Austin, Texas"})


def test_non_us_or_empty_locations_are_rejected():
    assert not is_probably_us_user({"location": ""})
    assert not is_probably_us_user({"location": "Ho Chi Minh City, Vietnam"})
    assert not is_probably_us_user({"location": "London, UK"})

