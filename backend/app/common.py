from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditLog, Stage, utcnow


def require_stage_open(db: Session, slug: str) -> None:
    stage = db.scalar(select(Stage).where(Stage.slug == slug))
    if not stage:
        return
    now = utcnow()
    if (
        not stage.is_enabled
        or (stage.starts_at and now < stage.starts_at)
        or (stage.ends_at and now >= stage.ends_at)
    ):
        raise HTTPException(409, f"Этап «{stage.title}» сейчас закрыт")


def audit(db: Session, actor_id: str, action: str, entity_id: str | None = None, **details):
    db.add(AuditLog(actor_id=actor_id, action=action, entity_id=entity_id, details=details))


def stage_state(stage: Stage) -> str:
    now = utcnow()
    if not stage.is_enabled:
        return "disabled"
    if stage.starts_at and now < stage.starts_at:
        return "upcoming"
    if stage.ends_at and now >= stage.ends_at:
        return "completed"
    return "active"
