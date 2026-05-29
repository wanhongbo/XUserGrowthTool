from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass

from app.models import XPost, XUser

KEYWORDS = {
    "private photos": 1.5,
    "photo vault": 1.6,
    "secure photo storage": 1.6,
    "encrypted photos": 1.6,
    "encrypted gallery": 1.5,
    "private gallery": 1.4,
    "secure gallery": 1.3,
    "hidden photos": 1.2,
    "hide photos": 1.2,
    "photo privacy": 1.4,
    "photo backup privacy": 1.5,
    "google photos alternative": 1.6,
    "icloud photos privacy": 1.5,
    "exif privacy": 1.3,
    "metadata removal": 1.2,
    "remove location from photos": 1.4,
    "end-to-end encrypted photos": 1.7,
    "encrypted photo backup": 1.6,
    "cloud photo privacy": 1.4,
    "private family photos": 1.4,
}

INTENT_PATTERNS = [
    r"\bdm me\b",
    r"\bmy dms are open\b",
    r"\bcontact me\b",
    r"\breach out\b",
    r"\blooking for\b",
    r"\bany recommendations\b",
    r"\bcan someone recommend\b",
    r"\bneed a (tool|product|service|solution)\b",
    r"\balternative to\b",
    r"\bswitching from\b",
    r"\btired of google photos\b",
    r"\bsecure backup\b",
    r"\bhow (do|can) i hide photos\b",
]

DM_INTENT_PATTERNS = [
    r"\bdm me\b",
    r"\bmy dms are open\b",
    r"\bcontact me\b",
    r"\breach out\b",
    r"\bsend me a dm\b",
]

RISK_PATTERNS = [
    r"\bfollow for follow\b",
    r"\bbuy followers\b",
    r"\bairdrop\b",
    r"\bcasino\b",
    r"\bnsfw\b",
    r"\bdiscount code\b",
    r"\baffiliate\b",
]


@dataclass
class ScoreResult:
    relevance: float
    activity: float
    influence: float
    intent: float
    risk: float
    final_score: float
    reason: str
    dm_eligible: bool
    dm_reason: str
    evidence_post_id: str
    product_relevant: bool


def _contains_any(patterns: list[str], text: str) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def _keyword_score(text: str) -> tuple[float, list[str]]:
    lower = text.lower()
    hits = [term for term in KEYWORDS if term in lower]
    raw = sum(KEYWORDS[term] for term in hits)
    return min(100.0, raw * 18), hits[:6]


def _metrics(user: XUser) -> dict:
    try:
        return json.loads(user.metrics_json or "{}")
    except json.JSONDecodeError:
        return {}


def score_user(user: XUser, posts: list[XPost]) -> ScoreResult:
    corpus = " ".join([user.bio or "", *[post.text for post in posts]])
    relevance, hits = _keyword_score(corpus)
    product_relevant = bool(hits)
    activity = min(100.0, len(posts) * 18)

    metrics = _metrics(user)
    followers = int(metrics.get("followers_count", 0) or 0)
    influence = min(100.0, math.log10(max(followers, 1)) * 22)
    if user.verified:
        influence = min(100.0, influence + 8)

    intent_post = next((post for post in posts if _contains_any(INTENT_PATTERNS, post.text)), None)
    dm_intent_post = next((post for post in posts if _contains_any(DM_INTENT_PATTERNS, post.text)), None)
    intent = 85.0 if dm_intent_post else 55.0 if intent_post else 12.0

    risk = 0.0
    if _contains_any(RISK_PATTERNS, corpus):
        risk += 45
    if user.protected:
        risk += 20
    if user.opt_out:
        risk = 100
    if followers < 10 and len(posts) > 3:
        risk += 20
    risk = min(100.0, risk)

    final = max(0.0, (relevance * 0.38) + (activity * 0.14) + (influence * 0.16) + (intent * 0.24) - (risk * 0.34))
    reason_bits = []
    if hits:
        reason_bits.append(f"topic hits: {', '.join(hits)}")
    else:
        reason_bits.append("no photo privacy product keyword hit")
    reason_bits.append(f"{len(posts)} recent matching post(s)")
    if intent_post:
        reason_bits.append("public intent signal detected")
    if user.verified:
        reason_bits.append("verified account")
    if risk:
        reason_bits.append(f"risk flags: {int(risk)}")

    dm_eligible = bool(product_relevant and dm_intent_post and not user.opt_out and risk < 40)
    if dm_eligible:
        dm_reason = "User publicly indicated they are open to contact/DM."
        evidence_post_id = dm_intent_post.x_post_id
    elif user.opt_out:
        dm_reason = "User is opted out."
        evidence_post_id = ""
    else:
        dm_reason = "No explicit public DM/contact intent found."
        evidence_post_id = ""

    return ScoreResult(
        relevance=round(relevance, 1),
        activity=round(activity, 1),
        influence=round(influence, 1),
        intent=round(intent, 1),
        risk=round(risk, 1),
        final_score=round(final, 1),
        reason="; ".join(reason_bits),
        dm_eligible=dm_eligible,
        dm_reason=dm_reason,
        evidence_post_id=evidence_post_id,
        product_relevant=product_relevant,
    )
