from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import Base, engine, get_db
from app.models import AuditEvent, DmEligibility, EngagementTask, LeadScore, TaskStatus, TaskType, XPost, XUser
from app.schemas import DiscoveryRequest, DiscoveryResult, LeadCandidateOut, OptOutRequest, OverviewOut, TaskOut, TaskUpdate
from app.serializers import post_out, task_out, user_out
from app.services.discovery import run_sample_discovery, run_x_discovery
from app.services.drafts import draft_for_task


Base.metadata.create_all(bind=engine)
settings = get_settings()

app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"ok": True, "app": settings.app_name}


@app.get("/api/overview", response_model=OverviewOut)
def overview(db: Session = Depends(get_db)) -> dict:
    leads = db.scalar(select(func.count(XUser.id))) or 0
    review_tasks = db.scalar(select(func.count(EngagementTask.id)).where(EngagementTask.status == TaskStatus.review)) or 0
    public_tasks = db.scalar(select(func.count(EngagementTask.id)).where(EngagementTask.task_type == TaskType.public_interaction)) or 0
    dm_tasks = db.scalar(select(func.count(EngagementTask.id)).where(EngagementTask.task_type == TaskType.dm_draft)) or 0
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
async def discover(request: DiscoveryRequest, db: Session = Depends(get_db)) -> dict:
    mode = request.mode or settings.discovery_mode
    if mode == "sample":
        users, posts, tasks = run_sample_discovery(db)
        return {"mode": mode, "users_upserted": users, "posts_upserted": posts, "tasks_created": tasks, "warnings": []}
    if mode == "x_api":
        users, posts, tasks, warnings = await run_x_discovery(db, request.queries, request.max_results)
        return {"mode": mode, "users_upserted": users, "posts_upserted": posts, "tasks_created": tasks, "warnings": warnings}
    raise HTTPException(status_code=400, detail="Unsupported discovery mode")


@app.get("/api/leads", response_model=list[LeadCandidateOut])
def leads(db: Session = Depends(get_db)) -> list[dict]:
    users = db.scalars(
        select(XUser)
        .options(joinedload(XUser.score), joinedload(XUser.dm_eligibility))
        .outerjoin(LeadScore)
        .order_by(func.coalesce(LeadScore.final_score, 0).desc())
    ).unique().all()
    output = []
    for user in users:
        posts = db.scalars(select(XPost).where(XPost.author_id == user.id).order_by(XPost.created_at.desc()).limit(3)).all()
        open_tasks = db.scalar(
            select(func.count(EngagementTask.id)).where(
                EngagementTask.user_id == user.id,
                EngagementTask.status.not_in([TaskStatus.done, TaskStatus.rejected, TaskStatus.opt_out]),
            )
        ) or 0
        output.append({"user": user_out(user), "posts": [post_out(post) for post in posts], "open_tasks": open_tasks})
    return output


@app.get("/api/tasks", response_model=list[TaskOut])
def tasks(status: TaskStatus | None = None, task_type: TaskType | None = None, db: Session = Depends(get_db)) -> list[dict]:
    query = select(EngagementTask).options(
        joinedload(EngagementTask.user).joinedload(XUser.score),
        joinedload(EngagementTask.user).joinedload(XUser.dm_eligibility),
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
def update_task(task_id: int, update: TaskUpdate, db: Session = Depends(get_db)) -> dict:
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
def regenerate_draft(task_id: int, actor: str = "operator", db: Session = Depends(get_db)) -> dict:
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
def opt_out(request: OptOutRequest, db: Session = Depends(get_db)) -> dict:
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
