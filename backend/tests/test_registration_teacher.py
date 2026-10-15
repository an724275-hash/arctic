from urllib.parse import parse_qs, urlsplit

from sqlalchemy import select

from app.models import Certificate, TeacherLink, User, utcnow
from test_auth import registration

API = "/api/v1"


def test_student_registration_requires_active_teacher_and_consent(client, users, db):
    data = registration()
    assert client.post(f"{API}/auth/register", json=data).status_code == 422
    data.update(teacher_id=users["admin"].id, teacher_consent=True)
    assert client.post(f"{API}/auth/register", json=data).status_code == 422
    assert db.scalar(select(User.id).where(User.email == data["email"])) is None
    data["teacher_id"] = users["teacher"].id
    data["teacher_consent"] = False
    assert client.post(f"{API}/auth/register", json=data).status_code == 422
    users["teacher"].is_active = False
    db.commit()
    data["teacher_consent"] = True
    assert client.post(f"{API}/auth/register", json=data).status_code == 422


def test_selected_teacher_is_linked_at_registration(client, users, db):
    result = client.post(f"{API}/auth/register", json=registration(users))
    assert result.status_code == 201
    link = db.scalar(select(TeacherLink).where(TeacherLink.participant_id == result.json()["user"]["id"]))
    assert link.teacher_id == users["teacher"].id
    assert link.status == "accepted"


def test_registration_invitation_is_atomic_and_single_use(client, users, auth_headers, db):
    invitation = client.post(f"{API}/teachers/invite-link", headers=auth_headers("teacher")).json()
    token = parse_qs(urlsplit(invitation["url"]).query)["token"][0]
    data = registration(mentor_token=token, teacher_consent=True)
    result = client.post(f"{API}/auth/register", json=data)
    assert result.status_code == 201
    link = db.scalar(select(TeacherLink).where(TeacherLink.participant_id == result.json()["user"]["id"]))
    assert link.teacher_id == users["teacher"].id
    data["email"] = "second-invitation-user@example.com"
    assert client.post(f"{API}/auth/register", json=data).status_code == 400
    assert db.scalar(select(User.id).where(User.email == data["email"])) is None


def test_public_teacher_search_returns_only_directory_fields(client, users, db):
    users["teacher"].school = "Уникальная школа поиска"
    db.commit()
    assert client.get(f"{API}/public/teachers?q=а").status_code == 422
    rows = client.get(f"{API}/public/teachers", params={"q": "Уникальная"}).json()
    assert len(rows) == 1
    assert set(rows[0]) == {"id", "full_name", "school", "region"}
    assert rows[0]["id"] == users["teacher"].id
    assert client.get(f"{API}/public/teachers", params={"q": "%_"}).json() == []
    users["teacher"].is_active = False
    db.commit()
    assert client.get(f"{API}/public/teachers", params={"q": "Уникальная"}).json() == []


def test_old_diploma_uses_linked_teacher_without_changing_snapshot(client, users, db, auth_headers, monkeypatch):
    from app import certificates

    db.add(TeacherLink(participant_id=users["participant"].id, teacher_id=users["teacher"].id, status="accepted"))
    cert = Certificate(user_id=users["participant"].id, kind="diploma", title="За исследование", number="LEGACY-TEST", public_token="legacy-test-token", issued_at=utcnow())
    db.add(cert)
    db.commit()
    captured = []

    def render(certificate, user, font, url, fit, mentor_name):
        captured.append((certificate.mentor_name, mentor_name))
        return b"%PDF-1.4\n%%EOF"

    monkeypatch.setattr(certificates, "render_document", render)
    assert client.get(f"{API}/certificates/{cert.id}/download", headers=auth_headers("participant")).status_code == 200
    assert captured[-1] == (None, users["teacher"].full_name)
    cert.mentor_name = "Наставник на момент выдачи"
    db.commit()
    assert client.get(f"{API}/certificates/{cert.id}/download", headers=auth_headers("participant")).status_code == 200
    assert captured[-1] == (cert.mentor_name, None)
