from __future__ import annotations

from fastapi.testclient import TestClient

from app import db, main


def create_client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setattr(db, 'DB_PATH', tmp_path / 'signal_flow_test.db')

    async def start_stub() -> None:
        return None

    async def stop_stub() -> None:
        return None

    monkeypatch.setattr(main, 'enforce_runtime_requirements', lambda: None)
    monkeypatch.setattr(main.runtime, 'start', start_stub)
    monkeypatch.setattr(main.runtime, 'stop', stop_stub)
    monkeypatch.setattr(main, 'runtime_config_issues', lambda: [])
    return TestClient(main.app)


def test_release_status_reports_https_and_android_readiness(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(main, 'PUBLIC_WEB_BASE_URL', 'https://signals.example.com')
    monkeypatch.setattr(main, 'PUBLIC_API_BASE_URL', 'https://signals.example.com')
    monkeypatch.setattr(main, 'PUBLIC_WS_BASE_URL', 'wss://signals.example.com/ws/stream')
    monkeypatch.setattr(main, 'ANDROID_PACKAGE_NAME', 'com.signalflow.live')
    monkeypatch.setattr(main, 'ANDROID_SHA256_CERT_FINGERPRINTS', ['AA:BB:CC'])

    with create_client(tmp_path, monkeypatch) as client:
        response = client.get('/api/release-status')
        assert response.status_code == 200
        payload = response.json()
        assert payload['ready_for_hosted_pwa'] is True
        assert payload['ready_for_android_packaging'] is True
        assert payload['android']['assetlinks_ready'] is True


def test_assetlinks_route_returns_configured_statement(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(main, 'ANDROID_PACKAGE_NAME', 'com.signalflow.live')
    monkeypatch.setattr(main, 'ANDROID_SHA256_CERT_FINGERPRINTS', ['AA:BB:CC'])

    with create_client(tmp_path, monkeypatch) as client:
        response = client.get('/.well-known/assetlinks.json')
        assert response.status_code == 200
        payload = response.json()
        assert payload[0]['target']['package_name'] == 'com.signalflow.live'
        assert payload[0]['target']['sha256_cert_fingerprints'] == ['AA:BB:CC']
