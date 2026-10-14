from alembic import op
import sqlalchemy as sa

revision = "d510a7f3"
down_revision = "c410e8a2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "assistant_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_assistant_requests_user_id", "assistant_requests", ["user_id"])
    op.create_index("ix_assistant_requests_created_at", "assistant_requests", ["created_at"])


def downgrade():
    op.drop_table("assistant_requests")
