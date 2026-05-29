from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TaskType(StrEnum):
    public_interaction = "public_interaction"
    dm_draft = "dm_draft"


class TaskStatus(StrEnum):
    review = "review"
    engage_publicly = "engage_publicly"
    dm_eligible = "dm_eligible"
    dm_draft = "dm_draft"
    done = "done"
    snoozed = "snoozed"
    rejected = "rejected"
    opt_out = "opt_out"


class XUser(Base):
    __tablename__ = "x_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    x_user_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    bio: Mapped[str] = mapped_column(Text, default="")
    location: Mapped[str] = mapped_column(String(255), default="")
    url: Mapped[str] = mapped_column(String(500), default="")
    profile_image_url: Mapped[str] = mapped_column(String(500), default="")
    metrics_json: Mapped[str] = mapped_column(Text, default="{}")
    dm_capability: Mapped[bool] = mapped_column(Boolean, default=False)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verified_type: Mapped[str] = mapped_column(String(64), default="")
    protected: Mapped[bool] = mapped_column(Boolean, default=False)
    opt_out: Mapped[bool] = mapped_column(Boolean, default=False)
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    posts: Mapped[list["XPost"]] = relationship(back_populates="author")
    score: Mapped["LeadScore | None"] = relationship(back_populates="user", uselist=False)
    dm_eligibility: Mapped["DmEligibility | None"] = relationship(back_populates="user", uselist=False)
    tasks: Mapped[list["EngagementTask"]] = relationship(back_populates="user")


class XPost(Base):
    __tablename__ = "x_posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    x_post_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("x_users.id"), index=True)
    text: Mapped[str] = mapped_column(Text, default="")
    text_hash: Mapped[str] = mapped_column(String(64), index=True)
    lang: Mapped[str] = mapped_column(String(16), default="")
    metrics_json: Mapped[str] = mapped_column(Text, default="{}")
    query_source: Mapped[str] = mapped_column(String(255), default="")
    source_url: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    author: Mapped[XUser] = relationship(back_populates="posts")


class LeadScore(Base):
    __tablename__ = "lead_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("x_users.id"), unique=True, index=True)
    relevance: Mapped[float] = mapped_column(Float, default=0)
    activity: Mapped[float] = mapped_column(Float, default=0)
    influence: Mapped[float] = mapped_column(Float, default=0)
    intent: Mapped[float] = mapped_column(Float, default=0)
    risk: Mapped[float] = mapped_column(Float, default=0)
    final_score: Mapped[float] = mapped_column(Float, default=0)
    reason: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user: Mapped[XUser] = relationship(back_populates="score")


class DmEligibility(Base):
    __tablename__ = "dm_eligibility"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("x_users.id"), unique=True, index=True)
    is_eligible: Mapped[bool] = mapped_column(Boolean, default=False)
    reason: Mapped[str] = mapped_column(Text, default="")
    evidence_post_id: Mapped[str] = mapped_column(String(64), default="")
    opt_out: Mapped[bool] = mapped_column(Boolean, default=False)
    last_contacted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user: Mapped[XUser] = relationship(back_populates="dm_eligibility")


class EngagementTask(Base):
    __tablename__ = "engagement_tasks"
    __table_args__ = (UniqueConstraint("user_id", "task_type", "source_post_id", name="uq_task_per_source"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("x_users.id"), index=True)
    task_type: Mapped[TaskType] = mapped_column(Enum(TaskType), index=True)
    status: Mapped[TaskStatus] = mapped_column(Enum(TaskStatus), default=TaskStatus.review, index=True)
    assigned_to: Mapped[str] = mapped_column(String(255), default="")
    source_post_id: Mapped[str] = mapped_column(String(64), default="")
    draft: Mapped[str] = mapped_column(Text, default="")
    review_notes: Mapped[str] = mapped_column(Text, default="")
    compliance_warning: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user: Mapped[XUser] = relationship(back_populates="tasks")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor: Mapped[str] = mapped_column(String(255), default="system")
    action: Mapped[str] = mapped_column(String(255))
    entity_type: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[str] = mapped_column(String(64))
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

