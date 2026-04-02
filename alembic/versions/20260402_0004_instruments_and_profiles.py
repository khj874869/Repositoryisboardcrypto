"""Add instrument registry and user signal profiles

Revision ID: 20260402_0004
Revises: 20260330_0003
Create Date: 2026-04-02 10:20:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = '20260402_0004'
down_revision = '20260330_0003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'instruments',
        sa.Column('symbol', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('market_type', sa.String(length=50), nullable=False),
        sa.Column('exchange', sa.String(length=64), nullable=False),
        sa.Column('quote_currency', sa.String(length=16), nullable=False),
        sa.Column('category', sa.String(length=64), nullable=False),
        sa.Column('search_aliases', sa.Text(), nullable=False, server_default=''),
        sa.Column('has_realtime_feed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('has_volume_feed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('has_orderbook_feed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('has_derivatives_feed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('supports_indicator_profiles', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('is_active', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.String(length=64), nullable=False),
        sa.Column('updated_at', sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint('symbol'),
    )
    op.create_table(
        'user_signal_profiles',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_name', sa.String(length=64), nullable=False),
        sa.Column('symbol', sa.String(length=50), nullable=False),
        sa.Column('is_enabled', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('rsi_buy_threshold', sa.Float(), nullable=False, server_default='35'),
        sa.Column('rsi_sell_threshold', sa.Float(), nullable=False, server_default='68'),
        sa.Column('volume_multiplier', sa.Float(), nullable=False, server_default='1.3'),
        sa.Column('score_threshold', sa.Float(), nullable=False, server_default='70'),
        sa.Column('use_orderbook_pressure', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('orderbook_bias_threshold', sa.Float(), nullable=False, server_default='1.5'),
        sa.Column('use_derivatives_confirm', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('derivatives_bias_threshold', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('created_at', sa.String(length=64), nullable=False),
        sa.Column('updated_at', sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_name', 'symbol', name='uq_user_signal_profiles_user_symbol'),
    )


def downgrade() -> None:
    op.drop_table('user_signal_profiles')
    op.drop_table('instruments')
