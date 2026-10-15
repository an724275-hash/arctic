import hashlib
from datetime import timedelta
from uuid import UUID

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl
from sqlalchemy import delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.common import audit, stage_state
from app.auth_schemas import InputModel
from app.config import settings
from app.db import get_db
from app.dependencies import require_roles
from app.models import ContactMessage, Content, Nomination, Project, Stage, User, VisitorPresence, utcnow

router = APIRouter(tags=["public content"])


@router.get("/capabilities")
def capabilities():
    return {"email_delivery": bool(settings.enable_email_delivery and settings.smtp_host), "vk_id": False}


class ContentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slug: str = Field(min_length=2, max_length=160, pattern=r"^[a-z0-9][a-z0-9-]*$")
    title: str = Field(min_length=2, max_length=300)
    kind: Literal["page", "news", "education", "faq", "partner", "media", "document", "banner"]
    body: str = Field(default="", max_length=100000)
    excerpt: str = Field(default="", max_length=1500)
    image_url: HttpUrl | None = None
    extra: dict = Field(default_factory=dict)
    published: bool = False


def content_out(row: Content) -> dict:
    return {
        key: getattr(row, key)
        for key in (
            "id",
            "slug",
            "title",
            "kind",
            "body",
            "excerpt",
            "image_url",
            "extra",
            "published",
            "created_at",
            "updated_at",
        )
    }


@router.get("/content")
def list_content(
    kind: str | None = None,
    q: str = "",
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    stmt = select(Content).where(Content.published.is_(True))
    if kind:
        stmt = stmt.where(Content.kind == kind)
    if q:
        stmt = stmt.where(or_(Content.title.ilike(f"%{q}%"), Content.body.ilike(f"%{q}%")))
    return [
        content_out(row)
        for row in db.scalars(stmt.order_by(Content.created_at.desc()).limit(limit).offset(offset))
    ]


@router.get("/content/{slug}")
def get_content(slug: str, db: Session = Depends(get_db)):
    row = db.scalar(select(Content).where(Content.slug == slug, Content.published.is_(True)))
    if not row:
        raise HTTPException(404, "Материал не найден")
    return content_out(row)


@router.get("/nominations")
def nominations(db: Session = Depends(get_db)):
    return [
        {"id": row.id, "title": row.title, "description": row.description}
        for row in db.scalars(
            select(Nomination).where(Nomination.is_active.is_(True)).order_by(Nomination.title)
        )
    ]


@router.get("/stages")
def stages(db: Session = Depends(get_db)):
    return [
        {
            "id": s.id,
            "slug": s.slug,
            "title": s.title,
            "starts_at": s.starts_at,
            "ends_at": s.ends_at,
            "status": stage_state(s),
            "position": s.position,
        }
        for s in db.scalars(select(Stage).order_by(Stage.position))
    ]


@router.get("/public/stats")
def public_stats(db: Session = Depends(get_db)):
    participants = select(User).where(User.role == "participant", User.is_active.is_(True)).subquery()
    return {
        "participants": db.scalar(select(func.count()).select_from(participants)),
        "projects": db.scalar(
            select(func.count(Project.id)).where(Project.status.notin_(["draft", "rejected"]))
        ),
        "regions": db.scalar(select(func.count(func.distinct(participants.c.region)))),
        "schools": db.scalar(select(func.count(func.distinct(participants.c.school)))),
    }


class ContactIn(InputModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["feedback", "sponsor", "volunteer"] = "feedback"
    name: str = Field(min_length=2, max_length=200)
    email: EmailStr
    message: str = Field(min_length=10, max_length=10000)
    consent: Literal[True]


@router.post("/contact", status_code=201)
def contact(body: ContactIn, db: Session = Depends(get_db)):
    row = ContactMessage(**body.model_dump(exclude={"consent"}))
    db.add(row)
    db.commit()
    return {"id": row.id, "message": "Обращение принято"}


@router.get("/admin/content", tags=["admin"])
def admin_content(
    kind: str | None = None,
    q: str = Query(default="", max_length=200),
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    stmt = select(Content)
    if kind:
        stmt = stmt.where(Content.kind == kind)
    if q:
        stmt = stmt.where(or_(Content.title.ilike(f"%{q}%"), Content.body.ilike(f"%{q}%")))
    return [
        content_out(row)
        for row in db.scalars(
            stmt.order_by(Content.updated_at.desc(), Content.id).limit(limit).offset(offset)
        )
    ]


@router.post("/admin/content", status_code=201, tags=["admin"])
def create_content(
    body: ContentIn, db: Session = Depends(get_db), admin: User = Depends(require_roles("admin"))
):
    if db.scalar(select(Content.id).where(Content.slug == body.slug)):
        raise HTTPException(409, "Такой адрес материала уже существует")
    data = body.model_dump(mode="json")
    row = Content(**data)
    db.add(row)
    db.flush()
    audit(db, admin.id, "content.create", row.id)
    db.commit()
    return content_out(row)


@router.put("/admin/content/{content_id}", tags=["admin"])
def update_content(
    content_id: str,
    body: ContentIn,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    row = db.get(Content, content_id)
    if not row:
        raise HTTPException(404, "Материал не найден")
    if db.scalar(select(Content.id).where(Content.slug == body.slug, Content.id != content_id)):
        raise HTTPException(409, "Такой адрес материала уже существует")
    for key, value in body.model_dump(mode="json").items():
        setattr(row, key, value)
    audit(db, admin.id, "content.update", row.id)
    db.commit()
    return content_out(row)


@router.delete("/admin/content/{content_id}", status_code=204, tags=["admin"])
def delete_content(
    content_id: str, db: Session = Depends(get_db), admin: User = Depends(require_roles("admin"))
):
    row = db.get(Content, content_id)
    if not row:
        raise HTTPException(404, "Материал не найден")
    audit(db, admin.id, "content.delete", row.id)
    db.delete(row)
    db.commit()


class PresenceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: UUID


@router.post("/public/presence")
def update_presence(body: PresenceIn, db: Session = Depends(get_db)):
    now = utcnow()
    session_hash = hashlib.sha256(str(body.session_id).encode()).hexdigest()
    db.execute(
        insert(VisitorPresence)
        .values(session_hash=session_hash, last_seen=now)
        .on_conflict_do_update(index_elements=[VisitorPresence.session_hash], set_={"last_seen": now})
    )
    db.execute(delete(VisitorPresence).where(VisitorPresence.last_seen < now - timedelta(minutes=5)))
    total = db.scalar(
        select(func.count())
        .select_from(VisitorPresence)
        .where(VisitorPresence.last_seen > now - timedelta(minutes=2))
    )
    db.commit()
    return {"active_sessions": total, "window_seconds": 120}
