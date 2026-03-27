from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


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
    rule_type: Literal['rsi_reversion', 'golden_cross', 'score_combo']
    rsi_buy_threshold: float | None = Field(default=35, ge=1, le=99)
    rsi_sell_threshold: float | None = Field(default=68, ge=1, le=99)
    volume_multiplier: float | None = Field(default=1.2, ge=1.0, le=10.0)
    score_threshold: float | None = Field(default=70, ge=1.0, le=100.0)


class StrategyToggleRequest(BaseModel):
    is_active: bool


class WatchlistCreateRequest(BaseModel):
    user_name: str = Field(default='demo', min_length=1, max_length=20)
    symbol: str


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
