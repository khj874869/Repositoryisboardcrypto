from __future__ import annotations

from fastapi.testclient import TestClient

from app import db, main


def create_client(tmp_path, monkeypatch, *, runtime_status=None, config_issues=None) -> TestClient:
    monkeypatch.setattr(db, 'DB_PATH', tmp_path / 'signal_flow_test.db')

    async def start_stub() -> None:
        return None

    async def stop_stub() -> None:
        return None

    monkeypatch.setattr(main, 'enforce_runtime_requirements', lambda: None)
    monkeypatch.setattr(main.runtime, 'start', start_stub)
    monkeypatch.setattr(main.runtime, 'stop', stop_stub)
    monkeypatch.setattr(
        main.runtime,
        'status',
        runtime_status
        or (
            lambda: {
                'requested_source': 'upbit',
                'active_source': 'upbit',
                'state': 'streaming',
                'interval': '1s',
                'last_error': None,
            }
        ),
    )
    monkeypatch.setattr(main, 'runtime_config_issues', lambda: config_issues or [])
    return TestClient(main.app)


def test_readiness_reports_ready_state(tmp_path, monkeypatch) -> None:
    with create_client(tmp_path, monkeypatch) as client:
        response = client.get('/api/readiness')
        assert response.status_code == 200
        payload = response.json()
        assert payload['status'] == 'ready'
        assert payload['environment']
        assert payload['issues'] == []


def test_readiness_reports_config_issues(tmp_path, monkeypatch) -> None:
    with create_client(tmp_path, monkeypatch, config_issues=['SIGNAL_FLOW_SECRET_KEY must be changed for production']) as client:
        response = client.get('/api/readiness')
        assert response.status_code == 200
        payload = response.json()
        assert payload['status'] == 'not_ready'
        assert payload['issues']


def test_init_db_skips_demo_seed_when_disabled(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(db, 'DB_PATH', tmp_path / 'signal_flow_test.db')
    monkeypatch.setattr(db, 'ENABLE_DEMO_SEED', False)
    db.init_db()
    assert db.get_user_by_username(db.DEMO_USER) is None
