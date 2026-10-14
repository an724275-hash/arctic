from datetime import timedelta

from sqlalchemy import select

from app.config import settings
from app.models import ContactMessage, Outbox, Stage, utcnow


def test_health_and_postgresql(client):
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/health/ready").json()["database"] == "postgresql"


def test_capabilities_do_not_expose_provider_secrets(client, monkeypatch):
    monkeypatch.setattr(settings, "enable_email_delivery", False)
    monkeypatch.setattr(settings, "smtp_password", "private-value")
    response = client.get("/api/v1/capabilities")
    assert response.status_code == 200
    assert response.json() == {"email_delivery": False, "vk_id": False}
    monkeypatch.setattr(settings, "enable_email_delivery", True)
    monkeypatch.setattr(settings, "smtp_host", "mail.example.com")
    assert client.get("/api/v1/capabilities").json()["email_delivery"] is True


def test_draft_content_stays_private_until_published(client, auth_headers):
    payload = {"slug": "hidden-page", "title": "Скрытый материал", "kind": "page", "body": "Черновик"}
    created = client.post("/api/v1/admin/content", json=payload, headers=auth_headers("admin"))
    assert created.status_code == 201
    assert client.get("/api/v1/content/hidden-page").status_code == 404
    assert client.get("/api/v1/content", params={"q": "Скрытый"}).json() == []
    payload["published"] = True
    assert (
        client.put(
            f"/api/v1/admin/content/{created.json()['id']}", json=payload, headers=auth_headers("admin")
        ).status_code
        == 200
    )
    assert client.get("/api/v1/content/hidden-page").json()["body"] == "Черновик"


def test_non_admin_cannot_write_content(client, auth_headers):
    response = client.post(
        "/api/v1/admin/content",
        json={"slug": "evil", "title": "Test", "kind": "page"},
        headers=auth_headers("participant"),
    )
    assert response.status_code == 403


def test_contact_requires_consent_and_stores_no_outbound_email(client, db):
    payload = {"name": "Автор", "email": "contact@example.com", "message": "Помогите разобраться с конкурсом"}
    assert client.post("/api/v1/contact", json=payload).status_code == 422
    payload["consent"] = True
    result = client.post("/api/v1/contact", json=payload)
    assert result.status_code == 201
    assert db.get(ContactMessage, result.json()["id"]).status == "new"
    assert not db.scalars(select(Outbox)).all()


def test_stage_status_changes_from_dates_without_cron(client, db):
    stage = db.scalar(select(Stage).where(Stage.slug == "testing"))
    stage.starts_at = utcnow() - timedelta(days=2)
    stage.ends_at = utcnow() - timedelta(days=1)
    db.commit()
    result = client.get("/api/v1/stages").json()
    assert next(row for row in result if row["slug"] == "testing")["status"] == "completed"


def test_public_stats_are_aggregates(client):
    data = client.get("/api/v1/public/stats").json()
    assert data["participants"] == 2
    assert set(data) == {"participants", "projects", "regions", "schools"}


def test_cors_allows_only_frontend_origins(client):
    good = client.options(
        "/api/v1/content", headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"}
    )
    assert good.headers["access-control-allow-origin"] == "http://localhost:3000"
    bad = client.options(
        "/api/v1/content", headers={"Origin": "https://other.example", "Access-Control-Request-Method": "GET"}
    )
    assert "access-control-allow-origin" not in bad.headers


def test_large_request_rejected_before_parsing(client, monkeypatch):
    monkeypatch.setattr(settings, "max_upload_mb", 1)
    response = client.post("/api/v1/contact", content=b"x" * (4 * 1024 * 1024))
    assert response.status_code == 413
