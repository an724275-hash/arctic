from sqlalchemy import select

from app.models import ArticleComment, Content

API = "/api/v1"
PATH = f"{API}/articles/arctic/comments"


def send(client, auth_headers, body="Вопрос об арктическом льде", **extra):
    return client.post(PATH, headers=auth_headers("participant"), json={"body": body, **extra})


def test_comments_are_private_until_admin_approval(client, auth_headers, users):
    assert client.post(PATH, json={"body": "Гостевой комментарий"}).status_code == 401
    assert send(client, auth_headers, status="approved").status_code == 422
    response = send(client, auth_headers)
    assert response.status_code == 201
    row = response.json()
    assert row["status"] == "pending"
    assert client.get(PATH).json() == {"total": 0, "items": []}
    assert len(client.get(PATH + "/mine", headers=auth_headers("participant")).json()) == 1
    assert client.get(PATH + "/mine", headers=auth_headers("participant2")).json() == []
    for role in ["participant", "expert", "teacher", "commission"]:
        assert client.get(f"{API}/admin/comments", headers=auth_headers(role)).status_code == 403
        assert (
            client.patch(
                f"{API}/admin/comments/{row['id']}", headers=auth_headers(role), json={"status": "approved"}
            ).status_code
            == 403
        )
    approved = client.patch(
        f"{API}/admin/comments/{row['id']}", headers=auth_headers("admin"), json={"status": "approved"}
    )
    assert approved.status_code == 200
    public = client.get(PATH).json()
    assert public["total"] == 1
    assert set(public["items"][0]) == {"id", "body", "created_at", "author"}
    assert users["participant"].full_name not in str(public)
    assert users["participant"].email not in str(public)


def test_rejection_reason_is_private_and_author_can_withdraw(client, auth_headers, db):
    row = send(client, auth_headers).json()
    rejected = client.patch(
        f"{API}/admin/comments/{row['id']}",
        headers=auth_headers("admin"),
        json={"status": "rejected", "reason": "Уточни вопрос по теме статьи\nИ добавь источник."},
    )
    assert rejected.status_code == 200
    assert client.get(PATH).json()["total"] == 0
    mine = client.get(PATH + "/mine", headers=auth_headers("participant")).json()
    assert mine[0]["reason"] == "Уточни вопрос по теме статьи\nИ добавь источник."
    assert (
        client.delete(f"{API}/article-comments/{row['id']}", headers=auth_headers("participant2")).status_code
        == 404
    )
    assert (
        client.delete(f"{API}/article-comments/{row['id']}", headers=auth_headers("participant")).status_code
        == 204
    )
    db.expire_all()
    record = db.get(ArticleComment, row["id"])
    assert record.body == "" and record.reason == "" and record.status == "withdrawn"
    assert client.get(PATH + "/mine", headers=auth_headers("participant")).json() == []
    assert (
        client.patch(
            f"{API}/admin/comments/{row['id']}", headers=auth_headers("admin"), json={"status": "approved"}
        ).status_code
        == 409
    )


def test_quota_cannot_be_bypassed_by_deleting_comments(client, auth_headers):
    for number in range(5):
        response = send(client, auth_headers, body=f"Комментарий для проверки {number}")
        assert response.status_code == 201
        assert (
            client.delete(
                f"{API}/article-comments/{response.json()['id']}", headers=auth_headers("participant")
            ).status_code
            == 204
        )
    assert send(client, auth_headers).status_code == 429


def test_unknown_and_draft_articles_do_not_accept_comments(client, auth_headers, db):
    article = Content(slug="private-comment-article", title="Черновик", kind="news", published=False)
    db.add(article)
    db.commit()
    path = f"{API}/articles/{article.slug}/comments"
    assert client.get(path).status_code == 404
    assert (
        client.post(path, headers=auth_headers("participant"), json={"body": "Текст комментария"}).status_code
        == 404
    )
    assert client.get(f"{API}/articles/unknown-article/comments").status_code == 404
    article.published = True
    db.commit()
    assert (
        client.post(path, headers=auth_headers("participant"), json={"body": "Текст комментария"}).status_code
        == 201
    )


def test_blocking_hides_comments_and_anonymization_removes_them(client, auth_headers, users, db):
    row = send(client, auth_headers).json()
    admin = auth_headers("admin")
    assert (
        client.patch(
            f"{API}/admin/comments/{row['id']}", headers=admin, json={"status": "approved"}
        ).status_code
        == 200
    )
    users["participant"].is_active = False
    db.commit()
    assert client.get(PATH).json()["total"] == 0
    assert (
        client.patch(
            f"{API}/admin/comments/{row['id']}", headers=admin, json={"status": "approved"}
        ).status_code
        == 409
    )
    assert client.delete(f"{API}/admin/users/{users['participant'].id}", headers=admin).status_code == 200
    assert (
        db.scalar(select(ArticleComment.id).where(ArticleComment.user_id == users["participant"].id)) is None
    )


def test_validation_and_public_pagination(client, auth_headers):
    for body in [" ", "x" * 2001, "bad\x00text"]:
        assert send(client, auth_headers, body=body).status_code == 422
    ids = []
    for index in range(3):
        row = send(client, auth_headers, body=f"Развёрнутый вопрос {index}").json()
        ids.append(row["id"])
        assert (
            client.patch(
                f"{API}/admin/comments/{row['id']}",
                headers=auth_headers("admin"),
                json={"status": "approved"},
            ).status_code
            == 200
        )
    page = client.get(PATH + "?limit=1&offset=1").json()
    assert page["total"] == 3 and len(page["items"]) == 1
    assert page["items"][0]["id"] == ids[1]
