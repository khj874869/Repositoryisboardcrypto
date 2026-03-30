from __future__ import annotations

from app import db


def test_fetch_recent_candles_returns_latest_rows_in_ascending_order(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(db, 'DB_PATH', tmp_path / 'signal_flow_test.db')
    db.init_db()
    for idx in range(5):
        db.upsert_candle(
            symbol='KRW-BTC',
            candle_time=f'2026-03-27T00:00:0{idx}+00:00',
            interval_type='upbit-1s',
            open_price=1 + idx,
            high_price=1 + idx,
            low_price=1 + idx,
            close_price=1 + idx,
            volume=1 + idx,
        )
    rows = db.fetch_recent_candles('KRW-BTC', limit=3, interval_type='upbit-1s')
    assert [row['candle_time'] for row in rows] == [
        '2026-03-27T00:00:02+00:00',
        '2026-03-27T00:00:03+00:00',
        '2026-03-27T00:00:04+00:00',
    ]
