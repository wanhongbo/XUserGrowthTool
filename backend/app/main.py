from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.auth import create_token, require_auth
from app.config import get_cors_origins, get_settings
from app.database import Base, engine, get_db
from app.models import AuditEvent, DmEligibility, EngagementTask, LeadScore, TaskStatus, TaskType, XPost, XUser
from app.schemas import AuthOut, CleanupResult, DiscoveryRequest, DiscoveryResult, LeadCandidateOut, LoginRequest, OptOutRequest, OverviewOut, TaskOut, TaskUpdate
from app.serializers import post_out, task_out, user_out
from app.services.discovery import run_x_discovery
from app.services.drafts import draft_for_task
from app.services.x_api import XApiError


Base.metadata.create_all(bind=engine)
settings = get_settings()

app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"ok": True, "app": settings.app_name}


@app.post("/api/auth/login", response_model=AuthOut)
def login(request: LoginRequest) -> dict:
    email = request.email.strip().lower()
    if email != settings.allowed_login_email.lower():
        raise HTTPException(status_code=403, detail="This email is not allowed")
    return {
        "email": email,
        "token": create_token(email),
        "expires_in": settings.auth_token_ttl_seconds,
    }


@app.get("/api/auth/me")
def me(email: str = Depends(require_auth)) -> dict:
    return {"email": email}


@app.get("/api/overview", response_model=OverviewOut)
def overview(_: str = Depends(require_auth), db: Session = Depends(get_db)) -> dict:
    live_task_ids = select(EngagementTask.id).join(XPost, EngagementTask.source_post_id == XPost.x_post_id).where(XPost.query_source != "sample")
    lead_user_ids = (
        select(EngagementTask.user_id)
        .join(XPost, EngagementTask.source_post_id == XPost.x_post_id)
        .where(
            XPost.query_source != "sample",
            EngagementTask.status.not_in([TaskStatus.done, TaskStatus.rejected, TaskStatus.opt_out]),
        )
        .distinct()
    )
    leads = db.scalar(select(func.count(XUser.id)).where(XUser.id.in_(lead_user_ids))) or 0
    review_tasks = db.scalar(select(func.count(EngagementTask.id)).where(EngagementTask.id.in_(live_task_ids), EngagementTask.status == TaskStatus.review)) or 0
    public_tasks = db.scalar(select(func.count(EngagementTask.id)).where(EngagementTask.id.in_(live_task_ids), EngagementTask.task_type == TaskType.public_interaction)) or 0
    dm_tasks = db.scalar(select(func.count(EngagementTask.id)).where(EngagementTask.id.in_(live_task_ids), EngagementTask.task_type == TaskType.dm_draft)) or 0
    opt_outs = db.scalar(select(func.count(XUser.id)).where(XUser.opt_out.is_(True))) or 0
    compliance_blocks = db.scalar(select(func.count(DmEligibility.id)).where(DmEligibility.is_eligible.is_(False))) or 0
    return {
        "leads": leads,
        "review_tasks": review_tasks,
        "public_tasks": public_tasks,
        "dm_tasks": dm_tasks,
        "opt_outs": opt_outs,
        "compliance_blocks": compliance_blocks,
    }


@app.post("/api/discover/run", response_model=DiscoveryResult)
async def discover(request: DiscoveryRequest, _: str = Depends(require_auth), db: Session = Depends(get_db)) -> dict:
    mode = request.mode or "x_api"
    if mode == "x_api":
        try:
            users, posts, tasks, warnings = await run_x_discovery(db, request.queries, request.max_results)
        except XApiError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return {"mode": mode, "users_upserted": users, "posts_upserted": posts, "tasks_created": tasks, "warnings": warnings}
    raise HTTPException(status_code=400, detail="Unsupported discovery mode")


@app.delete("/api/sample-data", response_model=CleanupResult)
def delete_sample_data(_: str = Depends(require_auth), db: Session = Depends(get_db)) -> dict:
    sample_posts = db.scalars(select(XPost).where(XPost.query_source == "sample")).all()
    sample_post_ids = {post.x_post_id for post in sample_posts}
    sample_author_ids = {post.author_id for post in sample_posts}

    tasks = db.scalars(select(EngagementTask).where(EngagementTask.source_post_id.in_(sample_post_ids))).all() if sample_post_ids else []
    for task in tasks:
        db.delete(task)
    for post in sample_posts:
        db.delete(post)
    db.flush()

    users_deleted = 0
    for user_id in sample_author_ids:
        remaining_posts = db.scalar(select(func.count(XPost.id)).where(XPost.author_id == user_id)) or 0
        if remaining_posts:
            continue
        for model in (LeadScore, DmEligibility):
            record = db.scalar(select(model).where(model.user_id == user_id))
            if record:
                db.delete(record)
        user = db.get(XUser, user_id)
        if user:
            db.delete(user)
            users_deleted += 1

    db.add(AuditEvent(action="sample.cleanup", entity_type="sample_data", entity_id="sample", detail=f"Deleted {len(sample_posts)} sample posts"))
    db.commit()
    return {"sample_posts_deleted": len(sample_posts), "tasks_deleted": len(tasks), "users_deleted": users_deleted}


@app.get("/api/leads", response_model=list[LeadCandidateOut])
def leads(_: str = Depends(require_auth), db: Session = Depends(get_db)) -> list[dict]:
    active_lead_user_ids = (
        select(EngagementTask.user_id)
        .join(XPost, EngagementTask.source_post_id == XPost.x_post_id)
        .where(
            XPost.query_source != "sample",
            EngagementTask.status.not_in([TaskStatus.done, TaskStatus.rejected, TaskStatus.opt_out]),
        )
        .distinct()
    )
    users = db.scalars(
        select(XUser)
        .options(joinedload(XUser.score), joinedload(XUser.dm_eligibility))
        .where(XUser.id.in_(active_lead_user_ids))
        .outerjoin(LeadScore)
        .order_by(func.coalesce(LeadScore.final_score, 0).desc())
    ).unique().all()
    output = []
    for user in users:
        posts = db.scalars(select(XPost).where(XPost.author_id == user.id, XPost.query_source != "sample").order_by(XPost.created_at.desc()).limit(3)).all()
        open_tasks = db.scalar(
            select(func.count(EngagementTask.id)).where(
                EngagementTask.user_id == user.id,
                EngagementTask.status.not_in([TaskStatus.done, TaskStatus.rejected, TaskStatus.opt_out]),
            )
        ) or 0
        output.append({"user": user_out(user), "posts": [post_out(post) for post in posts], "open_tasks": open_tasks})
    return output


@app.get("/api/tasks", response_model=list[TaskOut])
def tasks(status: TaskStatus | None = None, task_type: TaskType | None = None, _: str = Depends(require_auth), db: Session = Depends(get_db)) -> list[dict]:
    query = (
        select(EngagementTask)
        .join(XPost, EngagementTask.source_post_id == XPost.x_post_id)
        .where(XPost.query_source != "sample")
        .options(
            joinedload(EngagementTask.user).joinedload(XUser.score),
            joinedload(EngagementTask.user).joinedload(XUser.dm_eligibility),
        )
    )
    if status:
        query = query.where(EngagementTask.status == status)
    if task_type:
        query = query.where(EngagementTask.task_type == task_type)
    rows = db.scalars(query.order_by(EngagementTask.updated_at.desc())).unique().all()
    output = []
    for task in rows:
        source_post = db.scalar(select(XPost).where(XPost.x_post_id == task.source_post_id))
        output.append(task_out(task, source_post))
    return output


@app.patch("/api/tasks/{task_id}", response_model=TaskOut)
def update_task(task_id: int, update: TaskUpdate, _: str = Depends(require_auth), db: Session = Depends(get_db)) -> dict:
    task = db.scalar(
        select(EngagementTask)
        .where(EngagementTask.id == task_id)
        .options(joinedload(EngagementTask.user).joinedload(XUser.score), joinedload(EngagementTask.user).joinedload(XUser.dm_eligibility))
    )
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if update.status:
        if update.status in {TaskStatus.dm_eligible, TaskStatus.dm_draft, TaskStatus.done} and task.task_type == TaskType.dm_draft:
            eligibility = task.user.dm_eligibility
            if not eligibility or not eligibility.is_eligible or task.user.opt_out:
                raise HTTPException(status_code=409, detail="DM task is blocked because explicit DM/contact eligibility is missing or user opted out")
        task.status = update.status
    if update.assigned_to is not None:
        task.assigned_to = update.assigned_to
    if update.draft is not None:
        task.draft = update.draft
    if update.review_notes is not None:
        task.review_notes = update.review_notes
    db.add(AuditEvent(actor=update.actor, action="task.update", entity_type="engagement_task", entity_id=str(task.id), detail=f"status={task.status}"))
    db.commit()
    db.refresh(task)
    source_post = db.scalar(select(XPost).where(XPost.x_post_id == task.source_post_id))
    return task_out(task, source_post)


@app.post("/api/tasks/{task_id}/generate-draft", response_model=TaskOut)
def regenerate_draft(task_id: int, actor: str = "operator", _: str = Depends(require_auth), db: Session = Depends(get_db)) -> dict:
    task = db.scalar(
        select(EngagementTask)
        .where(EngagementTask.id == task_id)
        .options(joinedload(EngagementTask.user).joinedload(XUser.score), joinedload(EngagementTask.user).joinedload(XUser.dm_eligibility))
    )
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.task_type == TaskType.dm_draft:
        eligibility = task.user.dm_eligibility
        if not eligibility or not eligibility.is_eligible or task.user.opt_out:
            raise HTTPException(status_code=409, detail="DM draft generation blocked by compliance gate")
    source_post = db.scalar(select(XPost).where(XPost.x_post_id == task.source_post_id))
    task.draft = draft_for_task(task.task_type, task.user, source_post)
    db.add(AuditEvent(actor=actor, action="task.generate_draft", entity_type="engagement_task", entity_id=str(task.id), detail="Draft regenerated"))
    db.commit()
    db.refresh(task)
    return task_out(task, source_post)


@app.post("/api/opt-outs")
def opt_out(request: OptOutRequest, _: str = Depends(require_auth), db: Session = Depends(get_db)) -> dict:
    user = db.scalar(select(XUser).where(XUser.x_user_id == request.x_user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.opt_out = True
    eligibility = db.scalar(select(DmEligibility).where(DmEligibility.user_id == user.id))
    if eligibility:
        eligibility.opt_out = True
        eligibility.is_eligible = False
        eligibility.reason = "User opted out."
    for task in db.scalars(select(EngagementTask).where(EngagementTask.user_id == user.id)).all():
        task.status = TaskStatus.opt_out
        task.compliance_warning = "User opted out. Do not contact again."
    db.add(AuditEvent(actor=request.actor, action="user.opt_out", entity_type="x_user", entity_id=user.x_user_id, detail=request.reason))
    db.commit()
    return {"ok": True}
