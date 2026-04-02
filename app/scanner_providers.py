from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from . import db
from .config import (
    SCANNER_PROVIDER,
    SCANNER_YAHOO_BASE_URL,
    SCANNER_YAHOO_RANGE,
    SCANNER_YAHOO_TIMEOUT_SECONDS,
)

UTC = timezone.utc


class SyntheticScannerProvider:
    name = 'synthetic'

    async def refresh(self, instruments: list[dict[str, Any]]) -> list[dict[str, Any]]:
        del instruments
        return db.refresh_scanner_market_data()


def _yahoo_candle_rows(symbol: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
    chart = payload.get('chart') or {}
    result_rows = chart.get('result') or []
    if not result_rows:
        raise ValueError(f'Yahoo chart payload missing result for {symbol}')

    result = result_rows[0]
    timestamps = result.get('timestamp') or []
    quote_sets = ((result.get('indicators') or {}).get('quote') or [{}])
    quote = quote_sets[0] if quote_sets else {}
    opens = quote.get('open') or []
    highs = quote.get('high') or []
    lows = quote.get('low') or []
    closes = quote.get('close') or []
    volumes = quote.get('volume') or []

    rows: list[dict[str, Any]] = []
    for timestamp, open_price, high_price, low_price, close_price, volume in zip(
        timestamps,
        opens,
        highs,
        lows,
        closes,
        volumes,
    ):
        if None in (timestamp, open_price, high_price, low_price, close_price):
            continue
        candle_time = datetime.fromtimestamp(int(timestamp), tz=UTC)
        rows.append(
            {
                'symbol': symbol,
                'candle_time': db.isoformat(candle_time),
                'interval_type': db.DISCOVERABLE_SCANNER_INTERVAL,
                'open_price': round(float(open_price), 4),
                'high_price': round(float(high_price), 4),
                'low_price': round(float(low_price), 4),
                'close_price': round(float(close_price), 4),
                'volume': round(float(volume or 0.0), 4),
            }
        )
    if not rows:
        raise ValueError(f'Yahoo chart payload has no valid candle rows for {symbol}')
    return rows


def _yahoo_runtime_meta(payload: dict[str, Any]) -> dict[str, Any]:
    chart = payload.get('chart') or {}
    result_rows = chart.get('result') or []
    meta = result_rows[0].get('meta') if result_rows else None
    if not meta:
        return {
            'market_session': 'closed',
            'is_delayed': True,
        }
    market_state = str(meta.get('marketState') or 'CLOSED').strip().lower()
    session_map = {
        'regular': 'regular',
        'pre': 'pre',
        'prepre': 'pre',
        'post': 'post',
        'postpost': 'post',
        'closed': 'closed',
    }
    return {
        'market_session': session_map.get(market_state, market_state or 'closed'),
        'is_delayed': bool(meta.get('dataGranularity') == '1d'),
    }


class YahooScannerProvider:
    name = 'yahoo'

    def __init__(
        self,
        *,
        base_url: str = SCANNER_YAHOO_BASE_URL,
        history_range: str = SCANNER_YAHOO_RANGE,
        timeout_seconds: float = SCANNER_YAHOO_TIMEOUT_SECONDS,
    ) -> None:
        self.base_url = base_url
        self.history_range = history_range
        self.timeout_seconds = timeout_seconds

    async def refresh(self, instruments: list[dict[str, Any]]) -> list[dict[str, Any]]:
        updates: list[dict[str, Any]] = []
        failures: list[str] = []
        async with httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout_seconds) as client:
            for instrument in instruments:
                symbol = instrument['symbol']
                try:
                    response = await client.get(
                        f'/v8/finance/chart/{symbol}',
                        params={
                            'interval': '1d',
                            'range': self.history_range,
                            'includePrePost': 'false',
                            'events': 'div,splits',
                        },
                    )
                    response.raise_for_status()
                    payload = response.json()
                    rows = _yahoo_candle_rows(symbol, payload)
                    runtime_meta = _yahoo_runtime_meta(payload)
                    for row in rows:
                        db.upsert_candle(**row)
                    latest = rows[-1]
                    previous_close = rows[-2]['close_price'] if len(rows) >= 2 else latest['close_price']
                    change_rate = 0.0 if not previous_close else ((latest['close_price'] - previous_close) / previous_close) * 100
                    db.update_asset_price(
                        symbol,
                        last_price=latest['close_price'],
                        change_rate=round(change_rate, 4),
                        updated_at=latest['candle_time'],
                    )
                    updates.append(
                        {
                            'symbol': symbol,
                            'price': latest['close_price'],
                            'change_rate': round(change_rate, 4),
                            'candle_time': latest['candle_time'],
                            'updated_at': latest['candle_time'],
                            'interval_type': db.DISCOVERABLE_SCANNER_INTERVAL,
                            'source': self.name,
                            'data_mode': 'scanner',
                            'data_source': self.name,
                            'market_session': runtime_meta['market_session'],
                            'is_delayed': runtime_meta['is_delayed'],
                        }
                    )
                except Exception as exc:
                    failures.append(f'{symbol}: {exc}')
        if not updates and failures:
            raise RuntimeError('; '.join(failures))
        return updates


def build_scanner_provider(name: str | None = None):
    normalized = (name or SCANNER_PROVIDER).strip().lower()
    if normalized == 'yahoo':
        return YahooScannerProvider()
    return SyntheticScannerProvider()
