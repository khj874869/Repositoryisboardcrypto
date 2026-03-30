from __future__ import annotations

from app.release_values import build_env_values, derive_android_package_name, normalize_domain


def test_normalize_domain_strips_scheme_and_path() -> None:
    assert normalize_domain('https://Signals.Example.com/app/') == 'signals.example.com'


def test_derive_android_package_name_reverses_domain() -> None:
    assert derive_android_package_name('signals.example.com') == 'com.example.signals.signalflow'


def test_build_env_values_renders_expected_urls() -> None:
    values = build_env_values(
        'signals.example.com',
        'postgresql+psycopg://user:pass@db:5432/signal_flow',
        secret_key='secret',
        android_sha256_cert_fingerprints='AA:BB',
    )

    assert values.domain == 'signals.example.com'
    assert values.android_package_name == 'com.example.signals.signalflow'
    rendered = values.render()
    assert 'SIGNAL_FLOW_PUBLIC_WEB_BASE_URL=https://signals.example.com' in rendered
    assert 'SIGNAL_FLOW_PUBLIC_WS_BASE_URL=wss://signals.example.com/ws/stream' in rendered
    assert 'SIGNAL_FLOW_ANDROID_SHA256_CERT_FINGERPRINTS=AA:BB' in rendered
