from datetime import timedelta

import pytest
from sqlalchemy import select

from app.models import Assignment, Nomination, Project, Review, TeacherLink, utcnow


@pytest.fixture
def search_data(db, users):
    nomination_id = db.scalar(select(Nomination.id))
    now = utcnow()
    projects = [
        Project(
            user_id=users["participant"].id,
            nomination_id=nomination_id,
            title=f"Арктический лёд {i:03d}",
            abstract="Общее описание исследования",
            status="submitted" if i == 104 else "draft",
            created_at=now - timedelta(minutes=i),
        )
        for i in range(105)
    ]
    projects[104].abstract = "Уникальная метка%_для поиска"
    hidden = Project(
        user_id=users["participant2"].id,
        nomination_id=nomination_id,
        title="Чужая скрытая работа",
        abstract="Уникальная метка%_для поиска",
    )
    db.add_all(
        [
            *projects,
            hidden,
            TeacherLink(
                participant_id=users["participant"].id, teacher_id=users["teacher"].id, status="accepted"
            ),
        ]
    )
    db.flush()
    assignments = [
        Assignment(project_id=p.id, expert_id=users["expert"].id, created_at=p.created_at) for p in projects
    ]
    db.add_all(assignments)
    db.flush()
    db.add(
        Review(
            assignment_id=assignments[104].id,
            project_id=projects[104].id,
            expert_id=users["expert"].id,
            criteria_snapshot=[],
            scores={},
            weighted_score=80,
            comment="Рецензия отправлена",
        )
    )
    db.commit()
    return projects, hidden


def test_project_search_filters_before_pagination_and_preserves_role_scope(client, auth_headers, search_data):
    projects, hidden = search_data
    endpoint = "/api/v1/projects"
    for role in ["admin", "commission", "participant", "teacher", "expert"]:
        headers = auth_headers(role)
        page = client.get(endpoint, headers=headers, params={"limit": 100}).json()
        assert projects[104].id not in {row["id"] for row in page}
        found = client.get(
            endpoint, headers=headers, params={"q": "  лёд 104  ", "status": "submitted"}
        ).json()
        assert [row["id"] for row in found] == [projects[104].id]
        literal = client.get(endpoint, headers=headers, params={"q": "%_"}).json()
        expected = {projects[104].id, hidden.id} if role in {"admin", "commission"} else {projects[104].id}
        assert {row["id"] for row in literal} == expected
        page = client.get(
            endpoint, headers=headers, params={"q": "Арктический", "offset": 100, "limit": 2}
        ).json()
        assert [row["id"] for row in page] == [projects[100].id, projects[101].id]
    assert client.get(endpoint, headers=auth_headers("participant"), params={"q": "Чужая"}).json() == []
    assert (
        client.get(endpoint, headers=auth_headers("admin"), params={"status": "invalid"}).status_code == 422
    )
    assert client.get(endpoint, headers=auth_headers("admin"), params={"q": "x" * 201}).status_code == 422


def test_assignment_search_preserves_ownership_and_review_status(client, auth_headers, search_data):
    projects, _ = search_data
    endpoint = "/api/v1/expert/assignments"
    headers = auth_headers("expert")
    first_page = client.get(endpoint, headers=headers, params={"limit": 100}).json()
    assert projects[104].id not in {row["project_id"] for row in first_page}
    completed = client.get(endpoint, headers=headers, params={"q": "%_", "status": "completed"}).json()
    assert [row["project_id"] for row in completed] == [projects[104].id]
    assert completed[0]["review_submitted"] is True
    assert client.get(endpoint, headers=headers, params={"q": "%_", "status": "awaiting"}).json() == []
    assert client.get(endpoint, headers=headers, params={"q": "Чужая"}).json() == []
    page = client.get(
        endpoint, headers=headers, params={"status": "awaiting", "offset": 100, "limit": 2}
    ).json()
    assert [row["project_id"] for row in page] == [projects[100].id, projects[101].id]
    assert client.get(endpoint, headers=headers, params={"status": "draft"}).status_code == 422
    assert client.get(endpoint, headers=headers, params={"q": "x" * 201}).status_code == 422
    assert client.get(endpoint, headers=auth_headers("participant")).status_code == 403
