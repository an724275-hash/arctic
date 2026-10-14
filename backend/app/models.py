from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def uid() -> str:
    return str(uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class IdMixin:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)


class User(IdMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('participant','teacher','expert','commission','admin','partner')"),
    )
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20), default="participant", index=True)
    birth_date: Mapped[date | None] = mapped_column(Date)
    school: Mapped[str | None] = mapped_column(String(250))
    grade: Mapped[int | None] = mapped_column(Integer)
    region: Mapped[str | None] = mapped_column(String(150), index=True)
    city: Mapped[str | None] = mapped_column(String(150))
    avatar_kind: Mapped[str] = mapped_column(String(20), default="bear", server_default="bear")
    avatar_filename: Mapped[str | None] = mapped_column(String(100))
    guardian_name: Mapped[str | None] = mapped_column(String(200))
    guardian_email: Mapped[str | None] = mapped_column(String(320))
    consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    guardian_consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    token_version: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RefreshToken(IdMixin, Base):
    __tablename__ = "refresh_tokens"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ActionToken(IdMixin, Base):
    __tablename__ = "action_tokens"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(40), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TeacherLink(IdMixin, Base):
    __tablename__ = "teacher_links"
    participant_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    teacher_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="accepted")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class QuizConfig(Base):
    __tablename__ = "quiz_config"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    title: Mapped[str] = mapped_column(String(250), default="Удивительная и неизведанная Арктика")
    question_count: Mapped[int] = mapped_column(Integer, default=5)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=600)
    pass_percent: Mapped[float] = mapped_column(Float, default=60)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class Question(IdMixin, Base):
    __tablename__ = "questions"
    text: Mapped[str] = mapped_column(Text)
    options: Mapped[list] = mapped_column(JSONB)
    correct_option_ids: Mapped[list] = mapped_column(JSONB)
    topic: Mapped[str] = mapped_column(String(150), default="Арктика")
    difficulty: Mapped[str] = mapped_column(String(20), default="easy")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    explanation: Mapped[str] = mapped_column(Text, default="")


class QuizAttempt(IdMixin, Base):
    __tablename__ = "quiz_attempts"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    questions: Mapped[list] = mapped_column(JSONB)
    config_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict)
    answers: Mapped[dict] = mapped_column(JSONB, default=dict)
    score_percent: Mapped[float | None] = mapped_column(Float)
    passed: Mapped[bool | None] = mapped_column(Boolean)


class Nomination(IdMixin, Base):
    __tablename__ = "nominations"
    title: Mapped[str] = mapped_column(String(250), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ExpertNomination(Base):
    __tablename__ = "expert_nominations"
    expert_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    nomination_id: Mapped[str] = mapped_column(
        ForeignKey("nominations.id", ondelete="CASCADE"), primary_key=True
    )


class Project(IdMixin, Base):
    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint("status IN ('draft','submitted','admitted','rejected','reviewing','evaluated')"),
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    nomination_id: Mapped[str] = mapped_column(ForeignKey("nominations.id"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    abstract: Mapped[str] = mapped_column(Text, default="")
    video_url: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    moderation_comment: Mapped[str | None] = mapped_column(Text)
    reviews_released: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Upload(IdMixin, Base):
    __tablename__ = "uploads"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    uploaded_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    original_name: Mapped[str] = mapped_column(String(250))
    stored_name: Mapped[str] = mapped_column(String(100), unique=True)
    media_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Criterion(IdMixin, Base):
    __tablename__ = "criteria"
    __table_args__ = (CheckConstraint("max_score > 0 AND weight > 0"),)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    max_score: Mapped[float] = mapped_column(Float, default=10)
    weight: Mapped[float] = mapped_column(Float, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Assignment(IdMixin, Base):
    __tablename__ = "assignments"
    __table_args__ = (UniqueConstraint("project_id", "expert_id"),)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    expert_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Review(IdMixin, Base):
    __tablename__ = "reviews"
    assignment_id: Mapped[str] = mapped_column(ForeignKey("assignments.id", ondelete="CASCADE"), unique=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    expert_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    criteria_snapshot: Mapped[list] = mapped_column(JSONB)
    scores: Mapped[dict] = mapped_column(JSONB)
    comment: Mapped[str] = mapped_column(Text, default="")
    weighted_score: Mapped[float] = mapped_column(Float)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Certificate(IdMixin, Base):
    __tablename__ = "certificates"
    number: Mapped[str] = mapped_column(String(100), unique=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    attempt_id: Mapped[str | None] = mapped_column(
        ForeignKey("quiz_attempts.id", ondelete="SET NULL"), unique=True
    )
    kind: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(300))
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    public_token: Mapped[str] = mapped_column(String(100), unique=True)
    mentor_name: Mapped[str | None] = mapped_column(String(200))


class Defense(IdMixin, Base):
    __tablename__ = "defenses"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), unique=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    join_url: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, default="")


class Content(IdMixin, Base):
    __tablename__ = "content"
    slug: Mapped[str] = mapped_column(String(160), unique=True)
    title: Mapped[str] = mapped_column(String(300))
    kind: Mapped[str] = mapped_column(String(30), index=True)
    body: Mapped[str] = mapped_column(Text, default="")
    excerpt: Mapped[str] = mapped_column(Text, default="")
    image_url: Mapped[str | None] = mapped_column(Text)
    extra: Mapped[dict] = mapped_column(JSONB, default=dict)
    published: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Stage(IdMixin, Base):
    __tablename__ = "stages"
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    title: Mapped[str] = mapped_column(String(200))
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    position: Mapped[int] = mapped_column(Integer, default=0)


class ContactMessage(IdMixin, Base):
    __tablename__ = "contact_messages"
    kind: Mapped[str] = mapped_column(String(30), default="feedback")
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(320))
    message: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="new")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Notification(IdMixin, Base):
    __tablename__ = "notifications"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(250))
    body: Mapped[str] = mapped_column(Text)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Outbox(IdMixin, Base):
    __tablename__ = "outbox"
    recipient: Mapped[str] = mapped_column(String(320))
    subject: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditLog(IdMixin, Base):
    __tablename__ = "audit_logs"
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(100))
    entity_id: Mapped[str | None] = mapped_column(String(100))
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AssistantRequest(IdMixin, Base):
    __tablename__ = "assistant_requests"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
