from app.models import XPost, XUser
from app.services.scoring import score_user


def test_dm_eligibility_requires_explicit_contact_signal():
    user = XUser(x_user_id="1", username="a", bio="privacy and Signal", metrics_json='{"followers_count": 1000}')
    post = XPost(x_post_id="10", author=user, text="Looking for E2EE examples. My DMs are open.", text_hash="x")
    result = score_user(user, [post])
    assert result.dm_eligible is True
    assert result.evidence_post_id == "10"


def test_interest_without_dm_signal_is_not_dm_eligible():
    user = XUser(x_user_id="2", username="b", bio="privacy and cybersecurity", metrics_json='{"followers_count": 1000}')
    post = XPost(x_post_id="20", author=user, text="Any recommendations for privacy-preserving analytics?", text_hash="x")
    result = score_user(user, [post])
    assert result.intent > 40
    assert result.dm_eligible is False


def test_spam_risk_reduces_score():
    user = XUser(x_user_id="3", username="c", bio="follow for follow cybersecurity discount code", metrics_json='{"followers_count": 5}')
    post = XPost(x_post_id="30", author=user, text="Cybersecurity affiliate discount code. Follow for follow.", text_hash="x")
    result = score_user(user, [post])
    assert result.risk >= 45
    assert result.final_score < 35

