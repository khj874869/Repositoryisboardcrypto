from __future__ import annotations

import asyncio
from typing import Any

from . import db
from .broadcaster import Broadcaster
from .config import SCANNER_PROVIDER, SCANNER_PROVIDER_FALLBACK_TO_SYNTHETIC, SCANNER_REFRESH_SECONDS
from .scanner_providers import SyntheticScannerProvider, build_scanner_provider
from .signal_service import evaluate_symbol_and_broadcast


class ScannerRuntime:
    def __init__(self, broadcaster: Broadcaster) -> None:
        self.broadcaster = broadcaster
        self.refresh_seconds = SCANNER_REFRESH_SECONDS
        self.requested_provider = SCANNER_PROVIDER
        self._provider = build_scanner_provider(self.requested_provider)
        self._running = False
        self._status = {
            'state': 'idle',
            'last_error': None,
            'last_scan_at': None,
            'refresh_seconds': self.refresh_seconds,
            'symbols': [row['symbol'] for row in db.list_scanner_instruments()],
            'interval': db.DISCOVERABLE_SCANNER_INTERVAL,
            'requested_provider': self.requested_provider,
            'active_provider': self._provider.name,
        }

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._status['state'] = 'scanning'
        while self._running:
            try:
                await self.refresh_once()
                self._status['last_error'] = None
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._status['state'] = 'error'
                self._status['last_error'] = str(exc)
            await asyncio.sleep(self.refresh_seconds)

    async def stop(self) -> None:
        self._running = False
        if self._status['state'] != 'idle':
            self._status['state'] = 'stopped'

    def status(self) -> dict[str, Any]:
        return dict(self._status)

    def _refresh_provider(self):
        if self._provider.name == 'synthetic' and self.requested_provider != 'synthetic':
            return build_scanner_provider(self.requested_provider)
        return self._provider

    async def refresh_once(self) -> list[dict[str, Any]]:
        instruments = db.list_scanner_instruments()
        self._status['symbols'] = [row['symbol'] for row in instruments]
        provider = self._refresh_provider()
        try:
            updates = await provider.refresh(instruments)
            self._provider = provider
            self._status['last_error'] = None
            self._status['active_provider'] = self._provider.name
        except Exception as exc:
            self._status['last_error'] = str(exc)
            if not SCANNER_PROVIDER_FALLBACK_TO_SYNTHETIC or provider.name == 'synthetic':
                raise
            self._provider = SyntheticScannerProvider()
            self._status['active_provider'] = self._provider.name
            updates = await self._provider.refresh(instruments)
        self._status['last_scan_at'] = db.isoformat(db.utc_now())
        if self._running:
            self._status['state'] = 'scanning'
        for row in updates:
            db.upsert_instrument_runtime_state(
                row['symbol'],
                data_mode=row.get('data_mode', 'scanner'),
                data_source=row.get('data_source', self._provider.name),
                interval_type=row.get('interval_type', db.DISCOVERABLE_SCANNER_INTERVAL),
                market_session=row.get('market_session', 'scanner'),
                is_delayed=bool(row.get('is_delayed', False)),
                as_of=row.get('candle_time') or row.get('updated_at'),
                updated_at=row.get('updated_at') or row.get('candle_time'),
            )
            await self.broadcaster.broadcast(
                'market_snapshot',
                {
                    'symbol': row['symbol'],
                    'price': row['price'],
                    'change_rate': row['change_rate'],
                    'candle_time': row['updated_at'],
                    'source': row['source'],
                },
            )
            await evaluate_symbol_and_broadcast(
                row['symbol'],
                self.broadcaster,
                interval_type=db.DISCOVERABLE_SCANNER_INTERVAL,
            )
        return updates
