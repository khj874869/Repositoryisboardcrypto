from __future__ import annotations

import asyncio
import contextlib
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import auth, client_api, db
from .broadcaster import Broadcaster
from .config import (
    APP_ENV,
    APP_NAME,
    APP_VERSION,
    ANDROID_PACKAGE_NAME,
    ANDROID_SHA256_CERT_FINGERPRINTS,
    BASE_DIR,
    CORS_ORIGINS,
    enforce_runtime_requirements,
    PUBLIC_API_BASE_URL,
    PUBLIC_WEB_BASE_URL,
    PUBLIC_WS_BASE_URL,
    runtime_config_issues,
)
from .runtime import MarketRuntime
from .schemas import (
    ClientAssetDetailResponse,
    ClientBootstrapResponse,
    ClientDashboardResponse,
    NotificationSettingsUpdateRequest,
    StrategyCreateRequest,
    StrategyToggleRequest,
    UserLoginRequest,
    UserSignupRequest,
    WatchlistCreateRequest,
)

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
    enforce_runtime_requirements()
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
    title=APP_NAME,
    description='실시간 주식/코인 시그널 분석 플랫폼 데모',
    version=APP_VERSION,
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS or ['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)
app.mount('/static', StaticFiles(directory=STATIC_DIR), name='static')


@app.get('/')
def index() -> FileResponse:
    return FileResponse(Path(STATIC_DIR / 'index.html'))


@app.get('/manifest.webmanifest')
def manifest() -> FileResponse:
    return FileResponse(Path(STATIC_DIR / 'manifest.webmanifest'), media_type='application/manifest+json')


@app.get('/sw.js')
def service_worker() -> FileResponse:
    return FileResponse(Path(STATIC_DIR / 'sw.js'), media_type='application/javascript')


@app.get('/icon.svg')
def app_icon() -> FileResponse:
    return FileResponse(Path(STATIC_DIR / 'icon.svg'), media_type='image/svg+xml')


@app.get('/.well-known/assetlinks.json')
def asset_links() -> JSONResponse:
    if not ANDROID_PACKAGE_NAME or not ANDROID_SHA256_CERT_FINGERPRINTS:
        return JSONResponse([])
    return JSONResponse(
        [
            {
                'relation': ['delegate_permission/common.handle_all_urls'],
                'target': {
                    'namespace': 'android_app',
                    'package_name': ANDROID_PACKAGE_NAME,
                    'sha256_cert_fingerprints': ANDROID_SHA256_CERT_FINGERPRINTS,
                },
            }
        ]
    )


@app.get('/api/health')
def health() -> dict[str, object]:
    status_payload = runtime.status()
    database = db.database_status()
    return {
        'status': 'ok',
        'version': APP_VERSION,
        'requested_source': status_payload.get('requested_source'),
        'active_source': status_payload.get('active_source'),
        'state': status_payload.get('state'),
        'database': {
            'dialect': database['dialect'],
            'driver': database['driver'],
            'healthy': database['healthy'],
        },
    }


@app.get('/api/readiness')
def readiness() -> dict[str, object]:
    status_payload = runtime.status()
    issues = runtime_config_issues()
    database = db.database_status()
    ready = (
        status_payload.get('state') in {'streaming', 'connecting', 'reconnecting'}
        and not issues
        and database['healthy']
    )
    return {
        'status': 'ready' if ready else 'not_ready',
        'version': APP_VERSION,
        'environment': APP_ENV,
        'requested_source': status_payload.get('requested_source'),
        'active_source': status_payload.get('active_source'),
        'state': status_payload.get('state'),
        'issues': issues,
        'database': database,
    }


@app.get('/api/source-status')
def source_status() -> dict[str, object]:
    return runtime.status()


@app.get('/api/release-status')
def release_status() -> dict[str, object]:
    issues = runtime_config_issues()
    assetlinks_ready = bool(ANDROID_PACKAGE_NAME and ANDROID_SHA256_CERT_FINGERPRINTS)
    return {
        'environment': APP_ENV,
        'public_urls': {
            'web': PUBLIC_WEB_BASE_URL,
            'api': PUBLIC_API_BASE_URL,
            'websocket': PUBLIC_WS_BASE_URL,
        },
        'pwa': {
            'manifest_url': '/manifest.webmanifest',
            'service_worker_url': '/sw.js',
            'assetlinks_url': '/.well-known/assetlinks.json',
            'https_ready': bool(
                PUBLIC_WEB_BASE_URL.startswith('https://')
                and PUBLIC_API_BASE_URL.startswith('https://')
                and PUBLIC_WS_BASE_URL.startswith('wss://')
            ),
        },
        'android': {
            'package_name': ANDROID_PACKAGE_NAME,
            'sha256_cert_fingerprints': ANDROID_SHA256_CERT_FINGERPRINTS,
            'assetlinks_ready': assetlinks_ready,
        },
        'issues': issues,
        'ready_for_hosted_pwa': not issues
        and PUBLIC_WEB_BASE_URL.startswith('https://')
        and PUBLIC_API_BASE_URL.startswith('https://')
        and PUBLIC_WS_BASE_URL.startswith('wss://'),
        'ready_for_android_packaging': not issues and assetlinks_ready,
    }


@app.get('/api/client/bootstrap', response_model=ClientBootstrapResponse)
def client_bootstrap(request: Request, current_user: dict | None = Depends(auth.get_optional_user)):
    return client_api.build_bootstrap_payload(
        request,
        current_user,
        source_status=runtime.status(),
    )


@app.get('/api/client/dashboard', response_model=ClientDashboardResponse)
def client_dashboard(
    current_user: dict | None = Depends(auth.get_optional_user),
    signal_limit: int = 12,
    notification_limit: int = 10,
):
    return client_api.build_dashboard_payload(
        current_user,
        source_status=runtime.status(),
        interval_type=_active_interval_type(),
        signal_limit=signal_limit,
        notification_limit=notification_limit,
    )


@app.get('/api/client/assets/{symbol}', response_model=ClientAssetDetailResponse)
def client_asset_detail(
    symbol: str,
    interval_type: str | None = None,
    candle_limit: int = 60,
    signal_limit: int = 20,
):
    detail = client_api.build_asset_detail_payload(
        symbol,
        interval_type=interval_type or _active_interval_type(),
        candle_limit=candle_limit,
        signal_limit=signal_limit,
    )
    if detail is None:
        raise HTTPException(status_code=404, detail='Asset not found')
    return detail


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
    return client_api.build_market_overview(current_user, interval_type=_active_interval_type())


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
