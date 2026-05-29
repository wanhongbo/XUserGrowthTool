from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass

from app.models import XPost, XUser

KEYWORDS = {
    "privacy": 1.0,
    "signal": 1.0,
    "proton": 1.0,
    "end-to-end encryption": 1.2,
    "e2ee": 1.2,
    "cybersecurity": 1.0,
    "infosec": 1.0,
    "surveillance": 0.9,
    "data broker": 1.1,
    "zero knowledge": 1.1,
    "threat model": 1.1,
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

    final = max(0.0, (relevance * 0.34) + (activity * 0.18) + (influence * 0.18) + (intent * 0.22) - (risk * 0.28))
    reason_bits = []
    if hits:
        reason_bits.append(f"topic hits: {', '.join(hits)}")
    reason_bits.append(f"{len(posts)} recent matching post(s)")
    if intent_post:
        reason_bits.append("public intent signal detected")
    if user.verified:
        reason_bits.append("verified account")
    if risk:
        reason_bits.append(f"risk flags: {int(risk)}")

    dm_eligible = bool(dm_intent_post and not user.opt_out and risk < 60)
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
    )

