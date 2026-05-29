from __future__ import annotations

import hashlib
import json
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import AuditEvent, DmEligibility, EngagementTask, LeadScore, TaskStatus, TaskType, XPost, XUser
from app.services.drafts import draft_for_task
from app.services.scoring import score_user
from app.services.x_api import DEFAULT_QUERIES, XApiClient, parse_x_datetime


SAMPLE_USERS = [
    {
        "id": "1001",
        "username": "privacyrosa",
        "name": "Rosa Chen",
        "description": "Privacy engineer. E2EE, usable security, anti-surveillance.",
        "public_metrics": {"followers_count": 8200, "following_count": 640, "tweet_count": 12900},
        "verified": True,
        "verified_type": "blue",
        "receives_your_dm": True,
        "protected": False,
        "posts": [
            "Threat model first, tool second. Still looking for good examples of zero knowledge onboarding that normal people understand. My DMs are open for examples.",
            "Signal gets the human side of privacy right more often than most security products.",
        ],
    },
    {
        "id": "1002",
        "username": "packetjanitor",
        "name": "Mika",
        "description": "Cybersecurity analyst, detection engineering, privacy curious.",
        "public_metrics": {"followers_count": 2300, "following_count": 990, "tweet_count": 4200},
        "verified": False,
        "verified_type": "",
        "receives_your_dm": False,
        "protected": False,
        "posts": [
            "Any recommendations for privacy-preserving analytics that do not become a data broker nightmare?",
            "Infosec tooling still underestimates UX costs.",
        ],
    },
    {
        "id": "1003",
        "username": "growthblast",
        "name": "Growth Blast",
        "description": "Discount code affiliate growth. Follow for follow and buy followers.",
        "public_metrics": {"followers_count": 52, "following_count": 9001, "tweet_count": 76000},
        "verified": False,
        "verified_type": "",
        "receives_your_dm": True,
        "protected": False,
        "posts": [
            "Cybersecurity affiliate discount code. Follow for follow.",
        ],
    },
]


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _upsert_user(db: Session, payload: dict) -> XUser:
    x_user_id = str(payload["id"])
    user = db.scalar(select(XUser).where(XUser.x_user_id == x_user_id))
    if not user:
        user = XUser(x_user_id=x_user_id, username=payload.get("username", ""))
        db.add(user)
    user.username = payload.get("username", user.username)
    user.name = payload.get("name", "")
    user.bio = payload.get("description", "")
    user.location = payload.get("location", "") or ""
    user.url = payload.get("url", "") or ""
    user.profile_image_url = payload.get("profile_image_url", "") or ""
    user.metrics_json = json.dumps(payload.get("public_metrics", {}))
    user.dm_capability = bool(payload.get("receives_your_dm", False))
    user.verified = bool(payload.get("verified", False))
    user.verified_type = payload.get("verified_type", "") or ""
    user.protected = bool(payload.get("protected", False))
    user.last_seen = datetime.utcnow()
    return user


def _upsert_post(db: Session, user: XUser, payload: dict, query_source: str) -> XPost:
    x_post_id = str(payload["id"])
    post = db.scalar(select(XPost).where(XPost.x_post_id == x_post_id))
    if not post:
        post = XPost(x_post_id=x_post_id, author=user)
        db.add(post)
    text = payload.get("text", "")
    post.author = user
    post.text = text
    post.text_hash = _hash_text(text)
    post.lang = payload.get("lang", "en") or ""
    post.metrics_json = json.dumps(payload.get("public_metrics", {}))
    post.query_source = query_source
    post.source_url = f"https://x.com/{user.username}/status/{x_post_id}"
    post.created_at = parse_x_datetime(payload.get("created_at"))
    post.captured_at = datetime.utcnow()
    return post


def _score_and_task(db: Session, user: XUser) -> int:
    posts = list(db.scalars(select(XPost).where(XPost.author_id == user.id).order_by(XPost.created_at.desc())).all())
    result = score_user(user, posts)
    score = db.scalar(select(LeadScore).where(LeadScore.user_id == user.id))
    if not score:
        score = LeadScore(user=user)
        db.add(score)
    score.relevance = result.relevance
    score.activity = result.activity
    score.influence = result.influence
    score.intent = result.intent
    score.risk = result.risk
    score.final_score = result.final_score
    score.reason = result.reason

    eligibility = db.scalar(select(DmEligibility).where(DmEligibility.user_id == user.id))
    if not eligibility:
        eligibility = DmEligibility(user=user)
        db.add(eligibility)
    eligibility.is_eligible = result.dm_eligible
    eligibility.reason = result.dm_reason
    eligibility.evidence_post_id = result.evidence_post_id
    eligibility.opt_out = user.opt_out

    created = 0
    source_post = posts[0] if posts else None
    if result.final_score >= 35 and not user.opt_out and source_post:
        created += _ensure_task(db, user, TaskType.public_interaction, TaskStatus.review, source_post)
    if result.dm_eligible and source_post:
        evidence_post = next((post for post in posts if post.x_post_id == result.evidence_post_id), source_post)
        created += _ensure_task(db, user, TaskType.dm_draft, TaskStatus.dm_draft, evidence_post)
    return created


def _ensure_task(db: Session, user: XUser, task_type: TaskType, status: TaskStatus, source_post: XPost) -> int:
    existing = db.scalar(
        select(EngagementTask).where(
            EngagementTask.user_id == user.id,
            EngagementTask.task_type == task_type,
            EngagementTask.source_post_id == source_post.x_post_id,
        )
    )
    if existing:
        return 0
    if task_type == TaskType.dm_draft:
        eligibility = user.dm_eligibility
        if not eligibility or not eligibility.is_eligible or user.opt_out:
            return 0
    task = EngagementTask(
        user=user,
        task_type=task_type,
        status=status,
        source_post_id=source_post.x_post_id,
        draft=draft_for_task(task_type, user, source_post),
        compliance_warning=(
            "Human must manually send. No automated likes, follows, replies, or DMs."
            if task_type == TaskType.public_interaction
            else "DM draft allowed only because explicit contact intent evidence exists. Human review is required."
        ),
    )
    db.add(task)
    return 1


def run_sample_discovery(db: Session) -> tuple[int, int, int]:
    users, posts, tasks = 0, 0, 0
    for sample in SAMPLE_USERS:
        user = _upsert_user(db, sample)
        users += 1
        db.flush()
        for index, text in enumerate(sample["posts"]):
            _upsert_post(
                db,
                user,
                {
                    "id": f"{sample['id']}{index}",
                    "text": text,
                    "lang": "en",
                    "public_metrics": {"reply_count": 4 + index, "like_count": 20 + index * 11, "quote_count": index},
                    "created_at": datetime.utcnow().isoformat(),
                },
                "sample",
            )
            posts += 1
        db.flush()
        tasks += _score_and_task(db, user)
    db.add(AuditEvent(action="discovery.sample", entity_type="discovery", entity_id="sample", detail="Seeded sample discovery data"))
    db.commit()
    return users, posts, tasks


async def run_x_discovery(db: Session, queries: list[str] | None, max_results: int) -> tuple[int, int, int, list[str]]:
    settings = get_settings()
    client = XApiClient(settings.x_bearer_token)
    warnings: list[str] = []
    users_count = posts_count = tasks_count = 0

    for query in queries or DEFAULT_QUERIES:
        payload = await client.recent_search(query, max_results=max_results)
        users_by_id = {str(user["id"]): user for user in payload.get("includes", {}).get("users", [])}
        for post_payload in payload.get("data", []):
            author_payload = users_by_id.get(str(post_payload.get("author_id")))
            if not author_payload:
                warnings.append(f"Missing author for post {post_payload.get('id')}")
                continue
            user = _upsert_user(db, author_payload)
            users_count += 1
            db.flush()
            _upsert_post(db, user, post_payload, query)
            posts_count += 1
        db.flush()

    for user in db.scalars(select(XUser)).all():
        tasks_count += _score_and_task(db, user)
    db.add(AuditEvent(action="discovery.x_api", entity_type="discovery", entity_id="x_api", detail=f"Queries: {queries or DEFAULT_QUERIES}"))
    db.commit()
    return users_count, posts_count, tasks_count, warnings
