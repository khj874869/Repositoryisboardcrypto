from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Iterable

BASE_URL = 'https://api.upbit.com/v1'


def _get(path: str, params: dict[str, str] | None = None) -> list[dict]:
    url = f'{BASE_URL}{path}'
    if params:
        url = f'{url}?{urllib.parse.urlencode(params)}'
    request = urllib.request.Request(url, headers={'Accept': 'application/json'})
    with urllib.request.urlopen(request, timeout=10) as response:
        payload = response.read().decode('utf-8')
    return json.loads(payload)


def fetch_markets(codes: Iterable[str] | None = None) -> dict[str, str]:
    data = _get('/market/all', {'isDetails': 'false'})
    mapping = {
        item['market']: item.get('korean_name') or item.get('english_name') or item['market']
        for item in data
    }
    if not codes:
        return mapping
    return {code: mapping.get(code, code) for code in codes}


def fetch_ticker(codes: Iterable[str]) -> dict[str, float]:
    code_list = list(codes)
    if not code_list:
        return {}
    data = _get('/ticker', {'markets': ','.join(code_list)})
    return {item['market']: float(item['trade_price']) for item in data}


def fetch_minute_candles(market: str, unit: int, count: int = 200) -> list[dict]:
    data = _get(f'/candles/minutes/{unit}', {'market': market, 'count': str(count)})
    return list(reversed(data))
