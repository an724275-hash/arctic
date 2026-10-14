from datetime import timedelta
from sqlalchemy import select
from app.models import ActionToken, Certificate, TeacherLink, utcnow
from app.security import token_digest
from urllib.parse import parse_qs, urlsplit


def invite(client, auth_headers):
    reply = client.post("/api/v1/teachers/invite-link", headers=auth_headers("teacher"))
    assert reply.status_code == 201
    return parse_qs(urlsplit(reply.json()["url"]).query)["token"][0]


def test_teacher_personal_link_joins_only_after_student_consent(client, db, users, auth_headers):
    assert client.post("/api/v1/teachers/invite-link", headers=auth_headers("participant")).status_code == 403
    token = invite(client, auth_headers)
    assert (
        client.get("/api/v1/teachers/invite-link/" + token).json()["teacher_name"]
        == users["teacher"].full_name
    )
    assert client.get("/api/v1/teachers/link", headers=auth_headers("participant")).json() is None
    assert (
        client.post(
            "/api/v1/teachers/join", headers=auth_headers("expert"), json={"token": token}
        ).status_code
        == 403
    )
    response = client.post(
        "/api/v1/teachers/join", headers=auth_headers("participant"), json={"token": token}
    )
    assert response.status_code == 200
    students = client.get("/api/v1/teachers/students", headers=auth_headers("teacher")).json()
    assert users["participant"].id in {s["id"] for s in students}
    assert (
        client.post(
            "/api/v1/teachers/join", headers=auth_headers("participant2"), json={"token": token}
        ).status_code
        == 400
    )


def test_expired_mentor_link_cannot_link_student(client, db, auth_headers):
    token = invite(client, auth_headers)
    action = db.scalar(select(ActionToken).where(ActionToken.token_hash == token_digest(token)))
    action.expires_at = utcnow() - timedelta(seconds=1)
    db.commit()
    assert (
        client.post(
            "/api/v1/teachers/join", headers=auth_headers("participant"), json={"token": token}
        ).status_code
        == 400
    )
    assert db.scalar(select(TeacherLink)) is None


def test_student_award_preserves_mentor_name(client, db, users, auth_headers):
    token = invite(client, auth_headers)
    assert (
        client.post(
            "/api/v1/teachers/join", headers=auth_headers("participant"), json={"token": token}
        ).status_code
        == 200
    )
    result = client.post(
        "/api/v1/admin/certificates",
        headers=auth_headers("admin"),
        json={"user_id": users["participant"].id, "kind": "diploma", "title": "За исследовательскую работу"},
    )
    assert result.status_code == 201
    certificate = db.get(Certificate, result.json()["id"])
    assert certificate.mentor_name == users["teacher"].full_name
    assert client.delete("/api/v1/teachers/link", headers=auth_headers("participant")).status_code == 200
    assert certificate.mentor_name == users["teacher"].full_name
    assert (
        client.get(
            f"/api/v1/certificates/{certificate.id}/download", headers=auth_headers("participant")
        ).status_code
        == 200
    )
