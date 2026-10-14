from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from app.db import Base
from app.models import Certificate, Question, QuizAttempt, QuizConfig, Stage, User, utcnow
from app.quiz import QuizSubmission, start_attempt, submit_attempt

API = "/api/v1"


@pytest.fixture
def question_bank(db):
    db.execute(delete(Question))
    questions = [
        Question(
            text="Какая птица обитает в Арктике?",
            options=[{"id": "a", "text": "Белая сова"}, {"id": "b", "text": "Пингвин"}],
            correct_option_ids=["a"],
            topic="Животные",
            difficulty="easy",
            is_active=True,
            explanation="Белая сова обитает в арктической тундре.",
        ),
        Question(
            text="Выберите арктических животных.",
            options=[
                {"id": "a", "text": "Песец"},
                {"id": "b", "text": "Белый медведь"},
                {"id": "c", "text": "Жираф"},
            ],
            correct_option_ids=["a", "b"],
            topic="Животные",
            difficulty="medium",
            is_active=True,
            explanation="Песцы и белые медведи живут в Арктике.",
        ),
    ]
    db.add_all(questions)
    config = db.get(QuizConfig, 1)
    if config is None:
        config = QuizConfig(id=1)
        db.add(config)
    config.title = "Знаток Арктики"
    config.question_count = 2
    config.duration_seconds = 600
    config.pass_percent = 60
    config.max_attempts = 2
    config.enabled = True
    stage = db.scalar(select(Stage).where(Stage.slug == "testing"))
    if stage:
        stage.starts_at = None
        stage.ends_at = None
        stage.is_enabled = True
    db.commit()
    return questions


def start(client, headers):
    response = client.post(f"{API}/quiz/attempts", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def correct_answers(db, attempt_id):
    db.expire_all()
    attempt = db.get(QuizAttempt, attempt_id)
    return {question["id"]: question["correct_option_ids"] for question in attempt.questions}


def other_participant(client, db, users):
    other = User(
        email="other.quiz@example.com",
        hashed_password=users["participant"].hashed_password,
        full_name="Другой участник",
        role="participant",
        consent_at=utcnow(),
    )
    db.add(other)
    db.commit()
    response = client.post(f"{API}/auth/login", json={"email": other.email, "password": "DemoPass123!"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_start_resumes_and_never_exposes_answer_keys(client, db, auth_headers, question_bank):
    headers = auth_headers("participant")
    attempt = start(client, headers)
    resumed = start(client, headers)
    assert resumed["id"] == attempt["id"]
    assert resumed["expires_at"] == attempt["expires_at"]
    assert 0 < attempt["seconds_remaining"] <= 600
    assert attempt["score_percent"] is None
    assert len(attempt["questions"]) == 2
    assert len({question["id"] for question in attempt["questions"]}) == 2
    for question in attempt["questions"]:
        assert "correct_option_ids" not in question
        assert "explanation" not in question
        assert "is_correct" not in question
    own = client.get(f"{API}/quiz/attempts", headers=headers)
    assert own.status_code == 200
    assert "correct_option_ids" not in own.text
    assert "explanation" not in own.text
    assert db.scalar(select(func.count()).select_from(QuizAttempt)) == 1


def test_scores_snapshot_not_current_question_or_threshold(client, db, auth_headers, question_bank):
    headers = auth_headers("participant")
    attempt = start(client, headers)
    answers = correct_answers(db, attempt["id"])
    db.get(QuizConfig, 1).pass_percent = 100
    db.get(QuizConfig, 1).title = "Изменённое название"
    for question in question_bank:
        question.correct_option_ids = ["b"]
    db.commit()
    response = client.post(
        f"{API}/quiz/attempts/{attempt['id']}/submit", headers=headers, json={"answers": answers}
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["score_percent"] == 100
    assert result["passed"] is True
    assert result["config"]["pass_percent"] == 60
    assert result["certificate"]["title"] == "Знаток Арктики"
    assert result["certificate"]["kind"] == "test_passed"
    assert all(question["is_correct"] for question in result["questions"])
    assert all(question["explanation"] for question in result["questions"])


@pytest.mark.parametrize("multi_answer", [["a"], ["a", "b", "c"], []])
def test_multiselect_requires_exact_match(client, db, auth_headers, question_bank, multi_answer):
    headers = auth_headers("participant")
    attempt = start(client, headers)
    answers = correct_answers(db, attempt["id"])
    multi = next(question for question in question_bank if len(question.correct_option_ids) > 1)
    answers[multi.id] = multi_answer
    result = client.post(
        f"{API}/quiz/attempts/{attempt['id']}/submit", headers=headers, json={"answers": answers}
    ).json()
    assert result["score_percent"] == 50
    assert result["passed"] is False
    assert result["certificate"]["kind"] == "test_participation"


def test_repeated_submission_keeps_score_and_one_certificate(client, db, auth_headers, question_bank):
    headers = auth_headers("participant")
    attempt = start(client, headers)
    path = f"{API}/quiz/attempts/{attempt['id']}/submit"
    first = client.post(path, headers=headers, json={"answers": correct_answers(db, attempt["id"])}).json()
    second = client.post(path, headers=headers, json={"answers": {}}).json()
    assert first["score_percent"] == second["score_percent"] == 100
    assert first["submitted_at"] == second["submitted_at"]
    assert first["certificate"]["id"] == second["certificate"]["id"]
    assert db.scalar(select(func.count()).select_from(Certificate)) == 1


def test_late_submission_ignores_client_answers(client, db, auth_headers, question_bank):
    headers = auth_headers("participant")
    attempt = start(client, headers)
    answers = correct_answers(db, attempt["id"])
    row = db.get(QuizAttempt, attempt["id"])
    row.expires_at = utcnow() - timedelta(seconds=1)
    db.commit()
    response = client.post(
        f"{API}/quiz/attempts/{attempt['id']}/submit", headers=headers, json={"answers": answers}
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["status"] == "expired"
    assert result["seconds_remaining"] == 0
    assert result["score_percent"] == 0
    assert result["answers"] == {}
    assert result["certificate"]["kind"] == "test_participation"


def test_expired_attempt_counts_toward_limit_and_persists(client, db, auth_headers, question_bank):
    headers = auth_headers("participant")
    db.get(QuizConfig, 1).max_attempts = 1
    db.commit()
    attempt = start(client, headers)
    db.get(QuizAttempt, attempt["id"]).expires_at = utcnow() - timedelta(seconds=1)
    db.commit()
    response = client.post(f"{API}/quiz/attempts", headers=headers)
    assert response.status_code == 409
    db.expire_all()
    assert db.get(QuizAttempt, attempt["id"]).submitted_at is not None
    assert db.scalar(select(func.count()).select_from(QuizAttempt)) == 1
    result = client.get(f"{API}/quiz/attempts/{attempt['id']}", headers=headers)
    assert result.status_code == 200
    assert result.json()["status"] == "expired"


def test_cross_user_attempt_and_certificate_access_blocked(client, db, users, auth_headers, question_bank):
    headers = auth_headers("participant")
    attempt = start(client, headers)
    other_headers = other_participant(client, db, users)
    path = f"{API}/quiz/attempts/{attempt['id']}"
    assert client.get(path, headers=other_headers).status_code == 404
    assert client.post(path + "/submit", headers=other_headers, json={"answers": {}}).status_code == 404
    assert client.get(f"{API}/quiz/attempts", headers=other_headers).json() == []
    result = client.post(path + "/submit", headers=headers, json={"answers": {}}).json()
    assert client.get(result["certificate"]["download_url"], headers=other_headers).status_code == 404
    assert client.get(f"{API}/certificates", headers=other_headers).json() == []


@pytest.mark.parametrize("role", ["teacher", "expert", "commission", "admin"])
def test_only_participants_start_quiz(client, auth_headers, question_bank, role):
    assert client.post(f"{API}/quiz/attempts", headers=auth_headers(role)).status_code == 403


def test_invalid_answers_and_client_scores_rejected(client, auth_headers, question_bank):
    headers = auth_headers("participant")
    attempt = start(client, headers)
    question_id = attempt["questions"][0]["id"]
    path = f"{API}/quiz/attempts/{attempt['id']}/submit"
    for body in [
        {"answers": {}, "score_percent": 100},
        {"answers": {"unknown-question": ["a"]}},
        {"answers": {question_id: ["unknown-option"]}},
        {"answers": {question_id: ["a", "a"]}},
    ]:
        response = client.post(path, headers=headers, json=body)
        assert response.status_code == 422, response.text
        response = client.patch(f"{API}/quiz/attempts/{attempt['id']}/answers", headers=headers, json=body)
        assert response.status_code == 422, response.text
    assert client.get(f"{API}/quiz/attempts/{attempt['id']}", headers=headers).json()["status"] == "active"


def test_stage_closed_blocks_new_attempt_but_not_resume_or_submit(client, db, auth_headers, question_bank):
    headers = auth_headers("participant")
    attempt = start(client, headers)
    stage = db.scalar(select(Stage).where(Stage.slug == "testing"))
    if stage is None:
        stage = Stage(slug="testing", title="Тестирование")
        db.add(stage)
    stage.is_enabled = False
    db.commit()
    assert start(client, headers)["id"] == attempt["id"]
    response = client.post(
        f"{API}/quiz/attempts/{attempt['id']}/submit", headers=headers, json={"answers": {}}
    )
    assert response.status_code == 200
    assert client.post(f"{API}/quiz/attempts", headers=headers).status_code == 409


def test_certificate_pdf_private_and_public_verification_masked(
    client, db, users, auth_headers, question_bank
):
    headers = auth_headers("participant")
    attempt = start(client, headers)
    result = client.post(
        f"{API}/quiz/attempts/{attempt['id']}/submit", headers=headers, json={"answers": {}}
    ).json()
    certificate = result["certificate"]
    pdf = client.get(certificate["download_url"], headers=headers)
    assert pdf.status_code == 200, pdf.text if pdf.status_code != 200 else ""
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.headers["cache-control"] == "private, no-store"
    assert pdf.content.startswith(b"%PDF-")
    assert b"/ToUnicode" in pdf.content
    assert len(pdf.content) > 10000
    assert client.get(certificate["download_url"]).status_code == 401
    assert client.get(certificate["download_url"], headers=auth_headers("admin")).status_code == 200
    token = certificate["verification_url"].rsplit("/", 1)[-1]
    assert len(token) >= 40
    public = client.get(f"{API}/certificates/verify/{token}")
    assert public.status_code == 200
    assert public.json()["valid"] is True
    assert public.json()["number"] == certificate["number"]
    assert users["participant"].full_name not in public.text
    assert users["participant"].email not in public.text
    assert set(public.json()) == {"valid", "number", "kind", "title", "issued_at", "recipient"}
    assert client.get(f"{API}/certificates/verify/not-a-real-token").status_code == 404


def test_admin_question_crud_validation_and_no_public_bank(client, auth_headers, question_bank):
    participant = auth_headers("participant")
    admin = auth_headers("admin")
    assert client.get(f"{API}/admin/questions", headers=participant).status_code == 403
    assert client.get(f"{API}/admin/questions").status_code == 401
    payload = {
        "text": "Проверочный вопрос?",
        "options": [{"id": "yes", "text": "Да"}, {"id": "no", "text": "Нет"}],
        "correct_option_ids": ["missing"],
    }
    assert client.post(f"{API}/admin/questions", headers=admin, json=payload).status_code == 422
    payload["correct_option_ids"] = ["yes"]
    response = client.post(f"{API}/admin/questions", headers=admin, json=payload)
    assert response.status_code == 201, response.text
    question = response.json()
    payload["text"] = "Изменённый вопрос?"
    response = client.put(f"{API}/admin/questions/{question['id']}", headers=admin, json=payload)
    assert response.status_code == 200
    assert response.json()["text"] == payload["text"]
    assert client.delete(f"{API}/admin/questions/{question['id']}", headers=admin).status_code == 204
    assert client.get(f"{API}/admin/questions?limit=201", headers=admin).status_code == 422


def test_admin_config_validates_bank_and_ranges(client, auth_headers, question_bank):
    config = {
        "title": "Тест Арктики",
        "question_count": 3,
        "duration_seconds": 600,
        "pass_percent": 60,
        "max_attempts": 2,
        "enabled": True,
    }
    admin = auth_headers("admin")
    assert client.put(f"{API}/admin/quiz-config", headers=admin, json=config).status_code == 422
    config["question_count"] = 2
    config["pass_percent"] = 101
    assert client.put(f"{API}/admin/quiz-config", headers=admin, json=config).status_code == 422
    config["pass_percent"] = 50
    assert (
        client.put(f"{API}/admin/quiz-config", headers=auth_headers("participant"), json=config).status_code
        == 403
    )
    response = client.put(f"{API}/admin/quiz-config", headers=admin, json=config)
    assert response.status_code == 200
    assert client.get(f"{API}/quiz/config").json()["pass_percent"] == 50


def test_missing_consent_prevents_start(client, db, users, auth_headers, question_bank):
    headers = auth_headers("participant")
    user = db.get(User, users["participant"].id)
    user.consent_at = None
    db.commit()
    assert client.post(f"{API}/quiz/attempts", headers=headers).status_code == 422


def test_saved_draft_resumes_and_each_save_replaces_all_answers(client, db, auth_headers, question_bank):
    headers = auth_headers("participant")
    attempt = start(client, headers)
    answers = correct_answers(db, attempt["id"])
    path = f"{API}/quiz/attempts/{attempt['id']}/answers"
    saved = client.patch(path, headers=headers, json={"answers": answers})
    assert saved.status_code == 200, saved.text
    assert saved.json()["status"] == "active"
    assert saved.json()["submitted_at"] is None
    assert saved.json()["score_percent"] is None
    assert saved.json()["certificate"] is None
    assert "correct_option_ids" not in saved.text
    assert start(client, headers)["answers"] == answers
    remaining_id = attempt["questions"][0]["id"]
    replacement = {remaining_id: answers[remaining_id]}
    response = client.patch(path, headers=headers, json={"answers": replacement})
    assert response.status_code == 200
    restored = client.get(f"{API}/quiz/attempts/{attempt['id']}", headers=headers).json()
    assert restored["answers"] == replacement
    assert restored["expires_at"] == attempt["expires_at"]


def test_expired_save_grades_previous_draft_and_ignores_new_choices(client, db, auth_headers, question_bank):
    headers = auth_headers("participant")
    attempt = start(client, headers)
    answers = correct_answers(db, attempt["id"])
    path = f"{API}/quiz/attempts/{attempt['id']}/answers"
    assert client.patch(path, headers=headers, json={"answers": answers}).status_code == 200
    db.get(QuizAttempt, attempt["id"]).expires_at = utcnow() - timedelta(seconds=1)
    db.commit()
    response = client.patch(path, headers=headers, json={"answers": {}})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["status"] == "expired"
    assert result["answers"] == answers
    assert result["score_percent"] == 100
    assert result["passed"] is True
    assert result["certificate"]["kind"] == "test_passed"
    repeated = client.patch(path, headers=headers, json={"answers": {}}).json()
    assert repeated["certificate"]["id"] == result["certificate"]["id"]
    assert repeated["score_percent"] == 100


def test_draft_saves_require_ownership_and_participant_role(client, db, users, auth_headers, question_bank):
    headers = auth_headers("participant")
    attempt = start(client, headers)
    path = f"{API}/quiz/attempts/{attempt['id']}/answers"
    body = {"answers": correct_answers(db, attempt["id"])}
    assert client.patch(path, json=body).status_code == 401
    assert client.patch(path, headers=auth_headers("teacher"), json=body).status_code == 403
    other_headers = other_participant(client, db, users)
    assert client.patch(path, headers=other_headers, json=body).status_code == 404
    assert client.get(f"{API}/quiz/attempts/{attempt['id']}", headers=headers).json()["answers"] == {}


def test_parallel_start_and_submit_are_serialized_in_postgresql(test_engine):
    schema = "quiz_race_" + uuid4().hex
    with test_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    isolated = test_engine.execution_options(schema_translate_map={None: schema})
    try:
        Base.metadata.create_all(isolated)
        with Session(isolated, expire_on_commit=False) as db:
            user = User(
                email="race@example.com",
                hashed_password="unused",
                full_name="Проверка конкуренции",
                role="participant",
                consent_at=utcnow(),
            )
            question = Question(
                text="Проверка конкурентной отправки?",
                options=[{"id": "a", "text": "Да"}, {"id": "b", "text": "Нет"}],
                correct_option_ids=["a"],
                is_active=True,
            )
            db.add_all(
                [
                    user,
                    question,
                    QuizConfig(
                        id=1,
                        title="Проверка",
                        question_count=1,
                        duration_seconds=600,
                        pass_percent=60,
                        max_attempts=1,
                        enabled=True,
                    ),
                ]
            )
            db.commit()
            user_id, question_id = user.id, question.id
        barrier = Barrier(2)

        def concurrent_start(_index):
            with Session(isolated, expire_on_commit=False) as session:
                user = session.get(User, user_id)
                barrier.wait(timeout=10)
                return start_attempt(db=session, user=user)

        with ThreadPoolExecutor(max_workers=2) as pool:
            started = list(pool.map(concurrent_start, range(2)))
        assert started[0]["id"] == started[1]["id"]
        attempt_id = started[0]["id"]
        barrier = Barrier(2)

        def concurrent_submit(index):
            with Session(isolated, expire_on_commit=False) as session:
                user = session.get(User, user_id)
                barrier.wait(timeout=10)
                payload = QuizSubmission(answers={question_id: ["a"]} if index == 0 else {})
                return submit_attempt(attempt_id=attempt_id, payload=payload, db=session, user=user)

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(concurrent_submit, range(2)))
        assert results[0]["score_percent"] == results[1]["score_percent"]
        assert results[0]["certificate"]["id"] == results[1]["certificate"]["id"]
        with Session(isolated) as session:
            assert session.scalar(select(func.count()).select_from(QuizAttempt)) == 1
            assert session.scalar(select(func.count()).select_from(Certificate)) == 1
    finally:
        with test_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
