from datetime import timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import Field
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.auth_schemas import InputModel
from app.common import audit
from app.db import get_db
from app.dependencies import get_current_user, require_roles
from app.models import ArticleComment, Content, User, utcnow

router = APIRouter(tags=["comments"])
Db = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
Admin = Annotated[User, Depends(require_roles("admin"))]
BUILTIN_ARTICLES = frozenset(
    {
        "nature",
        "culture",
        "idea",
        "arctic",
        "polar-bear-guide",
        "bear-islands",
        "fragile-ice",
        "arctic-professions",
        "help-arctic",
        "northern-sea-route",
    }
)


class CommentInput(InputModel):
    body: str = Field(min_length=2, max_length=2000)


class ModerationInput(InputModel):
    status: Literal["approved", "rejected"]
    reason: str = Field(default="", max_length=500)


def require_article(db, slug):
    if slug in BUILTIN_ARTICLES:
        return
    if not db.scalar(
        select(Content.id).where(
            Content.slug == slug, Content.published.is_(True), Content.kind.in_(["news", "education"])
        )
    ):
        raise HTTPException(404, "Статья не найдена")


def own_comment(row):
    return {
        "id": row.id,
        "body": row.body,
        "status": row.status,
        "reason": row.reason,
        "created_at": row.created_at,
    }


@router.get("/articles/{slug}/comments")
def article_comments(slug: str, db: Db, offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=50)):
    require_article(db, slug)
    query = (
        select(ArticleComment)
        .join(User, User.id == ArticleComment.user_id)
        .where(
            ArticleComment.article_slug == slug, ArticleComment.status == "approved", User.is_active.is_(True)
        )
    )
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(
        query.order_by(ArticleComment.created_at.desc(), ArticleComment.id).offset(offset).limit(limit)
    )
    return {
        "total": total,
        "items": [
            {"id": row.id, "body": row.body, "created_at": row.created_at, "author": "Участник обсуждения"}
            for row in rows
        ],
    }


@router.get("/articles/{slug}/comments/mine")
def my_comments(slug: str, db: Db, user: CurrentUser):
    require_article(db, slug)
    rows = db.scalars(
        select(ArticleComment)
        .where(
            ArticleComment.article_slug == slug,
            ArticleComment.user_id == user.id,
            ArticleComment.status != "withdrawn",
        )
        .order_by(ArticleComment.created_at.desc(), ArticleComment.id)
        .limit(50)
    )
    return [own_comment(row) for row in rows]


@router.post("/articles/{slug}/comments", status_code=201)
def send_comment(slug: str, payload: CommentInput, db: Db, user: CurrentUser):
    require_article(db, slug)
    user = db.scalar(
        select(User).where(User.id == user.id).with_for_update().execution_options(populate_existing=True)
    )
    if not user or not user.is_active or not user.consent_at:
        raise HTTPException(403, "Для участия нужно согласие на обработку данных")
    db.execute(
        delete(ArticleComment).where(
            ArticleComment.user_id == user.id,
            ArticleComment.status == "withdrawn",
            ArticleComment.created_at <= utcnow() - timedelta(hours=1),
        )
    )
    count = db.scalar(
        select(func.count())
        .select_from(ArticleComment)
        .where(ArticleComment.user_id == user.id, ArticleComment.created_at > utcnow() - timedelta(hours=1))
    )
    if count >= 5:
        raise HTTPException(429, "Можно отправить до пяти комментариев в час. Попробуй позже.")
    row = ArticleComment(article_slug=slug, user_id=user.id, body=payload.body)
    db.add(row)
    db.flush()
    result = own_comment(row)
    db.commit()
    return result


@router.delete("/article-comments/{comment_id}", status_code=204)
def remove_comment(comment_id: str, db: Db, user: CurrentUser):
    row = db.scalar(select(ArticleComment).where(ArticleComment.id == comment_id).with_for_update())
    if not row or row.user_id != user.id:
        raise HTTPException(404, "Комментарий не найден")
    row.body = ""
    row.reason = ""
    row.status = "withdrawn"
    db.commit()
    return Response(status_code=204)


@router.get("/admin/comments")
def moderation_queue(
    db: Db,
    actor: Admin,
    status: Literal["pending", "approved", "rejected"] = "pending",
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=50),
):
    query = (
        select(ArticleComment, User.full_name)
        .join(User, User.id == ArticleComment.user_id)
        .where(ArticleComment.status == status)
    )
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.execute(
        query.order_by(ArticleComment.created_at, ArticleComment.id).offset(offset).limit(limit)
    )
    return {
        "total": total,
        "items": [
            {**own_comment(row), "article_slug": row.article_slug, "author_name": name} for row, name in rows
        ],
    }


@router.patch("/admin/comments/{comment_id}")
def moderate_comment(comment_id: str, payload: ModerationInput, db: Db, actor: Admin):
    row = db.scalar(select(ArticleComment).where(ArticleComment.id == comment_id).with_for_update())
    if not row:
        raise HTTPException(404, "Комментарий не найден")
    if row.status == "withdrawn":
        raise HTTPException(409, "Комментарий удалён автором")
    author = db.get(User, row.user_id)
    if payload.status == "approved" and (not author or not author.is_active):
        raise HTTPException(409, "Нельзя публиковать комментарий отключённого аккаунта")
    row.status = payload.status
    row.reason = payload.reason
    row.moderated_at = utcnow()
    row.moderator_id = actor.id
    audit(db, actor.id, "comment.moderated", row.id, status=row.status)
    db.commit()
    return own_comment(row)
