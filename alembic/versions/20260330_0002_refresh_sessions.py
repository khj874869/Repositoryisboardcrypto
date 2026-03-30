"""Add refresh sessions

Revision ID: 20260330_0002
Revises: 20260330_0001
Create Date: 2026-03-30 15:40:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = '20260330_0002'
down_revision = '20260330_0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'refresh_sessions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_name', sa.String(length=64), nullable=False),
        sa.Column('token_hash', sa.String(length=128), nullable=False),
        sa.Column('client_name', sa.String(length=128), nullable=True),
        sa.Column('user_agent', sa.String(length=255), nullable=True),
        sa.Column('ip_address', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.String(length=64), nullable=False),
        sa.Column('last_used_at', sa.String(length=64), nullable=True),
        sa.Column('expires_at', sa.String(length=64), nullable=False),
        sa.Column('revoked_at', sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token_hash'),
    )


def downgrade() -> None:
    op.drop_table('refresh_sessions')
