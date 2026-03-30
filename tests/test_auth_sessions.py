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


def test_login_returns_refresh_token_and_allows_email_identifier(tmp_path, monkeypatch) -> None:
    with create_client(tmp_path, monkeypatch) as client:
        response = client.post('/api/auth/login', json={'username': 'demo@signal-flow.local', 'password': 'demo1234'})
        assert response.status_code == 200
        payload = response.json()
        assert payload['access_token']
        assert payload['refresh_token']
        assert payload['user']['username'] == 'demo'


def test_refresh_rotates_session_and_invalidates_old_refresh_token(tmp_path, monkeypatch) -> None:
    with create_client(tmp_path, monkeypatch) as client:
        login_response = client.post(
            '/api/auth/login',
            json={'username': 'demo', 'password': 'demo1234', 'client_name': 'pytest-web'},
        )
        assert login_response.status_code == 200
        tokens = login_response.json()

        refresh_response = client.post(
            '/api/auth/refresh',
            json={'refresh_token': tokens['refresh_token'], 'client_name': 'pytest-web'},
        )
        assert refresh_response.status_code == 200
        refreshed = refresh_response.json()
        assert refreshed['refresh_token'] != tokens['refresh_token']

        stale_response = client.post('/api/auth/refresh', json={'refresh_token': tokens['refresh_token']})
        assert stale_response.status_code == 401


def test_logout_revokes_access_session_immediately(tmp_path, monkeypatch) -> None:
    with create_client(tmp_path, monkeypatch) as client:
        login_response = client.post('/api/auth/login', json={'username': 'demo', 'password': 'demo1234'})
        tokens = login_response.json()
        headers = {'Authorization': f"Bearer {tokens['access_token']}"}

        assert client.get('/api/auth/me', headers=headers).status_code == 200

        logout_response = client.post('/api/auth/logout', json={'refresh_token': tokens['refresh_token']})
        assert logout_response.status_code == 200

        assert client.get('/api/auth/me', headers=headers).status_code == 401


def test_session_listing_and_revoke_endpoint(tmp_path, monkeypatch) -> None:
    with create_client(tmp_path, monkeypatch) as client:
        tokens = client.post('/api/auth/login', json={'username': 'demo', 'password': 'demo1234'}).json()
        headers = {'Authorization': f"Bearer {tokens['access_token']}"}

        sessions_response = client.get('/api/auth/sessions', headers=headers)
        assert sessions_response.status_code == 200
        sessions = sessions_response.json()
        assert sessions
        assert any(session['is_current'] for session in sessions)

        target_session_id = sessions[0]['id']
        revoke_response = client.delete(f'/api/auth/sessions/{target_session_id}', headers=headers)
        assert revoke_response.status_code == 200

        assert client.get('/api/auth/me', headers=headers).status_code == 401
