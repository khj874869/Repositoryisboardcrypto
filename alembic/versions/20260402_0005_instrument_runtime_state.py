"""add instrument runtime state

Revision ID: 20260402_0005
Revises: 20260402_0004
Create Date: 2026-04-02 11:40:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = '20260402_0005'
down_revision = '20260402_0004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'instrument_runtime_state',
        sa.Column('symbol', sa.String(length=50), nullable=False),
        sa.Column('data_mode', sa.String(length=32), nullable=False),
        sa.Column('data_source', sa.String(length=64), nullable=False),
        sa.Column('interval_type', sa.String(length=32), nullable=False),
        sa.Column('market_session', sa.String(length=32), nullable=False),
        sa.Column('is_delayed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('as_of', sa.String(length=64), nullable=False),
        sa.Column('updated_at', sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint('symbol'),
    )


def downgrade() -> None:
    op.drop_table('instrument_runtime_state')
