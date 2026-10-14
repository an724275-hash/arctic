from alembic import op
import sqlalchemy as sa

revision = "e610b9c4"
down_revision = "d510a7f3"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "visitor_presence",
        sa.Column("session_hash", sa.String(64), primary_key=True),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_visitor_presence_last_seen", "visitor_presence", ["last_seen"])


def downgrade():
    op.drop_table("visitor_presence")
