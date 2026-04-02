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


def seed_legacy_asset() -> None:
    db.upsert_asset(
        symbol='BTC-KRW',
        name='Bitcoin',
        market_type='COIN',
        last_price=145_690_280.6063,
        change_rate=0.4761,
        updated_at='2026-03-27T06:31:22.225852+00:00',
    )


def seed_signal_row(
    *,
    symbol: str,
    signal_type: str,
    strategy_name: str,
    score: float,
    reason: str,
    price: float,
    created_at: str,
    notification_delivery: str,
    notification_delivery_reason: str | None = None,
    notification_count: int = 0,
) -> None:
    inserted = db.insert_signal_if_new(
        symbol=symbol,
        signal_type=signal_type,
        strategy_name=strategy_name,
        score=score,
        reason=reason,
        price=price,
        dedup_seconds=0,
    )
    assert inserted is not None
    db.execute(
        '''
        UPDATE signals
        SET created_at = ?, notification_delivery = ?, notification_delivery_reason = ?, notification_count = ?
        WHERE id = ?
        ''',
        (
            created_at,
            notification_delivery,
            notification_delivery_reason,
            notification_count,
            inserted['id'],
        ),
    )


def test_client_bootstrap_exposes_shared_contract(tmp_path, monkeypatch) -> None:
    with create_client(tmp_path, monkeypatch) as client:
        seed_legacy_asset()
        response = client.get('/api/client/bootstrap')
        assert response.status_code == 200
        payload = response.json()
        assert payload['app']['version'] == '0.4.0'
        assert payload['session']['authenticated'] is False
        assert payload['features']['web'] is True
        assert payload['features']['app'] is True
        assert payload['endpoints']['dashboard'] == '/api/client/dashboard'
        assert payload['endpoints']['refresh'] == '/api/auth/refresh'
        assert payload['endpoints']['request_password_reset'] == '/api/auth/password-reset/request'
        assert payload['endpoints']['verify_email'] == '/api/auth/email-verification/confirm'
        assert payload['endpoints']['instrument_search'] == '/api/instruments/search'
        assert payload['endpoints']['signal_profile'] == '/api/signal-profiles/{symbol}'
        assert payload['catalog']['assets']
        assert all(row['symbol'] != 'BTC-KRW' for row in payload['catalog']['assets'])
        assert payload['catalog']['supported_intervals'][0] == '10m'


def test_client_dashboard_aggregates_user_state(tmp_path, monkeypatch) -> None:
    with create_client(tmp_path, monkeypatch) as client:
        seed_market_data()
        seed_legacy_asset()
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
        assert payload['signals'][0]['notification_delivery'] in {'pending', 'notified', 'suppressed', 'no_subscribers'}
        btc_row = next(row for row in payload['overview'] if row['symbol'] == 'KRW-BTC')
        assert btc_row['profile_signal_type'] in {None, 'BUY', 'SELL'}
        assert any(row['symbol'] == 'AAPL' for row in payload['watchlist'])
        assert any(row['symbol'] == 'AAPL' for row in payload['overview'])
        assert all(row['symbol'] != 'BTC-KRW' for row in payload['overview'])


def test_signal_feed_prioritizes_notified_over_suppressed(tmp_path, monkeypatch) -> None:
    with create_client(tmp_path, monkeypatch) as client:
        seed_signal_row(
            symbol='AAPL',
            signal_type='BUY',
            strategy_name='Scanner Buy',
            score=91.0,
            reason='Suppressed scanner signal',
            price=210.0,
            created_at='2026-04-02T01:00:00+00:00',
            notification_delivery='suppressed',
            notification_delivery_reason='scanner_delayed_blocked',
        )
        seed_signal_row(
            symbol='KRW-BTC',
            signal_type='BUY',
            strategy_name='Live Buy',
            score=80.0,
            reason='Live notified signal',
            price=124.0,
            created_at='2026-04-02T00:59:00+00:00',
            notification_delivery='notified',
            notification_count=1,
        )

        dashboard = client.get('/api/client/dashboard', headers=login_headers(client))
        assert dashboard.status_code == 200
        dashboard_payload = dashboard.json()
        assert dashboard_payload['signals'][0]['symbol'] == 'KRW-BTC'
        assert dashboard_payload['signals'][0]['notification_delivery'] == 'notified'
        assert any(row['symbol'] == 'AAPL' and row['notification_delivery'] == 'suppressed' for row in dashboard_payload['signals'])

        recent = client.get('/api/signals/recent?limit=2')
        assert recent.status_code == 200
        recent_payload = recent.json()
        assert recent_payload[0]['symbol'] == 'KRW-BTC'
        assert recent_payload[0]['notification_delivery'] == 'notified'
        assert recent_payload[1]['symbol'] == 'AAPL'


def test_signal_feed_filters_by_delivery_and_mode(tmp_path, monkeypatch) -> None:
    with create_client(tmp_path, monkeypatch) as client:
        seed_signal_row(
            symbol='AAPL',
            signal_type='BUY',
            strategy_name='Scanner Buy',
            score=91.0,
            reason='Suppressed scanner signal',
            price=210.0,
            created_at='2026-04-02T01:00:00+00:00',
            notification_delivery='suppressed',
            notification_delivery_reason='scanner_delayed_blocked',
        )
        seed_signal_row(
            symbol='MSFT',
            signal_type='SELL',
            strategy_name='Scanner Watch',
            score=73.0,
            reason='Scanner signal without audit block',
            price=315.0,
            created_at='2026-04-02T00:58:00+00:00',
            notification_delivery='no_subscribers',
        )
        seed_signal_row(
            symbol='KRW-BTC',
            signal_type='BUY',
            strategy_name='Live Buy',
            score=80.0,
            reason='Live notified signal',
            price=124.0,
            created_at='2026-04-02T00:59:00+00:00',
            notification_delivery='notified',
            notification_count=1,
        )

        dashboard = client.get('/api/client/dashboard?signal_delivery=notified&include_suppressed=false')
        assert dashboard.status_code == 200
        dashboard_payload = dashboard.json()
        assert len(dashboard_payload['signals']) == 1
        assert dashboard_payload['signals'][0]['symbol'] == 'KRW-BTC'
        assert dashboard_payload['signals'][0]['notification_delivery'] == 'notified'

        recent = client.get('/api/signals/recent?signal_data_mode=scanner')
        assert recent.status_code == 200
        recent_payload = recent.json()
        assert len(recent_payload) == 2
        assert {row['symbol'] for row in recent_payload} == {'AAPL', 'MSFT'}

        audit_recent = client.get('/api/signals/recent?signal_data_mode=scanner&signal_audit_only=true')
        assert audit_recent.status_code == 200
        audit_recent_payload = audit_recent.json()
        assert len(audit_recent_payload) == 1
        assert audit_recent_payload[0]['symbol'] == 'AAPL'
        assert audit_recent_payload[0]['notification_delivery'] == 'suppressed'

        audit_dashboard = client.get('/api/client/dashboard?signal_audit_only=true')
        assert audit_dashboard.status_code == 200
        audit_dashboard_payload = audit_dashboard.json()
        assert len(audit_dashboard_payload['signals']) == 1
        assert audit_dashboard_payload['signals'][0]['symbol'] == 'AAPL'


def test_client_asset_detail_returns_snapshot_and_recent_rows(tmp_path, monkeypatch) -> None:
    with create_client(tmp_path, monkeypatch) as client:
        seed_market_data()
        response = client.get('/api/client/assets/KRW-BTC')
        assert response.status_code == 200
        payload = response.json()
        assert payload['asset']['symbol'] == 'KRW-BTC'
        assert payload['instrument']['symbol'] == 'KRW-BTC'
        assert payload['instrument']['runtime']['data_mode'] == 'realtime'
        assert payload['interval_type'] == 'upbit-1s'
        assert payload['requested_interval_type'] is None
        assert payload['interval_fallback_applied'] is False
        assert payload['candles']
        assert payload['signals']
        assert payload['snapshot']['rsi14'] is not None
        assert payload['user_signal_profile'] is None


def test_client_asset_detail_falls_back_to_active_interval_when_requested_interval_is_stale(tmp_path, monkeypatch) -> None:
    with create_client(tmp_path, monkeypatch) as client:
        seed_market_data()
        db.upsert_candle(
            symbol='KRW-BTC',
            candle_time='2026-03-30T00:10:00+00:00',
            interval_type='demo-5s',
            open_price=90.0,
            high_price=91.0,
            low_price=89.0,
            close_price=90.5,
            volume=3.0,
        )
        response = client.get('/api/client/assets/KRW-BTC?interval_type=demo-5s')
        assert response.status_code == 200
        payload = response.json()
        assert payload['requested_interval_type'] == 'demo-5s'
        assert payload['interval_type'] == 'upbit-1s'
        assert payload['interval_fallback_applied'] is True
        assert payload['candles']
        assert all(row['interval_type'] == 'upbit-1s' for row in payload['candles'])


def test_client_asset_detail_uses_scanner_interval_for_watch_only_instrument(tmp_path, monkeypatch) -> None:
    with create_client(tmp_path, monkeypatch) as client:
        headers = login_headers(client)
        response = client.get('/api/client/assets/AAPL', headers=headers)
        assert response.status_code == 200
        payload = response.json()
        assert payload['asset']['symbol'] == 'AAPL'
        assert payload['instrument']['symbol'] == 'AAPL'
        assert payload['instrument']['capabilities']['has_realtime_feed'] is False
        assert payload['instrument']['capabilities']['has_volume_feed'] is True
        assert payload['instrument']['runtime']['data_mode'] == 'scanner'
        assert payload['instrument']['runtime']['data_source'] == 'synthetic'
        assert payload['interval_type'] == 'scanner-1d'
        assert payload['requested_interval_type'] is None
        assert payload['interval_fallback_applied'] is False
        assert len(payload['candles']) >= 20
        assert all(row['interval_type'] == 'scanner-1d' for row in payload['candles'])
        assert payload['snapshot']['rsi14'] is not None
        assert payload['user_signal_profile']['symbol'] == 'AAPL'
        assert payload['profile_evaluation']['status'] in {'BUY', 'SELL', 'WATCH'}


def test_raw_candles_endpoint_falls_back_to_active_interval_when_requested_interval_has_no_rows(tmp_path, monkeypatch) -> None:
    with create_client(tmp_path, monkeypatch) as client:
        seed_market_data()
        response = client.get('/api/assets/KRW-BTC/candles?interval_type=upbit-1m&limit=5')
        assert response.status_code == 200
        payload = response.json()
        assert len(payload) == 5
        assert all(row['interval_type'] == 'upbit-1s' for row in payload)


def test_raw_candles_endpoint_uses_scanner_interval_for_watch_only_symbol(tmp_path, monkeypatch) -> None:
    with create_client(tmp_path, monkeypatch) as client:
        response = client.get('/api/assets/AAPL/candles?limit=5')
        assert response.status_code == 200
        payload = response.json()
        assert len(payload) == 5
        assert all(row['interval_type'] == 'scanner-1d' for row in payload)


def test_instrument_search_includes_coins_and_stocks(tmp_path, monkeypatch) -> None:
    with create_client(tmp_path, monkeypatch) as client:
        response = client.get('/api/instruments/search?q=apple')
        assert response.status_code == 200
        payload = response.json()
        apple = next(row for row in payload if row['symbol'] == 'AAPL')
        assert apple['runtime']['data_mode'] == 'scanner'
        assert apple['runtime']['data_source'] == 'synthetic'

        response = client.get('/api/instruments/search?q=btc')
        assert response.status_code == 200
        payload = response.json()
        btc = next(row for row in payload if row['symbol'] == 'KRW-BTC')
        assert btc['runtime']['data_mode'] == 'realtime'


def test_signal_profile_crud_and_asset_detail_profile_evaluation(tmp_path, monkeypatch) -> None:
    with create_client(tmp_path, monkeypatch) as client:
        seed_market_data()
        headers = login_headers(client)

        get_response = client.get('/api/signal-profiles/KRW-BTC', headers=headers)
        assert get_response.status_code == 200
        profile = get_response.json()
        assert profile['symbol'] == 'KRW-BTC'
        assert profile['is_enabled'] is True

        patch_response = client.patch(
            '/api/signal-profiles/KRW-BTC',
            json={
                'rsi_buy_threshold': 45,
                'score_threshold': 55,
                'use_orderbook_pressure': True,
            },
            headers=headers,
        )
        assert patch_response.status_code == 200
        updated = patch_response.json()
        assert updated['rsi_buy_threshold'] == 45
        assert updated['score_threshold'] == 55
        assert updated['use_orderbook_pressure'] is True

        detail_response = client.get('/api/client/assets/KRW-BTC', headers=headers)
        assert detail_response.status_code == 200
        detail = detail_response.json()
        assert detail['user_signal_profile']['symbol'] == 'KRW-BTC'
        assert detail['profile_evaluation']['status'] in {'BUY', 'WATCH', 'UNAVAILABLE'}
