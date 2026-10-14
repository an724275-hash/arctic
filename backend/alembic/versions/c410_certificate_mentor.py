"""Preserve mentor name when a document is issued."""

from alembic import op
import sqlalchemy as sa

revision = "c410e8a2"
down_revision = "b730d2e1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("certificates", sa.Column("mentor_name", sa.String(200), nullable=True))


def downgrade():
    op.drop_column("certificates", "mentor_name")
