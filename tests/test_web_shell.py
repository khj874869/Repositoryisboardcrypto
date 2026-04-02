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
        assetlinks_response = client.get('/.well-known/assetlinks.json')

        assert index_response.status_code == 200
        assert 'Install App' in index_response.text
        assert 'Secure Context' in index_response.text
        assert 'signal-filter-delivery' in index_response.text
        assert 'signal-filter-audit-only' in index_response.text
        assert 'signal-filter-presets' in index_response.text
        assert 'signal-filter-label' in index_response.text
        assert 'hero-feed-preset' in index_response.text
        assert 'detail-audit-warning' in index_response.text
        assert 'Scanner audit active.' in index_response.text
        assert 'scanner audit' in index_response.text
        assert 'audit review' in index_response.text
        assert 'Audit state' in index_response.text
        assert 'detailSignalDeliverySummary' in index_response.text
        assert 'post-market' in index_response.text
        assert 'closed-session' in index_response.text
        assert 'review before action' in index_response.text
        assert 'Review-only scanner context' in index_response.text
        assert 'Saved review rule for' in index_response.text
        assert 'review-only' in index_response.text
        assert 'Save Review Rule' in index_response.text
        assert 'Aggressive for review-only mode' in index_response.text
        assert 'audit watch' in index_response.text
        assert 'Added audit watch for' in index_response.text
        assert 'Open Audit Candidate' in index_response.text
        assert 'Top audit candidate is' in index_response.text
        assert 'No audit candidates in the current tape.' in index_response.text
        assert 'Custom Tape' in index_response.text
        assert 'data-tone="operator"' in index_response.text
        assert 'SIGNAL_FILTER_PRESET_TONES' in index_response.text
        assert 'signal_preset' in index_response.text
        assert 'signal_audit_only' in index_response.text
        assert 'history.replaceState' in index_response.text
        assert "window.addEventListener('popstate'" in index_response.text

        assert manifest_response.status_code == 200
        assert 'Signal Flow Live' in manifest_response.text

        assert sw_response.status_code == 200
        assert 'CACHE_NAME' in sw_response.text

        assert icon_response.status_code == 200
        assert '<svg' in icon_response.text

        assert assetlinks_response.status_code == 200
