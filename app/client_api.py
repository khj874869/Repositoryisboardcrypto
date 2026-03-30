from __future__ import annotations

from typing import Any

from fastapi import Request

from . import db
from .config import (
    APP_ENV,
    APP_NAME,
    APP_VERSION,
    PUBLIC_API_BASE_URL,
    PUBLIC_WS_BASE_URL,
    SUPPORTED_UPBIT_INTERVALS,
)
from .strategy_engine import build_snapshot


def resolve_api_base_url(request: Request) -> str:
    if PUBLIC_API_BASE_URL:
        return PUBLIC_API_BASE_URL
    return str(request.base_url).rstrip('/')


def resolve_websocket_url(request: Request) -> str:
    if PUBLIC_WS_BASE_URL:
        return PUBLIC_WS_BASE_URL
    api_base_url = resolve_api_base_url(request)
    if api_base_url.startswith('https://'):
        return f"wss://{api_base_url[len('https://'):]}/ws/stream"
    if api_base_url.startswith('http://'):
        return f"ws://{api_base_url[len('http://'):]}/ws/stream"
    return '/ws/stream'


def build_session_payload(current_user: dict[str, Any] | None) -> dict[str, Any]:
    return {
        'authenticated': current_user is not None,
        'user': current_user,
    }


def build_market_catalog() -> list[dict[str, Any]]:
    return db.fetch_all('SELECT symbol, name, market_type, last_price, change_rate, updated_at FROM assets ORDER BY symbol ASC')


def build_market_overview(current_user: dict[str, Any] | None, *, interval_type: str | None) -> list[dict[str, Any]]:
    assets = db.fetch_all('SELECT * FROM assets ORDER BY symbol ASC')
    watchlist_symbols: set[str] = set()
    if current_user:
        watchlist_symbols = {
            row['symbol']
            for row in db.fetch_all('SELECT symbol FROM watchlists WHERE user_name = ?', (current_user['username'],))
        }

    latest_signals = {
        row['symbol']: row
        for row in db.fetch_all(
            '''
            SELECT s1.*
            FROM signals s1
            JOIN (
              SELECT symbol, MAX(created_at) AS created_at
              FROM signals
              GROUP BY symbol
            ) s2 ON s1.symbol = s2.symbol AND s1.created_at = s2.created_at
            '''
        )
    }

    overview: list[dict[str, Any]] = []
    for asset in assets:
        candles = db.fetch_recent_candles(asset['symbol'], 120, interval_type=interval_type)
        signal = latest_signals.get(asset['symbol'])
        if candles:
            snapshot = build_snapshot(asset['symbol'], candles)
            overview.append(
                {
                    'symbol': asset['symbol'],
                    'name': asset['name'],
                    'price': asset['last_price'],
                    'change_rate': asset['change_rate'],
                    'rsi14': snapshot.rsi14,
                    'sma5': snapshot.sma5,
                    'sma20': snapshot.sma20,
                    'bollinger_upper': snapshot.bollinger_upper,
                    'bollinger_lower': snapshot.bollinger_lower,
                    'recent_signal_type': signal['signal_type'] if signal else None,
                    'recent_signal_reason': signal['reason'] if signal else None,
                    'in_watchlist': asset['symbol'] in watchlist_symbols,
                }
            )
            continue
        overview.append(
            {
                'symbol': asset['symbol'],
                'name': asset['name'],
                'price': asset['last_price'],
                'change_rate': asset['change_rate'],
                'rsi14': None,
                'sma5': None,
                'sma20': None,
                'bollinger_upper': None,
                'bollinger_lower': None,
                'recent_signal_type': None,
                'recent_signal_reason': None,
                'in_watchlist': asset['symbol'] in watchlist_symbols,
            }
        )
    return overview


def build_dashboard_payload(
    current_user: dict[str, Any] | None,
    *,
    source_status: dict[str, Any],
    interval_type: str | None,
    signal_limit: int,
    notification_limit: int,
) -> dict[str, Any]:
    overview = build_market_overview(current_user, interval_type=interval_type)
    signals = db.fetch_all('SELECT * FROM signals ORDER BY created_at DESC LIMIT ?', (signal_limit,))
    watchlist = db.get_watchlist_for_user(current_user['username']) if current_user else []
    notifications = db.fetch_notifications(current_user['username'], notification_limit) if current_user else []
    notification_settings = db.get_notification_settings(current_user['username']) if current_user else None
    unread_notifications = sum(1 for row in notifications if not row['is_read'])
    return {
        'session': build_session_payload(current_user),
        'source': source_status,
        'overview': overview,
        'signals': signals,
        'watchlist': watchlist,
        'notifications': notifications,
        'notification_settings': notification_settings,
        'counts': {
            'assets': len(overview),
            'watchlist': len(watchlist),
            'recent_signals': len(signals),
            'notifications': len(notifications),
            'unread_notifications': unread_notifications,
        },
    }


def build_asset_detail_payload(
    symbol: str,
    *,
    interval_type: str | None,
    candle_limit: int,
    signal_limit: int,
) -> dict[str, Any] | None:
    asset = db.fetch_one('SELECT * FROM assets WHERE symbol = ?', (symbol,))
    if asset is None:
        return None
    candles = db.fetch_recent_candles(symbol, candle_limit, interval_type=interval_type)
    signals = db.fetch_all(
        '''
        SELECT *
        FROM signals
        WHERE symbol = ?
        ORDER BY created_at DESC
        LIMIT ?
        ''',
        (symbol, signal_limit),
    )
    snapshot = None
    if candles:
        computed = build_snapshot(symbol, candles)
        snapshot = {
            'rsi14': computed.rsi14,
            'sma5': computed.sma5,
            'sma20': computed.sma20,
            'bollinger_upper': computed.bollinger_upper,
            'bollinger_lower': computed.bollinger_lower,
            'close_price': computed.close_price,
        }
    return {
        'asset': asset,
        'interval_type': interval_type,
        'candles': candles,
        'signals': signals,
        'snapshot': snapshot,
    }


def build_bootstrap_payload(
    request: Request,
    current_user: dict[str, Any] | None,
    *,
    source_status: dict[str, Any],
) -> dict[str, Any]:
    api_base_url = resolve_api_base_url(request)
    websocket_url = resolve_websocket_url(request)
    return {
        'app': {
            'name': APP_NAME,
            'version': APP_VERSION,
            'environment': APP_ENV,
        },
        'session': build_session_payload(current_user),
        'source': source_status,
        'platforms': [
            {'name': 'web', 'api_base_url': api_base_url, 'websocket_url': websocket_url},
            {'name': 'app', 'api_base_url': api_base_url, 'websocket_url': websocket_url},
        ],
        'endpoints': {
            'bootstrap': '/api/client/bootstrap',
            'dashboard': '/api/client/dashboard',
            'asset_detail': '/api/client/assets/{symbol}',
            'login': '/api/auth/login',
            'signup': '/api/auth/signup',
            'me': '/api/auth/me',
            'overview': '/api/market/overview',
            'signals_recent': '/api/signals/recent',
            'watchlist': '/api/watchlist',
            'notifications': '/api/notifications',
            'notification_settings': '/api/notification-settings',
            'websocket': websocket_url,
        },
        'features': {
            'auth': True,
            'watchlist': True,
            'notifications': True,
            'strategies': True,
            'realtime_stream': True,
            'web': True,
            'app': True,
        },
        'catalog': {
            'assets': [
                {
                    'symbol': row['symbol'],
                    'name': row['name'],
                    'market_type': row['market_type'],
                }
                for row in build_market_catalog()
            ],
            'supported_intervals': sorted(SUPPORTED_UPBIT_INTERVALS),
        },
    }
