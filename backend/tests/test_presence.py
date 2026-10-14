from datetime import timedelta
from uuid import uuid4

from app.models import VisitorPresence, utcnow


def test_presence_counts_sessions_not_registrations(client, db):
    visitor = str(uuid4())
    response = client.post("/api/v1/public/presence", json={"session_id": visitor})
    assert response.status_code == 200
    assert response.json() == {"active_sessions": 1, "window_seconds": 120}
    assert client.post("/api/v1/public/presence", json={"session_id": visitor}).json()["active_sessions"] == 1
    assert (
        client.post("/api/v1/public/presence", json={"session_id": str(uuid4())}).json()["active_sessions"]
        == 2
    )
    rows = db.query(VisitorPresence).all()
    assert all(row.session_hash != visitor for row in rows)
    assert set(VisitorPresence.__table__.columns.keys()) == {"session_hash", "last_seen"}


def test_inactive_sessions_expire_and_old_rows_are_removed(client, db):
    db.add(VisitorPresence(session_hash="a" * 64, last_seen=utcnow() - timedelta(minutes=3)))
    db.add(VisitorPresence(session_hash="b" * 64, last_seen=utcnow() - timedelta(minutes=6)))
    db.commit()
    response = client.post("/api/v1/public/presence", json={"session_id": str(uuid4())})
    assert response.json()["active_sessions"] == 1
    assert db.get(VisitorPresence, "b" * 64) is None


def test_presence_rejects_invalid_id_and_personal_fields(client):
    for body in [{"session_id": "invalid"}, {"session_id": str(uuid4()), "email": "child@example.com"}]:
        assert client.post("/api/v1/public/presence", json=body).status_code == 422


def test_admin_analytics_has_live_count(client, auth_headers):
    client.post("/api/v1/public/presence", json={"session_id": str(uuid4())})
    response = client.get("/api/v1/admin/stats", headers=auth_headers("admin"))
    assert response.status_code == 200
    assert response.json()["active_sessions"] == 1
