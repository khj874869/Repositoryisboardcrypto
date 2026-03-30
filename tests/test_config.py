from __future__ import annotations

from app import config


def test_runtime_config_issues_flags_insecure_production(monkeypatch) -> None:
    monkeypatch.setattr(config, 'IS_PRODUCTION', True)
    monkeypatch.setattr(config, 'SECRET_KEY', config.DEFAULT_SECRET_KEY)
    monkeypatch.setattr(config, 'ENABLE_DEMO_SEED', True)
    monkeypatch.setattr(config, 'CORS_ORIGINS', [])
    monkeypatch.setattr(config, 'PUBLIC_API_BASE_URL', 'https://api.example.com')
    monkeypatch.setattr(config, 'PUBLIC_WS_BASE_URL', '')
    issues = config.runtime_config_issues()
    assert 'SIGNAL_FLOW_SECRET_KEY must be changed for production' in issues
    assert 'SIGNAL_FLOW_ENABLE_DEMO_SEED must be disabled for production' in issues
    assert 'SIGNAL_FLOW_CORS_ORIGINS should be configured for production' in issues
    assert 'SIGNAL_FLOW_PUBLIC_WS_BASE_URL should be set when SIGNAL_FLOW_PUBLIC_API_BASE_URL is set' in issues
