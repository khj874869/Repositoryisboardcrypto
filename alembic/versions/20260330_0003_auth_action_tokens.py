"""Add auth action tokens and email verification

Revision ID: 20260330_0003
Revises: 20260330_0002
Create Date: 2026-03-30 16:05:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = '20260330_0003'
down_revision = '20260330_0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('email_verified_at', sa.String(length=64), nullable=True))
    op.create_table(
        'auth_action_tokens',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_name', sa.String(length=64), nullable=False),
        sa.Column('token_hash', sa.String(length=128), nullable=False),
        sa.Column('token_type', sa.String(length=32), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.String(length=64), nullable=False),
        sa.Column('consumed_at', sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token_hash'),
    )


def downgrade() -> None:
    op.drop_table('auth_action_tokens')
    op.drop_column('users', 'email_verified_at')
