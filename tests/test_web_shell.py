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
            'requested_source': 'simulator',
            'active_source': 'simulator',
            'state': 'streaming',
            'interval': 'demo-5s',
            'last_error': None,
        },
    )
    return TestClient(main.app)


def test_web_shell_routes_are_served(tmp_path, monkeypatch) -> None:
    with create_client(tmp_path, monkeypatch) as client:
        index_response = client.get('/')
        manifest_response = client.get('/manifest.webmanifest')
        sw_response = client.get('/sw.js')
        icon_response = client.get('/icon.svg')

        assert index_response.status_code == 200
        assert 'Install App' in index_response.text

        assert manifest_response.status_code == 200
        assert 'Signal Flow Live' in manifest_response.text

        assert sw_response.status_code == 200
        assert 'CACHE_NAME' in sw_response.text

        assert icon_response.status_code == 200
        assert '<svg' in icon_response.text
