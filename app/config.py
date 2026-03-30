from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / 'data'
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / 'signal_flow.db'
DATABASE_URL = os.getenv('DATABASE_URL', os.getenv('SIGNAL_FLOW_DATABASE_URL', '')).strip()
APP_NAME = 'Signal Flow Live'
APP_VERSION = '0.4.0'
APP_ENV = os.getenv('SIGNAL_FLOW_APP_ENV', 'development').strip().lower()
IS_PRODUCTION = APP_ENV in {'production', 'prod'}

DEMO_USER = 'demo'
DEMO_EMAIL = 'demo@signal-flow.local'
DEMO_PASSWORD = 'demo1234'
DEFAULT_SECRET_KEY = 'signal-flow-dev-secret-key'
SECRET_KEY = os.getenv('SIGNAL_FLOW_SECRET_KEY', DEFAULT_SECRET_KEY)
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv('SIGNAL_FLOW_ACCESS_TOKEN_EXPIRE_MINUTES', '180'))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv('SIGNAL_FLOW_REFRESH_TOKEN_EXPIRE_DAYS', '30'))
PASSWORD_RESET_TOKEN_EXPIRE_MINUTES = int(os.getenv('SIGNAL_FLOW_PASSWORD_RESET_TOKEN_EXPIRE_MINUTES', '30'))
EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS = int(os.getenv('SIGNAL_FLOW_EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS', '24'))
BOOTSTRAP_CANDLES = int(os.getenv('SIGNAL_FLOW_BOOTSTRAP_CANDLES', '60'))
TICK_SECONDS = float(os.getenv('SIGNAL_FLOW_TICK_SECONDS', '2'))
CANDLE_INTERVAL_SECONDS = int(os.getenv('SIGNAL_FLOW_CANDLE_INTERVAL_SECONDS', '5'))
SIGNAL_DEDUP_SECONDS = int(os.getenv('SIGNAL_FLOW_SIGNAL_DEDUP_SECONDS', '60'))


def _is_truthy(raw: str | None, *, default: bool = False) -> bool:
    if raw is None:
        return default
    return raw.strip().lower() in {'1', 'true', 'yes', 'y', 'on'}


def _parse_csv(raw: str | None) -> list[str]:
    if not raw:
        return []
    values: list[str] = []
    seen: set[str] = set()
    for item in raw.split(','):
        value = item.strip()
        if not value or value in seen:
            continue
        seen.add(value)
        values.append(value)
    return values


AUTH_TOKEN_PREVIEW_ENABLED = _is_truthy(
    os.getenv('SIGNAL_FLOW_AUTH_TOKEN_PREVIEW_ENABLED'),
    default=not IS_PRODUCTION,
)


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
PUBLIC_API_BASE_URL = os.getenv('SIGNAL_FLOW_PUBLIC_API_BASE_URL', '').strip().rstrip('/')
PUBLIC_WEB_BASE_URL = os.getenv('SIGNAL_FLOW_PUBLIC_WEB_BASE_URL', '').strip().rstrip('/')
PUBLIC_WS_BASE_URL = os.getenv('SIGNAL_FLOW_PUBLIC_WS_BASE_URL', '').strip().rstrip('/')
CORS_ORIGINS = _parse_csv(os.getenv('SIGNAL_FLOW_CORS_ORIGINS'))
ANDROID_PACKAGE_NAME = os.getenv('SIGNAL_FLOW_ANDROID_PACKAGE_NAME', '').strip()
ANDROID_SHA256_CERT_FINGERPRINTS = _parse_csv(os.getenv('SIGNAL_FLOW_ANDROID_SHA256_CERT_FINGERPRINTS'))
ENABLE_DEMO_SEED = _is_truthy(os.getenv('SIGNAL_FLOW_ENABLE_DEMO_SEED'), default=not IS_PRODUCTION)
STRICT_STARTUP_VALIDATION = _is_truthy(
    os.getenv('SIGNAL_FLOW_STRICT_STARTUP_VALIDATION'),
    default=IS_PRODUCTION,
)


SUPPORTED_UPBIT_INTERVALS = {'1s', '1m', '3m', '5m', '10m', '15m', '30m', '60m', '240m'}
if UPBIT_INTERVAL not in SUPPORTED_UPBIT_INTERVALS:
    UPBIT_INTERVAL = '1s'


def runtime_config_issues() -> list[str]:
    issues: list[str] = []
    if IS_PRODUCTION and SECRET_KEY == DEFAULT_SECRET_KEY:
        issues.append('SIGNAL_FLOW_SECRET_KEY must be changed for production')
    if IS_PRODUCTION and ENABLE_DEMO_SEED:
        issues.append('SIGNAL_FLOW_ENABLE_DEMO_SEED must be disabled for production')
    if IS_PRODUCTION and not CORS_ORIGINS:
        issues.append('SIGNAL_FLOW_CORS_ORIGINS should be configured for production')
    if IS_PRODUCTION and not PUBLIC_WEB_BASE_URL:
        issues.append('SIGNAL_FLOW_PUBLIC_WEB_BASE_URL should be set for production')
    if IS_PRODUCTION and not PUBLIC_API_BASE_URL:
        issues.append('SIGNAL_FLOW_PUBLIC_API_BASE_URL should be set for production')
    if IS_PRODUCTION and not PUBLIC_WS_BASE_URL:
        issues.append('SIGNAL_FLOW_PUBLIC_WS_BASE_URL should be set for production')
    if PUBLIC_API_BASE_URL and not PUBLIC_WS_BASE_URL:
        issues.append('SIGNAL_FLOW_PUBLIC_WS_BASE_URL should be set when SIGNAL_FLOW_PUBLIC_API_BASE_URL is set')
    if PUBLIC_WEB_BASE_URL and not PUBLIC_WEB_BASE_URL.startswith('https://'):
        issues.append('SIGNAL_FLOW_PUBLIC_WEB_BASE_URL must use https://')
    if PUBLIC_API_BASE_URL and not PUBLIC_API_BASE_URL.startswith('https://'):
        issues.append('SIGNAL_FLOW_PUBLIC_API_BASE_URL must use https://')
    if PUBLIC_WS_BASE_URL and not PUBLIC_WS_BASE_URL.startswith('wss://'):
        issues.append('SIGNAL_FLOW_PUBLIC_WS_BASE_URL must use wss://')
    if ANDROID_PACKAGE_NAME and not ANDROID_SHA256_CERT_FINGERPRINTS:
        issues.append('SIGNAL_FLOW_ANDROID_SHA256_CERT_FINGERPRINTS should be set when SIGNAL_FLOW_ANDROID_PACKAGE_NAME is set')
    return issues


def enforce_runtime_requirements() -> None:
    issues = runtime_config_issues()
    if STRICT_STARTUP_VALIDATION and issues:
        raise RuntimeError('; '.join(issues))
