"""add signal delivery metadata

Revision ID: 20260402_0006
Revises: 20260402_0005
Create Date: 2026-04-02 12:15:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = '20260402_0006'
down_revision = '20260402_0005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('signals', sa.Column('notification_delivery', sa.String(length=32), nullable=False, server_default='pending'))
    op.add_column('signals', sa.Column('notification_delivery_reason', sa.String(length=128), nullable=True))
    op.add_column('signals', sa.Column('notification_count', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    op.drop_column('signals', 'notification_count')
    op.drop_column('signals', 'notification_delivery_reason')
    op.drop_column('signals', 'notification_delivery')
