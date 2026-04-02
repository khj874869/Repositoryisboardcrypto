from __future__ import annotations

from typing import Any

from fastapi import Request

from . import db
from .config import (
    APP_ENV,
    APP_NAME,
    APP_VERSION,
    MARKETS,
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


def _configured_assets() -> list[dict[str, Any]]:
    configured_symbols = set(MARKETS.keys())
    return [row for row in db.fetch_all('SELECT * FROM assets ORDER BY symbol ASC') if row['symbol'] in configured_symbols]


def default_interval_type_for_symbol(symbol: str, active_interval_type: str | None) -> str | None:
    instrument = db.get_instrument(symbol)
    if instrument and not instrument['has_realtime_feed']:
        return db.DISCOVERABLE_SCANNER_INTERVAL
    return active_interval_type


def format_instrument_payload(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    runtime_state = row.get('runtime') or db.get_instrument_runtime_state(row['symbol'])
    return {
        'symbol': row['symbol'],
        'name': row['name'],
        'market_type': row['market_type'],
        'exchange': row['exchange'],
        'quote_currency': row['quote_currency'],
        'category': row['category'],
        'search_aliases': row.get('search_aliases', ''),
        'is_active': bool(row.get('is_active', True)),
        'capabilities': {
            'has_realtime_feed': bool(row['has_realtime_feed']),
            'has_volume_feed': bool(row['has_volume_feed']),
            'has_orderbook_feed': bool(row['has_orderbook_feed']),
            'has_derivatives_feed': bool(row['has_derivatives_feed']),
            'supports_indicator_profiles': bool(row['supports_indicator_profiles']),
        },
        'runtime': runtime_state,
        'last_price': row.get('last_price'),
        'change_rate': row.get('change_rate'),
        'updated_at': row.get('updated_at'),
    }


def _signal_delivery_priority(signal: dict[str, Any]) -> int:
    delivery = str(signal.get('notification_delivery') or 'pending')
    priority_map = {
        'notified': 0,
        'no_subscribers': 1,
        'pending': 2,
        'suppressed': 3,
    }
    return priority_map.get(delivery, 4)


def _is_audit_signal(signal: dict[str, Any], runtime_state: dict[str, Any] | None) -> bool:
    if not runtime_state or runtime_state.get('data_mode') != 'scanner':
        return False
    reason = str(signal.get('notification_delivery_reason') or '')
    if reason.startswith('scanner_'):
        return True
    return str(signal.get('notification_delivery') or '') == 'suppressed'


def build_signal_feed(
    limit: int,
    *,
    notification_delivery: str | None = None,
    data_mode: str | None = None,
    include_suppressed: bool = True,
    audit_only: bool = False,
) -> list[dict[str, Any]]:
    fetch_limit = max(limit * 4, limit, 20)
    rows = db.fetch_all('SELECT * FROM signals ORDER BY created_at DESC LIMIT ?', (fetch_limit,))
    runtime_states = db.get_instrument_runtime_states(list({row['symbol'] for row in rows}))
    filtered: list[dict[str, Any]] = []
    for row in rows:
        if not include_suppressed and row.get('notification_delivery') == 'suppressed':
            continue
        if notification_delivery and row.get('notification_delivery') != notification_delivery:
            continue
        if data_mode:
            runtime_state = runtime_states.get(row['symbol'])
            if (runtime_state or {}).get('data_mode') != data_mode:
                continue
        if audit_only and not _is_audit_signal(row, runtime_states.get(row['symbol'])):
            continue
        filtered.append(row)
    ranked = sorted(filtered, key=_signal_delivery_priority)
    return ranked[:limit]


def _interval_source(interval_type: str | None) -> str | None:
    if not interval_type:
        return None
    return interval_type.split('-', 1)[0]


def resolve_recent_candles(
    symbol: str,
    candle_limit: int,
    *,
    requested_interval_type: str | None,
    fallback_interval_type: str | None,
) -> dict[str, Any]:
    resolved_interval_type = requested_interval_type or fallback_interval_type
    requested_source = _interval_source(requested_interval_type)
    fallback_source = _interval_source(fallback_interval_type)

    if requested_interval_type and fallback_interval_type and requested_source != fallback_source:
        candles = db.fetch_recent_candles(symbol, candle_limit, interval_type=fallback_interval_type)
        return {
            'candles': candles,
            'interval_type': fallback_interval_type,
            'requested_interval_type': requested_interval_type,
            'interval_fallback_applied': True,
        }

    candles = db.fetch_recent_candles(symbol, candle_limit, interval_type=resolved_interval_type)
    if candles or not requested_interval_type or not fallback_interval_type or requested_interval_type == fallback_interval_type:
        return {
            'candles': candles,
            'interval_type': resolved_interval_type,
            'requested_interval_type': requested_interval_type,
            'interval_fallback_applied': False,
        }

    fallback_candles = db.fetch_recent_candles(symbol, candle_limit, interval_type=fallback_interval_type)
    if fallback_candles:
        return {
            'candles': fallback_candles,
            'interval_type': fallback_interval_type,
            'requested_interval_type': requested_interval_type,
            'interval_fallback_applied': True,
        }

    return {
        'candles': candles,
        'interval_type': resolved_interval_type,
        'requested_interval_type': requested_interval_type,
        'interval_fallback_applied': False,
    }


def evaluate_user_signal_profile(
    snapshot: Any | None,
    instrument: dict[str, Any] | None,
    profile: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if profile is None:
        return None
    if not profile['is_enabled']:
        return {
            'status': 'DISABLED',
            'score': 0.0,
            'reason': 'Custom profile is disabled for this symbol.',
            'blockers': [],
        }
    if snapshot is None:
        return {
            'status': 'UNAVAILABLE',
            'score': 0.0,
            'reason': 'No live candles are available for this symbol yet.',
            'blockers': ['live_candles_unavailable'],
        }

    blockers: list[str] = []
    if profile['use_orderbook_pressure'] and not (instrument and instrument['has_orderbook_feed']):
        blockers.append('orderbook_feed_unavailable')
    if profile['use_derivatives_confirm'] and not (instrument and instrument['has_derivatives_feed']):
        blockers.append('derivatives_feed_unavailable')
    if blockers:
        return {
            'status': 'UNAVAILABLE',
            'score': 0.0,
            'reason': 'Profile requests market data that is not available for this symbol.',
            'blockers': blockers,
        }

    buy_score = 0.0
    sell_score = 0.0
    reasons: list[str] = []
    if snapshot.rsi14 is not None and snapshot.rsi14 <= profile['rsi_buy_threshold']:
        buy_score += 35
        reasons.append(f"RSI {snapshot.rsi14:.1f} <= {profile['rsi_buy_threshold']:.1f}")
    if snapshot.rsi14 is not None and snapshot.rsi14 >= profile['rsi_sell_threshold']:
        sell_score += 35
    if snapshot.avg_volume_20 is not None and snapshot.volume >= snapshot.avg_volume_20 * profile['volume_multiplier']:
        buy_score += 20
        reasons.append(f"volume >= {profile['volume_multiplier']:.1f}x average")
    if snapshot.bollinger_lower is not None and snapshot.close_price <= snapshot.bollinger_lower * 1.01:
        buy_score += 25
        reasons.append('price near lower Bollinger')
    if snapshot.bollinger_upper is not None and snapshot.close_price >= snapshot.bollinger_upper * 0.99:
        sell_score += 25
    if None not in (snapshot.sma5, snapshot.sma20) and snapshot.sma5 > snapshot.sma20:
        buy_score += 20
        reasons.append('short trend leading')

    if sell_score >= profile['score_threshold']:
        return {
            'status': 'SELL',
            'score': round(sell_score, 1),
            'reason': f"Sell setup active. RSI {snapshot.rsi14:.1f} and upper band pressure are stretched.",
            'blockers': [],
        }
    if buy_score >= profile['score_threshold']:
        return {
            'status': 'BUY',
            'score': round(buy_score, 1),
            'reason': ', '.join(reasons) or 'Custom buy profile matched.',
            'blockers': [],
        }
    return {
        'status': 'WATCH',
        'score': round(max(buy_score, sell_score), 1),
        'reason': 'Profile conditions are not fully aligned yet.',
        'blockers': [],
    }


def build_market_catalog() -> list[dict[str, Any]]:
    return [
        {
            'symbol': row['symbol'],
            'name': row['name'],
            'market_type': row['market_type'],
            'last_price': row['last_price'],
            'change_rate': row['change_rate'],
            'updated_at': row['updated_at'],
        }
        for row in _configured_assets()
    ]


def build_market_overview(current_user: dict[str, Any] | None, *, interval_type: str | None) -> list[dict[str, Any]]:
    watchlist_symbols: set[str] = set()
    profiles_by_symbol: dict[str, dict[str, Any]] = {}
    symbols = {row['symbol'] for row in _configured_assets()}
    if current_user:
        watchlist_symbols = {row['symbol'] for row in db.fetch_all('SELECT symbol FROM watchlists WHERE user_name = ?', (current_user['username'],))}
        symbols.update(watchlist_symbols)
        profiles_by_symbol = {
            row['symbol']: row
            for row in db.fetch_all(
                'SELECT * FROM user_signal_profiles WHERE user_name = ?',
                (current_user['username'],),
            )
        }
        symbols.update(profiles_by_symbol.keys())

    assets = [row for row in db.fetch_all('SELECT * FROM assets ORDER BY symbol ASC') if row['symbol'] in symbols]
    instruments_by_symbol = {symbol: db.get_instrument(symbol) for symbol in symbols}
    runtime_state_by_symbol = db.get_instrument_runtime_states(list(symbols))
    assets.sort(
        key=lambda row: (
            0 if instruments_by_symbol.get(row['symbol'], {}).get('has_realtime_feed') else 1,
            0 if row['symbol'] in watchlist_symbols else 1,
            row['market_type'],
            row['symbol'],
        )
    )

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
        instrument = instruments_by_symbol.get(asset['symbol'])
        runtime_state = runtime_state_by_symbol.get(asset['symbol'])
        symbol_interval_type = default_interval_type_for_symbol(asset['symbol'], interval_type)
        candles = db.fetch_recent_candles(asset['symbol'], 120, interval_type=symbol_interval_type)
        signal = latest_signals.get(asset['symbol'])
        profile = profiles_by_symbol.get(asset['symbol'])
        if candles:
            snapshot = build_snapshot(asset['symbol'], candles)
            profile_signal = evaluate_user_signal_profile(snapshot, instrument, profile)
            overview.append(
                {
                    'symbol': asset['symbol'],
                    'name': asset['name'],
                    'price': asset['last_price'],
                    'change_rate': asset['change_rate'],
                    'data_mode': runtime_state['data_mode'] if runtime_state else None,
                    'data_source': runtime_state['data_source'] if runtime_state else None,
                    'market_session': runtime_state['market_session'] if runtime_state else None,
                    'is_delayed': bool(runtime_state['is_delayed']) if runtime_state else False,
                    'rsi14': snapshot.rsi14,
                    'sma5': snapshot.sma5,
                    'sma20': snapshot.sma20,
                    'bollinger_upper': snapshot.bollinger_upper,
                    'bollinger_lower': snapshot.bollinger_lower,
                    'recent_signal_type': signal['signal_type'] if signal else None,
                    'recent_signal_reason': signal['reason'] if signal else None,
                    'profile_signal_type': profile_signal['status'] if profile_signal and profile_signal['status'] in {'BUY', 'SELL'} else None,
                    'profile_signal_reason': profile_signal['reason'] if profile_signal and profile_signal['status'] in {'BUY', 'SELL'} else None,
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
                'data_mode': runtime_state['data_mode'] if runtime_state else None,
                'data_source': runtime_state['data_source'] if runtime_state else None,
                'market_session': runtime_state['market_session'] if runtime_state else None,
                'is_delayed': bool(runtime_state['is_delayed']) if runtime_state else False,
                'rsi14': None,
                'sma5': None,
                'sma20': None,
                'bollinger_upper': None,
                'bollinger_lower': None,
                'recent_signal_type': None,
                'recent_signal_reason': None,
                'profile_signal_type': None,
                'profile_signal_reason': None,
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
    signal_delivery: str | None = None,
    signal_data_mode: str | None = None,
    include_suppressed: bool = True,
    signal_audit_only: bool = False,
) -> dict[str, Any]:
    overview = build_market_overview(current_user, interval_type=interval_type)
    signals = build_signal_feed(
        signal_limit,
        notification_delivery=signal_delivery,
        data_mode=signal_data_mode,
        include_suppressed=include_suppressed,
        audit_only=signal_audit_only,
    )
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
    current_user: dict[str, Any] | None,
    requested_interval_type: str | None,
    fallback_interval_type: str | None,
    candle_limit: int,
    signal_limit: int,
) -> dict[str, Any] | None:
    asset = db.fetch_one('SELECT * FROM assets WHERE symbol = ?', (symbol,))
    if asset is None:
        return None
    instrument = db.get_instrument(symbol)
    runtime_state = db.get_instrument_runtime_state(symbol)
    resolved_fallback_interval = default_interval_type_for_symbol(symbol, fallback_interval_type)
    candle_result = resolve_recent_candles(
        symbol,
        candle_limit,
        requested_interval_type=requested_interval_type,
        fallback_interval_type=resolved_fallback_interval,
    )
    candles = candle_result['candles']
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
    profile = db.get_user_signal_profile(current_user['username'], symbol) if current_user else None
    profile_evaluation = None
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
        profile_evaluation = evaluate_user_signal_profile(computed, instrument, profile)
    elif profile:
        profile_evaluation = evaluate_user_signal_profile(None, instrument, profile)
    return {
        'asset': asset,
        'instrument': format_instrument_payload(
            {
                **instrument,
                'runtime': runtime_state,
                'last_price': asset.get('last_price'),
                'change_rate': asset.get('change_rate'),
                'updated_at': asset.get('updated_at'),
            } if instrument else None
        ),
        'interval_type': candle_result['interval_type'],
        'requested_interval_type': candle_result['requested_interval_type'],
        'interval_fallback_applied': candle_result['interval_fallback_applied'],
        'candles': candles,
        'signals': signals,
        'user_signal_profile': profile,
        'profile_evaluation': profile_evaluation,
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
            'refresh': '/api/auth/refresh',
            'logout': '/api/auth/logout',
            'sessions': '/api/auth/sessions',
            'request_password_reset': '/api/auth/password-reset/request',
            'reset_password': '/api/auth/password-reset/confirm',
            'request_email_verification': '/api/auth/email-verification/request',
            'verify_email': '/api/auth/email-verification/confirm',
            'me': '/api/auth/me',
            'overview': '/api/market/overview',
            'instrument_search': '/api/instruments/search',
            'instrument_detail': '/api/instruments/{symbol}',
            'signal_profile': '/api/signal-profiles/{symbol}',
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
            'instrument_search': True,
            'signal_profiles': True,
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
