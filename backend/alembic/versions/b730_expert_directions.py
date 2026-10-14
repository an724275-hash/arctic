"""Explicit expert directions, preserving legacy assignments."""

from alembic import op
import sqlalchemy as sa

revision = "b730d2e1"
down_revision = "a62a14c0"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "expert_nominations",
        sa.Column(
            "expert_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column(
            "nomination_id",
            sa.String(36),
            sa.ForeignKey("nominations.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )
    # Existing experts previously covered all directions; new experts must be configured.
    op.execute(
        "INSERT INTO expert_nominations SELECT u.id,n.id FROM users u CROSS JOIN nominations n WHERE u.role='expert' AND n.is_active=true"
    )


def downgrade():
    op.drop_table("expert_nominations")
