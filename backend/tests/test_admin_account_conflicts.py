from sqlalchemy import func, select

from app.models import User


def test_admin_duplicate_email_returns_conflict_and_session_recovers(client, db, auth_headers):
    headers = auth_headers("admin")
    payload = {
        "email": "Fresh.Expert@EXAMPLE.COM",
        "full_name": "Новый эксперт",
        "password": "ExpertPassword123!",
        "role": "expert",
    }
    created = client.post("/api/v1/admin/users", headers=headers, json=payload)
    assert created.status_code == 201
    assert created.json()["email"] == "fresh.expert@example.com"
    for email in ("fresh.expert@example.com", "FRESH.EXPERT@Example.com"):
        response = client.post("/api/v1/admin/users", headers=headers, json={**payload, "email": email})
        assert response.status_code == 409
        assert response.json()["detail"] == "Аккаунт с такой почтой уже существует"
    assert (
        db.scalar(select(func.count()).select_from(User).where(User.email == "fresh.expert@example.com")) == 1
    )
    response = client.post(
        "/api/v1/admin/users", headers=headers, json={**payload, "email": "another.expert@example.com"}
    )
    assert response.status_code == 201
