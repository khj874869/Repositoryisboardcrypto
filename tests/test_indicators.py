from app.indicators import bollinger, rsi, sma


def test_sma_calculates_average():
    assert sma([1, 2, 3, 4, 5], 5) == 3.0


def test_rsi_returns_high_value_for_uptrend():
    closes = list(range(1, 20))
    assert rsi(closes, 14) > 80


def test_bollinger_returns_upper_middle_lower():
    upper, middle, lower = bollinger([10] * 20, 20)
    assert upper == 10.0
    assert middle == 10.0
    assert lower == 10.0
