from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Iterator

from .config import DB_PATH, DEMO_EMAIL, DEMO_PASSWORD, DEMO_USER, MARKETS

UTC = timezone.utc


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def isoformat(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat()


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(
            '''
            PRAGMA journal_mode=WAL;

            CREATE TABLE IF NOT EXISTS assets (
                symbol TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                market_type TEXT NOT NULL,
                last_price REAL NOT NULL,
                change_rate REAL NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS candles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                candle_time TEXT NOT NULL,
                interval_type TEXT NOT NULL,
                open_price REAL NOT NULL,
                high_price REAL NOT NULL,
                low_price REAL NOT NULL,
                close_price REAL NOT NULL,
                volume REAL NOT NULL,
                UNIQUE(symbol, candle_time, interval_type)
            );

            CREATE TABLE IF NOT EXISTS strategies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                rule_type TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                rsi_buy_threshold REAL,
                rsi_sell_threshold REAL,
                volume_multiplier REAL,
                score_threshold REAL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                signal_type TEXT NOT NULL,
                strategy_name TEXT NOT NULL,
                score REAL NOT NULL,
                reason TEXT NOT NULL,
                price REAL NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS watchlists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_name TEXT NOT NULL,
                symbol TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(user_name, symbol)
            );

            CREATE TABLE IF NOT EXISTS notification_settings (
                user_name TEXT PRIMARY KEY,
                web_enabled INTEGER NOT NULL DEFAULT 1,
                email_enabled INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_name TEXT NOT NULL,
                signal_id INTEGER NOT NULL,
                is_read INTEGER NOT NULL DEFAULT 0,
                read_at TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(user_name, signal_id),
                FOREIGN KEY(signal_id) REFERENCES signals(id)
            );
            '''
        )
        seed_assets(conn)
        seed_strategies(conn)
        seed_demo_user(conn)
        seed_watchlist(conn)
        ensure_notification_settings(conn, DEMO_USER)


def seed_assets(conn: sqlite3.Connection) -> None:
    now = isoformat(utc_now())
    for symbol, meta in MARKETS.items():
        conn.execute(
            '''
            INSERT INTO assets(symbol, name, market_type, last_price, change_rate, updated_at)
            VALUES (?, ?, ?, ?, 0, ?)
            ON CONFLICT(symbol)
            DO UPDATE SET name = excluded.name,
                          market_type = excluded.market_type,
                          updated_at = excluded.updated_at
            ''',
            (symbol, meta['name'], meta['market_type'], meta['base_price'], now),
        )


def seed_strategies(conn: sqlite3.Connection) -> None:
    existing = conn.execute('SELECT COUNT(*) AS count FROM strategies').fetchone()['count']
    if existing:
        return

    now = isoformat(utc_now())
    conn.executemany(
        '''
        INSERT INTO strategies(
            name, rule_type, is_active, rsi_buy_threshold, rsi_sell_threshold,
            volume_multiplier, score_threshold, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        [
            ('RSI Reversion', 'rsi_reversion', 1, 35, 68, 1.2, None, now),
            ('Golden Cross', 'golden_cross', 1, None, None, None, None, now),
            ('Score Combo', 'score_combo', 1, 40, None, 1.3, 70, now),
        ],
    )


def seed_demo_user(conn: sqlite3.Connection) -> None:
    from .auth import hash_password

    existing = conn.execute('SELECT username FROM users WHERE username = ?', (DEMO_USER,)).fetchone()
    if existing:
        return
    conn.execute(
        '''
        INSERT INTO users(username, email, password_hash, created_at)
        VALUES (?, ?, ?, ?)
        ''',
        (DEMO_USER, DEMO_EMAIL, hash_password(DEMO_PASSWORD), isoformat(utc_now())),
    )


def seed_watchlist(conn: sqlite3.Connection) -> None:
    now = isoformat(utc_now())
    for symbol in ('KRW-BTC', 'KRW-ETH'):
        if symbol not in MARKETS:
            continue
        conn.execute(
            '''
            INSERT INTO watchlists(user_name, symbol, created_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_name, symbol) DO NOTHING
            ''',
            (DEMO_USER, symbol, now),
        )


def fetch_all(query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]


def fetch_one(query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute(query, params).fetchone()
        return dict(row) if row else None


def execute(query: str, params: tuple[Any, ...] = ()) -> None:
    with get_conn() as conn:
        conn.execute(query, params)


def get_user_by_username(username: str) -> dict[str, Any] | None:
    return fetch_one('SELECT * FROM users WHERE username = ?', (username,))


def create_user(*, username: str, email: str, password_hash: str) -> dict[str, Any]:
    now = isoformat(utc_now())
    with get_conn() as conn:
        conn.execute(
            '''
            INSERT INTO users(username, email, password_hash, created_at)
            VALUES (?, ?, ?, ?)
            ''',
            (username, email, password_hash, now),
        )
    ensure_notification_settings(None, username)
    user = fetch_one('SELECT id, username, email, created_at FROM users WHERE username = ?', (username,))
    assert user is not None
    return user


def ensure_notification_settings(conn: sqlite3.Connection | None, user_name: str) -> None:
    now = isoformat(utc_now())
    if conn is not None:
        conn.execute(
            '''
            INSERT INTO notification_settings(user_name, web_enabled, email_enabled, updated_at)
            VALUES (?, 1, 0, ?)
            ON CONFLICT(user_name) DO NOTHING
            ''',
            (user_name, now),
        )
        return
    with get_conn() as owned_conn:
        owned_conn.execute(
            '''
            INSERT INTO notification_settings(user_name, web_enabled, email_enabled, updated_at)
            VALUES (?, 1, 0, ?)
            ON CONFLICT(user_name) DO NOTHING
            ''',
            (user_name, now),
        )


def get_notification_settings(user_name: str) -> dict[str, Any]:
    ensure_notification_settings(None, user_name)
    settings = fetch_one(
        '''
        SELECT user_name, web_enabled, email_enabled, updated_at
        FROM notification_settings
        WHERE user_name = ?
        ''',
        (user_name,),
    )
    assert settings is not None
    settings['web_enabled'] = bool(settings['web_enabled'])
    settings['email_enabled'] = bool(settings['email_enabled'])
    return settings


def update_notification_settings(
    user_name: str,
    *,
    web_enabled: bool | None = None,
    email_enabled: bool | None = None,
) -> dict[str, Any]:
    current = get_notification_settings(user_name)
    next_web = current['web_enabled'] if web_enabled is None else web_enabled
    next_email = current['email_enabled'] if email_enabled is None else email_enabled
    execute(
        '''
        INSERT INTO notification_settings(user_name, web_enabled, email_enabled, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_name)
        DO UPDATE SET web_enabled = excluded.web_enabled,
                      email_enabled = excluded.email_enabled,
                      updated_at = excluded.updated_at
        ''',
        (user_name, int(next_web), int(next_email), isoformat(utc_now())),
    )
    return get_notification_settings(user_name)


def get_watchlist_for_user(user_name: str) -> list[dict[str, Any]]:
    return fetch_all(
        '''
        SELECT w.id, w.user_name, w.symbol, w.created_at, a.last_price, a.change_rate
        FROM watchlists w
        JOIN assets a ON a.symbol = w.symbol
        WHERE w.user_name = ?
        ORDER BY w.created_at DESC
        ''',
        (user_name,),
    )


def add_watchlist_item(user_name: str, symbol: str) -> None:
    execute(
        '''
        INSERT OR IGNORE INTO watchlists(user_name, symbol, created_at)
        VALUES (?, ?, ?)
        ''',
        (user_name, symbol, isoformat(utc_now())),
    )


def delete_watchlist_item(user_name: str, symbol: str) -> None:
    execute('DELETE FROM watchlists WHERE user_name = ? AND symbol = ?', (user_name, symbol))


def upsert_asset(
    *,
    symbol: str,
    name: str,
    market_type: str,
    last_price: float,
    change_rate: float = 0.0,
    updated_at: str | None = None,
) -> None:
    execute(
        '''
        INSERT INTO assets(symbol, name, market_type, last_price, change_rate, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(symbol)
        DO UPDATE SET name = excluded.name,
                      market_type = excluded.market_type,
                      last_price = excluded.last_price,
                      change_rate = excluded.change_rate,
                      updated_at = excluded.updated_at
        ''',
        (symbol, name, market_type, last_price, change_rate, updated_at or isoformat(utc_now())),
    )


def update_asset_price(
    symbol: str,
    *,
    last_price: float,
    change_rate: float | None = None,
    updated_at: str | None = None,
) -> None:
    row = fetch_one('SELECT symbol, name, market_type, change_rate FROM assets WHERE symbol = ?', (symbol,))
    if row is None:
        upsert_asset(
            symbol=symbol,
            name=symbol,
            market_type='COIN',
            last_price=last_price,
            change_rate=change_rate or 0.0,
            updated_at=updated_at,
        )
        return
    next_change = row['change_rate'] if change_rate is None else change_rate
    execute(
        '''
        UPDATE assets
        SET last_price = ?, change_rate = ?, updated_at = ?
        WHERE symbol = ?
        ''',
        (last_price, next_change, updated_at or isoformat(utc_now()), symbol),
    )


def upsert_candle(
    *,
    symbol: str,
    candle_time: str,
    interval_type: str,
    open_price: float,
    high_price: float,
    low_price: float,
    close_price: float,
    volume: float,
) -> None:
    execute(
        '''
        INSERT INTO candles(
            symbol, candle_time, interval_type, open_price, high_price, low_price, close_price, volume
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(symbol, candle_time, interval_type)
        DO UPDATE SET open_price = excluded.open_price,
                      high_price = excluded.high_price,
                      low_price = excluded.low_price,
                      close_price = excluded.close_price,
                      volume = excluded.volume
        ''',
        (symbol, candle_time, interval_type, open_price, high_price, low_price, close_price, volume),
    )


def fetch_recent_candles(symbol: str, limit: int = 120, interval_type: str | None = None) -> list[dict[str, Any]]:
    if interval_type is None:
        return fetch_all(
            '''
            SELECT *
            FROM (
                SELECT *
                FROM candles
                WHERE symbol = ?
                ORDER BY candle_time DESC
                LIMIT ?
            ) recent
            ORDER BY candle_time ASC
            ''',
            (symbol, limit),
        )
    return fetch_all(
        '''
        SELECT *
        FROM (
            SELECT *
            FROM candles
            WHERE symbol = ? AND interval_type = ?
            ORDER BY candle_time DESC
            LIMIT ?
        ) recent
        ORDER BY candle_time ASC
        ''',
        (symbol, interval_type, limit),
    )


def insert_signal_if_new(
    *,
    symbol: str,
    signal_type: str,
    strategy_name: str,
    score: float,
    reason: str,
    price: float,
    dedup_seconds: int,
) -> dict[str, Any] | None:
    threshold = isoformat(utc_now() - timedelta(seconds=dedup_seconds))
    with get_conn() as conn:
        recent = conn.execute(
            '''
            SELECT id
            FROM signals
            WHERE symbol = ?
              AND signal_type = ?
              AND strategy_name = ?
              AND created_at >= ?
            ORDER BY created_at DESC
            LIMIT 1
            ''',
            (symbol, signal_type, strategy_name, threshold),
        ).fetchone()
        if recent:
            return None
        cursor = conn.execute(
            '''
            INSERT INTO signals(symbol, signal_type, strategy_name, score, reason, price, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''',
            (symbol, signal_type, strategy_name, score, reason, price, isoformat(utc_now())),
        )
        signal_id = cursor.lastrowid
    return fetch_one('SELECT * FROM signals WHERE id = ?', (signal_id,))


def create_notifications_for_signal(signal_id: int, symbol: str) -> int:
    with get_conn() as conn:
        watchers = conn.execute(
            '''
            SELECT w.user_name
            FROM watchlists w
            JOIN notification_settings ns ON ns.user_name = w.user_name
            WHERE w.symbol = ?
              AND ns.web_enabled = 1
            ''',
            (symbol,),
        ).fetchall()
        inserted_count = 0
        now = isoformat(utc_now())
        for row in watchers:
            cursor = conn.execute(
                '''
                INSERT OR IGNORE INTO notifications(user_name, signal_id, is_read, read_at, created_at)
                VALUES (?, ?, 0, NULL, ?)
                ''',
                (row['user_name'], signal_id, now),
            )
            inserted_count += cursor.rowcount > 0
        return inserted_count


def fetch_notifications(user_name: str, limit: int = 30) -> list[dict[str, Any]]:
    rows = fetch_all(
        '''
        SELECT n.id,
               n.user_name,
               s.symbol,
               s.signal_type,
               s.strategy_name,
               s.reason,
               s.price,
               s.created_at,
               n.is_read,
               n.read_at
        FROM notifications n
        JOIN signals s ON s.id = n.signal_id
        WHERE n.user_name = ?
        ORDER BY n.created_at DESC
        LIMIT ?
        ''',
        (user_name, limit),
    )
    for row in rows:
        row['is_read'] = bool(row['is_read'])
    return rows


def mark_notification_read(user_name: str, notification_id: int) -> bool:
    with get_conn() as conn:
        current = conn.execute(
            'SELECT id FROM notifications WHERE id = ? AND user_name = ?',
            (notification_id, user_name),
        ).fetchone()
        if not current:
            return False
        conn.execute(
            'UPDATE notifications SET is_read = 1, read_at = ? WHERE id = ? AND user_name = ?',
            (isoformat(utc_now()), notification_id, user_name),
        )
        return True
