from __future__ import annotations

from app.upbit_provider import (
    build_rest_candle_request,
    normalize_rest_candle,
    normalize_ticker,
    normalize_ws_candle,
)


def test_build_rest_candle_request_for_seconds() -> None:
    path, params = build_rest_candle_request('KRW-BTC', interval='1s', count=60)
    assert path == '/v1/candles/seconds'
    assert params == {'market': 'KRW-BTC', 'count': 60}



def test_build_rest_candle_request_for_minutes() -> None:
    path, params = build_rest_candle_request('KRW-ETH', interval='5m', count=120)
    assert path == '/v1/candles/minutes/5'
    assert params == {'market': 'KRW-ETH', 'count': 120}



def test_normalize_rest_candle() -> None:
    payload = {
        'market': 'KRW-BTC',
        'candle_date_time_utc': '2026-03-27T01:02:03',
        'opening_price': 150000000,
        'high_price': 151000000,
        'low_price': 149500000,
        'trade_price': 150500000,
        'candle_acc_trade_volume': 1.25,
    }
    normalized = normalize_rest_candle(payload, interval_type='upbit-1s')
    assert normalized['symbol'] == 'KRW-BTC'
    assert normalized['interval_type'] == 'upbit-1s'
    assert normalized['close_price'] == 150500000.0
    assert normalized['volume'] == 1.25
    assert normalized['candle_time'].startswith('2026-03-27T01:02:03')



def test_normalize_ws_candle_supports_short_keys() -> None:
    payload = {
        'cd': 'KRW-ETH',
        'cdttmu': '2026-03-27T01:02:04',
        'op': 5100000,
        'hp': 5110000,
        'lp': 5090000,
        'tp': 5105000,
        'catv': 12.34,
    }
    normalized = normalize_ws_candle(payload, interval_type='upbit-1s')
    assert normalized['symbol'] == 'KRW-ETH'
    assert normalized['close_price'] == 5105000.0
    assert normalized['volume'] == 12.34



def test_normalize_ticker_converts_change_rate_to_percent() -> None:
    payload = {
        'code': 'KRW-XRP',
        'trade_price': 1000,
        'signed_change_rate': 0.0123,
        'trade_timestamp': 1_711_500_000_000,
    }
    normalized = normalize_ticker(payload)
    assert normalized['symbol'] == 'KRW-XRP'
    assert normalized['price'] == 1000.0
    assert round(normalized['change_rate'], 2) == 1.23
    assert normalized['updated_at'].endswith('+00:00')
