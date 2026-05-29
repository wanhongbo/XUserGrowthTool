import json

from app.models import DmEligibility, EngagementTask, LeadScore, XPost, XUser


def _json(value: str) -> dict:
    try:
        return json.loads(value or "{}")
    except json.JSONDecodeError:
        return {}


def score_out(score: LeadScore | None) -> dict | None:
    if not score:
        return None
    return {
        "relevance": score.relevance,
        "activity": score.activity,
        "influence": score.influence,
        "intent": score.intent,
        "risk": score.risk,
        "final_score": score.final_score,
        "reason": score.reason,
    }


def eligibility_out(eligibility: DmEligibility | None) -> dict | None:
    if not eligibility:
        return None
    return {
        "is_eligible": eligibility.is_eligible,
        "reason": eligibility.reason,
        "evidence_post_id": eligibility.evidence_post_id,
        "opt_out": eligibility.opt_out,
    }


def user_out(user: XUser) -> dict:
    return {
        "id": user.id,
        "x_user_id": user.x_user_id,
        "username": user.username,
        "name": user.name,
        "bio": user.bio,
        "location": user.location,
        "url": user.url,
        "dm_capability": user.dm_capability,
        "verified": user.verified,
        "verified_type": user.verified_type,
        "protected": user.protected,
        "opt_out": user.opt_out,
        "metrics": _json(user.metrics_json),
        "last_seen": user.last_seen,
        "score": score_out(user.score),
        "dm_eligibility": eligibility_out(user.dm_eligibility),
    }


def post_out(post: XPost) -> dict:
    return {
        "id": post.id,
        "x_post_id": post.x_post_id,
        "text": post.text,
        "lang": post.lang,
        "metrics": _json(post.metrics_json),
        "query_source": post.query_source,
        "source_url": post.source_url,
        "created_at": post.created_at,
    }


def task_out(task: EngagementTask, source_post: XPost | None = None) -> dict:
    return {
        "id": task.id,
        "task_type": task.task_type,
        "status": task.status,
        "assigned_to": task.assigned_to,
        "source_post_id": task.source_post_id,
        "draft": task.draft,
        "review_notes": task.review_notes,
        "compliance_warning": task.compliance_warning,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
        "user": user_out(task.user),
        "source_post": post_out(source_post) if source_post else None,
    }

