from app.models import XPost, XUser
from app.services.scoring import score_user


def test_dm_eligibility_requires_explicit_contact_signal():
    user = XUser(x_user_id="1", username="a", bio="private photo vault builder", metrics_json='{"followers_count": 1000}')
    post = XPost(x_post_id="10", author=user, text="Looking for encrypted photos examples. My DMs are open.", text_hash="x")
    result = score_user(user, [post])
    assert result.dm_eligible is True
    assert result.evidence_post_id == "10"
    assert result.product_relevant is True


def test_interest_without_dm_signal_is_not_dm_eligible():
    user = XUser(x_user_id="2", username="b", bio="photo privacy and secure gallery", metrics_json='{"followers_count": 1000}')
    post = XPost(x_post_id="20", author=user, text="Any recommendations for encrypted photo backup?", text_hash="x")
    result = score_user(user, [post])
    assert result.intent > 40
    assert result.dm_eligible is False
    assert result.product_relevant is True


def test_spam_risk_reduces_score():
    user = XUser(x_user_id="3", username="c", bio="follow for follow photo vault discount code", metrics_json='{"followers_count": 5}')
    post = XPost(x_post_id="30", author=user, text="Private photos affiliate discount code. Follow for follow.", text_hash="x")
    result = score_user(user, [post])
    assert result.risk >= 45
    assert result.final_score < 45


def test_broad_privacy_security_without_photo_keyword_is_not_product_relevant():
    user = XUser(x_user_id="4", username="d", bio="privacy and cybersecurity", metrics_json='{"followers_count": 5000}')
    post = XPost(x_post_id="40", author=user, text="Any recommendations for privacy-preserving analytics?", text_hash="x")
    result = score_user(user, [post])
    assert result.product_relevant is False
    assert result.relevance == 0
