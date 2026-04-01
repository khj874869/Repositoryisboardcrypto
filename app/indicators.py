from __future__ import annotations

from math import sqrt
from statistics import fmean


def sma(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    return round(fmean(values[-period:]), 4)



def rsi(closes: list[float], period: int = 14) -> float | None:
    if len(closes) <= period:
        return None

    gains: list[float] = []
    losses: list[float] = []
    for idx in range(-period, 0):
        diff = closes[idx] - closes[idx - 1]
        gains.append(max(diff, 0))
        losses.append(abs(min(diff, 0)))

    avg_gain = fmean(gains)
    avg_loss = fmean(losses)
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 4)

def bollinger(values: list[float], period: int = 20, k: float = 2.0) -> tuple[float, float, float] | None:
    if len(values) < period:
        return None

    window = values[-period:]
    mean = fmean(window)
    variance = sum((value - mean) ** 2 for value in window) / period
    std = sqrt(variance)
    upper = round(mean + (k * std), 4)
    lower = round(mean - (k * std), 4)
    return round(upper, 4), round(mean, 4), round(lower, 4)



