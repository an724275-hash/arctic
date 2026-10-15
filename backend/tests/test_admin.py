import csv
import io
from datetime import timedelta

from sqlalchemy import select

from app.models import (
    Assignment,
    ContactMessage,
    Nomination,
    Outbox,
    Project,
    Review,
    TeacherLink,
    User,
    utcnow,
)

API = "/api/v1"


def make_project(db, user, status="admitted"):
    nomination = db.scalar(select(Nomination).where(Nomination.is_active.is_(True)))
    project = Project(
        user_id=user.id,
        nomination_id=nomination.id,
        title="Исследование Арктики",
        abstract="Исследовательская работа об Арктике",
        status=status,
    )
    db.add(project)
    db.commit()
    return project


def test_admin_endpoints_reject_participant_and_commission_mutations(client, users, auth_headers):
    assert client.get(f"{API}/admin/users", headers=auth_headers("participant")).status_code == 403
    assert client.get(f"{API}/admin/audit", headers=auth_headers("teacher")).status_code == 403
    assert client.get(f"{API}/admin/stats", headers=auth_headers("commission")).status_code == 200
    assert (
        client.post(
            f"{API}/admin/criteria", headers=auth_headers("commission"), json={"name": "Новый критерий"}
        ).status_code
        == 403
    )
    response = client.get(f"{API}/admin/users?role=participant&limit=1", headers=auth_headers("admin"))
    assert response.status_code == 200
    assert response.json()["total"] >= 1
    assert len(response.json()["items"]) == 1
    assert "hashed_password" not in response.text


def test_last_admin_cannot_be_disabled_demoted_or_deleted(client, users, auth_headers):
    headers = auth_headers("admin")
    url = f"{API}/admin/users/{users['admin'].id}"
    assert client.patch(url, headers=headers, json={"is_active": False}).status_code == 409
    assert client.patch(url, headers=headers, json={"role": "participant"}).status_code == 409
    assert client.delete(url, headers=headers).status_code == 409


def test_admin_creates_privileged_user_and_role_change_revokes_existing_session(client, users, auth_headers):
    headers = auth_headers("admin")
    response = client.post(
        f"{API}/admin/users",
        headers=headers,
        json={
            "email": "new.expert@example.com",
            "full_name": "Новый эксперт",
            "password": "ExpertPassword123!",
            "role": "expert",
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["role"] == "expert"
    assert "hashed_password" not in response.text
    participant_headers = auth_headers("participant")
    response = client.patch(
        f"{API}/admin/users/{users['participant'].id}", headers=headers, json={"role": "expert"}
    )
    assert response.status_code == 200
    assert client.get(f"{API}/users/me", headers=participant_headers).status_code == 401


def test_delete_anonymizes_profile_but_preserves_project(client, db, users, auth_headers):
    project = make_project(db, users["participant"])
    old_email = users["participant"].email
    response = client.delete(f"{API}/admin/users/{users['participant'].id}", headers=auth_headers("admin"))
    assert response.status_code == 200
    db.expire_all()
    user = db.get(User, users["participant"].id)
    assert user.is_active is False
    assert user.email != old_email
    assert user.full_name == "Удалённый пользователь"
    assert user.guardian_email is None
    assert db.get(Project, project.id) is not None
    assert (
        client.patch(
            f"{API}/admin/users/{user.id}", headers=auth_headers("admin"), json={"is_active": True}
        ).status_code
        == 409
    )


def test_nomination_in_use_is_disabled_and_criteria_validation(client, db, users, auth_headers):
    headers = auth_headers("admin")
    project = make_project(db, users["participant"])
    response = client.delete(f"{API}/admin/nominations/{project.nomination_id}", headers=headers)
    assert response.status_code == 200
    db.expire_all()
    assert db.get(Nomination, project.nomination_id).is_active is False
    assert (
        client.post(
            f"{API}/admin/criteria", headers=headers, json={"name": "Невалидный", "weight": 0}
        ).status_code
        == 422
    )
    response = client.post(
        f"{API}/admin/criteria",
        headers=headers,
        json={"name": "Проверяемость результатов", "max_score": 5, "weight": 2},
    )
    assert response.status_code == 201
    criterion_id = response.json()["id"]
    response = client.patch(f"{API}/admin/criteria/{criterion_id}", headers=headers, json={"weight": 3})
    assert response.status_code == 200
    assert response.json()["weight"] == 3
    assert client.delete(f"{API}/admin/criteria/{criterion_id}", headers=headers).status_code == 200
    assert criterion_id not in {item["id"] for item in client.get(f"{API}/criteria").json()}


def test_stage_rejects_naive_or_inverted_dates_and_closed_registration(client, auth_headers, users):
    headers = auth_headers("admin")
    data = {"title": "Регистрация", "starts_at": "2026-10-15T10:00:00Z", "ends_at": "2026-10-14T10:00:00Z"}
    assert client.put(f"{API}/admin/stages/registration", headers=headers, json=data).status_code == 422
    data.update(starts_at="2026-10-13T10:00:00", ends_at=None)
    assert client.put(f"{API}/admin/stages/registration", headers=headers, json=data).status_code == 422
    assert (
        client.put(
            f"{API}/admin/stages/registration",
            headers=headers,
            json={"title": "Регистрация", "is_enabled": False},
        ).status_code
        == 200
    )
    response = client.post(
        f"{API}/auth/register",
        json={
            "email": "closed@example.com",
            "teacher_id": users["teacher"].id,
            "teacher_consent": True,
            "full_name": "Поздний участник",
            "password": "StrongPassword123!",
            "role": "participant",
            "birth_date": "2000-01-01",
            "consent": True,
        },
    )
    assert response.status_code == 409


def test_csv_exports_are_utf8_bom_and_neutralize_formulas(client, db, users, auth_headers):
    user = users["participant"]
    user.full_name = '=HYPERLINK("https://example.com")'
    db.commit()
    response = client.get(f"{API}/admin/export/users.csv", headers=auth_headers("admin"))
    assert response.status_code == 200
    assert response.content.startswith(b"\xef\xbb\xbf")
    rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))
    row = next(row for row in rows[1:] if row[0] == user.id)
    assert row[1].startswith("'=")
    assert "hashed_password" not in response.text
    assert client.get(f"{API}/admin/export/users.csv", headers=auth_headers("commission")).status_code == 403


def test_defenses_visible_to_owner_linked_teacher_and_assigned_expert(client, db, users, auth_headers):
    project = make_project(db, users["participant"])
    db.add(Assignment(project_id=project.id, expert_id=users["expert"].id))
    db.commit()
    response = client.post(
        f"{API}/admin/defenses",
        headers=auth_headers("admin"),
        json={
            "project_id": project.id,
            "starts_at": (utcnow() + timedelta(days=3)).isoformat(),
            "join_url": "https://meet.example.com/defense",
            "description": "Подготовьте презентацию",
        },
    )
    assert response.status_code == 201, response.text
    defense_id = response.json()["id"]
    for role in ("participant", "expert", "admin"):
        response = client.get(f"{API}/defenses", headers=auth_headers(role))
        assert defense_id in {item["id"] for item in response.json()}
    existing_link = db.scalar(
        select(TeacherLink).where(TeacherLink.participant_id == users["participant"].id)
    )
    if existing_link:
        db.delete(existing_link)
        db.commit()
    assert client.get(f"{API}/defenses", headers=auth_headers("teacher")).json() == []
    db.add(
        TeacherLink(participant_id=users["participant"].id, teacher_id=users["teacher"].id, status="accepted")
    )
    db.commit()
    assert defense_id in {
        item["id"] for item in client.get(f"{API}/defenses", headers=auth_headers("teacher")).json()
    }


def test_award_issuance_checks_recipient_role(client, users, auth_headers):
    headers = auth_headers("admin")
    data = {"user_id": users["participant"].id, "kind": "teacher_thanks", "title": "Благодарность наставнику"}
    assert client.post(f"{API}/admin/certificates", headers=headers, json=data).status_code == 422
    data.update(user_id=users["teacher"].id)
    response = client.post(f"{API}/admin/certificates", headers=headers, json=data)
    assert response.status_code == 201
    assert response.json()["kind"] == "teacher_thanks"
    assert response.json()["verification_url"].startswith("http")


def test_outbox_hides_tokens_and_announcements_only_queue_opted_in_email(client, db, users, auth_headers):
    headers = auth_headers("admin")
    db.add(
        Outbox(
            recipient=users["participant"].email,
            subject="Восстановление",
            body="secret-reset-token",
            status="pending",
            attempts=0,
        )
    )
    message = ContactMessage(name="Посетитель", email="visitor@example.com", message="Вопрос организатору")
    db.add(message)
    db.commit()
    response = client.get(f"{API}/admin/outbox", headers=headers)
    assert response.status_code == 200
    assert "secret-reset-token" not in response.text
    assert "body" not in response.json()["items"][0]
    response = client.post(
        f"{API}/admin/announcements",
        headers=headers,
        json={"title": "Новости конкурса", "body": "Первая строка\nВторая строка", "roles": ["participant"]},
    )
    assert response.status_code == 201, response.text
    assert response.json()["emails_queued"] == 0
    assert response.json()["notifications_created"] >= 1
    response = client.patch(
        f"{API}/admin/messages/{message.id}", headers=headers, json={"status": "resolved"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "resolved"


def test_rankings_include_only_completed_reviews_and_rank_ties(client, db, users, auth_headers):
    def scored_project(score, status="evaluated"):
        project = make_project(db, users["participant"], status)
        assignment = Assignment(project_id=project.id, expert_id=users["expert"].id)
        db.add(assignment)
        db.flush()
        db.add(
            Review(
                assignment_id=assignment.id,
                project_id=project.id,
                expert_id=users["expert"].id,
                criteria_snapshot=[],
                scores={},
                comment="Оценка",
                weighted_score=score,
            )
        )
        db.commit()
        return project

    lower = scored_project(70)
    high = scored_project(92)
    tied = scored_project(92)
    draft = scored_project(100, "draft")
    unreviewed = make_project(db, users["participant"], "evaluated")
    db.add(Assignment(project_id=high.id, expert_id=users["commission"].id))
    db.commit()
    # A project marked evaluated still stays out while an assigned review is missing.
    response = client.get(f"{API}/admin/rankings", headers=auth_headers("commission"))
    assert response.status_code == 200, response.text
    items = response.json()["items"]
    ids = [item["project"]["id"] for item in items]
    assert ids == [tied.id, lower.id]
    assert high.id not in ids and draft.id not in ids and unreviewed.id not in ids
    assert [item["rank"] for item in items] == [1, 2]
    db.delete(
        db.scalar(
            select(Assignment).where(
                Assignment.project_id == high.id, Assignment.expert_id == users["commission"].id
            )
        )
    )
    db.commit()
    items = client.get(f"{API}/admin/rankings?limit=3", headers=auth_headers("admin")).json()["items"]
    assert [item["average_score"] for item in items] == [92, 92, 70]
    assert [item["rank"] for item in items] == [1, 1, 2]
    assert [item["project"]["id"] for item in items[:2]] == sorted([high.id, tied.id])
    assert client.get(f"{API}/admin/rankings", headers=auth_headers("participant")).status_code == 403


def test_stats_count_only_filled_active_participant_schools_and_regions(client, db, users, auth_headers):
    users["participant"].region = "Республика Саха (Якутия)"
    users["participant"].school = "Школа для проверки"
    users["participant2"].region = "   "
    users["participant2"].school = ""
    db.commit()
    result = client.get(f"{API}/admin/stats", headers=auth_headers("admin")).json()
    assert result["regions_total"] == 1
    assert result["schools_total"] == 1
