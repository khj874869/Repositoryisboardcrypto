from __future__ import annotations

import asyncio
import random
from datetime import timedelta
from typing import Any

from . import db
from .broadcaster import Broadcaster
from .config import BOOTSTRAP_CANDLES, CANDLE_INTERVAL_SECONDS, MARKETS, SIGNAL_DEDUP_SECONDS, TICK_SECONDS
from .strategy_engine import build_snapshot, evaluate_strategies


class MarketSimulator:
    def __init__(self, broadcaster: Broadcaster) -> None:
        self.broadcaster = broadcaster
        self._running = False
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
        self._bootstrap_history()
        while self._running:
            await self._tick_once()
            await asyncio.sleep(TICK_SECONDS)

    async def stop(self) -> None:
        self._running = False

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
                },
            )
            await self._evaluate_symbol(symbol)

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
        db.execute(
            '''
            UPDATE assets
            SET last_price = ?, change_rate = ?, updated_at = ?
            WHERE symbol = ?
            ''',
            (round(close_price, 4), round(change_rate, 4), db.isoformat(db.utc_now()), symbol),
        )
        db.execute(
            '''
            INSERT OR REPLACE INTO candles(
                symbol, candle_time, interval_type, open_price, high_price, low_price, close_price, volume
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                symbol,
                db.isoformat(candle_time),
                f'demo-{CANDLE_INTERVAL_SECONDS}s',
                round(open_price, 4),
                round(high_price, 4),
                round(low_price, 4),
                round(close_price, 4),
                round(volume, 4),
            ),
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

    async def _evaluate_symbol(self, symbol: str) -> None:
        candles = db.fetch_all(
            '''
            SELECT *
            FROM candles
            WHERE symbol = ?
            ORDER BY candle_time ASC
            LIMIT 120
            ''',
            (symbol,),
        )
        strategies = db.fetch_all('SELECT * FROM strategies WHERE is_active = 1 ORDER BY id ASC')
        if len(candles) < 20 or not strategies:
            return

        snapshot = build_snapshot(symbol, candles)
        decisions = evaluate_strategies(snapshot, strategies)
        for decision in decisions:
            inserted = db.insert_signal_if_new(
                symbol=symbol,
                signal_type=decision.signal_type,
                strategy_name=decision.strategy_name,
                score=decision.score,
                reason=decision.reason,
                price=snapshot.close_price,
                dedup_seconds=SIGNAL_DEDUP_SECONDS,
            )
            if inserted:
                await self.broadcaster.broadcast(
                    'signal',
                    {
                        'symbol': symbol,
                        'signal_type': decision.signal_type,
                        'strategy_name': decision.strategy_name,
                        'score': decision.score,
                        'reason': decision.reason,
                        'price': snapshot.close_price,
                    },
                )
