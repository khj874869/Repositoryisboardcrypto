from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class UserSignupRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=30, pattern=r'^[a-zA-Z0-9_\-]+$')
    email: str = Field(..., min_length=5, max_length=100)
    password: str = Field(..., min_length=8, max_length=128)
    client_name: str | None = Field(default=None, max_length=120)


class UserLoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=8, max_length=128)
    client_name: str | None = Field(default=None, max_length=120)


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    email_verified: bool = False
    email_verified_at: str | None = None
    created_at: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal['bearer'] = 'bearer'
    expires_in: int
    refresh_expires_at: str
    user: UserResponse


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(..., min_length=20, max_length=255)
    client_name: str | None = Field(default=None, max_length=120)


class EmailRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=100)


class PasswordResetConfirmRequest(BaseModel):
    token: str = Field(..., min_length=20, max_length=255)
    new_password: str = Field(..., min_length=8, max_length=128)


class VerifyEmailRequest(BaseModel):
    token: str = Field(..., min_length=20, max_length=255)


class ActionTokenPreviewResponse(BaseModel):
    token: str


class AuthActionResponse(BaseModel):
    status: str
    delivery: str | None = None
    expires_at: str | None = None
    preview: ActionTokenPreviewResponse | None = None


class RefreshSessionResponse(BaseModel):
    id: int
    user_name: str
    client_name: str | None = None
    user_agent: str | None = None
    ip_address: str | None = None
    created_at: str
    last_used_at: str | None = None
    expires_at: str
    revoked_at: str | None = None
    is_active: bool
    is_current: bool = False


class AssetResponse(BaseModel):
    symbol: str
    name: str
    market_type: str
    last_price: float
    change_rate: float
    updated_at: str


class InstrumentCapabilitiesResponse(BaseModel):
    has_realtime_feed: bool
    has_volume_feed: bool
    has_orderbook_feed: bool
    has_derivatives_feed: bool
    supports_indicator_profiles: bool


class InstrumentRuntimeResponse(BaseModel):
    data_mode: str
    data_source: str
    interval_type: str
    market_session: str
    is_delayed: bool
    as_of: str
    updated_at: str


class InstrumentResponse(BaseModel):
    symbol: str
    name: str
    market_type: str
    exchange: str
    quote_currency: str
    category: str
    search_aliases: str = ''
    is_active: bool = True
    capabilities: InstrumentCapabilitiesResponse
    runtime: InstrumentRuntimeResponse | None = None
    last_price: float | None = None
    change_rate: float | None = None
    updated_at: str | None = None


class CandleResponse(BaseModel):
    id: int
    symbol: str
    candle_time: str
    interval_type: str
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: float


class SignalResponse(BaseModel):
    id: int
    symbol: str
    signal_type: str
    strategy_name: str
    score: float
    reason: str
    price: float
    notification_delivery: str = 'pending'
    notification_delivery_reason: str | None = None
    notification_count: int = 0
    created_at: str


class StrategyResponse(BaseModel):
    id: int
    name: str
    rule_type: str
    is_active: int
    rsi_buy_threshold: float | None = None
    rsi_sell_threshold: float | None = None
    volume_multiplier: float | None = None
    score_threshold: float | None = None
    created_at: str


class StrategyCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)
    rule_type: Literal['rsi_reversion', 'score_combo']
    rsi_buy_threshold: float | None = Field(default=35, ge=1, le=99)
    rsi_sell_threshold: float | None = Field(default=68, ge=1, le=99)
    volume_multiplier: float | None = Field(default=1.2, ge=1.0, le=10.0)
    score_threshold: float | None = Field(default=70, ge=1.0, le=100.0)


class StrategyToggleRequest(BaseModel):
    is_active: bool


class WatchlistCreateRequest(BaseModel):
    symbol: str


class NotificationSettingsResponse(BaseModel):
    user_name: str
    web_enabled: bool
    email_enabled: bool
    updated_at: str


class NotificationSettingsUpdateRequest(BaseModel):
    web_enabled: bool | None = None
    email_enabled: bool | None = None


class NotificationResponse(BaseModel):
    id: int
    user_name: str
    symbol: str
    signal_type: str
    strategy_name: str
    reason: str
    price: float
    created_at: str
    is_read: bool
    read_at: str | None = None


class OverviewResponse(BaseModel):
    symbol: str
    name: str
    price: float
    change_rate: float
    data_mode: str | None = None
    data_source: str | None = None
    market_session: str | None = None
    is_delayed: bool = False
    rsi14: float | None = None
    sma5: float | None = None
    sma20: float | None = None
    bollinger_upper: float | None = None
    bollinger_lower: float | None = None
    recent_signal_type: str | None = None
    recent_signal_reason: str | None = None
    profile_signal_type: str | None = None
    profile_signal_reason: str | None = None
    in_watchlist: bool = False


class BroadcastMessage(BaseModel):
    type: Literal['market_snapshot', 'signal']
    payload: dict
    timestamp: datetime


class ClientSessionResponse(BaseModel):
    authenticated: bool
    user: UserResponse | None = None


class ClientPlatformResponse(BaseModel):
    name: str
    api_base_url: str
    websocket_url: str


class ClientEndpointsResponse(BaseModel):
    bootstrap: str
    dashboard: str
    asset_detail: str
    login: str
    signup: str
    refresh: str
    logout: str
    sessions: str
    request_password_reset: str
    reset_password: str
    request_email_verification: str
    verify_email: str
    me: str
    overview: str
    instrument_search: str
    instrument_detail: str
    signal_profile: str
    signals_recent: str
    watchlist: str
    notifications: str
    notification_settings: str
    websocket: str


class ClientFeaturesResponse(BaseModel):
    auth: bool
    watchlist: bool
    notifications: bool
    strategies: bool
    instrument_search: bool
    signal_profiles: bool
    realtime_stream: bool
    web: bool
    app: bool


class MarketCatalogItemResponse(BaseModel):
    symbol: str
    name: str
    market_type: str


class ClientCatalogResponse(BaseModel):
    assets: list[MarketCatalogItemResponse]
    supported_intervals: list[str]


class ClientBootstrapResponse(BaseModel):
    app: dict[str, str]
    session: ClientSessionResponse
    source: dict[str, object]
    platforms: list[ClientPlatformResponse]
    endpoints: ClientEndpointsResponse
    features: ClientFeaturesResponse
    catalog: ClientCatalogResponse


class DashboardCountsResponse(BaseModel):
    assets: int
    watchlist: int
    recent_signals: int
    notifications: int
    unread_notifications: int


class ClientDashboardResponse(BaseModel):
    session: ClientSessionResponse
    source: dict[str, object]
    overview: list[OverviewResponse]
    signals: list[SignalResponse]
    watchlist: list[dict]
    notifications: list[NotificationResponse]
    notification_settings: NotificationSettingsResponse | None = None
    counts: DashboardCountsResponse


class SnapshotSummaryResponse(BaseModel):
    rsi14: float | None = None
    sma5: float | None = None
    sma20: float | None = None
    bollinger_upper: float | None = None
    bollinger_lower: float | None = None
    close_price: float | None = None


class UserSignalProfileResponse(BaseModel):
    id: int
    user_name: str
    symbol: str
    is_enabled: bool
    rsi_buy_threshold: float
    rsi_sell_threshold: float
    volume_multiplier: float
    score_threshold: float
    use_orderbook_pressure: bool
    orderbook_bias_threshold: float
    use_derivatives_confirm: bool
    derivatives_bias_threshold: float
    created_at: str
    updated_at: str


class UserSignalProfileUpdateRequest(BaseModel):
    is_enabled: bool | None = None
    rsi_buy_threshold: float | None = Field(default=None, ge=1, le=99)
    rsi_sell_threshold: float | None = Field(default=None, ge=1, le=99)
    volume_multiplier: float | None = Field(default=None, ge=1.0, le=10.0)
    score_threshold: float | None = Field(default=None, ge=1.0, le=100.0)
    use_orderbook_pressure: bool | None = None
    orderbook_bias_threshold: float | None = Field(default=None, ge=0.1, le=10.0)
    use_derivatives_confirm: bool | None = None
    derivatives_bias_threshold: float | None = Field(default=None, ge=0.1, le=10.0)


class ProfileEvaluationResponse(BaseModel):
    status: Literal['BUY', 'SELL', 'WATCH', 'DISABLED', 'UNAVAILABLE']
    score: float
    reason: str
    blockers: list[str] = []


class ClientAssetDetailResponse(BaseModel):
    asset: AssetResponse
    instrument: InstrumentResponse | None = None
    interval_type: str | None = None
    requested_interval_type: str | None = None
    interval_fallback_applied: bool = False
    candles: list[CandleResponse]
    signals: list[SignalResponse]
    user_signal_profile: UserSignalProfileResponse | None = None
    profile_evaluation: ProfileEvaluationResponse | None = None
    snapshot: SnapshotSummaryResponse | None = None
