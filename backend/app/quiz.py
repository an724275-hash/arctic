"""попытки теста"""

from __future__ import annotations

import math
import random
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.certificates import certificate_response, issue_quiz_certificate
from app.common import audit, require_stage_open
from app.db import get_db
from app.dependencies import require_roles
from app.models import Certificate, Question, QuizAttempt, QuizConfig, User, utcnow

router = APIRouter(tags=["quiz"])


class QuizConfigInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=3, max_length=200)
    question_count: int = Field(ge=1, le=100)
    duration_seconds: int = Field(ge=30, le=14400)
    pass_percent: float = Field(ge=0, le=100, allow_inf_nan=False)
    max_attempts: int = Field(ge=1, le=20)
    enabled: bool = True


class QuestionOption(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: str = Field(min_length=1, max_length=40, pattern=r"^[a-zA-Z0-9_-]+$")
    text: str = Field(min_length=1, max_length=1000)


class QuestionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    text: str = Field(min_length=3, max_length=4000)
    options: list[QuestionOption] = Field(min_length=2, max_length=8)
    correct_option_ids: list[str] = Field(min_length=1, max_length=8)
    topic: str = Field(default="Арктика", min_length=1, max_length=100)
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    is_active: bool = True
    explanation: str = Field(default="", max_length=4000)

    @model_validator(mode="after")
    def validate_answers(self) -> "QuestionInput":
        option_ids = [option.id for option in self.options]
        if len(set(option_ids)) != len(option_ids):
            raise ValueError("Идентификаторы вариантов должны быть уникальны")
        if len(set(self.correct_option_ids)) != len(self.correct_option_ids):
            raise ValueError("Правильные варианты не должны повторяться")
        if not set(self.correct_option_ids).issubset(option_ids):
            raise ValueError("Правильные ответы должны входить в список вариантов")
        return self


class QuizSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answers: dict[str, list[str]] = Field(default_factory=dict, max_length=100)

    @model_validator(mode="after")
    def validate_answer_sizes(self) -> "QuizSubmission":
        for key, values in self.answers.items():
            if len(key) > 64 or len(values) > 8 or any(len(value) > 40 for value in values):
                raise ValueError("Недопустимый размер ответа")
            if len(set(values)) != len(values):
                raise ValueError("Варианты ответа не должны повторяться")
        return self


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _lock_participant(db: Session, user: User) -> None:
    # одна попытка
    db.execute(select(User.id).where(User.id == user.id).with_for_update()).scalar_one()


def _get_config(db: Session) -> QuizConfig:
    config = db.get(QuizConfig, 1)
    if config is None:
        raise HTTPException(status_code=503, detail="Тестирование ещё не настроено")
    return config


def _config_response(config: QuizConfig) -> dict:
    return {
        "title": config.title,
        "question_count": config.question_count,
        "duration_seconds": config.duration_seconds,
        "pass_percent": config.pass_percent,
        "max_attempts": config.max_attempts,
        "enabled": config.enabled,
        "certificate_policy": "participation_on_submission; success_when_passed",
    }


def _finish_attempt(db: Session, attempt: QuizAttempt, answers: dict, now: datetime) -> None:
    if attempt.submitted_at is not None:
        return
    correct_count = sum(
        set(answers.get(question["id"], [])) == set(question["correct_option_ids"])
        for question in attempt.questions
    )
    total = len(attempt.questions)
    percentage = correct_count * 100 / total if total else 0
    attempt.answers = answers
    attempt.score_percent = round(percentage, 2)
    attempt.passed = percentage >= float(attempt.config_snapshot["pass_percent"])
    attempt.submitted_at = now
    db.flush()
    issue_quiz_certificate(db, attempt)


def _finish_if_expired(db: Session, attempt: QuizAttempt, now: datetime) -> None:
    if attempt.submitted_at is None and _aware(attempt.expires_at) <= now:
        # время вышло
        _finish_attempt(db, attempt, attempt.answers or {}, now)


def _attempt_response(db: Session, attempt: QuizAttempt, now: datetime) -> dict:
    completed = attempt.submitted_at is not None
    expired = completed and _aware(attempt.submitted_at) >= _aware(attempt.expires_at)
    questions = []
    for snapshot in attempt.questions:
        question = {
            "id": snapshot["id"],
            "text": snapshot["text"],
            "options": snapshot["options"],
            "topic": snapshot.get("topic", ""),
            "difficulty": snapshot.get("difficulty", "medium"),
            "multiple_choice": len(snapshot["correct_option_ids"]) > 1,
        }
        if completed:
            selected = (attempt.answers or {}).get(snapshot["id"], [])
            question.update(
                correct_option_ids=snapshot["correct_option_ids"],
                selected_option_ids=selected,
                is_correct=set(selected) == set(snapshot["correct_option_ids"]),
                explanation=snapshot.get("explanation", ""),
            )
        questions.append(question)
    certificate = db.scalar(select(Certificate).where(Certificate.attempt_id == attempt.id))
    return {
        "id": str(attempt.id),
        "started_at": attempt.started_at,
        "expires_at": attempt.expires_at,
        "submitted_at": attempt.submitted_at,
        "server_now": now,
        "seconds_remaining": 0
        if completed
        else max(0, math.ceil((_aware(attempt.expires_at) - now).total_seconds())),
        "status": "expired" if expired else "submitted" if completed else "active",
        "config": attempt.config_snapshot,
        "questions": questions,
        "answers": attempt.answers or {},
        "score_percent": attempt.score_percent if completed else None,
        "passed": attempt.passed if completed else None,
        "certificate": certificate_response(certificate) if certificate else None,
    }


@router.get("/quiz/config")
def get_quiz_config(db: Session = Depends(get_db)) -> dict:
    return _config_response(_get_config(db))


@router.post("/quiz/attempts")
def start_attempt(db: Session = Depends(get_db), user: User = Depends(require_roles("participant"))) -> dict:
    if not user.full_name or len(user.full_name.strip()) < 3:
        raise HTTPException(status_code=422, detail="Заполните ФИО в профиле перед тестированием")
    if user.consent_at is None:
        raise HTTPException(status_code=422, detail="Подтвердите согласие на обработку персональных данных")
    _lock_participant(db, user)
    now = utcnow()
    attempts = db.scalars(
        select(QuizAttempt)
        .where(QuizAttempt.user_id == user.id)
        .order_by(QuizAttempt.started_at.desc())
        .execution_options(populate_existing=True)
    ).all()
    for existing in attempts:
        _finish_if_expired(db, existing, now)
        if existing.submitted_at is None:
            result = _attempt_response(db, existing, now)
            db.commit()
            return result
    config = _get_config(db)
    # начатая попытка
    require_stage_open(db, "testing")
    if not config.enabled:
        db.commit()  # Persist any expired attempts finalized above.
        raise HTTPException(status_code=409, detail="Тестирование временно закрыто")
    if len(attempts) >= config.max_attempts:
        db.commit()
        raise HTTPException(status_code=409, detail="Лимит попыток исчерпан")
    available = db.scalars(select(Question).where(Question.is_active.is_(True))).all()
    if len(available) < config.question_count:
        db.commit()
        raise HTTPException(status_code=503, detail="В банке недостаточно активных вопросов")
    selected = random.SystemRandom().sample(available, config.question_count)
    snapshots = [
        {
            "id": str(question.id),
            "text": question.text,
            "options": question.options,
            "correct_option_ids": question.correct_option_ids,
            "topic": question.topic,
            "difficulty": question.difficulty,
            "explanation": question.explanation,
        }
        for question in selected
    ]
    attempt = QuizAttempt(
        user_id=user.id,
        started_at=now,
        expires_at=now + timedelta(seconds=config.duration_seconds),
        questions=snapshots,
        config_snapshot={
            "title": config.title,
            "question_count": config.question_count,
            "duration_seconds": config.duration_seconds,
            "pass_percent": config.pass_percent,
            "max_attempts": config.max_attempts,
        },
        answers={},
    )
    db.add(attempt)
    db.flush()
    result = _attempt_response(db, attempt, now)
    db.commit()
    return result


@router.get("/quiz/attempts")
def list_attempts(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("participant")),
) -> list[dict]:
    _lock_participant(db, user)
    now = utcnow()
    attempts = db.scalars(
        select(QuizAttempt)
        .where(QuizAttempt.user_id == user.id)
        .order_by(QuizAttempt.started_at.desc())
        .limit(limit)
        .offset(offset)
        .execution_options(populate_existing=True)
    ).all()
    for attempt in attempts:
        _finish_if_expired(db, attempt, now)
    result = [_attempt_response(db, attempt, now) for attempt in attempts]
    db.commit()
    return result


def _owned_attempt(db: Session, attempt_id: UUID, user: User) -> QuizAttempt:
    attempt = db.scalar(
        select(QuizAttempt)
        .where(QuizAttempt.id == str(attempt_id), QuizAttempt.user_id == user.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if attempt is None:
        raise HTTPException(status_code=404, detail="Попытка не найдена")
    return attempt


def _validate_answers(attempt: QuizAttempt, answers: dict[str, list[str]]) -> None:
    snapshot = {question["id"]: question for question in attempt.questions}
    for question_id, selected in answers.items():
        if question_id not in snapshot:
            raise HTTPException(status_code=422, detail="Ответ относится к вопросу вне этой попытки")
        options = {option["id"] for option in snapshot[question_id]["options"]}
        if not set(selected).issubset(options):
            raise HTTPException(status_code=422, detail="Указан неизвестный вариант ответа")


@router.get("/quiz/attempts/{attempt_id}")
def get_attempt(
    attempt_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("participant")),
) -> dict:
    _lock_participant(db, user)
    attempt = _owned_attempt(db, attempt_id, user)
    now = utcnow()
    _finish_if_expired(db, attempt, now)
    result = _attempt_response(db, attempt, now)
    db.commit()
    return result


@router.patch("/quiz/attempts/{attempt_id}/answers")
def save_answers(
    attempt_id: UUID,
    payload: QuizSubmission,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("participant")),
) -> dict:
    _lock_participant(db, user)
    attempt = _owned_attempt(db, attempt_id, user)
    now = utcnow()
    _finish_if_expired(db, attempt, now)
    if attempt.submitted_at is None:
        _validate_answers(attempt, payload.answers)
        # снимок ответов
        attempt.answers = payload.answers
        db.flush()
    result = _attempt_response(db, attempt, now)
    db.commit()
    return result


@router.post("/quiz/attempts/{attempt_id}/submit")
def submit_attempt(
    attempt_id: UUID,
    payload: QuizSubmission,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("participant")),
) -> dict:
    _lock_participant(db, user)
    attempt = _owned_attempt(db, attempt_id, user)
    now = utcnow()
    _finish_if_expired(db, attempt, now)
    if attempt.submitted_at is None:
        _validate_answers(attempt, payload.answers)
        _finish_attempt(db, attempt, payload.answers, now)
    result = _attempt_response(db, attempt, now)
    db.commit()
    return result


def _question_response(question: Question) -> dict:
    return {
        "id": str(question.id),
        "text": question.text,
        "options": question.options,
        "correct_option_ids": question.correct_option_ids,
        "topic": question.topic,
        "difficulty": question.difficulty,
        "is_active": question.is_active,
        "explanation": question.explanation,
    }


@router.get("/admin/questions")
def list_questions(
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles("admin")),
) -> list[dict]:
    return [
        _question_response(question)
        for question in db.scalars(select(Question).order_by(Question.id).limit(limit).offset(offset)).all()
    ]


@router.post("/admin/questions", status_code=201)
def create_question(
    payload: QuestionInput,
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles("admin")),
) -> dict:
    question = Question(**payload.model_dump())
    db.add(question)
    db.flush()
    audit(db, _user.id, "question.created", question.id)
    db.commit()
    db.refresh(question)
    return _question_response(question)


@router.put("/admin/questions/{question_id}")
def update_question(
    question_id: UUID,
    payload: QuestionInput,
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles("admin")),
) -> dict:
    question = db.get(Question, str(question_id))
    if question is None:
        raise HTTPException(status_code=404, detail="Вопрос не найден")
    for key, value in payload.model_dump().items():
        setattr(question, key, value)
    audit(db, _user.id, "question.updated", question.id)
    db.commit()
    db.refresh(question)
    return _question_response(question)


@router.delete("/admin/questions/{question_id}", status_code=204)
def delete_question(
    question_id: UUID,
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles("admin")),
) -> Response:
    question = db.get(Question, str(question_id))
    if question is None:
        raise HTTPException(status_code=404, detail="Вопрос не найден")
    # снимок вопросов
    audit(db, _user.id, "question.deleted", question.id)
    db.delete(question)
    db.commit()
    return Response(status_code=204)


@router.get("/admin/quiz-config")
def admin_quiz_config(db: Session = Depends(get_db), _user: User = Depends(require_roles("admin"))) -> dict:
    return _config_response(_get_config(db))


@router.put("/admin/quiz-config")
def update_quiz_config(
    payload: QuizConfigInput,
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles("admin")),
) -> dict:
    active_count = (
        db.scalar(select(func.count()).select_from(Question).where(Question.is_active.is_(True))) or 0
    )
    if payload.enabled and active_count < payload.question_count:
        raise HTTPException(
            status_code=422, detail="Число вопросов превышает количество активных вопросов в банке"
        )
    config = db.get(QuizConfig, 1)
    if config is None:
        config = QuizConfig(id=1, **payload.model_dump())
        db.add(config)
    else:
        for key, value in payload.model_dump().items():
            setattr(config, key, value)
    audit(db, _user.id, "quiz_config.updated", "1")
    db.commit()
    db.refresh(config)
    return _config_response(config)
