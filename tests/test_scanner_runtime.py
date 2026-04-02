from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from app import db, scanner_runtime

UTC = timezone.utc


class CaptureBroadcaster:
    def __init__(self) -> None:
        self.messages: list[tuple[str, dict]] = []

    async def broadcast(self, message_type: str, payload: dict) -> None:
        self.messages.append((message_type, payload))


def test_refresh_scanner_market_data_updates_watch_only_assets(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(db, 'DB_PATH', tmp_path / 'signal_flow_test.db')
    db.init_db()

    before = db.fetch_one('SELECT last_price, updated_at FROM assets WHERE symbol = ?', ('AAPL',))
    assert before is not None

    now = datetime(2026, 4, 2, 3, 45, tzinfo=UTC)
    updates = db.refresh_scanner_market_data(now=now)

    assert any(row['symbol'] == 'AAPL' for row in updates)
    after = db.fetch_one('SELECT last_price, updated_at FROM assets WHERE symbol = ?', ('AAPL',))
    assert after is not None
    assert after['updated_at'] == db.isoformat(now.replace(second=0, microsecond=0))
    assert after['last_price'] != before['last_price']

    candles = db.fetch_recent_candles('AAPL', 5, interval_type=db.DISCOVERABLE_SCANNER_INTERVAL)
    assert candles
    assert candles[-1]['interval_type'] == db.DISCOVERABLE_SCANNER_INTERVAL
    assert candles[-1]['candle_time'] == db.isoformat(now.replace(hour=0, minute=0, second=0, microsecond=0))
    runtime_state = db.get_instrument_runtime_state('AAPL')
    assert runtime_state is not None
    assert runtime_state['data_mode'] == 'scanner'
    assert runtime_state['data_source'] == 'synthetic'
    assert runtime_state['market_session'] == 'synthetic'
    assert runtime_state['is_delayed'] is False


def test_scanner_runtime_refresh_once_broadcasts_snapshots_and_evaluates_symbols(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(db, 'DB_PATH', tmp_path / 'signal_flow_test.db')
    db.init_db()

    calls: list[tuple[str, str]] = []

    async def fake_evaluate(symbol: str, broadcaster, *, interval_type: str) -> None:
        calls.append((symbol, interval_type))

    monkeypatch.setattr(scanner_runtime, 'evaluate_symbol_and_broadcast', fake_evaluate)
    broadcaster = CaptureBroadcaster()
    runtime = scanner_runtime.ScannerRuntime(broadcaster)

    updates = asyncio.run(runtime.refresh_once())

    assert updates
    assert any(message_type == 'market_snapshot' and payload['source'] == 'scanner' for message_type, payload in broadcaster.messages)
    assert calls
    assert all(interval_type == db.DISCOVERABLE_SCANNER_INTERVAL for _, interval_type in calls)
    status = runtime.status()
    assert status['interval'] == db.DISCOVERABLE_SCANNER_INTERVAL
    assert status['last_scan_at'] is not None
    assert 'AAPL' in status['symbols']


def test_scanner_runtime_falls_back_to_synthetic_provider(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(db, 'DB_PATH', tmp_path / 'signal_flow_test.db')
    db.init_db()

    class BrokenProvider:
        name = 'yahoo'

        async def refresh(self, instruments):
            del instruments
            raise RuntimeError('provider unavailable')

    broadcaster = CaptureBroadcaster()
    runtime = scanner_runtime.ScannerRuntime(broadcaster)
    runtime._provider = BrokenProvider()

    updates = asyncio.run(runtime.refresh_once())

    assert updates
    status = runtime.status()
    assert status['active_provider'] == 'synthetic'
    assert status['requested_provider']
    assert status['last_error'] == 'provider unavailable'


def test_scanner_runtime_updates_runtime_state_from_provider_payload(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(db, 'DB_PATH', tmp_path / 'signal_flow_test.db')
    db.init_db()

    class YahooLikeProvider:
        name = 'yahoo'

        async def refresh(self, instruments):
            assert any(row['symbol'] == 'AAPL' for row in instruments)
            return [
                {
                    'symbol': 'AAPL',
                    'price': 211.5,
                    'change_rate': 1.2,
                    'candle_time': '2026-04-02T00:00:00+00:00',
                    'updated_at': '2026-04-02T20:00:00+00:00',
                    'interval_type': db.DISCOVERABLE_SCANNER_INTERVAL,
                    'source': 'yahoo',
                    'data_mode': 'scanner',
                    'data_source': 'yahoo',
                    'market_session': 'regular',
                    'is_delayed': True,
                }
            ]

    async def fake_evaluate(symbol: str, broadcaster, *, interval_type: str) -> None:
        del symbol, broadcaster, interval_type

    monkeypatch.setattr(scanner_runtime, 'evaluate_symbol_and_broadcast', fake_evaluate)
    runtime = scanner_runtime.ScannerRuntime(CaptureBroadcaster())
    runtime._provider = YahooLikeProvider()

    asyncio.run(runtime.refresh_once())

    runtime_state = db.get_instrument_runtime_state('AAPL')
    assert runtime_state is not None
    assert runtime_state['data_source'] == 'yahoo'
    assert runtime_state['market_session'] == 'regular'
    assert runtime_state['is_delayed'] is True
