"""Initial schema

Revision ID: 20260330_0001
Revises:
Create Date: 2026-03-30 10:45:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = '20260330_0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'assets',
        sa.Column('symbol', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('market_type', sa.String(length=50), nullable=False),
        sa.Column('last_price', sa.Float(), nullable=False),
        sa.Column('change_rate', sa.Float(), nullable=False, server_default='0'),
        sa.Column('updated_at', sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint('symbol'),
    )
    op.create_table(
        'candles',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('symbol', sa.String(length=50), nullable=False),
        sa.Column('candle_time', sa.String(length=64), nullable=False),
        sa.Column('interval_type', sa.String(length=32), nullable=False),
        sa.Column('open_price', sa.Float(), nullable=False),
        sa.Column('high_price', sa.Float(), nullable=False),
        sa.Column('low_price', sa.Float(), nullable=False),
        sa.Column('close_price', sa.Float(), nullable=False),
        sa.Column('volume', sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('symbol', 'candle_time', 'interval_type', name='uq_candles_symbol_time_interval'),
    )
    op.create_table(
        'strategies',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('rule_type', sa.String(length=64), nullable=False),
        sa.Column('is_active', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('rsi_buy_threshold', sa.Float(), nullable=True),
        sa.Column('rsi_sell_threshold', sa.Float(), nullable=True),
        sa.Column('volume_multiplier', sa.Float(), nullable=True),
        sa.Column('score_threshold', sa.Float(), nullable=True),
        sa.Column('created_at', sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'signals',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('symbol', sa.String(length=50), nullable=False),
        sa.Column('signal_type', sa.String(length=16), nullable=False),
        sa.Column('strategy_name', sa.String(length=255), nullable=False),
        sa.Column('score', sa.Float(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('price', sa.Float(), nullable=False),
        sa.Column('created_at', sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('username', sa.String(length=64), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('username'),
    )
    op.create_table(
        'watchlists',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_name', sa.String(length=64), nullable=False),
        sa.Column('symbol', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_name', 'symbol', name='uq_watchlists_user_symbol'),
    )
    op.create_table(
        'notification_settings',
        sa.Column('user_name', sa.String(length=64), nullable=False),
        sa.Column('web_enabled', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('email_enabled', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('updated_at', sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint('user_name'),
    )
    op.create_table(
        'notifications',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_name', sa.String(length=64), nullable=False),
        sa.Column('signal_id', sa.Integer(), nullable=False),
        sa.Column('is_read', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('read_at', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(['signal_id'], ['signals.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_name', 'signal_id', name='uq_notifications_user_signal'),
    )


def downgrade() -> None:
    op.drop_table('notifications')
    op.drop_table('notification_settings')
    op.drop_table('watchlists')
    op.drop_table('users')
    op.drop_table('signals')
    op.drop_table('strategies')
    op.drop_table('candles')
    op.drop_table('assets')
