from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.models import TaskStatus, TaskType


class DiscoveryRequest(BaseModel):
    mode: Literal["sample", "x_api"] | None = None
    queries: list[str] | None = None
    max_results: int = Field(default=25, ge=10, le=100)


class DiscoveryResult(BaseModel):
    mode: str
    users_upserted: int
    posts_upserted: int
    tasks_created: int
    warnings: list[str] = []


class ScoreOut(BaseModel):
    relevance: float
    activity: float
    influence: float
    intent: float
    risk: float
    final_score: float
    reason: str


class DmEligibilityOut(BaseModel):
    is_eligible: bool
    reason: str
    evidence_post_id: str = ""
    opt_out: bool = False


class UserOut(BaseModel):
    id: int
    x_user_id: str
    username: str
    name: str
    bio: str
    location: str
    url: str
    dm_capability: bool
    verified: bool
    verified_type: str
    protected: bool
    opt_out: bool
    metrics: dict[str, Any]
    last_seen: datetime
    score: ScoreOut | None = None
    dm_eligibility: DmEligibilityOut | None = None


class PostOut(BaseModel):
    id: int
    x_post_id: str
    text: str
    lang: str
    metrics: dict[str, Any]
    query_source: str
    source_url: str
    created_at: datetime


class LeadCandidateOut(BaseModel):
    user: UserOut
    posts: list[PostOut]
    open_tasks: int


class TaskOut(BaseModel):
    id: int
    task_type: TaskType
    status: TaskStatus
    assigned_to: str
    source_post_id: str
    draft: str
    review_notes: str
    compliance_warning: str
    created_at: datetime
    updated_at: datetime
    user: UserOut
    source_post: PostOut | None = None


class TaskUpdate(BaseModel):
    status: TaskStatus | None = None
    assigned_to: str | None = None
    draft: str | None = None
    review_notes: str | None = None
    actor: str = "operator"


class OptOutRequest(BaseModel):
    x_user_id: str
    reason: str = ""
    actor: str = "operator"


class OverviewOut(BaseModel):
    leads: int
    review_tasks: int
    public_tasks: int
    dm_tasks: int
    opt_outs: int
    compliance_blocks: int

