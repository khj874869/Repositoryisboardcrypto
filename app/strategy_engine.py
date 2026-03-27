from __future__ import annotations

from dataclasses import dataclass
from statistics import fmean

from .indicators import bollinger, rsi, sma


@dataclass(slots=True)
class IndicatorSnapshot:
    symbol: str
    close_price: float
    volume: float
    avg_volume_20: float | None
    rsi14: float | None
    sma5: float | None
    sma20: float | None
    prev_sma5: float | None
    prev_sma20: float | None
    bollinger_upper: float | None
    bollinger_lower: float | None


@dataclass(slots=True)
class SignalDecision:
    signal_type: str
    strategy_name: str
    score: float
    reason: str


def build_snapshot(symbol: str, candles: list[dict]) -> IndicatorSnapshot:
    closes = [float(candle['close_price']) for candle in candles]
    volumes = [float(candle['volume']) for candle in candles]

    bands = bollinger(closes, 20)
    prev_bands = bollinger(closes[:-1], 20) if len(closes) > 20 else None

    return IndicatorSnapshot(
        symbol=symbol,
        close_price=closes[-1],
        volume=volumes[-1],
        avg_volume_20=round(fmean(volumes[-20:]), 4) if len(volumes) >= 20 else None,
        rsi14=rsi(closes, 14),
        sma5=sma(closes, 5),
        sma20=sma(closes, 20),
        prev_sma5=sma(closes[:-1], 5) if len(closes) > 5 else None,
        prev_sma20=sma(closes[:-1], 20) if len(closes) > 20 else None,
        bollinger_upper=bands[0] if bands else None,
        bollinger_lower=bands[2] if bands else None,
    )


def evaluate_strategies(snapshot: IndicatorSnapshot, strategies: list[dict]) -> list[SignalDecision]:
    decisions: list[SignalDecision] = []
    for strategy in strategies:
        if not strategy['is_active']:
            continue

        rule_type = strategy['rule_type']
        if rule_type == 'rsi_reversion':
            decisions.extend(_evaluate_rsi_reversion(snapshot, strategy))
        elif rule_type == 'golden_cross':
            decision = _evaluate_golden_cross(snapshot, strategy)
            if decision:
                decisions.append(decision)
        elif rule_type == 'score_combo':
            decision = _evaluate_score_combo(snapshot, strategy)
            if decision:
                decisions.append(decision)
    return decisions


def _evaluate_rsi_reversion(snapshot: IndicatorSnapshot, strategy: dict) -> list[SignalDecision]:
    out: list[SignalDecision] = []
    if None in (snapshot.rsi14, snapshot.bollinger_lower, snapshot.bollinger_upper, snapshot.avg_volume_20):
        return out

    buy_threshold = strategy.get('rsi_buy_threshold') or 35
    sell_threshold = strategy.get('rsi_sell_threshold') or 68
    volume_multiplier = strategy.get('volume_multiplier') or 1.2

    if (
        snapshot.rsi14 < buy_threshold
        and snapshot.close_price <= snapshot.bollinger_lower * 1.01
        and snapshot.volume >= snapshot.avg_volume_20 * volume_multiplier
    ):
        out.append(
            SignalDecision(
                signal_type='BUY',
                strategy_name=strategy['name'],
                score=82,
                reason=(
                    f"RSI {snapshot.rsi14:.1f}, Bollinger lower touch, "
                    f"volume x{volume_multiplier:.1f}"
                ),
            )
        )

    if snapshot.rsi14 > sell_threshold and snapshot.close_price >= snapshot.bollinger_upper * 0.99:
        out.append(
            SignalDecision(
                signal_type='SELL',
                strategy_name=strategy['name'],
                score=76,
                reason=f"RSI {snapshot.rsi14:.1f}, Bollinger upper near",
            )
        )
    return out


def _evaluate_golden_cross(snapshot: IndicatorSnapshot, strategy: dict) -> SignalDecision | None:
    if None in (snapshot.sma5, snapshot.sma20, snapshot.prev_sma5, snapshot.prev_sma20):
        return None
    if snapshot.prev_sma5 <= snapshot.prev_sma20 and snapshot.sma5 > snapshot.sma20:
        return SignalDecision(
            signal_type='BUY',
            strategy_name=strategy['name'],
            score=74,
            reason=f"Golden cross (SMA5 {snapshot.sma5:.2f} > SMA20 {snapshot.sma20:.2f})",
        )
    return None


def _evaluate_score_combo(snapshot: IndicatorSnapshot, strategy: dict) -> SignalDecision | None:
    score = 0
    reasons: list[str] = []
    threshold = strategy.get('score_threshold') or 70

    if snapshot.rsi14 is not None and snapshot.rsi14 < (strategy.get('rsi_buy_threshold') or 40):
        score += 30
        reasons.append(f"RSI {snapshot.rsi14:.1f}")

    if snapshot.avg_volume_20 is not None:
        volume_multiplier = strategy.get('volume_multiplier') or 1.3
        if snapshot.volume >= snapshot.avg_volume_20 * volume_multiplier:
            score += 20
            reasons.append('Volume surge')

    if snapshot.bollinger_lower is not None and snapshot.close_price <= snapshot.bollinger_lower * 1.01:
        score += 25
        reasons.append('Bollinger lower touch')

    if None not in (snapshot.sma5, snapshot.sma20) and snapshot.sma5 > snapshot.sma20:
        score += 25
        reasons.append('Short-term trend up')

    if score >= threshold:
        return SignalDecision(
            signal_type='BUY',
            strategy_name=strategy['name'],
            score=float(score),
            reason=', '.join(reasons) or 'Composite score met',
        )
    return None
