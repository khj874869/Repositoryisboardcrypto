from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / 'data'
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / 'signal_flow.db'
APP_VERSION = '0.3.0'

DEMO_USER = 'demo'
DEMO_EMAIL = 'demo@signal-flow.local'
DEMO_PASSWORD = 'demo1234'
SECRET_KEY = os.getenv('SIGNAL_FLOW_SECRET_KEY', 'signal-flow-dev-secret-key')
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv('SIGNAL_FLOW_ACCESS_TOKEN_EXPIRE_MINUTES', '180'))
BOOTSTRAP_CANDLES = int(os.getenv('SIGNAL_FLOW_BOOTSTRAP_CANDLES', '60'))
TICK_SECONDS = float(os.getenv('SIGNAL_FLOW_TICK_SECONDS', '2'))
CANDLE_INTERVAL_SECONDS = int(os.getenv('SIGNAL_FLOW_CANDLE_INTERVAL_SECONDS', '5'))
SIGNAL_DEDUP_SECONDS = int(os.getenv('SIGNAL_FLOW_SIGNAL_DEDUP_SECONDS', '60'))


def _is_truthy(raw: str | None, *, default: bool = False) -> bool:
    if raw is None:
        return default
    return raw.strip().lower() in {'1', 'true', 'yes', 'y', 'on'}


DEFAULT_SYMBOL_META = {
    'KRW-BTC': {'name': 'Bitcoin', 'market_type': 'COIN', 'base_price': 145_000_000.0, 'volatility': 0.006},
    'KRW-ETH': {'name': 'Ethereum', 'market_type': 'COIN', 'base_price': 5_100_000.0, 'volatility': 0.008},
    'KRW-XRP': {'name': 'XRP', 'market_type': 'COIN', 'base_price': 920.0, 'volatility': 0.015},
}


def _parse_market_list(raw: str | None) -> list[str]:
    if not raw:
        return list(DEFAULT_SYMBOL_META.keys())
    parsed: list[str] = []
    seen: set[str] = set()
    for item in raw.split(','):
        symbol = item.strip().upper()
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        parsed.append(symbol)
    return parsed or list(DEFAULT_SYMBOL_META.keys())


UPBIT_MARKETS = _parse_market_list(os.getenv('SIGNAL_FLOW_UPBIT_MARKETS'))
MARKETS = {
    symbol: DEFAULT_SYMBOL_META.get(
        symbol,
        {
            'name': symbol,
            'market_type': 'COIN',
            'base_price': 1_000.0,
            'volatility': 0.01,
        },
    )
    for symbol in UPBIT_MARKETS
}

DATA_SOURCE = os.getenv('SIGNAL_FLOW_DATA_SOURCE', 'upbit').strip().lower()
SOURCE_FALLBACK_TO_SIMULATOR = _is_truthy(os.getenv('SIGNAL_FLOW_SOURCE_FALLBACK_TO_SIMULATOR'), default=True)

UPBIT_API_BASE_URL = os.getenv('SIGNAL_FLOW_UPBIT_API_BASE_URL', 'https://api.upbit.com')
UPBIT_WS_URL = os.getenv('SIGNAL_FLOW_UPBIT_WS_URL', 'wss://api.upbit.com/websocket/v1')
UPBIT_INTERVAL = os.getenv('SIGNAL_FLOW_UPBIT_INTERVAL', '1s').strip().lower()
UPBIT_BOOTSTRAP_COUNT = int(os.getenv('SIGNAL_FLOW_UPBIT_BOOTSTRAP_COUNT', str(max(BOOTSTRAP_CANDLES, 60))))
UPBIT_HTTP_TIMEOUT_SECONDS = float(os.getenv('SIGNAL_FLOW_UPBIT_HTTP_TIMEOUT_SECONDS', '10'))
UPBIT_WS_PING_INTERVAL_SECONDS = float(os.getenv('SIGNAL_FLOW_UPBIT_WS_PING_INTERVAL_SECONDS', '30'))
UPBIT_WS_PING_TIMEOUT_SECONDS = float(os.getenv('SIGNAL_FLOW_UPBIT_WS_PING_TIMEOUT_SECONDS', '10'))
UPBIT_RECONNECT_SECONDS = float(os.getenv('SIGNAL_FLOW_UPBIT_RECONNECT_SECONDS', '2'))
MARKET_SNAPSHOT_PUSH_SECONDS = float(os.getenv('SIGNAL_FLOW_MARKET_SNAPSHOT_PUSH_SECONDS', '1'))


SUPPORTED_UPBIT_INTERVALS = {'1s', '1m', '3m', '5m', '10m', '15m', '30m', '60m', '240m'}
if UPBIT_INTERVAL not in SUPPORTED_UPBIT_INTERVALS:
    UPBIT_INTERVAL = '1s'
