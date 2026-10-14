from datetime import timedelta
import re

import pytest
from sqlalchemy import select

from app.models import ActionToken, AuditLog, Notification, Outbox, RefreshToken, TeacherLink, User, utcnow
from app.security import token_digest, verify_password

API = "/api/v1"


def registration(**overrides):
    data = {
        "email": "new.participant@example.com",
        "password": "StrongPassword123!",
        "full_name": "Новый участник",
        "role": "participant",
        "birth_date": "2000-06-15",
        "school": "Школа № 1",
        "grade": 11,
        "consent": True,
    }
    data.update(overrides)
    return data


def login(client, users, role="participant"):
    response = client.post(f"{API}/auth/login", json={"email": users[role].email, "password": "DemoPass123!"})
    assert response.status_code == 200, response.text
    return response.json()


def outbox_token(db, subject):
    mail = db.scalar(select(Outbox).where(Outbox.subject == subject).order_by(Outbox.created_at.desc()))
    assert mail is not None
    match = re.search(r"[?&]token=([A-Za-z0-9_-]+)", mail.body)
    assert match
    return match.group(1)


@pytest.mark.parametrize("role", ["admin", "expert", "commission", "partner"])
def test_public_registration_cannot_assign_privileged_role(client, role):
    response = client.post(f"{API}/auth/register", json=registration(role=role))
    assert response.status_code == 422


def test_register_hashes_password_and_records_consent(client, db):
    response = client.post(f"{API}/auth/register", json=registration(email="NEW.Participant@example.com"))
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["user"]["email"] == "new.participant@example.com"
    assert "hashed_password" not in payload["user"]
    assert "token_version" not in payload["user"]
    user = db.get(User, payload["user"]["id"])
    assert verify_password("StrongPassword123!", user.hashed_password)
    assert user.hashed_password != "StrongPassword123!"
    assert user.consent_at is not None
    persisted = db.scalar(select(RefreshToken).where(RefreshToken.user_id == user.id))
    assert persisted.token_hash == token_digest(payload["refresh_token"])
    assert persisted.token_hash != payload["refresh_token"]
    duplicate = client.post(f"{API}/auth/register", json=registration())
    assert duplicate.status_code == 409


def test_minor_requires_guardian_consent_and_records_it(client, db):
    birth_date = f"{utcnow().year - 15}-01-01"
    data = registration(birth_date=birth_date)
    assert client.post(f"{API}/auth/register", json=data).status_code == 422
    data.update(
        guardian_name="Законный представитель", guardian_email="guardian@example.com", guardian_consent=True
    )
    response = client.post(f"{API}/auth/register", json=data)
    assert response.status_code == 201, response.text
    user = db.get(User, response.json()["user"]["id"])
    assert user.guardian_consent_at is not None
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    response = client.patch(
        f"{API}/users/me", headers=headers, json={"guardian_email": "other.guardian@example.com"}
    )
    assert response.status_code == 422


def test_login_profile_and_oauth_form_do_not_leak_secrets(client, users):
    session = login(client, users)
    response = client.get(f"{API}/users/me", headers={"Authorization": f"Bearer {session['access_token']}"})
    assert response.status_code == 200
    assert response.json()["id"] == users["participant"].id
    assert "hashed_password" not in response.text
    response = client.post(
        f"{API}/auth/token", data={"username": users["participant"].email, "password": "DemoPass123!"}
    )
    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert (
        client.post(
            f"{API}/auth/login", json={"email": users["participant"].email, "password": "wrong-password"}
        ).status_code
        == 401
    )


def test_refresh_rotates_and_replay_revokes_the_new_session(client, users, db):
    original = login(client, users)
    response = client.post(f"{API}/auth/refresh", json={"refresh_token": original["refresh_token"]})
    assert response.status_code == 200
    rotated = response.json()
    assert rotated["refresh_token"] != original["refresh_token"]
    assert (
        client.post(f"{API}/auth/refresh", json={"refresh_token": original["refresh_token"]}).status_code
        == 401
    )
    assert (
        client.post(f"{API}/auth/refresh", json={"refresh_token": rotated["refresh_token"]}).status_code
        == 401
    )
    assert (
        client.get(
            f"{API}/users/me", headers={"Authorization": f"Bearer {rotated['access_token']}"}
        ).status_code
        == 401
    )
    logs = db.scalars(select(AuditLog)).all()
    assert all(original["refresh_token"] not in str(log.details) for log in logs)


def test_logout_revokes_bearer_and_refresh_tokens(client, users):
    session = login(client, users)
    headers = {"Authorization": f"Bearer {session['access_token']}"}
    assert client.post(f"{API}/auth/logout", headers=headers).status_code == 200
    assert client.get(f"{API}/users/me", headers=headers).status_code == 401
    assert (
        client.post(f"{API}/auth/refresh", json={"refresh_token": session["refresh_token"]}).status_code
        == 401
    )


def test_expired_revoked_refresh_cannot_revoke_new_sessions(client, db, users):
    old_session = login(client, users)
    old_token = db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == token_digest(old_session["refresh_token"]))
    )
    old_token.revoked_at = utcnow() - timedelta(days=30)
    old_token.expires_at = utcnow() - timedelta(days=1)
    db.commit()
    new_session = login(client, users)
    assert (
        client.post(f"{API}/auth/refresh", json={"refresh_token": old_session["refresh_token"]}).status_code
        == 401
    )
    assert (
        client.get(
            f"{API}/users/me", headers={"Authorization": f"Bearer {new_session['access_token']}"}
        ).status_code
        == 200
    )


def test_password_reset_is_private_single_use_and_revokes_sessions(client, db, users):
    session = login(client, users)
    response = client.post(f"{API}/auth/forgot-password", json={"email": users["participant"].email})
    unknown = client.post(f"{API}/auth/forgot-password", json={"email": "unknown@example.com"})
    assert response.status_code == unknown.status_code == 200
    assert response.json() == unknown.json()
    raw_token = outbox_token(db, "Восстановление пароля")
    assert raw_token not in response.text
    action = db.scalar(select(ActionToken).where(ActionToken.kind == "reset_password"))
    assert action.token_hash == token_digest(raw_token)
    response = client.post(
        f"{API}/auth/reset-password", json={"token": raw_token, "password": "ReplacementPass456!"}
    )
    assert response.status_code == 200
    assert (
        client.get(
            f"{API}/users/me", headers={"Authorization": f"Bearer {session['access_token']}"}
        ).status_code
        == 401
    )
    assert (
        client.post(
            f"{API}/auth/reset-password", json={"token": raw_token, "password": "ReplacementPass789!"}
        ).status_code
        == 400
    )
    assert (
        client.post(
            f"{API}/auth/login", json={"email": users["participant"].email, "password": "DemoPass123!"}
        ).status_code
        == 401
    )
    assert (
        client.post(
            f"{API}/auth/login", json={"email": users["participant"].email, "password": "ReplacementPass456!"}
        ).status_code
        == 200
    )


def test_expired_password_reset_is_rejected(client, db, users):
    client.post(f"{API}/auth/forgot-password", json={"email": users["participant"].email})
    raw_token = outbox_token(db, "Восстановление пароля")
    action = db.scalar(select(ActionToken).where(ActionToken.kind == "reset_password"))
    action.expires_at = utcnow() - timedelta(minutes=1)
    db.commit()
    assert (
        client.post(
            f"{API}/auth/reset-password", json={"token": raw_token, "password": "ReplacementPass456!"}
        ).status_code
        == 400
    )


def test_email_confirmation_is_single_use(client, db):
    response = client.post(f"{API}/auth/register", json=registration())
    assert response.status_code == 201
    raw_token = outbox_token(db, "Подтвердите электронную почту")
    assert client.post(f"{API}/auth/verify-email", json={"token": raw_token}).status_code == 200
    assert client.post(f"{API}/auth/verify-email", json={"token": raw_token}).status_code == 400
    db.expire_all()
    assert db.get(User, response.json()["user"]["id"]).email_verified is True


def test_profile_cannot_change_role_and_inactive_user_loses_access(client, db, users, auth_headers):
    headers = auth_headers("participant")
    assert client.patch(f"{API}/users/me", headers=headers, json={"role": "admin"}).status_code == 422
    assert client.patch(f"{API}/users/me", headers=headers, json={"full_name": " "}).status_code == 422
    user = db.get(User, users["participant"].id)
    user.is_active = False
    db.commit()
    assert client.get(f"{API}/users/me", headers=headers).status_code == 401


def test_teacher_invite_requires_intended_teacher_and_is_single_use(client, db, users, auth_headers):
    participant_headers = auth_headers("participant")
    teacher_headers = auth_headers("teacher")
    response = client.post(
        f"{API}/teachers/invite", headers=participant_headers, json={"email": users["teacher"].email}
    )
    assert response.status_code == 202, response.text
    raw_token = outbox_token(db, f"{users['participant'].full_name} приглашает вас стать наставником")
    assert raw_token not in response.text
    assert (
        client.post(
            f"{API}/teachers/confirm", headers=participant_headers, json={"token": raw_token}
        ).status_code
        == 403
    )
    response = client.post(f"{API}/teachers/confirm", headers=teacher_headers, json={"token": raw_token})
    assert response.status_code == 200, response.text
    assert (
        client.post(f"{API}/teachers/confirm", headers=teacher_headers, json={"token": raw_token}).status_code
        == 400
    )
    students = client.get(f"{API}/teachers/students", headers=teacher_headers)
    assert students.status_code == 200
    assert users["participant"].id in {student["id"] for student in students.json()}
    assert "guardian_email" not in students.text
    assert client.get(f"{API}/teachers/students", headers=participant_headers).status_code == 403
    assert client.delete(f"{API}/teachers/link", headers=participant_headers).status_code == 200
    assert db.scalar(select(TeacherLink).where(TeacherLink.participant_id == users["participant"].id)) is None


def test_wrong_teacher_cannot_claim_invitation(client, db, users, auth_headers):
    response = client.post(
        f"{API}/teachers/invite",
        headers=auth_headers("participant"),
        json={"email": "future.teacher@example.com"},
    )
    assert response.status_code == 202
    raw_token = outbox_token(db, f"{users['participant'].full_name} приглашает вас стать наставником")
    assert (
        client.post(
            f"{API}/teachers/confirm", headers=auth_headers("teacher"), json={"token": raw_token}
        ).status_code
        == 403
    )


def test_notifications_are_private(client, db, users, auth_headers):
    notification = Notification(
        user_id=users["participant"].id, title="Личное уведомление", body="Доступно только владельцу"
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    assert (
        client.patch(
            f"{API}/notifications/{notification.id}/read", headers=auth_headers("teacher")
        ).status_code
        == 404
    )
    response = client.patch(
        f"{API}/notifications/{notification.id}/read", headers=auth_headers("participant")
    )
    assert response.status_code == 200
    assert response.json()["read_at"] is not None
    teacher_notifications = client.get(f"{API}/notifications", headers=auth_headers("teacher")).json()
    assert notification.id not in {item["id"] for item in teacher_notifications}
