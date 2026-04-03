from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from app import db, scanner_providers

UTC = timezone.utc


class FakeYahooResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class FakeYahooClient:
    def __init__(self, *args, **kwargs) -> None:
        del args, kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, path: str, params: dict | None = None):
        del params
        symbol = path.rsplit('/', 1)[-1]
        if symbol != 'AAPL':
            raise AssertionError(f'unexpected symbol {symbol}')
        timestamps = [
            int(datetime(2026, 3, 31, tzinfo=UTC).timestamp()),
            int(datetime(2026, 4, 1, tzinfo=UTC).timestamp()),
            int(datetime(2026, 4, 2, tzinfo=UTC).timestamp()),
        ]
        return FakeYahooResponse(
            {
                'chart': {
                    'result': [
                        {
                            'meta': {
                                'marketState': 'REGULAR',
                                'dataGranularity': '1d',
                            },
                            'timestamp': timestamps,
                            'indicators': {
                                'quote': [
                                    {
                                        'open': [201.0, 204.0, 207.0],
                                        'high': [205.0, 208.0, 211.0],
                                        'low': [199.0, 202.0, 206.0],
                                        'close': [204.0, 207.0, 210.0],
                                        'volume': [51000000, 49000000, 53000000],
                                    }
                                ]
                            },
                        }
                    ]
                }
            }
        )


def test_build_scanner_provider_defaults_to_synthetic_for_unknown_name() -> None:
    provider = scanner_providers.build_scanner_provider('unknown')
    assert provider.name == 'synthetic'


def test_yahoo_provider_refresh_updates_assets_and_candles(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(db, 'DB_PATH', tmp_path / 'signal_flow_test.db')
    frozen_now = datetime(2026, 4, 2, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(db, 'utc_now', lambda: frozen_now)
    db.init_db()
    monkeypatch.setattr(scanner_providers.httpx, 'AsyncClient', FakeYahooClient)

    provider = scanner_providers.YahooScannerProvider(base_url='https://example.test', history_range='3mo', timeout_seconds=1)
    updates = asyncio.run(provider.refresh([{'symbol': 'AAPL'}]))

    assert len(updates) == 1
    assert updates[0]['symbol'] == 'AAPL'
    assert updates[0]['source'] == 'yahoo'
    assert updates[0]['price'] == 210.0

    asset = db.fetch_one('SELECT last_price, change_rate, updated_at FROM assets WHERE symbol = ?', ('AAPL',))
    assert asset is not None
    assert asset['last_price'] == 210.0
    assert round(asset['change_rate'], 4) == round(((210.0 - 207.0) / 207.0) * 100, 4)

    candles = db.fetch_recent_candles('AAPL', 5, interval_type=db.DISCOVERABLE_SCANNER_INTERVAL)
    assert len(candles) >= 3
    assert candles[-1]['close_price'] == 210.0
    runtime_state = db.get_instrument_runtime_state('AAPL')
    assert runtime_state is not None
    assert runtime_state['data_source'] == 'synthetic'
