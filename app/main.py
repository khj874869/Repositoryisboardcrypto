from __future__ import annotations

import asyncio
import contextlib
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import auth, db
from .broadcaster import Broadcaster
from .config import APP_VERSION, BASE_DIR
from .runtime import MarketRuntime
from .schemas import (
    NotificationSettingsUpdateRequest,
    StrategyCreateRequest,
    StrategyToggleRequest,
    UserLoginRequest,
    UserSignupRequest,
    WatchlistCreateRequest,
)
from .strategy_engine import build_snapshot

STATIC_DIR = BASE_DIR / 'static'

broadcaster = Broadcaster()
runtime = MarketRuntime(broadcaster)


def _active_interval_type() -> str | None:
    status_payload = runtime.status()
    active_source = status_payload.get('active_source')
    interval = status_payload.get('interval')
    if not interval:
        return None
    if active_source == 'upbit':
        return f'upbit-{interval}'
    return str(interval)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    task = asyncio.create_task(runtime.start())
    try:
        yield
    finally:
        await runtime.stop()
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


app = FastAPI(
    title='Signal Flow Live',
    description='실시간 주식/코인 시그널 분석 플랫폼 데모',
    version=APP_VERSION,
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
def health() -> dict[str, object]:
    status_payload = runtime.status()
    return {
        'status': 'ok',
        'version': APP_VERSION,
        'requested_source': status_payload.get('requested_source'),
        'active_source': status_payload.get('active_source'),
        'state': status_payload.get('state'),
    }


@app.get('/api/source-status')
def source_status() -> dict[str, object]:
    return runtime.status()


@app.post('/api/auth/signup', status_code=status.HTTP_201_CREATED)
def signup(payload: UserSignupRequest):
    if db.get_user_by_username(payload.username):
        raise HTTPException(status_code=409, detail='Username already exists')
    existing_email = db.fetch_one('SELECT id FROM users WHERE email = ?', (payload.email,))
    if existing_email:
        raise HTTPException(status_code=409, detail='Email already exists')

    user = db.create_user(
        username=payload.username,
        email=payload.email,
        password_hash=auth.hash_password(payload.password),
    )
    token = auth.create_access_token(payload.username)
    return {'access_token': token, 'token_type': 'bearer', 'user': user}


@app.post('/api/auth/login')
def login(payload: UserLoginRequest):
    user = db.get_user_by_username(payload.username)
    if not user or not auth.verify_password(payload.password, user['password_hash']):
        raise HTTPException(status_code=401, detail='Invalid credentials')
    public_user = {
        'id': user['id'],
        'username': user['username'],
        'email': user['email'],
        'created_at': user['created_at'],
    }
    token = auth.create_access_token(payload.username)
    return {'access_token': token, 'token_type': 'bearer', 'user': public_user}


@app.get('/api/auth/me')
def me(current_user: dict = Depends(auth.get_current_user)):
    return current_user


@app.get('/api/assets')
def list_assets():
    return db.fetch_all('SELECT * FROM assets ORDER BY symbol ASC')


@app.get('/api/assets/{symbol}/candles')
def get_candles(symbol: str, limit: int = 50, interval_type: str | None = None):
    effective_interval = interval_type or _active_interval_type()
    if effective_interval:
        return db.fetch_all(
            '''
            SELECT *
            FROM candles
            WHERE symbol = ? AND interval_type = ?
            ORDER BY candle_time DESC
            LIMIT ?
            ''',
            (symbol, effective_interval, limit),
        )
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
def list_watchlist(current_user: dict = Depends(auth.get_current_user)):
    return db.get_watchlist_for_user(current_user['username'])


@app.post('/api/watchlist', status_code=201)
def add_watchlist(payload: WatchlistCreateRequest, current_user: dict = Depends(auth.get_current_user)):
    asset = db.fetch_one('SELECT symbol FROM assets WHERE symbol = ?', (payload.symbol,))
    if not asset:
        raise HTTPException(status_code=404, detail='Unknown symbol')
    db.add_watchlist_item(current_user['username'], payload.symbol)
    return {'message': 'watchlist_added'}


@app.delete('/api/watchlist/{symbol}')
def delete_watchlist(symbol: str, current_user: dict = Depends(auth.get_current_user)):
    db.delete_watchlist_item(current_user['username'], symbol)
    return {'message': 'watchlist_deleted'}


@app.get('/api/market/overview')
def market_overview(current_user: dict | None = Depends(auth.get_optional_user)):
    assets = db.fetch_all('SELECT * FROM assets ORDER BY symbol ASC')
    effective_interval = _active_interval_type()
    watchlist_symbols = set()
    if current_user:
        watchlist_symbols = {
            row['symbol']
            for row in db.fetch_all('SELECT symbol FROM watchlists WHERE user_name = ?', (current_user['username'],))
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
        candles = db.fetch_recent_candles(asset['symbol'], 120, interval_type=effective_interval)
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
        else:
            overview.append(
                {
                    'symbol': asset['symbol'],
                    'name': asset['name'],
                    'price': asset['last_price'],
                    'change_rate': asset['change_rate'],
                    'rsi14': None,
                    'sma5': None,
                    'sma20': None,
                    'bollinger_upper': None,
                    'bollinger_lower': None,
                    'recent_signal_type': None,
                    'recent_signal_reason': None,
                    'in_watchlist': asset['symbol'] in watchlist_symbols,
                }
            )
    return overview


@app.get('/api/notifications')
def get_notifications(limit: int = 20, current_user: dict = Depends(auth.get_current_user)):
    return db.fetch_notifications(current_user['username'], limit)


@app.patch('/api/notifications/{notification_id}/read')
def read_notification(notification_id: int, current_user: dict = Depends(auth.get_current_user)):
    updated = db.mark_notification_read(current_user['username'], notification_id)
    if not updated:
        raise HTTPException(status_code=404, detail='Notification not found')
    return {'message': 'notification_marked_read'}


@app.get('/api/notification-settings')
def get_notification_settings(current_user: dict = Depends(auth.get_current_user)):
    return db.get_notification_settings(current_user['username'])


@app.patch('/api/notification-settings')
def patch_notification_settings(
    payload: NotificationSettingsUpdateRequest,
    current_user: dict = Depends(auth.get_current_user),
):
    return db.update_notification_settings(
        current_user['username'],
        web_enabled=payload.web_enabled,
        email_enabled=payload.email_enabled,
    )


@app.websocket('/ws/stream')
async def websocket_stream(websocket: WebSocket) -> None:
    await broadcaster.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await broadcaster.disconnect(websocket)
