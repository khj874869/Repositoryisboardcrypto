from app.strategy_engine import build_snapshot, evaluate_strategies


def make_candles(closes):
    return [
        {
            'close_price': close,
            'volume': 1000 if idx == len(closes) - 1 else 100,
        }
        for idx, close in enumerate(closes)
    ]


def test_score_combo_buy_signal_when_conditions_stack():
    closes = [100] * 18 + [90, 80, 79, 78, 77]
    candles = make_candles(closes)
    snapshot = build_snapshot('BTC-KRW', candles)
    strategies = [
        {
            'name': 'Score Combo',
            'rule_type': 'score_combo',
            'is_active': 1,
            'rsi_buy_threshold': 50,
            'volume_multiplier': 1.1,
            'score_threshold': 45,
        }
    ]
    decisions = evaluate_strategies(snapshot, strategies)
    assert decisions
    assert decisions[0].signal_type == 'BUY'
