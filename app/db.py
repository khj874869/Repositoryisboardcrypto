from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import math
from pathlib import Path
import random
from typing import Any, Iterator

from sqlalchemy import (
    Column,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    create_engine,
    delete,
    func,
    insert,
    select,
    text,
)
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Connection, Engine, make_url

from .config import DATABASE_URL, DB_PATH, DEMO_EMAIL, DEMO_PASSWORD, DEMO_USER, ENABLE_DEMO_SEED, MARKETS

UTC = timezone.utc
DISCOVERABLE_SCANNER_INTERVAL = 'scanner-1d'
DISCOVERABLE_SCANNER_CANDLES = 60

DISCOVERABLE_STOCKS = {
    'AAPL': {
        'name': 'Apple',
        'market_type': 'STOCK',
        'exchange': 'NASDAQ',
        'quote_currency': 'USD',
        'category': 'Large Cap Tech',
        'search_aliases': 'iphone ios big tech',
        'has_realtime_feed': 0,
        'has_volume_feed': 1,
        'has_orderbook_feed': 0,
        'has_derivatives_feed': 0,
        'supports_indicator_profiles': 1,
        'base_price': 205.0,
        'volatility': 0.022,
        'volume_base': 58_000_000.0,
    },
    'MSFT': {
        'name': 'Microsoft',
        'market_type': 'STOCK',
        'exchange': 'NASDAQ',
        'quote_currency': 'USD',
        'category': 'Large Cap Tech',
        'search_aliases': 'windows azure enterprise',
        'has_realtime_feed': 0,
        'has_volume_feed': 1,
        'has_orderbook_feed': 0,
        'has_derivatives_feed': 0,
        'supports_indicator_profiles': 1,
        'base_price': 428.0,
        'volatility': 0.017,
        'volume_base': 24_000_000.0,
    },
    'NVDA': {
        'name': 'NVIDIA',
        'market_type': 'STOCK',
        'exchange': 'NASDAQ',
        'quote_currency': 'USD',
        'category': 'Semiconductor',
        'search_aliases': 'gpu ai semiconductor',
        'has_realtime_feed': 0,
        'has_volume_feed': 1,
        'has_orderbook_feed': 0,
        'has_derivatives_feed': 0,
        'supports_indicator_profiles': 1,
        'base_price': 124.0,
        'volatility': 0.031,
        'volume_base': 46_000_000.0,
    },
    'TSLA': {
        'name': 'Tesla',
        'market_type': 'STOCK',
        'exchange': 'NASDAQ',
        'quote_currency': 'USD',
        'category': 'Auto',
        'search_aliases': 'ev electric vehicle',
        'has_realtime_feed': 0,
        'has_volume_feed': 1,
        'has_orderbook_feed': 0,
        'has_derivatives_feed': 0,
        'supports_indicator_profiles': 1,
        'base_price': 182.0,
        'volatility': 0.036,
        'volume_base': 96_000_000.0,
    },
    'SPY': {
        'name': 'SPDR S&P 500 ETF',
        'market_type': 'ETF',
        'exchange': 'NYSEARCA',
        'quote_currency': 'USD',
        'category': 'Index ETF',
        'search_aliases': 's&p 500 etf index',
        'has_realtime_feed': 0,
        'has_volume_feed': 1,
        'has_orderbook_feed': 0,
        'has_derivatives_feed': 0,
        'supports_indicator_profiles': 1,
        'base_price': 562.0,
        'volatility': 0.011,
        'volume_base': 72_000_000.0,
    },
    'QQQ': {
        'name': 'Invesco QQQ Trust',
        'market_type': 'ETF',
        'exchange': 'NASDAQ',
        'quote_currency': 'USD',
        'category': 'Index ETF',
        'search_aliases': 'nasdaq 100 etf index',
        'has_realtime_feed': 0,
        'has_volume_feed': 1,
        'has_orderbook_feed': 0,
        'has_derivatives_feed': 0,
        'supports_indicator_profiles': 1,
        'base_price': 486.0,
        'volatility': 0.013,
        'volume_base': 41_000_000.0,
    },
    '005930.KS': {
        'name': 'Samsung Electronics',
        'market_type': 'STOCK',
        'exchange': 'KRX',
        'quote_currency': 'KRW',
        'category': 'Korea Large Cap',
        'search_aliases': 'samsung semiconductors korea',
        'has_realtime_feed': 0,
        'has_volume_feed': 1,
        'has_orderbook_feed': 0,
        'has_derivatives_feed': 0,
        'supports_indicator_profiles': 1,
        'base_price': 83_500.0,
        'volatility': 0.018,
        'volume_base': 19_000_000.0,
    },
}

metadata = MetaData()

assets = Table(
    'assets',
    metadata,
    Column('symbol', String(50), primary_key=True),
    Column('name', String(255), nullable=False),
    Column('market_type', String(50), nullable=False),
    Column('last_price', Float, nullable=False),
    Column('change_rate', Float, nullable=False, server_default='0'),
    Column('updated_at', String(64), nullable=False),
)

instruments = Table(
    'instruments',
    metadata,
    Column('symbol', String(50), primary_key=True),
    Column('name', String(255), nullable=False),
    Column('market_type', String(50), nullable=False),
    Column('exchange', String(64), nullable=False),
    Column('quote_currency', String(16), nullable=False),
    Column('category', String(64), nullable=False),
    Column('search_aliases', Text, nullable=False, server_default=''),
    Column('has_realtime_feed', Integer, nullable=False, server_default='0'),
    Column('has_volume_feed', Integer, nullable=False, server_default='0'),
    Column('has_orderbook_feed', Integer, nullable=False, server_default='0'),
    Column('has_derivatives_feed', Integer, nullable=False, server_default='0'),
    Column('supports_indicator_profiles', Integer, nullable=False, server_default='1'),
    Column('is_active', Integer, nullable=False, server_default='1'),
    Column('created_at', String(64), nullable=False),
    Column('updated_at', String(64), nullable=False),
)

instrument_runtime_state = Table(
    'instrument_runtime_state',
    metadata,
    Column('symbol', String(50), primary_key=True),
    Column('data_mode', String(32), nullable=False),
    Column('data_source', String(64), nullable=False),
    Column('interval_type', String(32), nullable=False),
    Column('market_session', String(32), nullable=False),
    Column('is_delayed', Integer, nullable=False, server_default='0'),
    Column('as_of', String(64), nullable=False),
    Column('updated_at', String(64), nullable=False),
)

candles = Table(
    'candles',
    metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('symbol', String(50), nullable=False),
    Column('candle_time', String(64), nullable=False),
    Column('interval_type', String(32), nullable=False),
    Column('open_price', Float, nullable=False),
    Column('high_price', Float, nullable=False),
    Column('low_price', Float, nullable=False),
    Column('close_price', Float, nullable=False),
    Column('volume', Float, nullable=False),
    UniqueConstraint('symbol', 'candle_time', 'interval_type', name='uq_candles_symbol_time_interval'),
)

strategies = Table(
    'strategies',
    metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('name', String(255), nullable=False),
    Column('rule_type', String(64), nullable=False),
    Column('is_active', Integer, nullable=False, server_default='1'),
    Column('rsi_buy_threshold', Float),
    Column('rsi_sell_threshold', Float),
    Column('volume_multiplier', Float),
    Column('score_threshold', Float),
    Column('created_at', String(64), nullable=False),
)

signals = Table(
    'signals',
    metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('symbol', String(50), nullable=False),
    Column('signal_type', String(16), nullable=False),
    Column('strategy_name', String(255), nullable=False),
    Column('score', Float, nullable=False),
    Column('reason', Text, nullable=False),
    Column('price', Float, nullable=False),
    Column('notification_delivery', String(32), nullable=False, server_default='pending'),
    Column('notification_delivery_reason', String(128)),
    Column('notification_count', Integer, nullable=False, server_default='0'),
    Column('created_at', String(64), nullable=False),
)

users = Table(
    'users',
    metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('username', String(64), nullable=False, unique=True),
    Column('email', String(255), nullable=False, unique=True),
    Column('password_hash', String(255), nullable=False),
    Column('email_verified_at', String(64)),
    Column('created_at', String(64), nullable=False),
)

refresh_sessions = Table(
    'refresh_sessions',
    metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('user_name', String(64), nullable=False),
    Column('token_hash', String(128), nullable=False, unique=True),
    Column('client_name', String(128)),
    Column('user_agent', String(255)),
    Column('ip_address', String(64)),
    Column('created_at', String(64), nullable=False),
    Column('last_used_at', String(64)),
    Column('expires_at', String(64), nullable=False),
    Column('revoked_at', String(64)),
)

auth_action_tokens = Table(
    'auth_action_tokens',
    metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('user_name', String(64), nullable=False),
    Column('token_hash', String(128), nullable=False, unique=True),
    Column('token_type', String(32), nullable=False),
    Column('email', String(255)),
    Column('created_at', String(64), nullable=False),
    Column('expires_at', String(64), nullable=False),
    Column('consumed_at', String(64)),
)

watchlists = Table(
    'watchlists',
    metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('user_name', String(64), nullable=False),
    Column('symbol', String(50), nullable=False),
    Column('created_at', String(64), nullable=False),
    UniqueConstraint('user_name', 'symbol', name='uq_watchlists_user_symbol'),
)

notification_settings = Table(
    'notification_settings',
    metadata,
    Column('user_name', String(64), primary_key=True),
    Column('web_enabled', Integer, nullable=False, server_default='1'),
    Column('email_enabled', Integer, nullable=False, server_default='0'),
    Column('updated_at', String(64), nullable=False),
)

notifications = Table(
    'notifications',
    metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('user_name', String(64), nullable=False),
    Column('signal_id', Integer, ForeignKey('signals.id'), nullable=False),
    Column('is_read', Integer, nullable=False, server_default='0'),
    Column('read_at', String(64)),
    Column('created_at', String(64), nullable=False),
    UniqueConstraint('user_name', 'signal_id', name='uq_notifications_user_signal'),
)

user_signal_profiles = Table(
    'user_signal_profiles',
    metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('user_name', String(64), nullable=False),
    Column('symbol', String(50), nullable=False),
    Column('is_enabled', Integer, nullable=False, server_default='1'),
    Column('rsi_buy_threshold', Float, nullable=False, server_default='35'),
    Column('rsi_sell_threshold', Float, nullable=False, server_default='68'),
    Column('volume_multiplier', Float, nullable=False, server_default='1.3'),
    Column('score_threshold', Float, nullable=False, server_default='70'),
    Column('use_orderbook_pressure', Integer, nullable=False, server_default='0'),
    Column('orderbook_bias_threshold', Float, nullable=False, server_default='1.5'),
    Column('use_derivatives_confirm', Integer, nullable=False, server_default='0'),
    Column('derivatives_bias_threshold', Float, nullable=False, server_default='1.0'),
    Column('created_at', String(64), nullable=False),
    Column('updated_at', String(64), nullable=False),
    UniqueConstraint('user_name', 'symbol', name='uq_user_signal_profiles_user_symbol'),
)

_ENGINE: Engine | None = None
_ENGINE_URL: str | None = None


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def isoformat(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat()


def _sqlite_database_url(path: Path) -> str:
    return f"sqlite:///{path.resolve().as_posix()}"


def get_database_url() -> str:
    if DATABASE_URL:
        return DATABASE_URL
    return _sqlite_database_url(Path(DB_PATH))


def describe_database_url() -> str:
    return make_url(get_database_url()).render_as_string(hide_password=True)


def get_engine() -> Engine:
    global _ENGINE, _ENGINE_URL
    database_url = get_database_url()
    if _ENGINE is not None and _ENGINE_URL == database_url:
        return _ENGINE

    if _ENGINE is not None:
        _ENGINE.dispose()

    engine_kwargs: dict[str, Any] = {'future': True, 'pool_pre_ping': True}
    if database_url.startswith('sqlite'):
        engine_kwargs['connect_args'] = {'check_same_thread': False}

    _ENGINE = create_engine(database_url, **engine_kwargs)
    _ENGINE_URL = database_url
    return _ENGINE


def database_status() -> dict[str, Any]:
    engine = get_engine()
    status = {
        'url': describe_database_url(),
        'dialect': engine.dialect.name,
        'driver': engine.dialect.driver,
        'healthy': False,
        'error': None,
    }
    try:
        with engine.connect() as conn:
            conn.execute(text('SELECT 1'))
        status['healthy'] = True
    except Exception as exc:
        status['error'] = str(exc)
    return status


@contextmanager
def get_conn() -> Iterator[Connection]:
    with get_engine().begin() as conn:
        yield conn


def _prepare_query(query: str, params: tuple[Any, ...] | dict[str, Any] = ()) -> tuple[Any, dict[str, Any]]:
    if isinstance(params, dict):
        return text(query), params

    if not params:
        return text(query), {}

    placeholders = query.count('?')
    if placeholders != len(params):
        raise ValueError('Positional parameter count does not match placeholder count')

    pieces = query.split('?')
    rendered = pieces[0]
    bindings: dict[str, Any] = {}
    for idx, value in enumerate(params):
        key = f'p{idx}'
        rendered += f':{key}{pieces[idx + 1]}'
        bindings[key] = value
    return text(rendered), bindings


def _dialect_insert(conn: Connection, table: Table, values: dict[str, Any]):
    if conn.dialect.name == 'postgresql':
        return postgresql_insert(table).values(**values)
    return sqlite_insert(table).values(**values)


def _row_to_dict(row: Any) -> dict[str, Any]:
    return dict(row._mapping)


def init_db() -> None:
    engine = get_engine()
    with engine.begin() as conn:
        if conn.dialect.name == 'sqlite':
            conn.exec_driver_sql('PRAGMA foreign_keys=ON')
            conn.exec_driver_sql('PRAGMA journal_mode=WAL')
        metadata.create_all(conn)
        seed_instruments(conn)
        seed_assets(conn)
        seed_discoverable_scanner_data(conn)
        seed_strategies(conn)
        if ENABLE_DEMO_SEED:
            seed_demo_user(conn)
            seed_watchlist(conn)
            ensure_notification_settings(conn, DEMO_USER)


def _discoverable_instruments() -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for symbol, meta in MARKETS.items():
        rows[symbol] = {
            'name': meta['name'],
            'market_type': meta['market_type'],
            'exchange': 'UPBIT',
            'quote_currency': symbol.split('-', 1)[0] if '-' in symbol else 'KRW',
            'category': 'Crypto Spot',
            'search_aliases': f"{meta['name']} crypto coin upbit {symbol}",
            'has_realtime_feed': 1,
            'has_volume_feed': 1,
            'has_orderbook_feed': 0,
            'has_derivatives_feed': 0,
            'supports_indicator_profiles': 1,
        }
    rows.update(DISCOVERABLE_STOCKS)
    return rows


def seed_instruments(conn: Connection) -> None:
    now = isoformat(utc_now())
    for symbol, meta in _discoverable_instruments().items():
        values = {
            'symbol': symbol,
            'name': meta['name'],
            'market_type': meta['market_type'],
            'exchange': meta['exchange'],
            'quote_currency': meta['quote_currency'],
            'category': meta['category'],
            'search_aliases': meta.get('search_aliases', ''),
            'has_realtime_feed': int(meta.get('has_realtime_feed', 0)),
            'has_volume_feed': int(meta.get('has_volume_feed', 0)),
            'has_orderbook_feed': int(meta.get('has_orderbook_feed', 0)),
            'has_derivatives_feed': int(meta.get('has_derivatives_feed', 0)),
            'supports_indicator_profiles': int(meta.get('supports_indicator_profiles', 1)),
            'is_active': 1,
            'created_at': now,
            'updated_at': now,
        }
        stmt = _dialect_insert(conn, instruments, values).on_conflict_do_update(
            index_elements=['symbol'],
            set_={
                'name': values['name'],
                'market_type': values['market_type'],
                'exchange': values['exchange'],
                'quote_currency': values['quote_currency'],
                'category': values['category'],
                'search_aliases': values['search_aliases'],
                'has_realtime_feed': values['has_realtime_feed'],
                'has_volume_feed': values['has_volume_feed'],
                'has_orderbook_feed': values['has_orderbook_feed'],
                'has_derivatives_feed': values['has_derivatives_feed'],
                'supports_indicator_profiles': values['supports_indicator_profiles'],
                'is_active': values['is_active'],
                'updated_at': values['updated_at'],
            },
        )
        conn.execute(stmt)


def upsert_instrument_runtime_state(
    symbol: str,
    *,
    data_mode: str,
    data_source: str,
    interval_type: str,
    market_session: str,
    is_delayed: bool,
    as_of: str | None = None,
    updated_at: str | None = None,
) -> None:
    effective_as_of = as_of or isoformat(utc_now())
    effective_updated_at = updated_at or effective_as_of
    with get_conn() as conn:
        stmt = _dialect_insert(
            conn,
            instrument_runtime_state,
            {
                'symbol': symbol,
                'data_mode': data_mode,
                'data_source': data_source,
                'interval_type': interval_type,
                'market_session': market_session,
                'is_delayed': int(is_delayed),
                'as_of': effective_as_of,
                'updated_at': effective_updated_at,
            },
        ).on_conflict_do_update(
            index_elements=['symbol'],
            set_={
                'data_mode': data_mode,
                'data_source': data_source,
                'interval_type': interval_type,
                'market_session': market_session,
                'is_delayed': int(is_delayed),
                'as_of': effective_as_of,
                'updated_at': effective_updated_at,
            },
        )
        conn.execute(stmt)


def seed_assets(conn: Connection) -> None:
    now = isoformat(utc_now())
    for symbol, meta in MARKETS.items():
        values = {
            'symbol': symbol,
            'name': meta['name'],
            'market_type': meta['market_type'],
            'last_price': meta['base_price'],
            'change_rate': 0.0,
            'updated_at': now,
        }
        stmt = _dialect_insert(conn, assets, values).on_conflict_do_update(
            index_elements=['symbol'],
            set_={
                'name': values['name'],
                'market_type': values['market_type'],
                'updated_at': values['updated_at'],
            },
        )
        conn.execute(stmt)
        state_stmt = _dialect_insert(
            conn,
            instrument_runtime_state,
            {
                'symbol': symbol,
                'data_mode': 'realtime',
                'data_source': 'bootstrap',
                'interval_type': 'pending',
                'market_session': 'continuous',
                'is_delayed': 0,
                'as_of': now,
                'updated_at': now,
            },
        ).on_conflict_do_nothing(index_elements=['symbol'])
        conn.execute(state_stmt)


def _scanner_rows(symbol: str, meta: dict[str, Any]) -> list[dict[str, Any]]:
    anchor = utc_now().astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    rng = random.Random(f"scanner:{symbol}")
    last_close = float(meta['base_price'])
    rows: list[dict[str, Any]] = []
    for offset in range(DISCOVERABLE_SCANNER_CANDLES):
        candle_dt = anchor - timedelta(days=DISCOVERABLE_SCANNER_CANDLES - offset - 1)
        volatility = float(meta.get('volatility', 0.02))
        volume_base = float(meta.get('volume_base', 1_000_000.0))
        drift = ((offset % 10) - 4.5) * (volatility / 11)
        close_move = drift + rng.uniform(-volatility, volatility) * 0.75
        open_move = rng.uniform(-volatility, volatility) * 0.35
        open_price = max(0.01, last_close * (1 + open_move))
        close_price = max(0.01, last_close * (1 + close_move))
        wick_up = max(volatility * 0.7, 0.004) * rng.uniform(0.25, 1.0)
        wick_down = max(volatility * 0.7, 0.004) * rng.uniform(0.25, 1.0)
        high_price = max(open_price, close_price) * (1 + wick_up)
        low_price = min(open_price, close_price) * max(0.2, 1 - wick_down)
        volume = max(1.0, volume_base * (1 + rng.uniform(-0.45, 0.75)))
        rows.append(
            {
                'symbol': symbol,
                'candle_time': isoformat(candle_dt),
                'interval_type': DISCOVERABLE_SCANNER_INTERVAL,
                'open_price': round(open_price, 4),
                'high_price': round(high_price, 4),
                'low_price': round(low_price, 4),
                'close_price': round(close_price, 4),
                'volume': round(volume, 4),
            }
        )
        last_close = close_price
    return rows


def seed_discoverable_scanner_data(conn: Connection) -> None:
    now = isoformat(utc_now())
    for symbol, meta in DISCOVERABLE_STOCKS.items():
        rows = _scanner_rows(symbol, meta)
        previous_close = rows[-2]['close_price']
        latest = rows[-1]
        change_rate = 0.0
        if previous_close:
            change_rate = ((latest['close_price'] - previous_close) / previous_close) * 100

        asset_stmt = _dialect_insert(
            conn,
            assets,
            {
                'symbol': symbol,
                'name': meta['name'],
                'market_type': meta['market_type'],
                'last_price': latest['close_price'],
                'change_rate': change_rate,
                'updated_at': now,
            },
        ).on_conflict_do_update(
            index_elements=['symbol'],
            set_={
                'name': meta['name'],
                'market_type': meta['market_type'],
                'last_price': latest['close_price'],
                'change_rate': change_rate,
                'updated_at': now,
            },
        )
        conn.execute(asset_stmt)
        state_stmt = _dialect_insert(
            conn,
            instrument_runtime_state,
            {
                'symbol': symbol,
                'data_mode': 'scanner',
                'data_source': 'synthetic',
                'interval_type': DISCOVERABLE_SCANNER_INTERVAL,
                'market_session': 'synthetic',
                'is_delayed': 0,
                'as_of': latest['candle_time'],
                'updated_at': now,
            },
        ).on_conflict_do_nothing(index_elements=['symbol'])
        conn.execute(state_stmt)

        for row in rows:
            stmt = _dialect_insert(conn, candles, row).on_conflict_do_update(
                index_elements=['symbol', 'candle_time', 'interval_type'],
                set_={
                    'open_price': row['open_price'],
                    'high_price': row['high_price'],
                    'low_price': row['low_price'],
                    'close_price': row['close_price'],
                    'volume': row['volume'],
                },
            )
            conn.execute(stmt)


def seed_strategies(conn: Connection) -> None:
    existing = conn.execute(select(func.count()).select_from(strategies)).scalar_one()
    if existing:
        return

    now = isoformat(utc_now())
    conn.execute(
        insert(strategies),
        [
            {
                'name': 'RSI Reversion',
                'rule_type': 'rsi_reversion',
                'is_active': 1,
                'rsi_buy_threshold': 35,
                'rsi_sell_threshold': 68,
                'volume_multiplier': 1.2,
                'score_threshold': None,
                'created_at': now,
            },
            {
                'name': 'Golden Cross',
                'rule_type': 'golden_cross',
                'is_active': 1,
                'rsi_buy_threshold': None,
                'rsi_sell_threshold': None,
                'volume_multiplier': None,
                'score_threshold': None,
                'created_at': now,
            },
            {
                'name': 'Score Combo',
                'rule_type': 'score_combo',
                'is_active': 1,
                'rsi_buy_threshold': 40,
                'rsi_sell_threshold': None,
                'volume_multiplier': 1.3,
                'score_threshold': 70,
                'created_at': now,
            },
        ],
    )


def seed_demo_user(conn: Connection) -> None:
    from .auth import hash_password

    existing = conn.execute(select(users.c.username).where(users.c.username == DEMO_USER)).first()
    if existing:
        return
    conn.execute(
        insert(users).values(
            username=DEMO_USER,
            email=DEMO_EMAIL,
            password_hash=hash_password(DEMO_PASSWORD),
            email_verified_at=isoformat(utc_now()),
            created_at=isoformat(utc_now()),
        )
    )


def seed_watchlist(conn: Connection) -> None:
    now = isoformat(utc_now())
    for symbol in ('KRW-BTC', 'KRW-ETH', 'AAPL'):
        if symbol not in _discoverable_instruments():
            continue
        stmt = _dialect_insert(
            conn,
            watchlists,
            {
                'user_name': DEMO_USER,
                'symbol': symbol,
                'created_at': now,
            },
        ).on_conflict_do_nothing(index_elements=['user_name', 'symbol'])
        conn.execute(stmt)


def fetch_all(query: str, params: tuple[Any, ...] | dict[str, Any] = ()) -> list[dict[str, Any]]:
    statement, bindings = _prepare_query(query, params)
    with get_conn() as conn:
        rows = conn.execute(statement, bindings).mappings().all()
        return [dict(row) for row in rows]


def fetch_one(query: str, params: tuple[Any, ...] | dict[str, Any] = ()) -> dict[str, Any] | None:
    statement, bindings = _prepare_query(query, params)
    with get_conn() as conn:
        row = conn.execute(statement, bindings).mappings().first()
        return dict(row) if row else None


def execute(query: str, params: tuple[Any, ...] | dict[str, Any] = ()) -> None:
    statement, bindings = _prepare_query(query, params)
    with get_conn() as conn:
        conn.execute(statement, bindings)


def normalize_email(email: str) -> str:
    return email.strip().lower()


def get_user_by_username(username: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute(select(users).where(users.c.username == username)).mappings().first()
        return dict(row) if row else None


def get_user_by_email(email: str) -> dict[str, Any] | None:
    normalized_email = normalize_email(email)
    with get_conn() as conn:
        row = conn.execute(select(users).where(users.c.email == normalized_email)).mappings().first()
        return dict(row) if row else None


def get_user_by_login(login: str) -> dict[str, Any] | None:
    identifier = login.strip()
    if '@' in identifier:
        return get_user_by_email(identifier)
    return get_user_by_username(identifier)


def create_user(*, username: str, email: str, password_hash: str) -> dict[str, Any]:
    now = isoformat(utc_now())
    normalized_email = normalize_email(email)
    with get_conn() as conn:
        conn.execute(
            insert(users).values(
                username=username,
                email=normalized_email,
                password_hash=password_hash,
                email_verified_at=None,
                created_at=now,
            )
        )
        ensure_notification_settings(conn, username)
        row = conn.execute(
            select(users.c.id, users.c.username, users.c.email, users.c.email_verified_at, users.c.created_at).where(users.c.username == username)
        ).mappings().first()
    assert row is not None
    return dict(row)


def create_refresh_session(
    *,
    user_name: str,
    token_hash: str,
    expires_at: str,
    client_name: str | None = None,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> dict[str, Any]:
    now = isoformat(utc_now())
    with get_conn() as conn:
        result = conn.execute(
            insert(refresh_sessions).values(
                user_name=user_name,
                token_hash=token_hash,
                client_name=client_name,
                user_agent=user_agent,
                ip_address=ip_address,
                created_at=now,
                last_used_at=now,
                expires_at=expires_at,
                revoked_at=None,
            )
        )
        session_id = result.inserted_primary_key[0]
        row = conn.execute(select(refresh_sessions).where(refresh_sessions.c.id == session_id)).mappings().first()
    assert row is not None
    return dict(row)


def get_refresh_session_by_token_hash(token_hash: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute(select(refresh_sessions).where(refresh_sessions.c.token_hash == token_hash)).mappings().first()
        return dict(row) if row else None


def get_refresh_session_by_id(session_id: int) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute(select(refresh_sessions).where(refresh_sessions.c.id == session_id)).mappings().first()
        return dict(row) if row else None


def touch_refresh_session(session_id: int) -> None:
    with get_conn() as conn:
        conn.execute(
            refresh_sessions.update()
            .where(refresh_sessions.c.id == session_id)
            .values(last_used_at=isoformat(utc_now()))
        )


def revoke_refresh_session(session_id: int) -> None:
    with get_conn() as conn:
        conn.execute(
            refresh_sessions.update()
            .where(refresh_sessions.c.id == session_id, refresh_sessions.c.revoked_at.is_(None))
            .values(revoked_at=isoformat(utc_now()))
        )


def revoke_refresh_session_for_user(session_id: int, user_name: str) -> bool:
    with get_conn() as conn:
        result = conn.execute(
            refresh_sessions.update()
            .where(
                refresh_sessions.c.id == session_id,
                refresh_sessions.c.user_name == user_name,
                refresh_sessions.c.revoked_at.is_(None),
            )
            .values(revoked_at=isoformat(utc_now()))
        )
    return result.rowcount > 0


def list_refresh_sessions(user_name: str) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            select(refresh_sessions)
            .where(refresh_sessions.c.user_name == user_name)
            .order_by(refresh_sessions.c.created_at.desc(), refresh_sessions.c.id.desc())
        ).mappings().all()
    return [dict(row) for row in rows]


def create_auth_action_token(
    *,
    user_name: str,
    token_hash: str,
    token_type: str,
    email: str | None,
    expires_at: str,
) -> dict[str, Any]:
    now = isoformat(utc_now())
    with get_conn() as conn:
        result = conn.execute(
            insert(auth_action_tokens).values(
                user_name=user_name,
                token_hash=token_hash,
                token_type=token_type,
                email=email,
                created_at=now,
                expires_at=expires_at,
                consumed_at=None,
            )
        )
        token_id = result.inserted_primary_key[0]
        row = conn.execute(select(auth_action_tokens).where(auth_action_tokens.c.id == token_id)).mappings().first()
    assert row is not None
    return dict(row)


def revoke_auth_action_tokens(user_name: str, token_type: str) -> None:
    with get_conn() as conn:
        conn.execute(
            auth_action_tokens.update()
            .where(
                auth_action_tokens.c.user_name == user_name,
                auth_action_tokens.c.token_type == token_type,
                auth_action_tokens.c.consumed_at.is_(None),
            )
            .values(consumed_at=isoformat(utc_now()))
        )


def get_auth_action_token(token_hash: str, token_type: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute(
            select(auth_action_tokens).where(
                auth_action_tokens.c.token_hash == token_hash,
                auth_action_tokens.c.token_type == token_type,
            )
        ).mappings().first()
    return dict(row) if row else None


def consume_auth_action_token(token_id: int) -> None:
    with get_conn() as conn:
        conn.execute(
            auth_action_tokens.update()
            .where(auth_action_tokens.c.id == token_id, auth_action_tokens.c.consumed_at.is_(None))
            .values(consumed_at=isoformat(utc_now()))
        )


def mark_user_email_verified(user_name: str) -> dict[str, Any] | None:
    verified_at = isoformat(utc_now())
    with get_conn() as conn:
        conn.execute(
            users.update()
            .where(users.c.username == user_name)
            .values(email_verified_at=verified_at)
        )
        row = conn.execute(select(users).where(users.c.username == user_name)).mappings().first()
    return dict(row) if row else None


def update_user_password(user_name: str, password_hash: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        conn.execute(
            users.update()
            .where(users.c.username == user_name)
            .values(password_hash=password_hash)
        )
        row = conn.execute(select(users).where(users.c.username == user_name)).mappings().first()
    return dict(row) if row else None


def ensure_notification_settings(conn: Connection | None, user_name: str) -> None:
    now = isoformat(utc_now())
    owns_connection = conn is None
    if owns_connection:
        conn_ctx = get_conn()
        conn = conn_ctx.__enter__()
    try:
        stmt = _dialect_insert(
            conn,
            notification_settings,
            {
                'user_name': user_name,
                'web_enabled': 1,
                'email_enabled': 0,
                'updated_at': now,
            },
        ).on_conflict_do_nothing(index_elements=['user_name'])
        conn.execute(stmt)
    finally:
        if owns_connection:
            conn_ctx.__exit__(None, None, None)


def get_notification_settings(user_name: str) -> dict[str, Any]:
    ensure_notification_settings(None, user_name)
    with get_conn() as conn:
        settings = conn.execute(select(notification_settings).where(notification_settings.c.user_name == user_name)).mappings().first()
    assert settings is not None
    payload = dict(settings)
    payload['web_enabled'] = bool(payload['web_enabled'])
    payload['email_enabled'] = bool(payload['email_enabled'])
    return payload


def update_notification_settings(
    user_name: str,
    *,
    web_enabled: bool | None = None,
    email_enabled: bool | None = None,
) -> dict[str, Any]:
    current = get_notification_settings(user_name)
    next_web = current['web_enabled'] if web_enabled is None else web_enabled
    next_email = current['email_enabled'] if email_enabled is None else email_enabled
    with get_conn() as conn:
        stmt = _dialect_insert(
            conn,
            notification_settings,
            {
                'user_name': user_name,
                'web_enabled': int(next_web),
                'email_enabled': int(next_email),
                'updated_at': isoformat(utc_now()),
            },
        ).on_conflict_do_update(
            index_elements=['user_name'],
            set_={
                'web_enabled': int(next_web),
                'email_enabled': int(next_email),
                'updated_at': isoformat(utc_now()),
            },
        )
        conn.execute(stmt)


def list_scanner_instruments() -> list[dict[str, Any]]:
    rows = fetch_all(
        '''
        SELECT symbol, name, market_type, exchange, quote_currency, category
        FROM instruments
        WHERE is_active = 1
          AND has_realtime_feed = 0
        ORDER BY market_type ASC, symbol ASC
        '''
    )
    return rows


def refresh_scanner_market_data(now: datetime | None = None) -> list[dict[str, Any]]:
    effective_now = (now or utc_now()).astimezone(UTC)
    bucket = effective_now.replace(second=0, microsecond=0)
    candle_time = effective_now.replace(hour=0, minute=0, second=0, microsecond=0)
    day_progress = ((bucket.hour * 3600) + (bucket.minute * 60) + bucket.second) / 86400
    updates: list[dict[str, Any]] = []

    for symbol, meta in DISCOVERABLE_STOCKS.items():
        recent = fetch_recent_candles(symbol, 3, interval_type=DISCOVERABLE_SCANNER_INTERVAL)
        if not recent:
            continue

        latest = recent[-1]
        latest_time = datetime.fromisoformat(latest['candle_time']).astimezone(UTC)
        if latest_time == candle_time and len(recent) >= 2:
            previous_close = float(recent[-2]['close_price'])
        else:
            previous_close = float(latest['close_price'])

        volatility = float(meta.get('volatility', 0.02))
        volume_base = float(meta.get('volume_base', 1_000_000.0))
        rng = random.Random(f"scanner-refresh:{symbol}:{bucket.isoformat()}")
        drift_wave = math.sin(day_progress * math.tau * 2.2) * volatility * 0.55
        close_move = drift_wave + rng.uniform(-volatility, volatility) * 0.28
        open_move = rng.uniform(-volatility, volatility) * 0.08

        open_price = max(0.01, previous_close * (1 + open_move))
        close_price = max(0.01, previous_close * (1 + close_move))
        wick_up = max(volatility * 0.55, 0.004) * (0.35 + rng.random() * 0.8)
        wick_down = max(volatility * 0.55, 0.004) * (0.35 + rng.random() * 0.8)
        high_price = max(open_price, close_price) * (1 + wick_up)
        low_price = min(open_price, close_price) * max(0.2, 1 - wick_down)
        volume = max(1.0, volume_base * (0.55 + day_progress * 0.9 + rng.uniform(-0.12, 0.2)))
        change_rate = ((close_price - previous_close) / previous_close) * 100 if previous_close else 0.0

        upsert_candle(
            symbol=symbol,
            candle_time=isoformat(candle_time),
            interval_type=DISCOVERABLE_SCANNER_INTERVAL,
            open_price=round(open_price, 4),
            high_price=round(high_price, 4),
            low_price=round(low_price, 4),
            close_price=round(close_price, 4),
            volume=round(volume, 4),
        )
        update_asset_price(
            symbol,
            last_price=round(close_price, 4),
            change_rate=round(change_rate, 4),
            updated_at=isoformat(bucket),
        )
        upsert_instrument_runtime_state(
            symbol,
            data_mode='scanner',
            data_source='synthetic',
            interval_type=DISCOVERABLE_SCANNER_INTERVAL,
            market_session='synthetic',
            is_delayed=False,
            as_of=isoformat(candle_time),
            updated_at=isoformat(bucket),
        )
        updates.append(
            {
                'symbol': symbol,
                'price': round(close_price, 4),
                'change_rate': round(change_rate, 4),
                'candle_time': isoformat(candle_time),
                'updated_at': isoformat(bucket),
                'interval_type': DISCOVERABLE_SCANNER_INTERVAL,
                'source': 'scanner',
                'data_mode': 'scanner',
                'data_source': 'synthetic',
                'market_session': 'synthetic',
                'is_delayed': False,
            }
        )
    return updates
    return get_notification_settings(user_name)


def get_watchlist_for_user(user_name: str) -> list[dict[str, Any]]:
    return fetch_all(
        '''
        SELECT w.id,
               w.user_name,
               w.symbol,
               w.created_at,
               i.name,
               i.market_type,
               i.exchange,
               i.has_realtime_feed,
               a.last_price,
               a.change_rate
        FROM watchlists w
        LEFT JOIN instruments i ON i.symbol = w.symbol
        LEFT JOIN assets a ON a.symbol = w.symbol
        WHERE w.user_name = ?
        ORDER BY w.created_at DESC
        ''',
        (user_name,),
    )


def add_watchlist_item(user_name: str, symbol: str) -> None:
    with get_conn() as conn:
        stmt = _dialect_insert(
            conn,
            watchlists,
            {
                'user_name': user_name,
                'symbol': symbol,
                'created_at': isoformat(utc_now()),
            },
        ).on_conflict_do_nothing(index_elements=['user_name', 'symbol'])
        conn.execute(stmt)


def get_instrument(symbol: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute(select(instruments).where(instruments.c.symbol == symbol)).mappings().first()
    if not row:
        return None
    payload = dict(row)
    payload['has_realtime_feed'] = bool(payload['has_realtime_feed'])
    payload['has_volume_feed'] = bool(payload['has_volume_feed'])
    payload['has_orderbook_feed'] = bool(payload['has_orderbook_feed'])
    payload['has_derivatives_feed'] = bool(payload['has_derivatives_feed'])
    payload['supports_indicator_profiles'] = bool(payload['supports_indicator_profiles'])
    payload['is_active'] = bool(payload['is_active'])
    return payload


def get_instrument_runtime_state(symbol: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute(
            select(instrument_runtime_state).where(instrument_runtime_state.c.symbol == symbol)
        ).mappings().first()
    if not row:
        return None
    payload = dict(row)
    payload['is_delayed'] = bool(payload['is_delayed'])
    return payload


def get_instrument_runtime_states(symbols: list[str]) -> dict[str, dict[str, Any]]:
    if not symbols:
        return {}
    with get_conn() as conn:
        rows = conn.execute(
            select(instrument_runtime_state).where(instrument_runtime_state.c.symbol.in_(symbols))
        ).mappings().all()
    payload: dict[str, dict[str, Any]] = {}
    for row in rows:
        item = dict(row)
        item['is_delayed'] = bool(item['is_delayed'])
        payload[item['symbol']] = item
    return payload


def search_instruments(query: str = '', *, market_type: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    normalized_query = f"%{query.strip().lower()}%" if query.strip() else '%'
    rows = fetch_all(
        '''
        SELECT i.symbol,
               i.name,
               i.market_type,
               i.exchange,
               i.quote_currency,
               i.category,
               i.search_aliases,
               i.has_realtime_feed,
               i.has_volume_feed,
               i.has_orderbook_feed,
               i.has_derivatives_feed,
               i.supports_indicator_profiles,
               i.is_active,
               a.last_price,
               a.change_rate,
               a.updated_at
        FROM instruments i
        LEFT JOIN assets a ON a.symbol = i.symbol
        WHERE i.is_active = 1
          AND (:market_type IS NULL OR i.market_type = :market_type)
          AND (
                lower(i.symbol) LIKE :query
             OR lower(i.name) LIKE :query
             OR lower(i.exchange) LIKE :query
             OR lower(i.category) LIKE :query
             OR lower(i.search_aliases) LIKE :query
          )
        ORDER BY i.has_realtime_feed DESC, i.market_type ASC, i.symbol ASC
        LIMIT :limit
        ''',
        {
            'query': normalized_query,
            'market_type': market_type,
            'limit': max(1, min(limit, 50)),
        },
    )
    for row in rows:
        row['has_realtime_feed'] = bool(row['has_realtime_feed'])
        row['has_volume_feed'] = bool(row['has_volume_feed'])
        row['has_orderbook_feed'] = bool(row['has_orderbook_feed'])
        row['has_derivatives_feed'] = bool(row['has_derivatives_feed'])
        row['supports_indicator_profiles'] = bool(row['supports_indicator_profiles'])
        row['is_active'] = bool(row['is_active'])
    return rows


def _default_signal_profile(symbol: str) -> dict[str, Any]:
    instrument = get_instrument(symbol)
    orderbook_enabled = bool(instrument and instrument['has_orderbook_feed'])
    derivatives_enabled = bool(instrument and instrument['has_derivatives_feed'])
    return {
        'is_enabled': 1,
        'rsi_buy_threshold': 35.0,
        'rsi_sell_threshold': 68.0,
        'volume_multiplier': 1.3,
        'score_threshold': 70.0,
        'use_orderbook_pressure': int(orderbook_enabled),
        'orderbook_bias_threshold': 1.5,
        'use_derivatives_confirm': int(derivatives_enabled),
        'derivatives_bias_threshold': 1.0,
    }


def ensure_user_signal_profile(conn: Connection | None, user_name: str, symbol: str) -> None:
    now = isoformat(utc_now())
    defaults = _default_signal_profile(symbol)
    owns_connection = conn is None
    if owns_connection:
        conn_ctx = get_conn()
        conn = conn_ctx.__enter__()
    try:
        stmt = _dialect_insert(
            conn,
            user_signal_profiles,
            {
                'user_name': user_name,
                'symbol': symbol,
                **defaults,
                'created_at': now,
                'updated_at': now,
            },
        ).on_conflict_do_nothing(index_elements=['user_name', 'symbol'])
        conn.execute(stmt)
    finally:
        if owns_connection:
            conn_ctx.__exit__(None, None, None)


def get_user_signal_profile(user_name: str, symbol: str) -> dict[str, Any]:
    ensure_user_signal_profile(None, user_name, symbol)
    with get_conn() as conn:
        row = conn.execute(
            select(user_signal_profiles).where(
                user_signal_profiles.c.user_name == user_name,
                user_signal_profiles.c.symbol == symbol,
            )
        ).mappings().first()
    assert row is not None
    payload = dict(row)
    payload['is_enabled'] = bool(payload['is_enabled'])
    payload['use_orderbook_pressure'] = bool(payload['use_orderbook_pressure'])
    payload['use_derivatives_confirm'] = bool(payload['use_derivatives_confirm'])
    return payload


def update_user_signal_profile(
    user_name: str,
    symbol: str,
    *,
    is_enabled: bool | None = None,
    rsi_buy_threshold: float | None = None,
    rsi_sell_threshold: float | None = None,
    volume_multiplier: float | None = None,
    score_threshold: float | None = None,
    use_orderbook_pressure: bool | None = None,
    orderbook_bias_threshold: float | None = None,
    use_derivatives_confirm: bool | None = None,
    derivatives_bias_threshold: float | None = None,
) -> dict[str, Any]:
    current = get_user_signal_profile(user_name, symbol)
    next_values = {
        'is_enabled': int(current['is_enabled'] if is_enabled is None else is_enabled),
        'rsi_buy_threshold': current['rsi_buy_threshold'] if rsi_buy_threshold is None else rsi_buy_threshold,
        'rsi_sell_threshold': current['rsi_sell_threshold'] if rsi_sell_threshold is None else rsi_sell_threshold,
        'volume_multiplier': current['volume_multiplier'] if volume_multiplier is None else volume_multiplier,
        'score_threshold': current['score_threshold'] if score_threshold is None else score_threshold,
        'use_orderbook_pressure': int(current['use_orderbook_pressure'] if use_orderbook_pressure is None else use_orderbook_pressure),
        'orderbook_bias_threshold': current['orderbook_bias_threshold'] if orderbook_bias_threshold is None else orderbook_bias_threshold,
        'use_derivatives_confirm': int(current['use_derivatives_confirm'] if use_derivatives_confirm is None else use_derivatives_confirm),
        'derivatives_bias_threshold': current['derivatives_bias_threshold'] if derivatives_bias_threshold is None else derivatives_bias_threshold,
        'updated_at': isoformat(utc_now()),
    }
    with get_conn() as conn:
        stmt = _dialect_insert(
            conn,
            user_signal_profiles,
            {
                'user_name': user_name,
                'symbol': symbol,
                **_default_signal_profile(symbol),
                'created_at': isoformat(utc_now()),
                **next_values,
            },
        ).on_conflict_do_update(
            index_elements=['user_name', 'symbol'],
            set_=next_values,
        )
        conn.execute(stmt)
    return get_user_signal_profile(user_name, symbol)


def delete_watchlist_item(user_name: str, symbol: str) -> None:
    with get_conn() as conn:
        conn.execute(delete(watchlists).where(watchlists.c.user_name == user_name, watchlists.c.symbol == symbol))


def upsert_asset(
    *,
    symbol: str,
    name: str,
    market_type: str,
    last_price: float,
    change_rate: float = 0.0,
    updated_at: str | None = None,
) -> None:
    effective_updated_at = updated_at or isoformat(utc_now())
    with get_conn() as conn:
        stmt = _dialect_insert(
            conn,
            assets,
            {
                'symbol': symbol,
                'name': name,
                'market_type': market_type,
                'last_price': last_price,
                'change_rate': change_rate,
                'updated_at': effective_updated_at,
            },
        ).on_conflict_do_update(
            index_elements=['symbol'],
            set_={
                'name': name,
                'market_type': market_type,
                'last_price': last_price,
                'change_rate': change_rate,
                'updated_at': effective_updated_at,
            },
        )
        conn.execute(stmt)


def update_asset_price(
    symbol: str,
    *,
    last_price: float,
    change_rate: float | None = None,
    updated_at: str | None = None,
) -> None:
    row = fetch_one('SELECT symbol, name, market_type, change_rate FROM assets WHERE symbol = ?', (symbol,))
    if row is None:
        instrument = get_instrument(symbol)
        upsert_asset(
            symbol=symbol,
            name=instrument['name'] if instrument else symbol,
            market_type=instrument['market_type'] if instrument else 'COIN',
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
    with get_conn() as conn:
        stmt = _dialect_insert(
            conn,
            candles,
            {
                'symbol': symbol,
                'candle_time': candle_time,
                'interval_type': interval_type,
                'open_price': open_price,
                'high_price': high_price,
                'low_price': low_price,
                'close_price': close_price,
                'volume': volume,
            },
        ).on_conflict_do_update(
            index_elements=['symbol', 'candle_time', 'interval_type'],
            set_={
                'open_price': open_price,
                'high_price': high_price,
                'low_price': low_price,
                'close_price': close_price,
                'volume': volume,
            },
        )
        conn.execute(stmt)


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
            select(signals.c.id)
            .where(
                signals.c.symbol == symbol,
                signals.c.signal_type == signal_type,
                signals.c.strategy_name == strategy_name,
                signals.c.created_at >= threshold,
            )
            .order_by(signals.c.created_at.desc())
            .limit(1)
        ).first()
        if recent:
            return None
        result = conn.execute(
            insert(signals).values(
                symbol=symbol,
                signal_type=signal_type,
                strategy_name=strategy_name,
                score=score,
                reason=reason,
                price=price,
                created_at=isoformat(utc_now()),
            )
        )
        signal_id = result.inserted_primary_key[0]
    return fetch_one('SELECT * FROM signals WHERE id = ?', (signal_id,))


def update_signal_delivery(
    signal_id: int,
    *,
    notification_delivery: str,
    notification_delivery_reason: str | None,
    notification_count: int,
) -> dict[str, Any] | None:
    with get_conn() as conn:
        conn.execute(
            signals.update()
            .where(signals.c.id == signal_id)
            .values(
                notification_delivery=notification_delivery,
                notification_delivery_reason=notification_delivery_reason,
                notification_count=notification_count,
            )
        )
        row = conn.execute(select(signals).where(signals.c.id == signal_id)).mappings().first()
    return dict(row) if row else None


def create_notifications_for_signal(signal_id: int, symbol: str) -> int:
    with get_conn() as conn:
        watchers = conn.execute(
            text(
                '''
                SELECT w.user_name
                FROM watchlists w
                JOIN notification_settings ns ON ns.user_name = w.user_name
                WHERE w.symbol = :symbol
                  AND ns.web_enabled = 1
                '''
            ),
            {'symbol': symbol},
        ).mappings().all()
        inserted_count = 0
        now = isoformat(utc_now())
        for row in watchers:
            stmt = _dialect_insert(
                conn,
                notifications,
                {
                    'user_name': row['user_name'],
                    'signal_id': signal_id,
                    'is_read': 0,
                    'read_at': None,
                    'created_at': now,
                },
            ).on_conflict_do_nothing(index_elements=['user_name', 'signal_id'])
            result = conn.execute(stmt)
            inserted_count += int(bool(result.rowcount and result.rowcount > 0))
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
            select(notifications.c.id).where(
                notifications.c.id == notification_id,
                notifications.c.user_name == user_name,
            )
        ).first()
        if not current:
            return False
        conn.execute(
            notifications.update()
            .where(notifications.c.id == notification_id, notifications.c.user_name == user_name)
            .values(is_read=1, read_at=isoformat(utc_now()))
        )
        return True
