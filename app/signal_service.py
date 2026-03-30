from __future__ import annotations

from . import db
from .broadcaster import Broadcaster
from .config import SIGNAL_DEDUP_SECONDS
from .strategy_engine import build_snapshot, evaluate_strategies


async def evaluate_symbol_and_broadcast(symbol: str, broadcaster: Broadcaster, *, interval_type: str) -> None:
    candles = db.fetch_recent_candles(symbol, 120, interval_type=interval_type)
    strategies = db.fetch_all('SELECT * FROM strategies WHERE is_active = 1 ORDER BY id ASC')
    if len(candles) < 20 or not strategies:
        return

    snapshot = build_snapshot(symbol, candles)
    decisions = evaluate_strategies(snapshot, strategies)
    for decision in decisions:
        inserted_signal = db.insert_signal_if_new(
            symbol=symbol,
            signal_type=decision.signal_type,
            strategy_name=decision.strategy_name,
            score=decision.score,
            reason=decision.reason,
            price=snapshot.close_price,
            dedup_seconds=SIGNAL_DEDUP_SECONDS,
        )
        if inserted_signal:
            db.create_notifications_for_signal(inserted_signal['id'], symbol)
            await broadcaster.broadcast(
                'signal',
                {
                    'id': inserted_signal['id'],
                    'symbol': symbol,
                    'signal_type': decision.signal_type,
                    'strategy_name': decision.strategy_name,
                    'score': decision.score,
                    'reason': decision.reason,
                    'price': snapshot.close_price,
                },
            )
