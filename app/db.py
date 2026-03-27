from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Iterator

from .config import DB_PATH, DEMO_USER, MARKETS

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

            CREATE TABLE IF NOT EXISTS watchlists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_name TEXT NOT NULL,
                symbol TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(user_name, symbol)
            );
            '''
        )
        seed_assets(conn)
        seed_strategies(conn)
        seed_watchlist(conn)


def seed_assets(conn: sqlite3.Connection) -> None:
    now = isoformat(utc_now())
    for symbol, meta in MARKETS.items():
        conn.execute(
            '''
            INSERT INTO assets(symbol, name, market_type, last_price, change_rate, updated_at)
            VALUES (?, ?, ?, ?, 0, ?)
            ON CONFLICT(symbol) DO NOTHING
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


def seed_watchlist(conn: sqlite3.Connection) -> None:
    now = isoformat(utc_now())
    for symbol in ('BTC-KRW', 'ETH-KRW'):
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



def insert_signal_if_new(
    *,
    symbol: str,
    signal_type: str,
    strategy_name: str,
    score: float,
    reason: str,
    price: float,
    dedup_seconds: int,
) -> bool:
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
            return False
        conn.execute(
            '''
            INSERT INTO signals(symbol, signal_type, strategy_name, score, reason, price, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''',
            (symbol, signal_type, strategy_name, score, reason, price, isoformat(utc_now())),
        )
        return True
