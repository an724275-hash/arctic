from uuid import uuid4

from sqlalchemy import select

from app.config import settings
from app.models import Upload
from test_projects import PDF, make_project


def send(client, project, headers, key, data=PDF, kind="document", name="report.pdf"):
    return client.post(
        f"/api/v1/projects/{project['id']}/files",
        headers=headers,
        data={"kind": kind, "upload_id": key},
        files={"file": (name, data, "application/pdf")},
    )


def test_retry_returns_saved_file_without_another_copy(client, db, auth_headers, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "uploads_dir", tmp_path)
    headers = auth_headers("participant")
    project = make_project(client, db, headers)
    key = str(uuid4())
    first = send(client, project, headers, key)
    assert first.status_code == 201
    repeated = send(client, project, headers, key)
    assert repeated.status_code == 200
    assert repeated.json() == first.json()
    assert first.json()["id"] == key
    assert len(db.scalars(select(Upload).where(Upload.project_id == project["id"])).all()) == 1
    assert len([p for p in tmp_path.rglob("*") if p.is_file()]) == 1


def test_reused_key_cannot_change_contents_kind_or_project(client, db, auth_headers, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "uploads_dir", tmp_path)
    headers = auth_headers("participant")
    project = make_project(client, db, headers)
    other = make_project(client, db, headers)
    key = str(uuid4())
    assert send(client, project, headers, key).status_code == 201
    for data in (PDF + b"extra", PDF.replace(b"1.4", b"1.5")):
        assert send(client, project, headers, key, data=data).status_code == 409
    assert send(client, project, headers, key, kind="presentation").status_code == 409
    assert send(client, project, headers, key, name="other.pdf").status_code == 409
    assert send(client, other, headers, key).status_code == 409
    assert send(client, project, auth_headers("participant2"), key).status_code == 403
    assert len([p for p in tmp_path.rglob("*") if p.is_file()]) == 1
    assert client.get(f"/api/v1/files/{key}/download", headers=headers).content == PDF


def test_failed_upload_does_not_reserve_key(client, db, auth_headers, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "uploads_dir", tmp_path)
    headers = auth_headers("participant")
    project = make_project(client, db, headers)
    key = str(uuid4())
    assert send(client, project, headers, key, data=b"invalid").status_code == 422
    assert not any(p.is_file() for p in tmp_path.rglob("*"))
    assert send(client, project, headers, key).status_code == 201
    assert send(client, project, headers, "invalid-key").status_code == 422
    assert len([p for p in tmp_path.rglob("*") if p.is_file()]) == 1
