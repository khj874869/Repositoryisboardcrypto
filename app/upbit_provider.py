from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
import websockets

from . import db
from .broadcaster import Broadcaster
from .config import (
    MARKET_SNAPSHOT_PUSH_SECONDS,
    MARKETS,
    UPBIT_API_BASE_URL,
    UPBIT_BOOTSTRAP_COUNT,
    UPBIT_HTTP_TIMEOUT_SECONDS,
    UPBIT_INTERVAL,
    UPBIT_MARKETS,
    UPBIT_RECONNECT_SECONDS,
    UPBIT_WS_PING_INTERVAL_SECONDS,
    UPBIT_WS_PING_TIMEOUT_SECONDS,
    UPBIT_WS_URL,
)
from .signal_service import evaluate_symbol_and_broadcast

logger = logging.getLogger(__name__)
UTC = timezone.utc


def parse_upbit_datetime(value: str) -> datetime:
    if value.endswith('Z'):
        return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(UTC)
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def normalize_rest_candle(payload: dict[str, Any], *, interval_type: str) -> dict[str, Any]:
    candle_time = payload.get('candle_date_time_utc') or payload.get('candle_date_time')
    if not candle_time:
        raise ValueError('Missing candle_date_time_utc in REST payload')
    symbol = payload.get('market') or payload.get('code')
    if not symbol:
        raise ValueError('Missing market/code in REST payload')
    return {
        'symbol': symbol,
        'candle_time': db.isoformat(parse_upbit_datetime(str(candle_time))),
        'interval_type': interval_type,
        'open_price': float(payload['opening_price']),
        'high_price': float(payload['high_price']),
        'low_price': float(payload['low_price']),
        'close_price': float(payload.get('trade_price') or payload.get('closing_price')),
        'volume': float(payload.get('candle_acc_trade_volume', 0.0)),
    }


def normalize_ws_candle(payload: dict[str, Any], *, interval_type: str) -> dict[str, Any]:
    candle_time = payload.get('candle_date_time_utc') or payload.get('cdttmu')
    if not candle_time:
        raise ValueError('Missing candle_date_time_utc in WebSocket payload')
    symbol = payload.get('code') or payload.get('cd')
    if not symbol:
        raise ValueError('Missing code in WebSocket payload')
    return {
        'symbol': symbol,
        'candle_time': db.isoformat(parse_upbit_datetime(str(candle_time))),
        'interval_type': interval_type,
        'open_price': float(payload.get('opening_price', payload.get('op'))),
        'high_price': float(payload.get('high_price', payload.get('hp'))),
        'low_price': float(payload.get('low_price', payload.get('lp'))),
        'close_price': float(payload.get('trade_price', payload.get('tp'))),
        'volume': float(payload.get('candle_acc_trade_volume', payload.get('catv', 0.0))),
    }


def normalize_ticker(payload: dict[str, Any]) -> dict[str, Any]:
    symbol = payload.get('code') or payload.get('cd')
    if not symbol:
        raise ValueError('Missing code in ticker payload')
    price = float(payload.get('trade_price', payload.get('tp')))
    signed_change_rate = payload.get('signed_change_rate', payload.get('scr'))
    change_rate_percent = float(signed_change_rate) * 100 if signed_change_rate is not None else 0.0
    timestamp_ms = payload.get('trade_timestamp', payload.get('ttms'))
    if timestamp_ms is None:
        updated_at = db.isoformat(db.utc_now())
    else:
        updated_at = db.isoformat(datetime.fromtimestamp(int(timestamp_ms) / 1000, tz=UTC))
    return {
        'symbol': symbol,
        'price': price,
        'change_rate': change_rate_percent,
        'updated_at': updated_at,
    }


def build_rest_candle_request(symbol: str, *, interval: str, count: int) -> tuple[str, dict[str, Any]]:
    if interval == '1s':
        return '/v1/candles/seconds', {'market': symbol, 'count': count}
    if not interval.endswith('m'):
        raise ValueError(f'Unsupported Upbit interval: {interval}')
    unit = int(interval[:-1])
    return f'/v1/candles/minutes/{unit}', {'market': symbol, 'count': count}


class UpbitMarketStream:
    def __init__(self, broadcaster: Broadcaster) -> None:
        self.broadcaster = broadcaster
        self.interval = UPBIT_INTERVAL
        self.interval_type = f'upbit-{self.interval}'
        self._running = False
        self._ws: Any | None = None
        self._last_market_push = 0.0
        self._market_catalog: dict[str, dict[str, Any]] = {}
        self._status = {
            'requested_source': 'upbit',
            'active_source': 'upbit',
            'state': 'idle',
            'last_error': None,
            'last_message_at': None,
            'markets': list(UPBIT_MARKETS),
            'interval': self.interval,
        }

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._status['state'] = 'bootstrapping'
        await self._bootstrap()
        self._status['state'] = 'connecting'
        while self._running:
            try:
                await self._stream_loop()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # pragma: no cover - network dependent
                logger.warning('Upbit stream reconnecting after error: %s', exc)
                self._status['state'] = 'reconnecting'
                self._status['last_error'] = str(exc)
                if not self._running:
                    break
                await asyncio.sleep(UPBIT_RECONNECT_SECONDS)

    async def stop(self) -> None:
        self._running = False
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                pass
        if self._status['state'] != 'idle':
            self._status['state'] = 'stopped'

    def status(self) -> dict[str, Any]:
        return dict(self._status)

    async def _bootstrap(self) -> None:
        self._market_catalog = await self._fetch_market_catalog()
        async with httpx.AsyncClient(base_url=UPBIT_API_BASE_URL, timeout=UPBIT_HTTP_TIMEOUT_SECONDS) as client:
            for symbol in UPBIT_MARKETS:
                meta = MARKETS.get(symbol, {})
                market_info = self._market_catalog.get(symbol, {})
                name = market_info.get('korean_name') or market_info.get('english_name') or meta.get('name') or symbol
                db.upsert_asset(
                    symbol=symbol,
                    name=name,
                    market_type=meta.get('market_type', 'COIN'),
                    last_price=float(meta.get('base_price', 0.0)),
                    change_rate=0.0,
                )
                candles = await self._fetch_recent_candles(client, symbol)
                for candle in candles:
                    db.upsert_candle(**candle)
                if candles:
                    db.update_asset_price(
                        symbol,
                        last_price=candles[-1]['close_price'],
                        updated_at=candles[-1]['candle_time'],
                    )
                    db.upsert_instrument_runtime_state(
                        symbol,
                        data_mode='realtime',
                        data_source='upbit',
                        interval_type=self.interval_type,
                        market_session='continuous',
                        is_delayed=False,
                        as_of=candles[-1]['candle_time'],
                        updated_at=candles[-1]['candle_time'],
                    )
                    await evaluate_symbol_and_broadcast(symbol, self.broadcaster, interval_type=self.interval_type)
        self._status['last_message_at'] = db.isoformat(db.utc_now())

    async def _fetch_market_catalog(self) -> dict[str, dict[str, Any]]:
        async with httpx.AsyncClient(base_url=UPBIT_API_BASE_URL, timeout=UPBIT_HTTP_TIMEOUT_SECONDS) as client:
            response = await client.get('/v1/market/all', params={'isDetails': 'false'})
            response.raise_for_status()
            rows = response.json()
        catalog: dict[str, dict[str, Any]] = {}
        for row in rows:
            market = row.get('market')
            if market:
                catalog[market] = row
        return catalog

    async def _fetch_recent_candles(self, client: httpx.AsyncClient, symbol: str) -> list[dict[str, Any]]:
        path, params = build_rest_candle_request(symbol, interval=self.interval, count=UPBIT_BOOTSTRAP_COUNT)
        response = await client.get(path, params=params)
        response.raise_for_status()
        payload = response.json()
        normalized = [normalize_rest_candle(row, interval_type=self.interval_type) for row in reversed(payload)]
        return normalized
    
    async def _stream_loop(self) -> None:
        subscription_message = json.dumps(
            [
                {'ticket': f'signal-flow-{uuid.uuid4()}'},
                {'type': f'candle.{self.interval}', 'codes': UPBIT_MARKETS},
                {'type': 'ticker', 'codes': UPBIT_MARKETS},
                {'format': 'DEFAULT'},
            ],
            ensure_ascii=False,
        )
        async with websockets.connect(
            UPBIT_WS_URL,
            ping_interval=UPBIT_WS_PING_INTERVAL_SECONDS,
            ping_timeout=UPBIT_WS_PING_TIMEOUT_SECONDS,
            max_size=None,
            open_timeout=UPBIT_HTTP_TIMEOUT_SECONDS,
        ) as websocket:
            self._ws = websocket
            await websocket.send(subscription_message)
            self._status['state'] = 'streaming'
            self._status['last_error'] = None
            async for raw_message in websocket:
                await self._handle_message(raw_message)
        self._ws = None

    async def _handle_message(self, raw_message: Any) -> None:
        if isinstance(raw_message, bytes):
            raw_message = raw_message.decode('utf-8')
        payload = json.loads(raw_message)
        if isinstance(payload, list):
            for item in payload:
                await self._handle_payload(item)
            return
        await self._handle_payload(payload)

    async def _handle_payload(self, payload: dict[str, Any]) -> None:
        message_type = payload.get('type') or payload.get('ty')
        self._status['last_message_at'] = db.isoformat(db.utc_now())
        if message_type == 'ticker':
            await self._handle_ticker(payload)
            return
        if isinstance(message_type, str) and message_type.startswith('candle.'):
            await self._handle_candle(payload)

    async def _handle_ticker(self, payload: dict[str, Any]) -> None:
        ticker = normalize_ticker(payload)
        db.update_asset_price(
            ticker['symbol'],
            last_price=ticker['price'],
            change_rate=ticker['change_rate'],
            updated_at=ticker['updated_at'],
        )
        db.upsert_instrument_runtime_state(
            ticker['symbol'],
            data_mode='realtime',
            data_source='upbit',
            interval_type=self.interval_type,
            market_session='continuous',
            is_delayed=False,
            as_of=ticker['updated_at'],
            updated_at=ticker['updated_at'],
        )
        await self._push_market_snapshot(
            symbol=ticker['symbol'],
            price=ticker['price'],
            change_rate=ticker['change_rate'],
            candle_time=ticker['updated_at'],
        )

    async def _handle_candle(self, payload: dict[str, Any]) -> None:
        candle = normalize_ws_candle(payload, interval_type=self.interval_type)
        db.upsert_candle(**candle)
        db.update_asset_price(
            candle['symbol'],
            last_price=candle['close_price'],
            updated_at=candle['candle_time'],
        )
        db.upsert_instrument_runtime_state(
            candle['symbol'],
            data_mode='realtime',
            data_source='upbit',
            interval_type=self.interval_type,
            market_session='continuous',
            is_delayed=False,
            as_of=candle['candle_time'],
            updated_at=candle['candle_time'],
        )
        await evaluate_symbol_and_broadcast(candle['symbol'], self.broadcaster, interval_type=self.interval_type)
        await self._push_market_snapshot(
            symbol=candle['symbol'],
            price=candle['close_price'],
            change_rate=None,
            candle_time=candle['candle_time'],
        )
    
    async def _push_market_snapshot(
        self,
        *,
        symbol: str,
        price: float,
        change_rate: float | None,
        candle_time: str,
    ) -> None:
        now_monotonic = asyncio.get_running_loop().time()
        if now_monotonic - self._last_market_push < MARKET_SNAPSHOT_PUSH_SECONDS:
            return
        self._last_market_push = now_monotonic
        if change_rate is None:
            row = db.fetch_one('SELECT change_rate FROM assets WHERE symbol = ?', (symbol,))
            change_rate = float(row['change_rate']) if row else 0.0
        await self.broadcaster.broadcast(
            'market_snapshot',
            {
                'symbol': symbol,
                'price': price,
                'change_rate': change_rate,
                'candle_time': candle_time,
                'source': 'upbit',
            },
        )
