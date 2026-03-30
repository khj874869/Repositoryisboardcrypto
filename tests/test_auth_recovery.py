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


def _login_tokens(client: TestClient) -> dict[str, object]:
    response = client.post('/api/auth/login', json={'username': 'demo', 'password': 'demo1234'})
    assert response.status_code == 200
    return response.json()


def test_request_and_confirm_email_verification(tmp_path, monkeypatch) -> None:
    with create_client(tmp_path, monkeypatch) as client:
        tokens = _login_tokens(client)
        headers = {'Authorization': f"Bearer {tokens['access_token']}"}

        request_response = client.post('/api/auth/email-verification/request', headers=headers)
        assert request_response.status_code == 200
        payload = request_response.json()
        assert payload['preview']['token']

        confirm_response = client.post(
            '/api/auth/email-verification/confirm',
            json={'token': payload['preview']['token']},
        )
        assert confirm_response.status_code == 200
        confirmed = confirm_response.json()
        assert confirmed['email_verified'] is True
        assert confirmed['email_verified_at'] is not None


def test_password_reset_flow_rotates_password_and_revokes_sessions(tmp_path, monkeypatch) -> None:
    with create_client(tmp_path, monkeypatch) as client:
        tokens = _login_tokens(client)
        old_headers = {'Authorization': f"Bearer {tokens['access_token']}"}

        request_response = client.post('/api/auth/password-reset/request', json={'email': 'demo@signal-flow.local'})
        assert request_response.status_code == 200
        payload = request_response.json()
        assert payload['preview']['token']

        confirm_response = client.post(
            '/api/auth/password-reset/confirm',
            json={'token': payload['preview']['token'], 'new_password': 'updated-demo-1234'},
        )
        assert confirm_response.status_code == 200

        assert client.get('/api/auth/me', headers=old_headers).status_code == 401

        old_login = client.post('/api/auth/login', json={'username': 'demo', 'password': 'demo1234'})
        assert old_login.status_code == 401

        new_login = client.post('/api/auth/login', json={'username': 'demo', 'password': 'updated-demo-1234'})
        assert new_login.status_code == 200


def test_password_reset_request_is_safe_for_unknown_email(tmp_path, monkeypatch) -> None:
    with create_client(tmp_path, monkeypatch) as client:
        response = client.post('/api/auth/password-reset/request', json={'email': 'missing@example.com'})
        assert response.status_code == 200
        payload = response.json()
        assert payload['status'] == 'ok'
