from __future__ import annotations

import asyncio

from app import db, signal_service
from app.strategy_engine import SignalDecision


class CaptureBroadcaster:
    def __init__(self) -> None:
        self.messages: list[tuple[str, dict]] = []

    async def broadcast(self, message_type: str, payload: dict) -> None:
        self.messages.append((message_type, payload))


def _force_buy_decision(monkeypatch) -> None:
    monkeypatch.setattr(
        signal_service,
        'evaluate_strategies',
        lambda snapshot, strategies: [
            SignalDecision(
                signal_type='BUY',
                strategy_name='Forced Buy',
                score=88.0,
                reason='Forced test decision',
            )
        ],
    )


def test_scanner_signal_notifications_are_suppressed_outside_allowed_session(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(db, 'DB_PATH', tmp_path / 'signal_flow_test.db')
    db.init_db()
    _force_buy_decision(monkeypatch)
    broadcaster = CaptureBroadcaster()

    asyncio.run(
        signal_service.evaluate_symbol_and_broadcast(
            'AAPL',
            broadcaster,
            interval_type=db.DISCOVERABLE_SCANNER_INTERVAL,
        )
    )

    notifications = db.fetch_notifications('demo')
    assert notifications == []
    signals = db.fetch_all('SELECT * FROM signals WHERE symbol = ? ORDER BY created_at DESC', ('AAPL',))
    assert signals
    assert signals[0]['notification_delivery'] == 'suppressed'
    assert signals[0]['notification_delivery_reason'] == 'scanner_session_blocked:synthetic'
    assert signals[0]['notification_count'] == 0
    assert broadcaster.messages
    message = broadcaster.messages[-1][1]
    assert message['notification_delivery'] == 'suppressed'
    assert message['notification_delivery_reason'] == 'scanner_session_blocked:synthetic'


def test_scanner_signal_notifications_are_allowed_in_regular_session(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(db, 'DB_PATH', tmp_path / 'signal_flow_test.db')
    db.init_db()
    _force_buy_decision(monkeypatch)
    db.upsert_instrument_runtime_state(
        'AAPL',
        data_mode='scanner',
        data_source='yahoo',
        interval_type=db.DISCOVERABLE_SCANNER_INTERVAL,
        market_session='regular',
        is_delayed=False,
        as_of='2026-04-02T00:00:00+00:00',
        updated_at='2026-04-02T20:00:00+00:00',
    )
    broadcaster = CaptureBroadcaster()

    asyncio.run(
        signal_service.evaluate_symbol_and_broadcast(
            'AAPL',
            broadcaster,
            interval_type=db.DISCOVERABLE_SCANNER_INTERVAL,
        )
    )

    notifications = db.fetch_notifications('demo')
    assert notifications
    signals = db.fetch_all('SELECT * FROM signals WHERE symbol = ? ORDER BY created_at DESC', ('AAPL',))
    assert signals[0]['notification_delivery'] == 'notified'
    assert signals[0]['notification_delivery_reason'] is None
    assert signals[0]['notification_count'] >= 1
    message = broadcaster.messages[-1][1]
    assert message['notification_delivery'] == 'notified'
    assert message['notification_delivery_reason'] is None
    assert message['notification_count'] >= 1


def test_scanner_signal_notifications_are_suppressed_when_delayed(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(db, 'DB_PATH', tmp_path / 'signal_flow_test.db')
    db.init_db()
    _force_buy_decision(monkeypatch)
    db.upsert_instrument_runtime_state(
        'AAPL',
        data_mode='scanner',
        data_source='yahoo',
        interval_type=db.DISCOVERABLE_SCANNER_INTERVAL,
        market_session='regular',
        is_delayed=True,
        as_of='2026-04-02T00:00:00+00:00',
        updated_at='2026-04-02T20:00:00+00:00',
    )
    broadcaster = CaptureBroadcaster()

    asyncio.run(
        signal_service.evaluate_symbol_and_broadcast(
            'AAPL',
            broadcaster,
            interval_type=db.DISCOVERABLE_SCANNER_INTERVAL,
        )
    )

    notifications = db.fetch_notifications('demo')
    assert notifications == []
    signals = db.fetch_all('SELECT * FROM signals WHERE symbol = ? ORDER BY created_at DESC', ('AAPL',))
    assert signals[0]['notification_delivery'] == 'suppressed'
    assert signals[0]['notification_delivery_reason'] == 'scanner_delayed_blocked'
    assert signals[0]['notification_count'] == 0
    message = broadcaster.messages[-1][1]
    assert message['notification_delivery'] == 'suppressed'
    assert message['notification_delivery_reason'] == 'scanner_delayed_blocked'
