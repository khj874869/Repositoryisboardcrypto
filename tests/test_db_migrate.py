from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, func, select

from app import db
from app.db_migrate import migrate_database


def _sqlite_url(path: Path) -> str:
    return f"sqlite:///{path.resolve().as_posix()}"


def test_migrate_database_copies_all_tables(tmp_path) -> None:
    source_path = tmp_path / 'source.db'
    target_path = tmp_path / 'target.db'

    source_engine = create_engine(_sqlite_url(source_path), future=True)
    target_engine = create_engine(_sqlite_url(target_path), future=True)

    with source_engine.begin() as conn:
        db.metadata.create_all(conn)
        conn.execute(
            db.assets.insert(),
            [
                {
                    'symbol': 'KRW-BTC',
                    'name': 'Bitcoin',
                    'market_type': 'crypto',
                    'last_price': 100.0,
                    'change_rate': 0.1,
                    'updated_at': '2026-03-30T00:00:00+00:00',
                }
            ],
        )
        conn.execute(
            db.strategies.insert(),
            [
                {
                    'id': 1,
                    'name': 'Momentum',
                    'rule_type': 'rsi_volume',
                    'is_active': 1,
                    'rsi_buy_threshold': 30.0,
                    'rsi_sell_threshold': 70.0,
                    'volume_multiplier': 1.5,
                    'score_threshold': 0.8,
                    'created_at': '2026-03-30T00:00:00+00:00',
                }
            ],
        )
        conn.execute(
            db.signals.insert(),
            [
                {
                    'id': 1,
                    'symbol': 'KRW-BTC',
                    'signal_type': 'buy',
                    'strategy_name': 'Momentum',
                    'score': 0.91,
                    'reason': 'RSI recovered',
                    'price': 100.0,
                    'created_at': '2026-03-30T00:01:00+00:00',
                }
            ],
        )
        conn.execute(
            db.users.insert(),
            [
                {
                    'id': 1,
                    'username': 'demo',
                    'email': 'demo@example.com',
                    'password_hash': 'hash',
                    'created_at': '2026-03-30T00:00:00+00:00',
                }
            ],
        )
        conn.execute(
            db.watchlists.insert(),
            [
                {
                    'id': 1,
                    'user_name': 'demo',
                    'symbol': 'KRW-BTC',
                    'created_at': '2026-03-30T00:02:00+00:00',
                }
            ],
        )
        conn.execute(
            db.notification_settings.insert(),
            [
                {
                    'user_name': 'demo',
                    'web_enabled': 1,
                    'email_enabled': 0,
                    'updated_at': '2026-03-30T00:03:00+00:00',
                }
            ],
        )
        conn.execute(
            db.notifications.insert(),
            [
                {
                    'id': 1,
                    'user_name': 'demo',
                    'signal_id': 1,
                    'is_read': 0,
                    'read_at': None,
                    'created_at': '2026-03-30T00:04:00+00:00',
                }
            ],
        )

    with target_engine.begin() as conn:
        db.metadata.create_all(conn)
        conn.execute(
            db.assets.insert(),
            [
                {
                    'symbol': 'KRW-ETH',
                    'name': 'Ethereum',
                    'market_type': 'crypto',
                    'last_price': 50.0,
                    'change_rate': 0.0,
                    'updated_at': '2026-03-30T00:00:00+00:00',
                }
            ],
        )

    result = migrate_database(_sqlite_url(source_path), _sqlite_url(target_path), reset_target=True)

    assert result['rows_copied'] == 7
    assert result['tables']['assets'] == 1
    assert result['tables']['notification_settings'] == 1
    assert result['tables']['notifications'] == 1

    with target_engine.connect() as conn:
        asset_symbols = conn.execute(select(db.assets.c.symbol)).scalars().all()
        usernames = conn.execute(select(db.users.c.username)).scalars().all()
        notification_total = conn.execute(select(func.count()).select_from(db.notifications)).scalar_one()

    assert asset_symbols == ['KRW-BTC']
    assert usernames == ['demo']
    assert notification_total == 1

    source_engine.dispose()
    target_engine.dispose()
