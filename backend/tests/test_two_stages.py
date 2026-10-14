from sqlalchemy import select
from app.models import Nomination, QuizAttempt, utcnow
from test_projects import admit_project


def test_second_stage_requires_a_completed_passing_test(client, db, users, auth_headers):
    user = users["participant"]
    nomination = db.scalar(select(Nomination))
    payload = {
        "title": "Работа второго этапа",
        "abstract": "Исследование природы Арктики.",
        "nomination_id": nomination.id,
    }
    headers = auth_headers("participant")
    assert client.post("/api/v1/projects", json=payload, headers=headers).status_code == 409
    attempt = QuizAttempt(
        user_id=user.id,
        expires_at=utcnow(),
        questions=[],
        passed=False,
        submitted_at=utcnow(),
        score_percent=20,
    )
    db.add(attempt)
    db.commit()
    assert client.post("/api/v1/projects", json=payload, headers=headers).status_code == 409
    attempt.passed = True
    attempt.submitted_at = None
    db.commit()
    assert client.post("/api/v1/projects", json=payload, headers=headers).status_code == 409
    attempt.submitted_at = utcnow()
    attempt.score_percent = 100
    db.commit()
    assert client.post("/api/v1/projects", json=payload, headers=headers).status_code == 201


def test_experts_are_assigned_only_within_their_directions(client, db, users, auth_headers):
    project = admit_project(client, db, auth_headers)
    expert = users["expert"]
    endpoint = f"/api/v1/admin/experts/{expert.id}/directions"
    admin = auth_headers("admin")
    assert (
        client.put(endpoint, headers=auth_headers("expert"), json={"nomination_ids": []}).status_code == 403
    )
    assert client.put(endpoint, headers=admin, json={"nomination_ids": ["missing"]}).status_code == 422
    assert client.put(endpoint, headers=admin, json={"nomination_ids": []}).status_code == 200
    assign = f"/api/v1/admin/projects/{project['id']}/assign"
    assert client.post(assign, headers=admin, json={"expert_ids": [expert.id]}).status_code == 422
    assert (
        client.put(endpoint, headers=admin, json={"nomination_ids": [project["nomination_id"]]}).status_code
        == 200
    )
    assert client.post(assign, headers=admin, json={"expert_ids": [expert.id]}).status_code == 200


def test_full_analytics_and_review_exports_are_admin_only(client, auth_headers):
    for path in ["/api/v1/admin/export/analytics.json", "/api/v1/admin/export/reviews.csv"]:
        assert client.get(path, headers=auth_headers("participant")).status_code == 403
        response = client.get(path, headers=auth_headers("admin"))
        assert response.status_code == 200
        assert "attachment" in response.headers["content-disposition"]
