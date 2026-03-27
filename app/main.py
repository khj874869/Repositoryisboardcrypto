from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import db
from .broadcaster import Broadcaster
from .config import BASE_DIR, DEMO_USER
from .market_simulator import MarketSimulator
from .schemas import StrategyCreateRequest, StrategyToggleRequest, WatchlistCreateRequest
from .strategy_engine import build_snapshot

STATIC_DIR = BASE_DIR / 'static'

broadcaster = Broadcaster()
simulator = MarketSimulator(broadcaster)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    task = asyncio.create_task(simulator.start())
    try:
        yield
    finally:
        await simulator.stop()
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


# Python 3.13 contextlib imported after use by flake? keep explicit.
import contextlib

app = FastAPI(
    title='Signal Flow MVP',
    description='Real-time simulated market stream with strategy signals.',
    version='0.1.0',
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)
app.mount('/static', StaticFiles(directory=STATIC_DIR), name='static')


@app.get('/')
def index() -> FileResponse:
    return FileResponse(Path(STATIC_DIR / 'index.html'))


@app.get('/api/health')
def health() -> dict[str, str]:
    return {'status': 'ok'}


@app.get('/api/assets')
def list_assets():
    return db.fetch_all('SELECT * FROM assets ORDER BY symbol ASC')


@app.get('/api/assets/{symbol}/candles')
def get_candles(symbol: str, limit: int = 50):
    return db.fetch_all(
        '''
        SELECT *
        FROM candles
        WHERE symbol = ?
        ORDER BY candle_time DESC
        LIMIT ?
        ''',
        (symbol, limit),
    )


@app.get('/api/assets/{symbol}/signals')
def get_signals(symbol: str, limit: int = 30):
    return db.fetch_all(
        '''
        SELECT *
        FROM signals
        WHERE symbol = ?
        ORDER BY created_at DESC
        LIMIT ?
        ''',
        (symbol, limit),
    )


@app.get('/api/signals/recent')
def recent_signals(limit: int = 30):
    return db.fetch_all('SELECT * FROM signals ORDER BY created_at DESC LIMIT ?', (limit,))


@app.get('/api/strategies')
def list_strategies():
    return db.fetch_all('SELECT * FROM strategies ORDER BY id ASC')


@app.post('/api/strategies', status_code=201)
def create_strategy(payload: StrategyCreateRequest):
    db.execute(
        '''
        INSERT INTO strategies(
            name, rule_type, is_active, rsi_buy_threshold, rsi_sell_threshold,
            volume_multiplier, score_threshold, created_at
        )
        VALUES (?, ?, 1, ?, ?, ?, ?, ?)
        ''',
        (
            payload.name,
            payload.rule_type,
            payload.rsi_buy_threshold,
            payload.rsi_sell_threshold,
            payload.volume_multiplier,
            payload.score_threshold,
            db.isoformat(db.utc_now()),
        ),
    )
    return {'message': 'strategy_created'}


@app.patch('/api/strategies/{strategy_id}')
def toggle_strategy(strategy_id: int, payload: StrategyToggleRequest):
    strategy = db.fetch_one('SELECT * FROM strategies WHERE id = ?', (strategy_id,))
    if not strategy:
        raise HTTPException(status_code=404, detail='Strategy not found')
    db.execute('UPDATE strategies SET is_active = ? WHERE id = ?', (int(payload.is_active), strategy_id))
    return {'message': 'strategy_updated'}


@app.get('/api/watchlist')
def list_watchlist(user_name: str = DEMO_USER):
    return db.fetch_all(
        '''
        SELECT w.id, w.user_name, w.symbol, w.created_at, a.last_price, a.change_rate
        FROM watchlists w
        JOIN assets a ON a.symbol = w.symbol
        WHERE w.user_name = ?
        ORDER BY w.created_at DESC
        ''',
        (user_name,),
    )


@app.post('/api/watchlist', status_code=201)
def add_watchlist(payload: WatchlistCreateRequest):
    asset = db.fetch_one('SELECT symbol FROM assets WHERE symbol = ?', (payload.symbol,))
    if not asset:
        raise HTTPException(status_code=404, detail='Unknown symbol')
    db.execute(
        '''
        INSERT OR IGNORE INTO watchlists(user_name, symbol, created_at)
        VALUES (?, ?, ?)
        ''',
        (payload.user_name, payload.symbol, db.isoformat(db.utc_now())),
    )
    return {'message': 'watchlist_added'}


@app.delete('/api/watchlist/{symbol}')
def delete_watchlist(symbol: str, user_name: str = DEMO_USER):
    db.execute('DELETE FROM watchlists WHERE user_name = ? AND symbol = ?', (user_name, symbol))
    return {'message': 'watchlist_deleted'}


@app.get('/api/market/overview')
def market_overview():
    assets = db.fetch_all('SELECT * FROM assets ORDER BY symbol ASC')
    watchlist_symbols = {
        row['symbol']
        for row in db.fetch_all('SELECT symbol FROM watchlists WHERE user_name = ?', (DEMO_USER,))
    }
    latest_signals = {
        row['symbol']: row
        for row in db.fetch_all(
            '''
            SELECT s1.*
            FROM signals s1
            JOIN (
              SELECT symbol, MAX(created_at) AS created_at
              FROM signals
              GROUP BY symbol
            ) s2 ON s1.symbol = s2.symbol AND s1.created_at = s2.created_at
            '''
        )
    }

    overview: list[dict] = []
    for asset in assets:
        candles = db.fetch_all(
            '''
            SELECT *
            FROM candles
            WHERE symbol = ?
            ORDER BY candle_time ASC
            LIMIT 120
            ''',
            (asset['symbol'],),
        )
        if candles:
            snapshot = build_snapshot(asset['symbol'], candles)
            signal = latest_signals.get(asset['symbol'])
            overview.append(
                {
                    'symbol': asset['symbol'],
                    'name': asset['name'],
                    'price': asset['last_price'],
                    'change_rate': asset['change_rate'],
                    'rsi14': snapshot.rsi14,
                    'sma5': snapshot.sma5,
                    'sma20': snapshot.sma20,
                    'bollinger_upper': snapshot.bollinger_upper,
                    'bollinger_lower': snapshot.bollinger_lower,
                    'recent_signal_type': signal['signal_type'] if signal else None,
                    'recent_signal_reason': signal['reason'] if signal else None,
                    'in_watchlist': asset['symbol'] in watchlist_symbols,
                }
            )
    return overview


@app.websocket('/ws/stream')
async def websocket_stream(websocket: WebSocket) -> None:
    await broadcaster.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await broadcaster.disconnect(websocket)
    except Exception:
        await broadcaster.disconnect(websocket)
