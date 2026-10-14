"""Participant city, preserving existing profiles."""
from alembic import op
import sqlalchemy as sa

revision = 'a62a14c0'
down_revision = 'e44a091a1abf'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('users', sa.Column('city', sa.String(150), nullable=True))
    op.add_column('users', sa.Column('avatar_kind', sa.String(20), nullable=False, server_default='bear'))
    op.add_column('users', sa.Column('avatar_filename', sa.String(100), nullable=True))

def downgrade():
    op.drop_column('users', 'avatar_filename')
    op.drop_column('users', 'avatar_kind')
    op.drop_column('users', 'city')
