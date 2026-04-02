from __future__ import annotations

import asyncio
import random
from datetime import timedelta
from typing import Any

from . import db
from .broadcaster import Broadcaster
from .config import BOOTSTRAP_CANDLES, CANDLE_INTERVAL_SECONDS, MARKETS, TICK_SECONDS
from .signal_service import evaluate_symbol_and_broadcast


class MarketSimulator:
    def __init__(self, broadcaster: Broadcaster) -> None:
        self.broadcaster = broadcaster
        self._running = False
        self._status = {
            'requested_source': 'simulator',
            'active_source': 'simulator',
            'state': 'idle',
            'last_error': None,
            'last_message_at': None,
            'markets': list(MARKETS.keys()),
            'interval': f'demo-{CANDLE_INTERVAL_SECONDS}s',
        }
        self._state = {
            symbol: {
                'last_price': float(meta['base_price']),
                'base_price': float(meta['base_price']),
                'volatility': float(meta['volatility']),
            }
            for symbol, meta in MARKETS.items()
        }

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._status['state'] = 'bootstrapping'
        self._bootstrap_history()
        self._status['state'] = 'streaming'
        while self._running:
            await self._tick_once()
            await asyncio.sleep(TICK_SECONDS)

    async def stop(self) -> None:
        self._running = False
        if self._status['state'] != 'idle':
            self._status['state'] = 'stopped'

    def status(self) -> dict[str, Any]:
        return dict(self._status)

    def _bootstrap_history(self) -> None:
        now = db.utc_now() - timedelta(seconds=BOOTSTRAP_CANDLES * CANDLE_INTERVAL_SECONDS)
        for _ in range(BOOTSTRAP_CANDLES):
            for symbol in MARKETS:
                self._generate_candle(symbol, now)
            now += timedelta(seconds=CANDLE_INTERVAL_SECONDS)

    async def _tick_once(self) -> None:
        candle_time = db.utc_now()
        for symbol in MARKETS:
            candle = self._generate_candle(symbol, candle_time)
            await self.broadcaster.broadcast(
                'market_snapshot',
                {
                    'symbol': symbol,
                    'price': candle['close_price'],
                    'change_rate': self._calculate_change_rate(symbol),
                    'candle_time': candle['candle_time'],
                    'source': 'simulator',
                },
            )
            await evaluate_symbol_and_broadcast(symbol, self.broadcaster, interval_type=f'demo-{CANDLE_INTERVAL_SECONDS}s')
        self._status['last_message_at'] = db.isoformat(db.utc_now())

    def _generate_candle(self, symbol: str, candle_time) -> dict[str, Any]:
        state = self._state[symbol]
        open_price = state['last_price']
        drift = random.uniform(-state['volatility'], state['volatility'])
        close_price = max(1.0, open_price * (1 + drift))
        wick = abs(random.uniform(0, state['volatility'] * 0.6))
        high_price = max(open_price, close_price) * (1 + wick)
        low_price = min(open_price, close_price) * (1 - wick)
        volume = random.uniform(10, 1000)

        state['last_price'] = close_price
        change_rate = self._calculate_change_rate(symbol)
        db.update_asset_price(
            symbol,
            last_price=round(close_price, 4),
            change_rate=round(change_rate, 4),
            updated_at=db.isoformat(db.utc_now()),
        )
        db.upsert_instrument_runtime_state(
            symbol,
            data_mode='realtime',
            data_source='simulator',
            interval_type=f'demo-{CANDLE_INTERVAL_SECONDS}s',
            market_session='continuous',
            is_delayed=False,
            as_of=db.isoformat(candle_time),
            updated_at=db.isoformat(db.utc_now()),
        )
        db.upsert_candle(
            symbol=symbol,
            candle_time=db.isoformat(candle_time),
            interval_type=f'demo-{CANDLE_INTERVAL_SECONDS}s',
            open_price=round(open_price, 4),
            high_price=round(high_price, 4),
            low_price=round(low_price, 4),
            close_price=round(close_price, 4),
            volume=round(volume, 4),
        )
        return {
            'symbol': symbol,
            'candle_time': db.isoformat(candle_time),
            'open_price': round(open_price, 4),
            'high_price': round(high_price, 4),
            'low_price': round(low_price, 4),
            'close_price': round(close_price, 4),
            'volume': round(volume, 4),
        }

    def _calculate_change_rate(self, symbol: str) -> float:
        state = self._state[symbol]
        return ((state['last_price'] - state['base_price']) / state['base_price']) * 100
