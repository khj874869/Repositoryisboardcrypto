from __future__ import annotations

from fastapi.testclient import TestClient

from app import db, main


def create_client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setattr(db, 'DB_PATH', tmp_path / 'signal_flow_test.db')

    async def start_stub() -> None:
        return None

    async def stop_stub() -> None:
        return None

    monkeypatch.setattr(main.runtime, 'start', start_stub)
    monkeypatch.setattr(main.runtime, 'stop', stop_stub)
    monkeypatch.setattr(
        main.runtime,
        'status',
        lambda: {
            'requested_source': 'upbit',
            'active_source': 'upbit',
            'state': 'streaming',
            'interval': '1s',
            'last_error': None,
        },
    )
    return TestClient(main.app)


def login_headers(client: TestClient) -> dict[str, str]:
    response = client.post('/api/auth/login', json={'username': 'demo', 'password': 'demo1234'})
    assert response.status_code == 200
    token = response.json()['access_token']
    return {'Authorization': f'Bearer {token}'}


def seed_market_data() -> None:
    for idx, price in enumerate((100.0, 102.0, 103.0, 105.0, 108.0, 107.0, 109.0, 110.0, 111.0, 113.0, 112.0, 114.0, 116.0, 118.0, 117.0, 119.0, 121.0, 123.0, 122.0, 124.0)):
        db.upsert_candle(
            symbol='KRW-BTC',
            candle_time=f'2026-03-30T00:00:{idx:02d}+00:00',
            interval_type='upbit-1s',
            open_price=price - 1,
            high_price=price + 1,
            low_price=price - 2,
            close_price=price,
            volume=10 + idx,
        )
    db.update_asset_price('KRW-BTC', last_price=124.0, change_rate=2.5, updated_at='2026-03-30T00:01:00+00:00')
    inserted = db.insert_signal_if_new(
        symbol='KRW-BTC',
        signal_type='BUY',
        strategy_name='Score Combo',
        score=82.0,
        reason='Stacked momentum conditions',
        price=124.0,
        dedup_seconds=1,
    )
    assert inserted is not None
    db.create_notifications_for_signal(inserted['id'], 'KRW-BTC')


def test_client_bootstrap_exposes_shared_contract(tmp_path, monkeypatch) -> None:
    with create_client(tmp_path, monkeypatch) as client:
        response = client.get('/api/client/bootstrap')
        assert response.status_code == 200
        payload = response.json()
        assert payload['app']['version'] == '0.4.0'
        assert payload['session']['authenticated'] is False
        assert payload['features']['web'] is True
        assert payload['features']['app'] is True
        assert payload['endpoints']['dashboard'] == '/api/client/dashboard'
        assert payload['catalog']['assets']
        assert payload['catalog']['supported_intervals'][0] == '10m'


def test_client_dashboard_aggregates_user_state(tmp_path, monkeypatch) -> None:
    with create_client(tmp_path, monkeypatch) as client:
        seed_market_data()
        headers = login_headers(client)
        response = client.get('/api/client/dashboard', headers=headers)
        assert response.status_code == 200
        payload = response.json()
        assert payload['session']['authenticated'] is True
        assert payload['watchlist']
        assert payload['notifications']
        assert payload['notification_settings']['web_enabled'] is True
        assert payload['counts']['unread_notifications'] >= 1
        assert payload['signals'][0]['symbol'] == 'KRW-BTC'
        assert any(row['symbol'] == 'KRW-BTC' for row in payload['overview'])


def test_client_asset_detail_returns_snapshot_and_recent_rows(tmp_path, monkeypatch) -> None:
    with create_client(tmp_path, monkeypatch) as client:
        seed_market_data()
        response = client.get('/api/client/assets/KRW-BTC')
        assert response.status_code == 200
        payload = response.json()
        assert payload['asset']['symbol'] == 'KRW-BTC'
        assert payload['interval_type'] == 'upbit-1s'
        assert payload['candles']
        assert payload['signals']
        assert payload['snapshot']['rsi14'] is not None
