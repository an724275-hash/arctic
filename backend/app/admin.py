import csv
import io
import secrets
import json
from datetime import datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    HttpUrl,
    field_validator,
    model_validator,
)
from sqlalchemy import Numeric, cast, delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth_schemas import InputModel, MessageOutput, UserOutput, age_on_today, validate_password
from app.avatars import remove_avatar_file
from app.certificates import certificate_response
from app.common import audit
from app.db import get_db
from app.dependencies import get_current_user, require_roles
from app.models import (
    ArticleComment,
    Assignment,
    AuditLog,
    Certificate,
    ContactMessage,
    Criterion,
    Defense,
    ExpertNomination,
    Nomination,
    Notification,
    Outbox,
    Project,
    QuizAttempt,
    RefreshToken,
    Review,
    Stage,
    TeacherLink,
    User,
    VisitorPresence,
    utcnow,
)
from app.security import hash_password

router = APIRouter(tags=["Administration"])
Db = Annotated[Session, Depends(get_db)]
Admin = Annotated[User, Depends(require_roles("admin"))]
Analyst = Annotated[User, Depends(require_roles("admin", "commission"))]
CurrentUser = Annotated[User, Depends(get_current_user)]
Role = Literal["participant", "teacher", "expert", "commission", "admin", "partner"]


class AdminUserInput(InputModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=200)
    password: str = Field(min_length=10, max_length=256)
    role: Literal["teacher", "expert", "commission", "admin", "partner"]

    _password = field_validator("password")(validate_password)


class AdminUserUpdate(InputModel):
    role: Role | None = None
    is_active: bool | None = None


class ExpertDirectionsInput(InputModel):
    nomination_ids: list[str] = Field(default_factory=list, max_length=100)


@router.get("/admin/expert-directions")
def expert_directions(db: Db, actor: Admin):
    return [
        {"expert_id": row.expert_id, "nomination_id": row.nomination_id}
        for row in db.scalars(select(ExpertNomination))
    ]


@router.put("/admin/experts/{expert_id}/directions")
def save_expert_directions(expert_id: str, data: ExpertDirectionsInput, db: Db, actor: Admin):
    expert = db.get(User, expert_id)
    if not expert or expert.role != "expert":
        raise HTTPException(404, "Эксперт не найден")
    ids = set(data.nomination_ids)
    found = set(
        db.scalars(select(Nomination.id).where(Nomination.id.in_(ids), Nomination.is_active.is_(True)))
    )
    if ids != found:
        raise HTTPException(422, "Выберите действующие направления конкурса")
    db.execute(delete(ExpertNomination).where(ExpertNomination.expert_id == expert_id))
    db.add_all([ExpertNomination(expert_id=expert_id, nomination_id=item) for item in sorted(ids)])
    audit(db, actor.id, "expert.directions_changed", expert_id)
    db.commit()
    return {"expert_id": expert_id, "nomination_ids": sorted(ids)}


class NominationInput(InputModel):
    title: str = Field(min_length=2, max_length=250)
    description: str = Field(default="", max_length=10000)
    is_active: bool = True


class CriterionInput(InputModel):
    name: str = Field(min_length=2, max_length=200)
    description: str = Field(default="", max_length=10000)
    max_score: float = Field(default=10, gt=0, le=1000, allow_inf_nan=False)
    weight: float = Field(default=1, gt=0, le=1000, allow_inf_nan=False)
    is_active: bool = True


class NominationUpdate(NominationInput):
    title: str | None = Field(default=None, min_length=2, max_length=250)


class CriterionUpdate(CriterionInput):
    name: str | None = Field(default=None, min_length=2, max_length=200)


class StageInput(InputModel):
    title: str = Field(min_length=2, max_length=200)
    starts_at: AwareDatetime | None = None
    ends_at: AwareDatetime | None = None
    is_enabled: bool = True
    position: int = Field(default=0, ge=0, le=1000)

    @model_validator(mode="after")
    def chronological(self):
        if self.starts_at and self.ends_at and self.starts_at >= self.ends_at:
            raise ValueError("Окончание этапа должно быть позже начала")
        return self


class DefenseInput(InputModel):
    project_id: str = Field(min_length=1, max_length=36)
    starts_at: AwareDatetime
    join_url: HttpUrl
    description: str = Field(default="", max_length=5000)


class CertificateInput(InputModel):
    user_id: str = Field(min_length=1, max_length=36)
    kind: Literal["diploma", "teacher_thanks"]
    title: str = Field(min_length=2, max_length=300)


class ContactUpdate(InputModel):
    status: Literal["new", "in_progress", "resolved", "closed"]


class AnnouncementInput(InputModel):
    title: str = Field(min_length=2, max_length=250)
    body: str = Field(min_length=2, max_length=10000)
    roles: list[Role] = Field(min_length=1, max_length=6)
    email: bool = False


class OrmOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class NominationOutput(OrmOutput):
    id: str
    title: str
    description: str
    is_active: bool


class CriterionOutput(OrmOutput):
    id: str
    name: str
    description: str
    max_score: float
    weight: float
    is_active: bool


class StageOutput(OrmOutput):
    id: str
    slug: str
    title: str
    starts_at: datetime | None
    ends_at: datetime | None
    is_enabled: bool
    position: int


class DefenseOutput(OrmOutput):
    id: str
    project_id: str
    starts_at: datetime
    join_url: str
    description: str


class ContactOutput(OrmOutput):
    id: str
    kind: str
    name: str
    email: str
    message: str
    status: str
    created_at: datetime


class OutboxOutput(OrmOutput):
    id: str
    recipient: str
    subject: str
    status: str
    attempts: int
    created_at: datetime
    sent_at: datetime | None


class AuditOutput(OrmOutput):
    id: str
    actor_id: str | None
    action: str
    entity_id: str | None
    details: dict
    created_at: datetime


def _page(db, query, schema, limit, offset):
    total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery()))
    rows = db.scalars(query.offset(offset).limit(limit)).all()
    return {
        "items": [schema.model_validate(row).model_dump() for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def _get(db, model, item_id, lock=False):
    query = select(model).where(model.id == item_id)
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    item = db.scalar(query)
    if not item:
        raise HTTPException(404, "Запись не найдена")
    return item


def _lock_admins(db, actor):
    # последний администратор
    db.execute(select(func.pg_advisory_xact_lock(func.hashtext("arctic.admin_roles"))))
    admins = db.scalars(
        select(User)
        .where(User.role == "admin", User.is_active.is_(True))
        .order_by(User.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).all()
    if actor.id not in {admin.id for admin in admins}:
        raise HTTPException(403, "Полномочия администратора отозваны")
    return admins


def _revoke(db, user):
    user.token_version += 1
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )


@router.get("/admin/users")
def list_users(
    db: Db,
    actor: Admin,
    q: str | None = Query(default=None, max_length=200),
    role: Role | None = None,
    is_active: bool | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    query = select(User)
    if q:
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.where(
            or_(
                User.full_name.ilike(f"%{escaped}%", escape="\\"),
                User.email.ilike(f"%{escaped}%", escape="\\"),
            )
        )
    if role:
        query = query.where(User.role == role)
    if is_active is not None:
        query = query.where(User.is_active == is_active)
    return _page(db, query.order_by(User.created_at.desc(), User.id), UserOutput, limit, offset)


@router.post("/admin/users", response_model=UserOutput, status_code=201)
def create_user(data: AdminUserInput, db: Db, actor: Admin):
    _lock_admins(db, actor)
    user = User(
        email=str(data.email).lower(),
        full_name=data.full_name,
        hashed_password=hash_password(data.password),
        role=data.role,
        is_active=True,
        email_verified=False,
        token_version=0,
    )
    db.add(user)
    try:
        db.flush()
        audit(db, actor.id, "admin.user_created", user.id, role=user.role)
        db.commit()
    except IntegrityError as error:
        db.rollback()
        if (
            getattr(error.orig, "sqlstate", None) == "23505"
            and getattr(getattr(error.orig, "diag", None), "constraint_name", None) == "ix_users_email"
        ):
            raise HTTPException(409, "Аккаунт с такой почтой уже существует") from None
        raise
    return user


@router.patch("/admin/users/{user_id}", response_model=UserOutput)
def update_user(user_id: str, data: AdminUserUpdate, db: Db, actor: Admin):
    active_admins = _lock_admins(db, actor)
    user = _get(db, User, user_id, lock=True)
    role = data.role if data.role is not None else user.role
    active = data.is_active if data.is_active is not None else user.is_active
    if (
        user.role == "admin"
        and user.is_active
        and (role != "admin" or not active)
        and len(active_admins) <= 1
    ):
        raise HTTPException(409, "Нельзя отключить или понизить последнего активного администратора")
    if user.email == f"deleted-{user.id}@example.invalid" and (active or role != "participant"):
        raise HTTPException(409, "Обезличенный аккаунт нельзя восстановить")
    if role == "participant" and role != user.role:
        if (
            not user.birth_date
            or not user.consent_at
            or (age_on_today(user.birth_date) < 18 and not user.guardian_consent_at)
        ):
            raise HTTPException(422, "Для роли участника необходимы дата рождения и зафиксированное согласие")
    if role == "teacher" and user.birth_date and age_on_today(user.birth_date) < 18:
        raise HTTPException(422, "Наставнику должно быть не менее 18 лет")
    if role != user.role or active != user.is_active:
        _revoke(db, user)
    user.role = role
    user.is_active = active
    audit(db, actor.id, "admin.user_updated", user.id, role=role, is_active=active)
    db.commit()
    return user


@router.delete("/admin/users/{user_id}", response_model=MessageOutput)
def delete_user(user_id: str, db: Db, actor: Admin):
    active_admins = _lock_admins(db, actor)
    user = _get(db, User, user_id, lock=True)
    if user.role == "admin" and user.is_active and len(active_admins) <= 1:
        raise HTTPException(409, "Нельзя удалить последнего активного администратора")
    _revoke(db, user)
    old_avatar = user.avatar_filename
    db.execute(delete(ArticleComment).where(ArticleComment.user_id == user.id))
    user.avatar_filename = None
    user.avatar_kind = "bear"
    user.email = f"deleted-{user.id}@example.invalid"
    user.full_name = "Удалённый пользователь"
    user.hashed_password = hash_password(secrets.token_urlsafe(48))
    user.is_active = False
    user.email_verified = False
    user.role = "participant"
    for field in (
        "birth_date",
        "school",
        "grade",
        "region",
        "city",
        "guardian_name",
        "guardian_email",
        "consent_at",
        "guardian_consent_at",
    ):
        setattr(user, field, None)
    audit(db, actor.id, "admin.user_anonymized", user.id)
    db.commit()
    remove_avatar_file(old_avatar)
    return {"message": "Аккаунт обезличен и отключён. Конкурсные материалы сохранены"}


@router.get("/admin/nominations", response_model=list[NominationOutput])
def list_nominations(db: Db, actor: Admin):
    return db.scalars(select(Nomination).order_by(Nomination.title)).all()


@router.post("/admin/nominations", response_model=NominationOutput, status_code=201)
def create_nomination(data: NominationInput, db: Db, actor: Admin):
    item = Nomination(**data.model_dump())
    db.add(item)
    db.flush()
    audit(db, actor.id, "admin.nomination_created", item.id)
    db.commit()
    return item


@router.put("/admin/nominations/{item_id}", response_model=NominationOutput)
@router.patch("/admin/nominations/{item_id}", response_model=NominationOutput)
def update_nomination(item_id: str, data: NominationUpdate, db: Db, actor: Admin):
    item = _get(db, Nomination, item_id, lock=True)
    for field, value in data.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(item, field, value)
    audit(db, actor.id, "admin.nomination_updated", item.id)
    db.commit()
    return item


@router.delete("/admin/nominations/{item_id}", response_model=MessageOutput)
def delete_nomination(item_id: str, db: Db, actor: Admin):
    item = _get(db, Nomination, item_id, lock=True)
    if db.scalar(select(Project.id).where(Project.nomination_id == item.id).limit(1)):
        item.is_active = False
    else:
        db.delete(item)
    audit(db, actor.id, "admin.nomination_removed", item.id)
    db.commit()
    return {"message": "Номинация удалена или отключена, если в ней есть проекты"}


@router.get("/criteria", response_model=list[CriterionOutput])
def public_criteria(db: Db):
    return db.scalars(select(Criterion).where(Criterion.is_active.is_(True)).order_by(Criterion.name)).all()


@router.get("/admin/criteria", response_model=list[CriterionOutput])
def list_criteria(db: Db, actor: Admin):
    return db.scalars(select(Criterion).order_by(Criterion.name)).all()


@router.post("/admin/criteria", response_model=CriterionOutput, status_code=201)
def create_criterion(data: CriterionInput, db: Db, actor: Admin):
    item = Criterion(**data.model_dump())
    db.add(item)
    db.flush()
    audit(db, actor.id, "admin.criterion_created", item.id)
    db.commit()
    return item


@router.put("/admin/criteria/{item_id}", response_model=CriterionOutput)
@router.patch("/admin/criteria/{item_id}", response_model=CriterionOutput)
def update_criterion(item_id: str, data: CriterionUpdate, db: Db, actor: Admin):
    item = _get(db, Criterion, item_id, lock=True)
    for field, value in data.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(item, field, value)
    audit(db, actor.id, "admin.criterion_updated", item.id)
    db.commit()
    return item


@router.delete("/admin/criteria/{item_id}", response_model=MessageOutput)
def delete_criterion(item_id: str, db: Db, actor: Admin):
    item = _get(db, Criterion, item_id, lock=True)
    item.is_active = False
    audit(db, actor.id, "admin.criterion_disabled", item.id)
    db.commit()
    return {"message": "Критерий отключён. Уже выставленные оценки сохранены"}


@router.get("/admin/stages", response_model=list[StageOutput])
def list_stages(db: Db, actor: Admin):
    return db.scalars(select(Stage).order_by(Stage.position, Stage.slug)).all()


@router.put("/admin/stages/{slug}", response_model=StageOutput)
def update_stage(slug: str, data: StageInput, db: Db, actor: Admin):
    if (
        not slug
        or len(slug) > 80
        or not all(char in "abcdefghijklmnopqrstuvwxyz0123456789-_" for char in slug)
    ):
        raise HTTPException(422, "Недопустимый код этапа")
    stage = db.scalar(select(Stage).where(Stage.slug == slug).with_for_update())
    if stage is None:
        stage = Stage(slug=slug, **data.model_dump())
        db.add(stage)
    else:
        for field, value in data.model_dump().items():
            setattr(stage, field, value)
    db.flush()
    audit(db, actor.id, "admin.stage_updated", stage.id)
    db.commit()
    return stage


@router.get("/admin/stats")
def stats(db: Db, actor: Analyst):
    def count(model, *filters):
        return db.scalar(select(func.count()).select_from(model).where(*filters))

    def distinct_participant_values(column):
        return db.scalar(
            select(func.count(func.distinct(column))).where(
                User.role == "participant", User.is_active.is_(True), func.length(func.trim(column)) > 0
            )
        )

    def grouped(column, model, *filters):
        return [
            {"label": str(label) if label is not None else "Не указано", "count": amount}
            for label, amount in db.execute(
                select(column, func.count())
                .select_from(model)
                .where(*filters)
                .group_by(column)
                .order_by(func.count().desc())
            )
        ]

    nominations = db.execute(
        select(Nomination.title, func.count(Project.id))
        .outerjoin(Project, Project.nomination_id == Nomination.id)
        .group_by(Nomination.id, Nomination.title)
        .order_by(Nomination.title)
    ).all()
    return {
        "active_sessions": count(
            VisitorPresence, VisitorPresence.last_seen > utcnow() - timedelta(minutes=2)
        ),
        "users_total": count(User),
        "active_users": count(User, User.is_active.is_(True)),
        "participants_total": count(User, User.role == "participant", User.is_active.is_(True)),
        "regions_total": distinct_participant_values(User.region),
        "schools_total": distinct_participant_values(User.school),
        "teachers_total": count(User, User.role == "teacher", User.is_active.is_(True)),
        "projects_total": count(Project),
        "reviews_total": count(Review),
        "quiz_attempts_total": count(QuizAttempt),
        "quiz_passed": count(QuizAttempt, QuizAttempt.passed.is_(True)),
        "certificates_total": count(Certificate),
        "regions": grouped(User.region, User, User.role == "participant", User.is_active.is_(True)),
        "schools": grouped(User.school, User, User.role == "participant", User.is_active.is_(True)),
        "roles": grouped(User.role, User),
        "project_statuses": grouped(Project.status, Project),
        "nominations": [{"label": title, "count": amount} for title, amount in nominations],
        "signups_daily": sorted(
            grouped(func.date(User.created_at), User, User.created_at >= utcnow() - timedelta(days=30)),
            key=lambda item: item["label"],
        ),
    }


@router.get("/admin/rankings")
def rankings(
    db: Db,
    actor: Analyst,
    nomination_id: str | None = Query(default=None, max_length=36),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    average_score = func.round(cast(func.avg(Review.weighted_score), Numeric), 2).label("average_score")
    query = (
        select(
            Project.id.label("project_id"),
            Project.title.label("project_title"),
            Project.reviews_released,
            User.id.label("participant_id"),
            User.full_name.label("participant_name"),
            User.school,
            User.region,
            Nomination.id.label("nomination_id"),
            Nomination.title.label("nomination_title"),
            average_score,
            func.count(Review.id).label("review_count"),
        )
        .join(User, User.id == Project.user_id)
        .join(Nomination, Nomination.id == Project.nomination_id)
        .join(
            Assignment,
            Assignment.project_id == Project.id,
        )
        .outerjoin(Review, (Review.assignment_id == Assignment.id) & (Review.project_id == Project.id))
        .where(
            Project.status == "evaluated",
        )
        .group_by(Project.id, User.id, Nomination.id)
        .having(
            func.count(Review.id) > 0,
            func.count(Review.id) == func.count(Assignment.id),
        )
    )
    if nomination_id:
        query = query.where(Project.nomination_id == nomination_id)
    completed = query.subquery()
    total = db.scalar(select(func.count()).select_from(completed))
    ranked = (
        select(completed, func.dense_rank().over(order_by=completed.c.average_score.desc()).label("rank"))
        .order_by(
            completed.c.average_score.desc(),
            completed.c.project_id,
        )
        .offset(offset)
        .limit(limit)
    )
    rows = db.execute(ranked).mappings().all()
    return {
        "items": [
            {
                "rank": row["rank"],
                "average_score": float(row["average_score"]),
                "review_count": row["review_count"],
                "reviews_released": row["reviews_released"],
                "project": {"id": row["project_id"], "title": row["project_title"]},
                "participant": {
                    "id": row["participant_id"],
                    "full_name": row["participant_name"],
                    "school": row["school"],
                    "region": row["region"],
                },
                "nomination": {"id": row["nomination_id"], "title": row["nomination_title"]},
            }
            for row in rows
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def _csv_response(filename, header, rows):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(header)
    for row in rows:
        clean = []
        for value in row:
            value = "" if value is None else str(value)
            if value.lstrip().startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n")):
                value = "'" + value
            clean.append(value)
        writer.writerow(clean)
    return Response(
        content=stream.getvalue().encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/admin/export/users.csv")
def export_users(db: Db, actor: Admin):
    users = db.scalars(select(User).order_by(User.created_at, User.id)).all()
    audit(db, actor.id, "admin.users_exported", count=len(users))
    db.commit()
    return _csv_response(
        "users.csv",
        ["ID", "ФИО", "Почта", "Роль", "Школа", "Класс", "Регион", "Активен", "Регистрация"],
        [
            (
                u.id,
                u.full_name,
                u.email,
                u.role,
                u.school,
                u.grade,
                u.region,
                u.is_active,
                u.created_at.isoformat(),
            )
            for u in users
        ],
    )


@router.get("/admin/export/analytics.json")
def export_analytics(db: Db, actor: Admin):
    report = {"generated_at": utcnow().isoformat(), "statistics": stats(db, actor)}
    audit(db, actor.id, "admin.analytics_exported")
    db.commit()
    return Response(
        content=json.dumps(report, ensure_ascii=False),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="analytics.json"'},
    )


@router.get("/admin/export/analytics.csv")
def export_analytics_csv(db: Db, actor: Admin):
    generated_at = utcnow().isoformat()
    data = stats(db, actor)
    totals = {
        "active_sessions": "Активные сессии за две минуты",
        "users_total": "Всего аккаунтов", "active_users": "Активные аккаунты",
        "participants_total": "Активные участники", "teachers_total": "Активные наставники",
        "regions_total": "Регионы", "schools_total": "Учебные заведения",
        "projects_total": "Проекты", "reviews_total": "Рецензии",
        "quiz_attempts_total": "Попытки теста", "quiz_passed": "Успешные попытки теста",
        "certificates_total": "Выданные документы",
    }
    groups = {
        "regions": "Участники по регионам", "schools": "Участники по учебным заведениям",
        "roles": "Аккаунты по ролям", "project_statuses": "Проекты по статусам",
        "nominations": "Проекты по номинациям", "signups_daily": "Регистрации по дням",
    }
    rows = [(generated_at, "Общие показатели", label, data[key]) for key, label in totals.items()]
    rows.extend((generated_at, title, item["label"], item["count"]) for key, title in groups.items() for item in data[key])
    audit(db, actor.id, "admin.analytics_csv_exported", rows=len(rows))
    db.commit()
    return _csv_response("analytics.csv", ["Сформировано UTC", "Раздел", "Показатель", "Количество"], rows)


@router.get("/admin/export/reviews.csv")
def export_reviews(db: Db, actor: Admin):
    rows = db.execute(
        select(Review, Project.title, User.full_name)
        .join(Project, Project.id == Review.project_id)
        .join(User, User.id == Review.expert_id)
        .order_by(Review.submitted_at)
    ).all()
    audit(db, actor.id, "admin.reviews_exported", count=len(rows))
    db.commit()
    return _csv_response(
        "reviews.csv",
        ["Проект", "Эксперт", "Итоговая оценка", "Оценки по критериям", "Комментарий", "Дата"],
        [
            (
                title,
                name,
                review.weighted_score,
                json.dumps(
                    {
                        criterion["name"]: review.scores.get(criterion["id"])
                        for criterion in review.criteria_snapshot
                    },
                    ensure_ascii=False,
                ),
                review.comment,
                review.submitted_at.isoformat(),
            )
            for review, title, name in rows
        ],
    )


@router.get("/admin/export/projects.csv")
def export_projects(db: Db, actor: Admin):
    rows = db.execute(
        select(Project, User.full_name, Nomination.title)
        .join(User, User.id == Project.user_id)
        .join(Nomination, Nomination.id == Project.nomination_id)
        .order_by(Project.created_at, Project.id)
    ).all()
    audit(db, actor.id, "admin.projects_exported", count=len(rows))
    db.commit()
    return _csv_response(
        "projects.csv",
        ["ID", "Название", "Участник", "Номинация", "Статус", "Создан", "Подан"],
        [
            (
                p.id,
                p.title,
                name,
                nomination,
                p.status,
                p.created_at.isoformat(),
                p.submitted_at.isoformat() if p.submitted_at else None,
            )
            for p, name, nomination in rows
        ],
    )


@router.get("/defenses", response_model=list[DefenseOutput])
def defenses(db: Db, user: CurrentUser):
    query = select(Defense).join(Project, Project.id == Defense.project_id)
    if user.role == "participant":
        query = query.where(Project.user_id == user.id)
    elif user.role == "teacher":
        query = query.join(TeacherLink, TeacherLink.participant_id == Project.user_id).where(
            TeacherLink.teacher_id == user.id, TeacherLink.status == "accepted"
        )
    elif user.role == "expert":
        query = query.join(Assignment, Assignment.project_id == Project.id).where(
            Assignment.expert_id == user.id
        )
    elif user.role != "admin":
        raise HTTPException(403, "Недостаточно прав")
    return db.scalars(query.order_by(Defense.starts_at)).unique().all()


def _save_defense(data, db, actor, item_id=None):
    project = _get(db, Project, data.project_id, lock=True)
    if project.status not in {"admitted", "reviewing", "evaluated"}:
        raise HTTPException(409, "Защиту можно назначить только допущенному проекту")
    if item_id:
        defense = _get(db, Defense, item_id, lock=True)
        for field, value in data.model_dump(mode="json").items():
            if field != "starts_at":
                setattr(defense, field, value)
        defense.starts_at = data.starts_at
    else:
        defense = Defense(
            project_id=data.project_id,
            starts_at=data.starts_at,
            join_url=str(data.join_url),
            description=data.description,
        )
        db.add(defense)
    db.flush()
    db.add(
        Notification(
            user_id=project.user_id,
            title="Обновлена защита проекта" if item_id else "Назначена защита проекта",
            body=f"Время и ссылка защиты «{project.title}» доступны в личном кабинете.",
        )
    )
    audit(db, actor.id, "admin.defense_updated" if item_id else "admin.defense_scheduled", defense.id)
    db.commit()
    return defense


@router.post("/admin/defenses", response_model=DefenseOutput, status_code=201)
def create_defense(data: DefenseInput, db: Db, actor: Admin):
    return _save_defense(data, db, actor)


@router.put("/admin/defenses/{item_id}", response_model=DefenseOutput)
def update_defense(item_id: str, data: DefenseInput, db: Db, actor: Admin):
    return _save_defense(data, db, actor, item_id)


@router.post("/admin/certificates", status_code=201)
def issue_certificate(data: CertificateInput, db: Db, actor: Admin):
    user = _get(db, User, data.user_id, lock=True)
    if (
        not user.is_active
        or (data.kind == "teacher_thanks" and user.role != "teacher")
        or (data.kind == "diploma" and user.role != "participant")
    ):
        raise HTTPException(422, "Тип документа не соответствует получателю")
    certificate = Certificate(
        user_id=user.id,
        kind=data.kind,
        title=data.title,
        number=f"ARC-{utcnow().year}-{secrets.token_hex(6).upper()}",
        public_token=secrets.token_urlsafe(32),
        mentor_name=db.scalar(
            select(User.full_name)
            .join(TeacherLink, TeacherLink.teacher_id == User.id)
            .where(TeacherLink.participant_id == user.id, TeacherLink.status == "accepted")
        )
        if data.kind == "diploma"
        else None,
    )
    db.add(certificate)
    db.flush()
    db.add(
        Notification(
            user_id=user.id,
            title="Новый наградной документ",
            body=f"В вашем кабинете доступен документ: {data.title}",
        )
    )
    audit(db, actor.id, "admin.certificate_issued", certificate.id, kind=data.kind)
    db.commit()
    return certificate_response(certificate)


@router.get("/admin/messages")
def list_messages(
    db: Db,
    actor: Admin,
    status: Literal["new", "in_progress", "resolved", "closed"] | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    query = select(ContactMessage)
    if status:
        query = query.where(ContactMessage.status == status)
    return _page(
        db, query.order_by(ContactMessage.created_at.desc(), ContactMessage.id), ContactOutput, limit, offset
    )


@router.patch("/admin/messages/{item_id}", response_model=ContactOutput)
def update_message(item_id: str, data: ContactUpdate, db: Db, actor: Admin):
    item = _get(db, ContactMessage, item_id, lock=True)
    item.status = data.status
    audit(db, actor.id, "admin.message_updated", item.id, status=item.status)
    db.commit()
    return item


@router.post("/admin/announcements", status_code=201)
def announce(data: AnnouncementInput, db: Db, actor: Admin):
    users = db.scalars(select(User).where(User.role.in_(set(data.roles)), User.is_active.is_(True))).all()
    for user in users:
        db.add(Notification(user_id=user.id, title=data.title, body=data.body))
        if data.email:
            db.add(
                Outbox(recipient=user.email, subject=data.title, body=data.body, status="pending", attempts=0)
            )
    audit(
        db,
        actor.id,
        "admin.announcement_queued",
        recipients=len(users),
        email=data.email,
        roles=sorted(set(data.roles)),
    )
    db.commit()
    return {"notifications_created": len(users), "emails_queued": len(users) if data.email else 0}


@router.get("/admin/outbox")
def outbox(
    db: Db,
    actor: Admin,
    status: str | None = Query(default=None, max_length=30),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    query = select(Outbox)
    if status:
        query = query.where(Outbox.status == status)
    return _page(db, query.order_by(Outbox.created_at.desc(), Outbox.id), OutboxOutput, limit, offset)


@router.get("/admin/audit")
def audit_logs(
    db: Db,
    actor: Admin,
    action: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    query = select(AuditLog)
    if action:
        query = query.where(AuditLog.action == action)
    return _page(db, query.order_by(AuditLog.created_at.desc(), AuditLog.id), AuditOutput, limit, offset)
