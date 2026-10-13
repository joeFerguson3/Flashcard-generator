"""session token on user, so sign-ins can be revoked (sign out everywhere)

Revision ID: 0004_session_token
Revises: 0003_analytics
Create Date: 2026-10-13 18:00:00

"""
from alembic import op
import sqlalchemy as sa


revision = '0004_session_token'
down_revision = '0003_analytics'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('user') as batch_op:
        batch_op.add_column(sa.Column('session_token', sa.String(length=64), nullable=True))


def downgrade():
    with op.batch_alter_table('user') as batch_op:
        batch_op.drop_column('session_token')
