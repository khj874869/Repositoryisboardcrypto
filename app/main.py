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
    AUTH_EMAIL_DELIVERY_MODE,
    AUTH_TOKEN_PREVIEW_ENABLED,
    BASE_DIR,
    CORS_ORIGINS,
    enforce_runtime_requirements,
    PUBLIC_API_BASE_URL,
    PUBLIC_WEB_BASE_URL,
    PUBLIC_WS_BASE_URL,
    auth_email_delivery_ready,
    runtime_config_issues,
)
from .runtime import MarketRuntime
from .schemas import (
    AuthActionResponse,
    ClientAssetDetailResponse,
    ClientBootstrapResponse,
    ClientDashboardResponse,
    EmailRequest,
    InstrumentResponse,
    NotificationSettingsUpdateRequest,
    UserSignalProfileResponse,
    UserSignalProfileUpdateRequest,
    PasswordResetConfirmRequest,
    RefreshSessionResponse,
    RefreshTokenRequest,
    StrategyCreateRequest,
    StrategyToggleRequest,
    TokenResponse,
    UserLoginRequest,
    UserSignupRequest,
    VerifyEmailRequest,
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
        'auth': {
            'email_delivery_mode': AUTH_EMAIL_DELIVERY_MODE,
            'token_preview_enabled': AUTH_TOKEN_PREVIEW_ENABLED,
            'email_delivery_ready': auth_email_delivery_ready(),
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
    signal_delivery: str | None = None,
    signal_data_mode: str | None = None,
    include_suppressed: bool = True,
    signal_audit_only: bool = False,
):
    return client_api.build_dashboard_payload(
        current_user,
        source_status=runtime.status(),
        interval_type=_active_interval_type(),
        signal_limit=signal_limit,
        notification_limit=notification_limit,
        signal_delivery=signal_delivery,
        signal_data_mode=signal_data_mode,
        include_suppressed=include_suppressed,
        signal_audit_only=signal_audit_only,
    )


@app.get('/api/client/assets/{symbol}', response_model=ClientAssetDetailResponse)
def client_asset_detail(
    symbol: str,
    current_user: dict | None = Depends(auth.get_optional_user),
    interval_type: str | None = None,
    candle_limit: int = 60,
    signal_limit: int = 20,
):
    active_interval_type = _active_interval_type()
    detail = client_api.build_asset_detail_payload(
        symbol,
        current_user=current_user,
        requested_interval_type=interval_type,
        fallback_interval_type=client_api.default_interval_type_for_symbol(symbol, active_interval_type),
        candle_limit=candle_limit,
        signal_limit=signal_limit,
    )
    if detail is None:
        raise HTTPException(status_code=404, detail='Asset not found')
    return detail


@app.post('/api/auth/signup', response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def signup(request: Request, payload: UserSignupRequest):
    if db.get_user_by_username(payload.username):
        raise HTTPException(status_code=409, detail='Username already exists')
    normalized_email = db.normalize_email(payload.email)
    existing_email = db.fetch_one('SELECT id FROM users WHERE email = ?', (normalized_email,))
    if existing_email:
        raise HTTPException(status_code=409, detail='Email already exists')

    user = db.create_user(
        username=payload.username,
        email=normalized_email,
        password_hash=auth.hash_password(payload.password),
    )
    return auth.build_auth_response(user, request, client_name=payload.client_name)


@app.post('/api/auth/login', response_model=TokenResponse)
def login(request: Request, payload: UserLoginRequest):
    user = db.get_user_by_login(payload.username)
    if not user or not auth.verify_password(payload.password, user['password_hash']):
        raise HTTPException(status_code=401, detail='Invalid credentials')
    return auth.build_auth_response(user, request, client_name=payload.client_name)


@app.post('/api/auth/refresh', response_model=TokenResponse)
def refresh_auth(request: Request, payload: RefreshTokenRequest):
    return auth.refresh_auth_response(payload.refresh_token, request, client_name=payload.client_name)


@app.post('/api/auth/logout')
def logout(payload: RefreshTokenRequest):
    auth.revoke_refresh_token(payload.refresh_token)
    return {'status': 'ok'}


@app.post('/api/auth/email-verification/request', response_model=AuthActionResponse)
def request_email_verification(current_user: dict = Depends(auth.get_current_user)):
    user = db.get_user_by_username(current_user['username'])
    if not user:
        raise HTTPException(status_code=404, detail='User not found')
    return auth.create_email_verification(user)


@app.post('/api/auth/email-verification/confirm')
def confirm_email_verification(payload: VerifyEmailRequest):
    return auth.verify_email_token(payload.token)


@app.post('/api/auth/password-reset/request', response_model=AuthActionResponse)
def request_password_reset(payload: EmailRequest):
    return auth.create_password_reset(db.normalize_email(payload.email))


@app.post('/api/auth/password-reset/confirm')
def confirm_password_reset(payload: PasswordResetConfirmRequest):
    return auth.reset_password_with_token(payload.token, payload.new_password)


@app.get('/api/auth/me')
def me(current_user: dict = Depends(auth.get_current_user)):
    return current_user


@app.get('/api/auth/sessions', response_model=list[RefreshSessionResponse])
def list_auth_sessions(context: dict = Depends(auth.get_current_auth_context)):
    current_session_id = context['token'].get('sid')
    sessions = db.list_refresh_sessions(context['user']['username'])
    payload: list[dict[str, object]] = []
    for session in sessions:
        is_active = not bool(session.get('revoked_at')) and auth.time_from_iso(session['expires_at']) > db.utc_now()
        payload.append(
            {
                'id': session['id'],
                'user_name': session['user_name'],
                'client_name': session.get('client_name'),
                'user_agent': session.get('user_agent'),
                'ip_address': session.get('ip_address'),
                'created_at': session['created_at'],
                'last_used_at': session.get('last_used_at'),
                'expires_at': session['expires_at'],
                'revoked_at': session.get('revoked_at'),
                'is_active': is_active,
                'is_current': session['id'] == current_session_id,
            }
        )
    return payload


@app.delete('/api/auth/sessions/{session_id}')
def revoke_auth_session(session_id: int, current_user: dict = Depends(auth.get_current_user)):
    revoked = db.revoke_refresh_session_for_user(session_id, current_user['username'])
    if not revoked:
        raise HTTPException(status_code=404, detail='Session not found')
    return {'status': 'ok'}


@app.get('/api/assets')
def list_assets():
    return db.fetch_all('SELECT * FROM assets ORDER BY symbol ASC')


@app.get('/api/instruments/search', response_model=list[InstrumentResponse])
def search_instruments(q: str = '', market_type: str | None = None, limit: int = 20):
    return [client_api.format_instrument_payload(row) for row in db.search_instruments(q, market_type=market_type, limit=limit)]


@app.get('/api/instruments/{symbol}', response_model=InstrumentResponse)
def get_instrument(symbol: str):
    instrument = db.get_instrument(symbol)
    if instrument is None:
        raise HTTPException(status_code=404, detail='Instrument not found')
    asset = db.fetch_one('SELECT last_price, change_rate, updated_at FROM assets WHERE symbol = ?', (symbol,))
    payload = dict(instrument)
    if asset:
        payload.update(asset)
    return client_api.format_instrument_payload(payload)


@app.get('/api/assets/{symbol}/candles')
def get_candles(symbol: str, limit: int = 50, interval_type: str | None = None):
    active_interval_type = _active_interval_type()
    candle_result = client_api.resolve_recent_candles(
        symbol,
        limit,
        requested_interval_type=interval_type,
        fallback_interval_type=client_api.default_interval_type_for_symbol(symbol, active_interval_type),
    )
    return list(reversed(candle_result['candles']))


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
def recent_signals(
    limit: int = 30,
    signal_delivery: str | None = None,
    signal_data_mode: str | None = None,
    include_suppressed: bool = True,
    signal_audit_only: bool = False,
):
    return client_api.build_signal_feed(
        limit,
        notification_delivery=signal_delivery,
        data_mode=signal_data_mode,
        include_suppressed=include_suppressed,
        audit_only=signal_audit_only,
    )


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
    instrument = db.get_instrument(payload.symbol)
    if not instrument:
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


@app.get('/api/signal-profiles/{symbol}', response_model=UserSignalProfileResponse)
def get_signal_profile(symbol: str, current_user: dict = Depends(auth.get_current_user)):
    instrument = db.get_instrument(symbol)
    if not instrument:
        raise HTTPException(status_code=404, detail='Unknown symbol')
    return db.get_user_signal_profile(current_user['username'], symbol)


@app.patch('/api/signal-profiles/{symbol}', response_model=UserSignalProfileResponse)
def patch_signal_profile(
    symbol: str,
    payload: UserSignalProfileUpdateRequest,
    current_user: dict = Depends(auth.get_current_user),
):
    instrument = db.get_instrument(symbol)
    if not instrument:
        raise HTTPException(status_code=404, detail='Unknown symbol')
    return db.update_user_signal_profile(
        current_user['username'],
        symbol,
        is_enabled=payload.is_enabled,
        rsi_buy_threshold=payload.rsi_buy_threshold,
        rsi_sell_threshold=payload.rsi_sell_threshold,
        volume_multiplier=payload.volume_multiplier,
        score_threshold=payload.score_threshold,
        use_orderbook_pressure=payload.use_orderbook_pressure,
        orderbook_bias_threshold=payload.orderbook_bias_threshold,
        use_derivatives_confirm=payload.use_derivatives_confirm,
        derivatives_bias_threshold=payload.derivatives_bias_threshold,
    )


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
