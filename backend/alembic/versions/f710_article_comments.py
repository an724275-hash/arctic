from alembic import op
import sqlalchemy as sa

revision = "f710c8d2"
down_revision = "e610b9c4"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "article_comments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("article_slug", sa.String(160), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("body", sa.String(2000), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("moderated_at", sa.DateTime(timezone=True)),
        sa.Column("moderator_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.CheckConstraint(
            "status IN ('pending','approved','rejected','withdrawn')", name="ck_article_comments_status"
        ),
    )
    for name in ("article_slug", "user_id", "status", "created_at"):
        op.create_index(f"ix_article_comments_{name}", "article_comments", [name])


def downgrade():
    op.drop_table("article_comments")
