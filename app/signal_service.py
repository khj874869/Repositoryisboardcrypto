from __future__ import annotations

from typing import Any

from . import db
from .broadcaster import Broadcaster
from .config import SCANNER_ALERT_ALLOWED_SESSIONS, SCANNER_ALERT_ALLOW_DELAYED, SIGNAL_DEDUP_SECONDS
from .strategy_engine import build_snapshot, evaluate_strategies


def resolve_signal_delivery_policy(symbol: str) -> dict[str, Any]:
    runtime_state = db.get_instrument_runtime_state(symbol)
    if not runtime_state:
        return {'allow_notifications': True, 'reason': None}
    if runtime_state['data_mode'] != 'scanner':
        return {'allow_notifications': True, 'reason': None}
    if runtime_state['market_session'] not in SCANNER_ALERT_ALLOWED_SESSIONS:
        return {
            'allow_notifications': False,
            'reason': f"scanner_session_blocked:{runtime_state['market_session']}",
        }
    if runtime_state['is_delayed'] and not SCANNER_ALERT_ALLOW_DELAYED:
        return {
            'allow_notifications': False,
            'reason': 'scanner_delayed_blocked',
        }
    return {'allow_notifications': True, 'reason': None}


def resolve_signal_delivery_outcome(
    *,
    allow_notifications: bool,
    policy_reason: str | None,
    notification_count: int,
    audience: dict[str, int] | None = None,
) -> dict[str, Any]:
    if not allow_notifications:
        return {
            'notification_delivery': 'suppressed',
            'notification_delivery_reason': policy_reason,
        }
    if notification_count > 0:
        return {
            'notification_delivery': 'notified',
            'notification_delivery_reason': None,
        }

    audience = audience or {
        'watchlist_watchers': 0,
        'web_enabled_watchers': 0,
        'email_enabled_watchers': 0,
    }
    if audience['watchlist_watchers'] <= 0:
        reason = 'no_watchlist_subscribers'
    elif audience['web_enabled_watchers'] <= 0 and audience['email_enabled_watchers'] > 0:
        reason = 'email_only_delivery_not_implemented'
    else:
        reason = 'web_notifications_disabled'
    return {
        'notification_delivery': 'no_subscribers',
        'notification_delivery_reason': reason,
    }


async def evaluate_symbol_and_broadcast(symbol: str, broadcaster: Broadcaster, *, interval_type: str) -> None:
    candles = db.fetch_recent_candles(symbol, 120, interval_type=interval_type)
    strategies = db.fetch_all('SELECT * FROM strategies WHERE is_active = 1 ORDER BY id ASC')
    if len(candles) < 20 or not strategies:
        return

    snapshot = build_snapshot(symbol, candles)
    decisions = evaluate_strategies(snapshot, strategies)
    for decision in decisions:
        inserted_signal = db.insert_signal_if_new(
            symbol=symbol,
            signal_type=decision.signal_type,
            strategy_name=decision.strategy_name,
            score=decision.score,
            reason=decision.reason,
            price=snapshot.close_price,
            dedup_seconds=SIGNAL_DEDUP_SECONDS,
        )
        if inserted_signal:
            delivery = resolve_signal_delivery_policy(symbol)
            notification_count = 0
            audience: dict[str, int] | None = None
            if delivery['allow_notifications']:
                audience = db.get_signal_delivery_audience(symbol)
                notification_count = db.create_notifications_for_signal(inserted_signal['id'], symbol)
            outcome = resolve_signal_delivery_outcome(
                allow_notifications=delivery['allow_notifications'],
                policy_reason=delivery['reason'],
                notification_count=notification_count,
                audience=audience,
            )
            persisted_signal = db.update_signal_delivery(
                inserted_signal['id'],
                notification_delivery=outcome['notification_delivery'],
                notification_delivery_reason=outcome['notification_delivery_reason'],
                notification_count=notification_count,
            ) or inserted_signal
            await broadcaster.broadcast(
                'signal',
                {
                    'id': persisted_signal['id'],
                    'symbol': persisted_signal['symbol'],
                    'signal_type': persisted_signal['signal_type'],
                    'strategy_name': persisted_signal['strategy_name'],
                    'score': persisted_signal['score'],
                    'reason': persisted_signal['reason'],
                    'price': persisted_signal['price'],
                    'notification_delivery': persisted_signal['notification_delivery'],
                    'notification_delivery_reason': persisted_signal['notification_delivery_reason'],
                    'notification_count': persisted_signal['notification_count'],
                },
            )
