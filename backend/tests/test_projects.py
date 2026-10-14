from io import BytesIO
from uuid import uuid4
from zipfile import ZipFile

import pytest
from sqlalchemy import select

from app.config import settings
from app.models import Assignment, Criterion, Nomination, Notification, Stage, TeacherLink, Upload, User
from app.security import create_access_token


PDF = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n"


def extra_user(db, role):
    user = User(
        email=f"{uuid4().hex}@example.test",
        full_name=f"Другой {role}",
        role=role,
        hashed_password="unused-test-password",
        is_active=True,
        email_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user, {"Authorization": f"Bearer {create_access_token(user)}"}


def make_project(client, db, headers, title="Исследование арктического льда"):
    nomination = db.scalar(select(Nomination).where(Nomination.is_active.is_(True)))
    response = client.post(
        "/api/v1/projects",
        headers=headers,
        json={
            "title": title,
            "abstract": "Исследование состава и изменения арктического льда.",
            "nomination_id": nomination.id,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def add_document(client, project_id, headers, name="report.pdf", data=PDF):
    return client.post(
        f"/api/v1/projects/{project_id}/files",
        headers=headers,
        data={"kind": "document"},
        files={"file": (name, data, "application/pdf")},
    )


def admit_project(client, db, auth_headers):
    project = make_project(client, db, auth_headers("participant"))
    assert add_document(client, project["id"], auth_headers("participant")).status_code == 201
    response = client.post(f"/api/v1/projects/{project['id']}/submit", headers=auth_headers("participant"))
    assert response.status_code == 200, response.text
    response = client.post(
        f"/api/v1/admin/projects/{project['id']}/moderate",
        headers=auth_headers("admin"),
        json={"status": "admitted"},
    )
    assert response.status_code == 200, response.text
    return project


def review_payload(db, fraction=0.5):
    return {
        "scores": {
            c.id: c.max_score * fraction
            for c in db.scalars(select(Criterion).where(Criterion.is_active.is_(True)))
        },
        "comment": "Обоснованная работа с понятными результатами и выводами.",
    }


def test_project_access_and_private_download(client, db, users, auth_headers):
    owner = auth_headers("participant")
    project = make_project(client, db, owner)
    _, stranger = extra_user(db, "participant")
    upload = add_document(client, project["id"], owner, name="../../reports\\report.pdf")
    assert upload.status_code == 201, upload.text
    file = upload.json()
    assert file["original_name"] == "report.pdf"
    assert "stored_name" not in file
    for headers in (stranger, auth_headers("teacher"), auth_headers("expert")):
        assert client.get(f"/api/v1/projects/{project['id']}", headers=headers).status_code == 403
        assert client.get(f"/api/v1/files/{file['id']}/download", headers=headers).status_code == 403
        assert project["id"] not in {p["id"] for p in client.get("/api/v1/projects", headers=headers).json()}
    assert client.get(f"/api/v1/files/{file['id']}/download").status_code == 401
    db.add(
        TeacherLink(participant_id=users["participant"].id, teacher_id=users["teacher"].id, status="accepted")
    )
    db.commit()
    response = client.get(f"/api/v1/projects/{project['id']}", headers=auth_headers("teacher"))
    assert response.status_code == 200
    assert response.json()["participant_name"] == users["participant"].full_name
    assert "hashed_password" not in response.text
    downloaded = client.get(f"/api/v1/files/{file['id']}/download", headers=auth_headers("teacher"))
    assert downloaded.status_code == 200
    assert downloaded.content == PDF
    assert downloaded.headers["content-disposition"].startswith("attachment;")
    assert downloaded.headers["x-content-type-options"] == "nosniff"
    for role in ("teacher", "admin"):
        assert (
            client.patch(
                f"/api/v1/projects/{project['id']}",
                headers=auth_headers(role),
                json={"title": "Изменение названия"},
            ).status_code
            == 403
        )


def test_project_submit_requires_document_and_open_stage(client, db, auth_headers):
    owner = auth_headers("participant")
    project = make_project(client, db, owner)
    path = f"/api/v1/projects/{project['id']}"
    assert client.post(path + "/submit", headers=owner).status_code == 422
    assert add_document(client, project["id"], owner).status_code == 201
    stage = db.scalar(select(Stage).where(Stage.slug == "projects"))
    if stage is None:
        stage = Stage(slug="projects", title="Проектный этап", is_enabled=False)
        db.add(stage)
    else:
        stage.is_enabled = False
    db.commit()
    assert client.post(path + "/submit", headers=owner).status_code == 409
    stage.is_enabled = True
    stage.starts_at = None
    stage.ends_at = None
    db.commit()
    assert client.post(path + "/submit", headers=owner).json()["status"] == "submitted"
    assert client.patch(path, headers=owner, json={"title": "Новое название"}).status_code == 409
    assert client.delete(path, headers=owner).status_code == 409
    assert add_document(client, project["id"], owner).status_code == 409
    assert client.post(path + "/submit", headers=owner).status_code == 409


@pytest.mark.parametrize(
    "filename,data",
    [
        ("program.exe", b"MZ executable"),
        ("report.pdf", b"MZ executable disguised as PDF"),
        ("report.pdf", b""),
        ("report.docx", b"%PDF-1.4\n%%EOF"),
    ],
)
def test_invalid_uploads_leave_no_files(client, db, auth_headers, tmp_path, monkeypatch, filename, data):
    monkeypatch.setattr(settings, "uploads_dir", tmp_path)
    project = make_project(client, db, auth_headers("participant"))
    response = add_document(client, project["id"], auth_headers("participant"), filename, data)
    assert response.status_code == 422, response.text
    assert not any(item.is_file() for item in tmp_path.rglob("*"))
    assert list(db.scalars(select(Upload).where(Upload.project_id == project["id"]))) == []


def test_oversized_upload_is_bounded_and_cleans_temp_file(client, db, auth_headers, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "uploads_dir", tmp_path)
    monkeypatch.setattr(settings, "max_upload_mb", 1)
    project = make_project(client, db, auth_headers("participant"))
    response = add_document(
        client, project["id"], auth_headers("participant"), data=PDF + b"x" * (1024 * 1024)
    )
    assert response.status_code == 413, response.text
    assert not any(item.is_file() for item in tmp_path.rglob("*"))


def test_office_structure_and_embedded_executable_validation(client, db, auth_headers):
    project = make_project(client, db, auth_headers("participant"))

    def document(unsafe=False):
        output = BytesIO()
        with ZipFile(output, "w") as archive:
            archive.writestr(
                "[Content_Types].xml",
                '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>',
            )
            archive.writestr(
                "_rels/.rels",
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>',
            )
            archive.writestr(
                "word/document.xml",
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body/></w:document>',
            )
            if unsafe:
                archive.writestr("word/embeddings/run.exe", b"MZ")
        return output.getvalue()

    assert (
        add_document(
            client, project["id"], auth_headers("participant"), "report.docx", document()
        ).status_code
        == 201
    )
    assert (
        add_document(
            client, project["id"], auth_headers("participant"), "report.docx", document(True)
        ).status_code
        == 422
    )


def test_rejection_reopen_and_draft_file_cleanup(client, db, auth_headers, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "uploads_dir", tmp_path)
    owner = auth_headers("participant")
    project = make_project(client, db, owner)
    path = f"/api/v1/projects/{project['id']}"
    uploaded = add_document(client, project["id"], owner).json()
    assert client.post(path + "/submit", headers=owner).status_code == 200
    moderation = f"/api/v1/admin/projects/{project['id']}/moderate"
    assert client.post(moderation, headers=owner, json={"status": "admitted"}).status_code == 403
    assert (
        client.post(moderation, headers=auth_headers("admin"), json={"status": "rejected"}).status_code == 422
    )
    response = client.post(
        moderation,
        headers=auth_headers("admin"),
        json={"status": "rejected", "comment": "Добавьте описание метода исследования"},
    )
    assert response.json()["status"] == "rejected"
    assert client.patch(path, headers=owner, json={"title": "Уточнённая работа"}).status_code == 409
    assert client.post(path + "/reopen", headers=owner).json()["status"] == "draft"
    assert client.patch(path, headers=owner, json={"title": "Уточнённая работа"}).status_code == 200
    assert client.delete(path + f"/files/{uploaded['id']}", headers=owner).status_code == 204
    assert not any(item.is_file() for item in tmp_path.rglob("*"))
    assert add_document(client, project["id"], owner).status_code == 201
    assert client.delete(path, headers=owner).status_code == 204
    assert not any(item.is_file() for item in tmp_path.rglob("*"))
    assert client.get(path, headers=owner).status_code == 404


def test_full_expert_workflow_keeps_reviews_private_until_publication(client, db, users, auth_headers):
    project = admit_project(client, db, auth_headers)
    expert2, expert2_headers = extra_user(db, "expert")
    response = client.post(
        f"/api/v1/admin/projects/{project['id']}/assign",
        headers=auth_headers("admin"),
        json={
            "expert_ids": [users["expert"].id, expert2.id],
        },
    )
    assert response.status_code == 200, response.text
    assignments = {a["expert_id"]: a["id"] for a in response.json()["assignments"]}
    assert response.json()["assigned"] == 2
    own_assignment = assignments[users["expert"].id]
    peer_assignment = assignments[expert2.id]
    reviews_path = f"/api/v1/projects/{project['id']}/reviews"
    assert client.get(reviews_path, headers=auth_headers("participant")).json() == []
    response = client.post(
        f"/api/v1/expert/assignments/{own_assignment}/review",
        headers=auth_headers("expert"),
        json=review_payload(db, 0.5),
    )
    assert response.status_code == 201, response.text
    first_review = response.json()
    assert first_review["weighted_score"] == pytest.approx(50.0)
    assert client.get(reviews_path, headers=expert2_headers).json() == []
    assert client.get(reviews_path, headers=auth_headers("participant")).json() == []
    assert (
        client.get(f"/api/v1/projects/{project['id']}", headers=auth_headers("admin")).json()["status"]
        == "reviewing"
    )
    assert (
        client.post(
            f"/api/v1/expert/assignments/{own_assignment}/review",
            headers=expert2_headers,
            json=review_payload(db),
        ).status_code
        == 403
    )
    assert (
        client.put(
            f"/api/v1/expert/assignments/{own_assignment}/review",
            headers=auth_headers("expert"),
            json=review_payload(db),
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"/api/v1/admin/projects/{project['id']}/publish", headers=auth_headers("admin")
        ).status_code
        == 409
    )
    response = client.post(
        f"/api/v1/expert/assignments/{peer_assignment}/review",
        headers=expert2_headers,
        json=review_payload(db, 0.8),
    )
    assert response.status_code == 201, response.text
    assert response.json()["weighted_score"] == pytest.approx(80.0)
    assert client.get(reviews_path, headers=auth_headers("participant")).json() == []
    assert (
        client.get(f"/api/v1/projects/{project['id']}", headers=auth_headers("admin")).json()["status"]
        == "evaluated"
    )
    response = client.post(f"/api/v1/admin/projects/{project['id']}/publish", headers=auth_headers("admin"))
    assert response.status_code == 200, response.text
    published = client.get(reviews_path, headers=auth_headers("participant")).json()
    assert len(published) == 2
    assert {r["weighted_score"] for r in published} == {50.0, 80.0}
    criterion = db.get(Criterion, first_review["criteria_snapshot"][0]["id"])
    criterion.weight = 99
    db.commit()
    assert (
        client.get(reviews_path, headers=auth_headers("participant")).json()[0]["criteria_snapshot"]
        == first_review["criteria_snapshot"]
    )
    assert (
        client.post(
            f"/api/v1/admin/projects/{project['id']}/publish", headers=auth_headers("admin")
        ).status_code
        == 200
    )
    notifications = list(
        db.scalars(
            select(Notification).where(
                Notification.user_id == users["participant"].id,
                Notification.title == "Результаты экспертизы опубликованы",
            )
        )
    )
    assert len(notifications) == 1
    own = client.get("/api/v1/expert/assignments", headers=auth_headers("expert")).json()
    assert own[0]["review_submitted"] is True
    assert own[0]["own_review"]["expert_id"] == users["expert"].id


def test_review_requires_exact_rubric_and_valid_range(client, db, users, auth_headers):
    project = admit_project(client, db, auth_headers)
    response = client.post(
        f"/api/v1/admin/projects/{project['id']}/assign",
        headers=auth_headers("admin"),
        json={"expert_ids": [users["expert"].id]},
    )
    assignment = response.json()["assignments"][0]["id"]
    path = f"/api/v1/expert/assignments/{assignment}/review"
    payload = review_payload(db)
    criterion_id = next(iter(payload["scores"]))
    for scores in (
        {"unknown": 1},
        {**payload["scores"], criterion_id: -1},
        {**payload["scores"], criterion_id: 100000},
        {**payload["scores"], criterion_id: True},
    ):
        response = client.post(path, headers=auth_headers("expert"), json={**payload, "scores": scores})
        assert response.status_code == 422, response.text
    assert client.post(path, headers=auth_headers("participant"), json=payload).status_code == 403
    assert client.post(path, headers=auth_headers("expert"), json=payload).status_code == 201


def test_auto_assignment_balances_load_without_duplicates(client, db, users, auth_headers):
    expert2, _ = extra_user(db, "expert")
    projects = [admit_project(client, db, auth_headers) for _ in range(3)]
    payload = {"count": 2, "project_ids": [project["id"] for project in projects]}
    response = client.post("/api/v1/admin/projects/auto-assign", headers=auth_headers("admin"), json=payload)
    assert response.status_code == 200, response.text
    assert response.json()["assigned"] == 6
    loads = {
        expert.id: 0
        for expert in db.scalars(select(User).where(User.role == "expert", User.is_active.is_(True)))
    }
    for assignment in response.json()["assignments"]:
        loads[assignment["expert_id"]] += 1
    assert max(loads.values()) - min(loads.values()) <= 1
    assert (
        client.post("/api/v1/admin/projects/auto-assign", headers=auth_headers("admin"), json=payload).json()[
            "assigned"
        ]
        == 0
    )
    assert (
        len(list(db.scalars(select(Assignment).where(Assignment.project_id.in_(payload["project_ids"])))))
        == 6
    )


def test_project_validation_prevents_role_or_status_injection(client, db, auth_headers):
    project = make_project(client, db, auth_headers("participant"))
    path = f"/api/v1/projects/{project['id']}"
    assert (
        client.patch(path, headers=auth_headers("participant"), json={"status": "admitted"}).status_code
        == 422
    )
    assert client.patch(path, headers=auth_headers("participant"), json={"title": None}).status_code == 422
    for url in ("http://example.com/video", "javascript:alert(1)", "https://user:secret@example.com/video"):
        assert (
            client.patch(path, headers=auth_headers("participant"), json={"video_url": url}).status_code
            == 422
        )
    assert (
        client.patch(
            path, headers=auth_headers("participant"), json={"video_url": "https://example.com/video"}
        ).status_code
        == 200
    )
    assert client.get("/api/v1/projects?limit=201", headers=auth_headers("participant")).status_code == 422
