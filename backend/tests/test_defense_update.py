from sqlalchemy import select

from app.models import Defense, Notification
from test_admin import make_project


def test_reschedule_updates_same_meeting_and_notifies_participant(client, db, users, auth_headers):
    project = make_project(db, users["participant"])
    payload = {
        "project_id": project.id,
        "starts_at": "2030-01-15T09:30:00+09:00",
        "join_url": "https://meet.example.com/first",
        "description": "Первое назначение",
    }
    created = client.post("/api/v1/admin/defenses", headers=auth_headers("admin"), json=payload)
    assert created.status_code == 201
    meeting_id = created.json()["id"]
    updated = {
        **payload,
        "starts_at": "2030-01-16T10:45:00+09:00",
        "join_url": "https://meet.example.com/updated",
        "description": "Новое время и ссылка",
    }
    path = f"/api/v1/admin/defenses/{meeting_id}"
    for role in ["participant", "teacher", "expert", "commission"]:
        assert client.put(path, headers=auth_headers(role), json=updated).status_code == 403
    result = client.put(path, headers=auth_headers("admin"), json=updated)
    assert result.status_code == 200
    assert result.json()["id"] == meeting_id
    assert result.json()["join_url"] == updated["join_url"]
    db.expire_all()
    rows = db.scalars(select(Defense).where(Defense.project_id == project.id)).all()
    assert len(rows) == 1
    assert rows[0].starts_at.isoformat() == "2030-01-16T01:45:00+00:00"
    notification = db.scalar(
        select(Notification).where(
            Notification.user_id == users["participant"].id, Notification.title == "Обновлена защита проекта"
        )
    )
    assert notification is not None
    visible = client.get("/api/v1/defenses", headers=auth_headers("participant")).json()
    assert len(visible) == 1 and visible[0]["id"] == meeting_id
    assert visible[0]["description"] == updated["description"]
