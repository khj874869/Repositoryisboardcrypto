from __future__ import annotations

import asyncio
import json
from contextlib import suppress
from datetime import datetime, timezone
from typing import Any

import websockets

from . import db
from .broadcaster import Broadcaster
from .config import (
    SIGNAL_DEDUP_SECONDS,
    UPBIT_BOOTSTRAP_CANDLES,
    UPBIT_CANDLE_UNIT,
    UPBIT_MARKETS,
    UPBIT_WS_URL,
)
from .strategy_engine import build_snapshot, evaluate_strategies
from .upbit_client import fetch_minute_candles


class UpbitStreamer:
    def __init__(self, broadcaster: Broadcaster) -> None:
        self.broadcaster = broadcaster
        self._running = False
        self._task: asyncio.Task | None = None
        self._candle_type = f'candle.{UPBIT_CANDLE_UNIT}'
        self._interval_type = f'upbit-{UPBIT_CANDLE_UNIT}'

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        await asyncio.to_thread(self._bootstrap_history)
        self._task = asyncio.create_task(self._stream_loop())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task

    def _bootstrap_history(self) -> None:
        unit = _parse_minute_unit(UPBIT_CANDLE_UNIT)
        for market in UPBIT_MARKETS:
            candles = fetch_minute_candles(market, unit, count=UPBIT_BOOTSTRAP_CANDLES)
            for candle in candles:
                self._store_candle(market, candle)

    async def _stream_loop(self) -> None:
        while self._running:
            try:
                async with websockets.connect(
                    UPBIT_WS_URL,
                    ping_interval=60,
                    ping_timeout=20,
                ) as websocket:
                    await websocket.send(
                        json.dumps(
                            [
                                {'ticket': 'signal-flow'},
                                {'type': 'ticker', 'codes': list(UPBIT_MARKETS)},
                                {'type': self._candle_type, 'codes': list(UPBIT_MARKETS)},
                                {'format': 'DEFAULT'},
                            ]
                        )
                    )
                    while self._running:
                        raw = await websocket.recv()
                        message = _decode_message(raw)
                        if not message:
                            continue
                        message_type = message.get('type')
                        if message_type == 'ticker':
                            await self._handle_ticker(message)
                        elif message_type == self._candle_type:
                            await self._handle_candle(message)
            except Exception:
                await asyncio.sleep(2)

    async def _handle_ticker(self, message: dict[str, Any]) -> None:
        symbol = message.get('code')
        if not symbol:
            return
        price = float(message.get('trade_price') or 0)
        change_rate = float(message.get('signed_change_rate') or 0) * 100
        db.execute(
            '''
            UPDATE assets
            SET last_price = ?, change_rate = ?, updated_at = ?
            WHERE symbol = ?
            ''',
            (round(price, 4), round(change_rate, 4), db.isoformat(db.utc_now()), symbol),
        )
        await self.broadcaster.broadcast(
            'market_snapshot',
            {
                'symbol': symbol,
                'price': price,
                'change_rate': change_rate,
                'candle_time': db.isoformat(db.utc_now()),
            },
        )

    async def _handle_candle(self, message: dict[str, Any]) -> None:
        symbol = message.get('code')
        if not symbol:
            return
        self._store_candle(symbol, message)
        await self._evaluate_symbol(symbol)

    def _store_candle(self, symbol: str, message: dict[str, Any]) -> None:
        candle_time = _parse_candle_time(message)
        db.execute(
            '''
            INSERT OR REPLACE INTO candles(
                symbol, candle_time, interval_type, open_price, high_price, low_price, close_price, volume
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                symbol,
                candle_time,
                self._interval_type,
                round(float(message.get('opening_price') or 0), 4),
                round(float(message.get('high_price') or 0), 4),
                round(float(message.get('low_price') or 0), 4),
                round(float(message.get('trade_price') or 0), 4),
                round(float(message.get('candle_acc_trade_volume') or 0), 4),
            ),
        )

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


def _decode_message(raw: str | bytes) -> dict[str, Any] | None:
    if isinstance(raw, bytes):
        try:
            raw = raw.decode('utf-8')
        except UnicodeDecodeError:
            return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _parse_candle_time(message: dict[str, Any]) -> str:
    timestamp = message.get('candle_date_time_utc')
    if not timestamp:
        return db.isoformat(db.utc_now())
    try:
        dt = datetime.fromisoformat(timestamp).replace(tzinfo=timezone.utc)
        return dt.isoformat()
    except ValueError:
        return db.isoformat(db.utc_now())


def _parse_minute_unit(unit: str) -> int:
    if unit.endswith('m'):
        return int(unit[:-1])
    return int(unit)
