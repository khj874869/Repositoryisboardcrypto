from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class UserSignupRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=30, pattern=r'^[a-zA-Z0-9_\-]+$')
    email: str = Field(..., min_length=5, max_length=100)
    password: str = Field(..., min_length=8, max_length=128)


class UserLoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=30)
    password: str = Field(..., min_length=8, max_length=128)


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    created_at: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal['bearer'] = 'bearer'
    user: UserResponse


class AssetResponse(BaseModel):
    symbol: str
    name: str
    market_type: str
    last_price: float
    change_rate: float
    updated_at: str


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
    rsi14: float | None = None
    sma5: float | None = None
    sma20: float | None = None
    bollinger_upper: float | None = None
    bollinger_lower: float | None = None
    recent_signal_type: str | None = None
    recent_signal_reason: str | None = None
    in_watchlist: bool = False


class BroadcastMessage(BaseModel):
    type: Literal['market_snapshot', 'signal']
    payload: dict
    timestamp: datetime
