from app.services.x_api import DEFAULT_QUERIES


def test_default_live_queries_are_photo_privacy_queries():
    assert DEFAULT_QUERIES
    assert all("lang:en" in query for query in DEFAULT_QUERIES)
    assert any("photo vault" in query for query in DEFAULT_QUERIES)
    assert any("Google Photos alternative" in query for query in DEFAULT_QUERIES)
