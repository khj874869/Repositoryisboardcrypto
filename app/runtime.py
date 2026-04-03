from __future__ import annotations

import asyncio
import contextlib
from typing import Any

from .broadcaster import Broadcaster
from .config import DATA_SOURCE, SOURCE_FALLBACK_TO_SIMULATOR
from .market_simulator import MarketSimulator
from .scanner_runtime import ScannerRuntime
from .upbit_provider import UpbitMarketStream


class MarketRuntime:
    def __init__(self, broadcaster: Broadcaster) -> None:
        self.broadcaster = broadcaster
        self.requested_source = DATA_SOURCE
        self.active_source = DATA_SOURCE
        self._engine: Any | None = None
        self._scanner = ScannerRuntime(broadcaster)
        self._scanner_task: asyncio.Task | None = None
        self._last_error: str | None = None

    async def start(self) -> None:
        if self._scanner_task is None or self._scanner_task.done():
            self._scanner_task = asyncio.create_task(self._scanner.start())
        if self.requested_source == 'upbit':
            upbit = UpbitMarketStream(self.broadcaster)
            self._engine = upbit
            self.active_source = 'upbit'
            try:
                await upbit.start()
                return
            except Exception as exc:
                self._last_error = str(exc)
                if not SOURCE_FALLBACK_TO_SIMULATOR:
                    raise
        simulator = MarketSimulator(self.broadcaster)
        self._engine = simulator
        self.active_source = 'simulator'
        await simulator.start()

    async def stop(self) -> None:
        if self._engine is not None:
            await self._engine.stop()
        await self._scanner.stop()
        if self._scanner_task is not None:
            self._scanner_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._scanner_task
            self._scanner_task = None

    def status(self) -> dict[str, Any]:
        if self._engine is None:
            return {
                'requested_source': self.requested_source,
                'active_source': self.active_source,
                'state': 'idle',
                'last_error': self._last_error,
                'scanner': self._scanner.status(),
            }
        status = self._engine.status()
        status['requested_source'] = self.requested_source
        status['active_source'] = self.active_source
        status['scanner'] = self._scanner.status()
        if self._last_error and not status.get('last_error'):
            status['last_error'] = self._last_error
        return status
    
