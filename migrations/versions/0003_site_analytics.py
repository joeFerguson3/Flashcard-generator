"""site analytics: SiteEvent table and signup attribution on user

Revision ID: 0003_analytics
Revises: 0002_billing
Create Date: 2026-10-12 12:00:00

"""
from alembic import op
import sqlalchemy as sa


revision = '0003_analytics'
down_revision = '0002_billing'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('site_event',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('kind', sa.String(length=32), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('sid', sa.String(length=16), nullable=True),
    sa.Column('source', sa.String(length=60), nullable=True),
    sa.Column('path', sa.String(length=200), nullable=True),
    sa.Column('device', sa.String(length=10), nullable=True),
    sa.Column('detail', sa.String(length=200), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], name='fk_site_event_user', ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_site_event_kind_time', 'site_event', ['kind', 'created_at'], unique=False)
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('signup_source', sa.String(length=60), nullable=True))
        batch_op.add_column(sa.Column('signup_landing', sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column('signup_device', sa.String(length=10), nullable=True))
        batch_op.add_column(sa.Column('signup_sid', sa.String(length=16), nullable=True))


def downgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('signup_sid')
        batch_op.drop_column('signup_device')
        batch_op.drop_column('signup_landing')
        batch_op.drop_column('signup_source')
    op.drop_index('ix_site_event_kind_time', table_name='site_event')
    op.drop_table('site_event')
