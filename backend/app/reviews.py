"""Expert assignments, independent reviews, and controlled publication."""

from __future__ import annotations

import math
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import get_current_user, require_roles
from app.models import (
    Assignment,
    AuditLog,
    Criterion,
    ExpertNomination,
    Notification,
    Project,
    Review,
    User,
    utcnow,
)
from app.projects import ProjectOut, project_for_access

router = APIRouter(tags=["reviews"])


class CriterionSnapshot(BaseModel):
    id: str
    name: str
    description: str
    max_score: float
    weight: float


class ReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    assignment_id: str
    project_id: str
    expert_id: str
    criteria_snapshot: list[CriterionSnapshot]
    scores: dict[str, float]
    comment: str
    weighted_score: float
    submitted_at: datetime


class AssignmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    project_id: str
    expert_id: str
    created_at: datetime


class ExpertAssignmentOut(AssignmentOut):
    project: ProjectOut
    review_submitted: bool
    own_review: ReviewOut | None


class ReviewWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scores: dict[str, float] = Field(min_length=1, max_length=100)
    comment: str = Field(min_length=10, max_length=20000)

    @field_validator("scores", mode="before")
    @classmethod
    def numeric_scores(cls, value):
        if not isinstance(value, dict):
            raise ValueError("Передайте оценки по всем критериям")
        try:
            invalid = any(
                isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score)
                for score in value.values()
            )
        except OverflowError:
            invalid = True
        if invalid:
            raise ValueError("Оценки должны быть конечными числами")
        return value

    @field_validator("comment", mode="before")
    @classmethod
    def strip_comment(cls, value):
        return value.strip() if isinstance(value, str) else value


class AssignmentWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expert_ids: list[str] = Field(min_length=1, max_length=100)

    @field_validator("expert_ids")
    @classmethod
    def unique_experts(cls, value):
        if len(set(value)) != len(value):
            raise ValueError("Список экспертов содержит повторы")
        return value


class AutoAssignWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    count: int = Field(default=2, ge=1, le=10)
    project_ids: list[str] | None = Field(default=None, min_length=1, max_length=200)


class AssignmentResult(BaseModel):
    assigned: int
    assignments: list[AssignmentOut]


def admin_project(db: Session, project_id: str) -> Project:
    project = db.scalar(select(Project).where(Project.id == project_id).with_for_update())
    if project is None:
        raise HTTPException(404, "Проект не найден")
    return project


def check_assignable(project: Project):
    if project.status not in ("admitted", "reviewing") or project.reviews_released:
        raise HTTPException(409, "Экспертов можно назначить только допущенному проекту до завершения оценки")


def add_assignment(db: Session, project: Project, expert: User) -> Assignment:
    assignment = Assignment(project_id=project.id, expert_id=expert.id)
    db.add(assignment)
    db.add(
        Notification(
            user_id=expert.id,
            title="Новый проект для экспертизы",
            body=f"Вам назначен проект «{project.title}». Материалы доступны в кабинете эксперта.",
        )
    )
    project.status = "reviewing"
    project.updated_at = utcnow()
    return assignment


@router.post("/admin/projects/{project_id}/assign", response_model=AssignmentResult)
def assign_experts(
    project_id: str,
    payload: AssignmentWrite,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin")),
):
    project = admin_project(db, project_id)
    check_assignable(project)
    experts = list(
        db.scalars(
            select(User).where(
                User.id.in_(payload.expert_ids),
                User.role == "expert",
                User.is_active.is_(True),
            )
        )
    )
    if len(experts) != len(payload.expert_ids):
        raise HTTPException(422, "Назначать можно только действующих экспертов")
    allowed = set(
        db.scalars(
            select(ExpertNomination.expert_id).where(ExpertNomination.nomination_id == project.nomination_id)
        )
    )
    if any(expert.id not in allowed for expert in experts):
        raise HTTPException(422, "Эксперт должен работать по направлению выбранного проекта")
    existing_ids = set(db.scalars(select(Assignment.expert_id).where(Assignment.project_id == project.id)))
    created = [add_assignment(db, project, expert) for expert in experts if expert.id not in existing_ids]
    db.add(
        AuditLog(
            actor_id=user.id,
            action="project.assign",
            entity_id=project.id,
            details={"expert_ids": payload.expert_ids},
        )
    )
    db.flush()
    result = AssignmentResult(
        assigned=len(created), assignments=[AssignmentOut.model_validate(item) for item in created]
    )
    db.commit()
    return result


@router.post("/admin/projects/auto-assign", response_model=AssignmentResult)
def auto_assign_experts(
    payload: AutoAssignWrite,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin")),
):
    # Одинаковый порядок блокировок предотвращает взаимное ожидание.
    stmt = select(Project).where(
        Project.status.in_(["admitted", "reviewing"]), Project.reviews_released.is_(False)
    )
    if payload.project_ids is not None:
        stmt = stmt.where(Project.id.in_(payload.project_ids))
    projects = list(db.scalars(stmt.order_by(Project.id).with_for_update()))
    if payload.project_ids is not None and {p.id for p in projects} != set(payload.project_ids):
        raise HTTPException(422, "Некоторые проекты не существуют или недоступны для назначения")
    experts = list(
        db.scalars(select(User).where(User.role == "expert", User.is_active.is_(True)).order_by(User.id))
    )
    if len(experts) < payload.count:
        raise HTTPException(422, "Недостаточно действующих экспертов для выбранного числа рецензий")
    loads = dict(
        db.execute(
            select(Assignment.expert_id, func.count(Assignment.id)).group_by(Assignment.expert_id)
        ).all()
    )
    created = []
    for project in projects:
        assigned_ids = set(
            db.scalars(select(Assignment.expert_id).where(Assignment.project_id == project.id))
        )
        needed = max(0, payload.count - len(assigned_ids))
        allowed = set(
            db.scalars(
                select(ExpertNomination.expert_id).where(
                    ExpertNomination.nomination_id == project.nomination_id
                )
            )
        )
        eligible = sorted(
            (expert for expert in experts if expert.id not in assigned_ids and expert.id in allowed),
            key=lambda e: (loads.get(e.id, 0), e.id),
        )
        if len(eligible) < needed:
            raise HTTPException(422, "Недостаточно экспертов по направлению проекта")
        for expert in eligible[:needed]:
            created.append(add_assignment(db, project, expert))
            loads[expert.id] = loads.get(expert.id, 0) + 1
    db.add(
        AuditLog(
            actor_id=user.id,
            action="projects.auto_assign",
            details={"count": payload.count, "assigned": len(created)},
        )
    )
    db.flush()
    result = AssignmentResult(
        assigned=len(created), assignments=[AssignmentOut.model_validate(item) for item in created]
    )
    db.commit()
    return result


@router.get("/expert/assignments", response_model=list[ExpertAssignmentOut])
def expert_assignments(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("expert")),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
):
    rows = db.execute(
        select(Assignment, Project, Review)
        .join(Project, Assignment.project_id == Project.id)
        .outerjoin(Review, Review.assignment_id == Assignment.id)
        .where(Assignment.expert_id == user.id)
        .order_by(Assignment.created_at.desc(), Assignment.id)
        .offset(offset)
        .limit(limit)
    ).all()
    return [
        ExpertAssignmentOut(
            **AssignmentOut.model_validate(assignment).model_dump(),
            project=ProjectOut.model_validate(project),
            review_submitted=review is not None,
            own_review=ReviewOut.model_validate(review) if review else None,
        )
        for assignment, project, review in rows
    ]


@router.post("/expert/assignments/{assignment_id}/review", response_model=ReviewOut, status_code=201)
@router.put("/expert/assignments/{assignment_id}/review", response_model=ReviewOut, status_code=201)
def submit_review(
    assignment_id: str,
    payload: ReviewWrite,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("expert")),
):
    assignment = db.get(Assignment, assignment_id)
    if assignment is None:
        raise HTTPException(404, "Назначение не найдено")
    if assignment.expert_id != user.id:
        raise HTTPException(403, "Нельзя оценить проект другого эксперта")
    project = admin_project(db, assignment.project_id)
    if project.status != "reviewing" or project.reviews_released:
        raise HTTPException(409, "Приём рецензий для этого проекта завершён")
    if db.scalar(select(Review.id).where(Review.assignment_id == assignment.id)):
        raise HTTPException(409, "Рецензия уже отправлена и не может быть изменена")
    # Критерии не должны измениться посреди расчёта.
    criteria = list(
        db.scalars(
            select(Criterion)
            .where(Criterion.is_active.is_(True))
            .order_by(Criterion.id)
            .with_for_update(read=True)
        )
    )
    if not criteria:
        raise HTTPException(409, "Администратор ещё не настроил критерии")
    if set(payload.scores) != {criterion.id for criterion in criteria}:
        raise HTTPException(422, "Оцените все действующие критерии без дополнительных полей")
    for criterion in criteria:
        if (
            not math.isfinite(criterion.max_score)
            or not math.isfinite(criterion.weight)
            or criterion.max_score <= 0
            or criterion.weight <= 0
        ):
            raise HTTPException(409, "Некорректные параметры критериев")
        if not 0 <= payload.scores[criterion.id] <= criterion.max_score:
            raise HTTPException(422, f"Оценка «{criterion.name}» должна быть от 0 до {criterion.max_score:g}")
    largest_weight = max(c.weight for c in criteria)
    weighted = (
        100
        * sum(payload.scores[c.id] / c.max_score * (c.weight / largest_weight) for c in criteria)
        / sum(c.weight / largest_weight for c in criteria)
    )
    review = Review(
        assignment_id=assignment.id,
        project_id=project.id,
        expert_id=user.id,
        criteria_snapshot=[
            {
                "id": c.id,
                "name": c.name,
                "description": c.description,
                "max_score": c.max_score,
                "weight": c.weight,
            }
            for c in criteria
        ],
        scores=payload.scores,
        comment=payload.comment,
        weighted_score=round(weighted, 4),
        submitted_at=utcnow(),
    )
    db.add(review)
    db.flush()
    assignment_count = db.scalar(select(func.count(Assignment.id)).where(Assignment.project_id == project.id))
    review_count = db.scalar(select(func.count(Review.id)).where(Review.project_id == project.id))
    if assignment_count == review_count:
        project.status = "evaluated"
    project.updated_at = utcnow()
    db.add(
        AuditLog(
            actor_id=user.id,
            action="review.submit",
            entity_id=project.id,
            details={"assignment_id": assignment.id},
        )
    )
    db.commit()
    db.refresh(review)
    return review


@router.get("/projects/{project_id}/reviews", response_model=list[ReviewOut])
def project_reviews(project_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    project = project_for_access(db, project_id, user)
    if user.role not in ("admin", "commission", "expert") and not project.reviews_released:
        return []
    if user.role == "expert" and not db.scalar(
        select(Review.id).where(Review.project_id == project.id, Review.expert_id == user.id)
    ):
        return []
    return list(
        db.scalars(
            select(Review).where(Review.project_id == project.id).order_by(Review.submitted_at, Review.id)
        )
    )


@router.post("/admin/projects/{project_id}/publish", response_model=ProjectOut)
def publish_reviews(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin")),
):
    project = admin_project(db, project_id)
    if project.status != "evaluated":
        raise HTTPException(409, "Опубликовать можно только проект с завершённой экспертизой")
    assignment_count = db.scalar(select(func.count(Assignment.id)).where(Assignment.project_id == project.id))
    review_count = db.scalar(select(func.count(Review.id)).where(Review.project_id == project.id))
    if not assignment_count or review_count != assignment_count:
        raise HTTPException(409, "Не все назначенные эксперты отправили рецензии")
    if not project.reviews_released:
        project.reviews_released = True
        project.updated_at = utcnow()
        db.add(
            Notification(
                user_id=project.user_id,
                title="Результаты экспертизы опубликованы",
                body=f"Оценки и рецензии по проекту «{project.title}» доступны в личном кабинете.",
            )
        )
        db.add(AuditLog(actor_id=user.id, action="reviews.publish", entity_id=project.id, details={}))
    db.commit()
    db.refresh(project)
    return project
