"""учётные записи"""

from datetime import datetime, timedelta, timezone
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth_schemas import (
    EmailInput,
    LoginInput,
    MessageOutput,
    NotificationOutput,
    ProfileInput,
    RefreshInput,
    RegisterInput,
    ResetPasswordInput,
    SessionOutput,
    StudentOutput,
    TeacherLinkOutput,
    TeacherOutput,
    TokenInput,
    UserOutput,
    age_on_today,
)
from app.config import settings
from app.common import require_stage_open
from app.db import get_db
from app.dependencies import get_current_user, require_roles
from app.models import ActionToken, AuditLog, Notification, Outbox, RefreshToken, TeacherLink, User, utcnow
from app.security import create_access_token, hash_password, new_secret, token_digest, verify_password

router = APIRouter(tags=["Accounts"])
Db = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
Participant = Annotated[User, Depends(require_roles("participant"))]
Teacher = Annotated[User, Depends(require_roles("teacher"))]


class JoinMentorInput(TokenInput):
    replace: bool = False


@router.post("/teachers/invite-link", status_code=201)
def create_mentor_link(db: Db, user: Teacher):
    token = new_secret()
    expires = utcnow() + timedelta(days=3)
    db.add(
        ActionToken(user_id=user.id, kind="mentor_link", token_hash=token_digest(token), expires_at=expires)
    )
    _audit(db, "teacher.link_created", user)
    db.commit()
    return {
        "url": settings.frontend_url.rstrip("/") + "/teacher-invite?" + urlencode({"token": token}),
        "expires_at": expires,
        "single_use": True,
    }


@router.get("/teachers/invite-link/{token}")
def mentor_link_info(token: str, db: Db):
    if len(token) > 128:
        raise HTTPException(400, "Ссылка недействительна")
    action = db.scalar(
        select(ActionToken).where(
            ActionToken.token_hash == token_digest(token),
            ActionToken.kind == "mentor_link",
            ActionToken.used_at.is_(None),
        )
    )
    teacher = db.get(User, action.user_id) if action else None
    if (
        not action
        or _aware(action.expires_at) <= utcnow()
        or not teacher
        or teacher.role != "teacher"
        or not teacher.is_active
    ):
        raise HTTPException(400, "Ссылка недействительна или срок её действия истёк")
    return {"teacher_name": teacher.full_name, "school": teacher.school, "expires_at": action.expires_at}


@router.post("/teachers/join", response_model=MessageOutput)
def join_mentor(data: JoinMentorInput, db: Db, user: Participant):
    action = _action(db, data.token, "mentor_link")
    teacher = db.get(User, action.user_id)
    if not teacher or teacher.role != "teacher" or not teacher.is_active:
        raise HTTPException(400, "Наставник недоступен")
    db.scalar(select(User).where(User.id == user.id).with_for_update())
    link = db.scalar(select(TeacherLink).where(TeacherLink.participant_id == user.id).with_for_update())
    if link and link.teacher_id != teacher.id and not data.replace:
        raise HTTPException(409, "У вас уже есть наставник. Подтвердите замену отдельно")
    if link:
        link.teacher_id = teacher.id
        link.status = "accepted"
        link.created_at = utcnow()
    else:
        db.add(TeacherLink(participant_id=user.id, teacher_id=teacher.id, status="accepted"))
    action.used_at = utcnow()
    db.add(
        Notification(
            user_id=teacher.id, title="Новый ученик", body=f"{user.full_name} подтвердил связь с вами."
        )
    )
    _audit(db, "teacher.link_joined", user, teacher.id)
    db.commit()
    return {"message": "Наставник привязан. Он видит ваши работы и опубликованные результаты."}


_DUMMY_HASH = hash_password("unavailable-account-" + new_secret())


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _email(value: str) -> str:
    return str(value).strip().lower()


def _audit(db: Session, action: str, user: User | None, entity_id: str | None = None) -> None:
    db.add(AuditLog(actor_id=user.id if user else None, action=action, entity_id=entity_id, details={}))


def _session(db: Session, user: User) -> SessionOutput:
    raw_token = new_secret()
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=token_digest(raw_token),
            expires_at=utcnow() + timedelta(days=settings.refresh_token_days),
        )
    )
    db.flush()
    return SessionOutput(
        access_token=create_access_token(user),
        refresh_token=raw_token,
        expires_in=settings.access_token_minutes * 60,
        user=UserOutput.model_validate(user),
    )


def _queue_action(
    db: Session,
    user: User,
    kind: str,
    recipient: str,
    subject: str,
    path: str,
    lifetime: timedelta,
    payload: dict | None = None,
) -> None:
    # новая ссылка
    db.execute(
        update(ActionToken)
        .where(
            ActionToken.user_id == user.id,
            ActionToken.kind == kind,
            ActionToken.used_at.is_(None),
        )
        .values(used_at=utcnow())
    )
    secret = new_secret()
    db.add(
        ActionToken(
            user_id=user.id,
            kind=kind,
            token_hash=token_digest(secret),
            payload=payload or {},
            expires_at=utcnow() + lifetime,
        )
    )
    link = f"{settings.frontend_url.rstrip('/')}/{path.lstrip('/')}?{urlencode({'token': secret})}"
    db.add(
        Outbox(
            recipient=recipient,
            subject=subject,
            body=f"{subject}\n\nОткройте ссылку: {link}\n\nЕсли вы не запрашивали это действие, проигнорируйте письмо.",
            status="pending",
            attempts=0,
        )
    )
    _audit(db, f"auth.{kind}.queued", user)


def _action(db: Session, raw_token: str, kind: str) -> ActionToken:
    query = select(ActionToken).where(
        ActionToken.token_hash == token_digest(raw_token),
        ActionToken.kind == kind,
    )
    action = db.scalar(query)
    if not action:
        raise HTTPException(status_code=400, detail="Ссылка недействительна или срок её действия истёк")
    # порядок блокировок
    db.scalar(
        select(User)
        .where(User.id == action.user_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    action = db.scalar(query.with_for_update().execution_options(populate_existing=True))
    if not action or action.used_at or _aware(action.expires_at) <= utcnow():
        raise HTTPException(status_code=400, detail="Ссылка недействительна или срок её действия истёк")
    return action


def _revoke_sessions(db: Session, user: User) -> None:
    user.token_version += 1
    db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.user_id == user.id,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=utcnow())
    )


@router.post("/auth/register", response_model=SessionOutput, status_code=201)
def register(data: RegisterInput, db: Db):
    require_stage_open(db, "registration")
    normalized_email = _email(data.email)
    if db.scalar(select(User.id).where(User.email == normalized_email)):
        raise HTTPException(status_code=409, detail="Аккаунт с такой почтой уже существует")
    invitation = None
    teacher = None
    if data.role == "participant":
        invitation = _action(db, data.mentor_token, "mentor_link") if data.mentor_token else None
        teacher = db.scalar(
            select(User).where(User.id == (invitation.user_id if invitation else data.teacher_id)).with_for_update()
        )
        if not teacher or teacher.role != "teacher" or not teacher.is_active:
            raise HTTPException(status_code=422, detail="Выберите действующего преподавателя")
    user = User(
        email=normalized_email,
        hashed_password=hash_password(data.password),
        full_name=data.full_name.strip(),
        role=data.role,
        birth_date=data.birth_date,
        school=data.school,
        grade=data.grade,
        region=data.region,
        city=data.city,
        guardian_name=data.guardian_name,
        guardian_email=_email(data.guardian_email) if data.guardian_email else None,
        consent_at=utcnow(),
        guardian_consent_at=utcnow()
        if data.birth_date and age_on_today(data.birth_date) < 18 and data.guardian_consent
        else None,
        is_active=True,
        email_verified=False,
        token_version=0,
    )
    db.add(user)
    try:
        db.flush()
        if teacher:
            db.add(TeacherLink(participant_id=user.id, teacher_id=teacher.id, status="accepted"))
            if invitation:
                invitation.used_at = utcnow()
            db.add(Notification(user_id=teacher.id, title="Новый ученик", body=f"{user.full_name} выбрал вас наставником."))
            _audit(db, "teacher.registration_linked", user, teacher.id)
        _queue_action(
            db,
            user,
            "verify_email",
            user.email,
            "Подтвердите электронную почту",
            "verify-email",
            timedelta(hours=24),
        )
        db.add(
            Notification(
                user_id=user.id,
                title="Добро пожаловать",
                body="Профиль создан. Уведомления и документы конкурса доступны в личном кабинете.",
            )
        )
        _audit(db, "auth.register", user)
        response = _session(db, user)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Аккаунт с такой почтой уже существует") from None
    return response


def _login(db: Session, email: str, password: str) -> SessionOutput:
    user = db.scalar(select(User).where(User.email == _email(email)).with_for_update())
    valid = (
        verify_password(password, user.hashed_password if user else _DUMMY_HASH)
        if len(password) <= 256
        else False
    )
    if not user or not valid or not user.is_active:
        _audit(db, "auth.login_failed", user)
        db.commit()
        raise HTTPException(
            status_code=401, detail="Неверная почта или пароль", headers={"WWW-Authenticate": "Bearer"}
        )
    response = _session(db, user)
    _audit(db, "auth.login", user)
    db.commit()
    return response


@router.post("/auth/login", response_model=SessionOutput)
def login(data: LoginInput, db: Db):
    return _login(db, str(data.email), data.password)


@router.post("/auth/token", response_model=SessionOutput)
def oauth_token(db: Db, form: Annotated[OAuth2PasswordRequestForm, Depends()]):
    return _login(db, form.username, form.password)


@router.post("/auth/refresh", response_model=SessionOutput)
def refresh(data: RefreshInput, db: Db):
    # порядок блокировок
    token = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_digest(data.refresh_token)))
    if not token:
        raise HTTPException(status_code=401, detail="Сессия недействительна")
    user = db.scalar(
        select(User)
        .where(User.id == token.user_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    token = db.scalar(
        select(RefreshToken)
        .where(RefreshToken.id == token.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if not token or not user:
        raise HTTPException(status_code=401, detail="Сессия недействительна")
    if not user.is_active or _aware(token.expires_at) <= utcnow():
        raise HTTPException(status_code=401, detail="Сессия истекла. Войдите снова")
    if token.revoked_at:
        _revoke_sessions(db, user)
        _audit(db, "auth.refresh_replay", user)
        db.commit()
        raise HTTPException(status_code=401, detail="Сессия недействительна. Войдите снова")
    token.revoked_at = utcnow()
    response = _session(db, user)
    _audit(db, "auth.refresh", user)
    db.commit()
    return response


@router.post("/auth/logout", response_model=MessageOutput)
def logout(db: Db, user: CurrentUser):
    user = db.scalar(
        select(User).where(User.id == user.id).with_for_update().execution_options(populate_existing=True)
    )
    _revoke_sessions(db, user)
    _audit(db, "auth.logout", user)
    db.commit()
    return {"message": "Вы вышли из аккаунта на всех устройствах"}


@router.post("/auth/forgot-password", response_model=MessageOutput)
def forgot_password(data: EmailInput, db: Db):
    user = db.scalar(select(User).where(User.email == _email(data.email)).with_for_update())
    if user and user.is_active:
        _queue_action(
            db,
            user,
            "reset_password",
            user.email,
            "Восстановление пароля",
            "reset-password",
            timedelta(minutes=30),
        )
        db.commit()
    return {"message": "Если аккаунт существует, письмо для восстановления пароля поставлено в очередь"}


@router.post("/auth/reset-password", response_model=MessageOutput)
def reset_password(data: ResetPasswordInput, db: Db):
    action = _action(db, data.token, "reset_password")
    user = db.scalar(
        select(User)
        .where(User.id == action.user_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if not user or not user.is_active:
        raise HTTPException(status_code=400, detail="Ссылка недействительна")
    user.hashed_password = hash_password(data.password)
    action.used_at = utcnow()
    _revoke_sessions(db, user)
    _audit(db, "auth.password_reset", user)
    db.commit()
    return {"message": "Пароль изменён. Войдите с новым паролем"}


@router.post("/auth/verify-email", response_model=MessageOutput)
def verify_email(data: TokenInput, db: Db):
    action = _action(db, data.token, "verify_email")
    user = db.scalar(select(User).where(User.id == action.user_id).with_for_update())
    if not user or not user.is_active:
        raise HTTPException(status_code=400, detail="Ссылка недействительна")
    user.email_verified = True
    action.used_at = utcnow()
    _audit(db, "auth.email_verified", user)
    db.commit()
    return {"message": "Электронная почта подтверждена"}


@router.post("/auth/resend-verification", response_model=MessageOutput)
def resend_verification(db: Db, user: CurrentUser):
    user = db.scalar(
        select(User).where(User.id == user.id).with_for_update().execution_options(populate_existing=True)
    )
    if not user.email_verified:
        _queue_action(
            db,
            user,
            "verify_email",
            user.email,
            "Подтвердите электронную почту",
            "verify-email",
            timedelta(hours=24),
        )
        db.commit()
    return {"message": "Если подтверждение необходимо, письмо поставлено в очередь"}


@router.get("/users/me", response_model=UserOutput)
def get_profile(user: CurrentUser):
    return user


@router.patch("/users/me", response_model=UserOutput)
def update_profile(data: ProfileInput, db: Db, user: CurrentUser):
    user = db.scalar(
        select(User).where(User.id == user.id).with_for_update().execution_options(populate_existing=True)
    )
    changes = data.model_dump(exclude_unset=True)
    guardian_consent = changes.pop("guardian_consent", False)
    if changes.get("full_name", user.full_name) is None:
        raise HTTPException(status_code=422, detail="Имя не может быть пустым")
    if "avatar_kind" in changes and changes["avatar_kind"] is None:
        raise HTTPException(status_code=422, detail="Выберите один из аватаров")
    if user.birth_date and age_on_today(user.birth_date) < 18:
        if not changes.get("guardian_name", user.guardian_name) or not changes.get(
            "guardian_email", user.guardian_email
        ):
            raise HTTPException(
                status_code=422, detail="Для несовершеннолетнего нужны данные законного представителя"
            )
        guardian_changed = any(
            key in changes and changes[key] != getattr(user, key)
            for key in ("guardian_name", "guardian_email")
        )
        if guardian_changed:
            if not guardian_consent:
                raise HTTPException(
                    status_code=422,
                    detail="Подтвердите согласие законного представителя при изменении его данных",
                )
            user.guardian_consent_at = utcnow()
    for key, value in changes.items():
        setattr(user, key, _email(value) if key == "guardian_email" and value else value)
    db.commit()
    db.refresh(user)
    return user


@router.get("/public/teachers", response_model=list[TeacherOutput])
def teacher_directory(db: Db, q: str = Query(min_length=2, max_length=100)):
    term = q.strip()
    if len(term) < 2:
        return []
    pattern = "%" + term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    return db.scalars(
        select(User)
        .where(
            User.role == "teacher", User.is_active.is_(True),
            User.full_name.ilike(pattern, escape="\\") | User.school.ilike(pattern, escape="\\"),
        )
        .order_by(User.full_name, User.id)
        .limit(20)
    ).all()


@router.get("/teachers", response_model=list[TeacherOutput])
def list_teachers(
    db: Db,
    user: CurrentUser,
    limit: int = Query(default=100, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    return db.scalars(
        select(User)
        .where(User.role == "teacher", User.is_active.is_(True))
        .order_by(User.full_name, User.id)
        .offset(offset)
        .limit(limit)
    ).all()


@router.get("/teachers/link", response_model=TeacherLinkOutput | None)
def teacher_link(db: Db, user: Participant):
    link = db.scalar(select(TeacherLink).where(TeacherLink.participant_id == user.id))
    if not link:
        return None
    teacher = db.get(User, link.teacher_id)
    return TeacherLinkOutput(
        id=link.id,
        status=link.status,
        teacher=TeacherOutput.model_validate(teacher),
        created_at=link.created_at,
    )


@router.post("/teachers/invite", response_model=MessageOutput, status_code=202)
def invite_teacher(data: EmailInput, db: Db, user: Participant):
    user = db.scalar(
        select(User).where(User.id == user.id).with_for_update().execution_options(populate_existing=True)
    )
    recipient = _email(data.email)
    if recipient == user.email:
        raise HTTPException(status_code=422, detail="Нельзя пригласить самого себя")
    existing = db.scalar(select(User).where(User.email == recipient))
    if existing and (existing.role != "teacher" or not existing.is_active):
        raise HTTPException(status_code=422, detail="Укажите почту аккаунта наставника")
    _queue_action(
        db,
        user,
        "teacher_invitation",
        recipient,
        f"{user.full_name} приглашает вас стать наставником",
        "teacher/confirm",
        timedelta(days=7),
        {"participant_id": user.id, "teacher_email": recipient},
    )
    # ожидаем подтверждения
    db.commit()
    return {"message": "Приглашение наставнику поставлено в очередь. Связь появится после подтверждения"}


@router.post("/teachers/confirm", response_model=MessageOutput)
def confirm_teacher(data: TokenInput, db: Db, user: Teacher):
    action = _action(db, data.token, "teacher_invitation")
    if _email(action.payload.get("teacher_email", "")) != user.email:
        raise HTTPException(status_code=403, detail="Приглашение предназначено другому наставнику")
    participant = db.scalar(select(User).where(User.id == action.user_id).with_for_update())
    if not participant or participant.role != "participant" or not participant.is_active:
        raise HTTPException(status_code=400, detail="Приглашение недействительно")
    link = db.scalar(
        select(TeacherLink).where(TeacherLink.participant_id == participant.id).with_for_update()
    )
    if link:
        link.teacher_id = user.id
        link.status = "accepted"
        link.created_at = utcnow()
    else:
        db.add(TeacherLink(participant_id=participant.id, teacher_id=user.id, status="accepted"))
    action.used_at = utcnow()
    db.add(
        Notification(
            user_id=participant.id,
            title="Наставник подтвердил приглашение",
            body=f"{user.full_name} теперь ваш наставник.",
        )
    )
    _audit(db, "teacher.invitation_accepted", user, participant.id)
    db.commit()
    return {"message": "Приглашение принято. Участник появился в вашем списке"}


@router.delete("/teachers/link", response_model=MessageOutput)
def remove_teacher_link(db: Db, user: Participant):
    user = db.scalar(select(User).where(User.id == user.id).with_for_update())
    link = db.scalar(select(TeacherLink).where(TeacherLink.participant_id == user.id).with_for_update())
    if link:
        db.delete(link)
    db.execute(
        update(ActionToken)
        .where(
            ActionToken.user_id == user.id,
            ActionToken.kind == "teacher_invitation",
            ActionToken.used_at.is_(None),
        )
        .values(used_at=utcnow())
    )
    _audit(db, "teacher.link_removed", user)
    db.commit()
    return {"message": "Связь с наставником и действующие приглашения отменены"}


@router.get("/teachers/students", response_model=list[StudentOutput])
def teacher_students(
    db: Db, user: Teacher, limit: int = Query(default=100, ge=1, le=100), offset: int = Query(default=0, ge=0)
):
    rows = db.execute(
        select(User, TeacherLink.created_at)
        .join(
            TeacherLink,
            TeacherLink.participant_id == User.id,
        )
        .where(TeacherLink.teacher_id == user.id, TeacherLink.status == "accepted", User.is_active.is_(True))
        .order_by(User.full_name, User.id)
        .offset(offset)
        .limit(limit)
    ).all()
    return [
        StudentOutput(
            id=student.id,
            full_name=student.full_name,
            school=student.school,
            grade=student.grade,
            region=student.region,
            linked_at=linked_at,
        )
        for student, linked_at in rows
    ]


@router.get("/notifications", response_model=list[NotificationOutput])
def notifications(
    db: Db,
    user: CurrentUser,
    unread_only: bool = False,
    limit: int = Query(default=100, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    query = select(Notification).where(Notification.user_id == user.id)
    if unread_only:
        query = query.where(Notification.read_at.is_(None))
    return db.scalars(
        query.order_by(Notification.created_at.desc(), Notification.id).offset(offset).limit(limit)
    ).all()


@router.post("/notifications/read-all", response_model=MessageOutput)
def read_all_notifications(db: Db, user: CurrentUser):
    db.execute(
        update(Notification)
        .where(Notification.user_id == user.id, Notification.read_at.is_(None))
        .values(read_at=utcnow())
    )
    db.commit()
    return {"message": "Все уведомления отмечены прочитанными"}


@router.patch("/notifications/{notification_id}/read", response_model=NotificationOutput)
def read_notification(notification_id: str, db: Db, user: CurrentUser):
    notification = db.scalar(
        select(Notification)
        .where(Notification.id == notification_id, Notification.user_id == user.id)
        .with_for_update()
    )
    if not notification:
        raise HTTPException(status_code=404, detail="Уведомление не найдено")
    notification.read_at = notification.read_at or utcnow()
    db.commit()
    db.refresh(notification)
    return notification
