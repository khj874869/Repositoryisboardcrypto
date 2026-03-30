from __future__ import annotations

from app import mailer


def test_send_email_verification_uses_preview_when_smtp_is_disabled(monkeypatch) -> None:
    monkeypatch.setattr(mailer, 'AUTH_EMAIL_DELIVERY_MODE', 'preview')
    monkeypatch.setattr(mailer, 'auth_email_delivery_ready', lambda: False)

    payload = mailer.send_email_verification(
        recipient='demo@example.com',
        token='token-value',
        expires_at='2026-03-30T00:00:00+00:00',
    )

    assert payload['delivery'] == 'preview'


def test_send_password_reset_uses_smtp_when_configured(monkeypatch) -> None:
    delivered: dict[str, str] = {}

    def fake_send_email(*, recipient: str, subject: str, text_body: str, html_body: str | None = None) -> None:
        delivered['recipient'] = recipient
        delivered['subject'] = subject
        delivered['text_body'] = text_body
        delivered['html_body'] = html_body or ''

    monkeypatch.setattr(mailer, 'AUTH_EMAIL_DELIVERY_MODE', 'smtp')
    monkeypatch.setattr(mailer, 'auth_email_delivery_ready', lambda: True)
    monkeypatch.setattr(mailer, 'send_email', fake_send_email)

    payload = mailer.send_password_reset(
        recipient='demo@example.com',
        token='reset-token',
        expires_at='2026-03-30T00:00:00+00:00',
    )

    assert payload['delivery'] == 'email'
    assert delivered['recipient'] == 'demo@example.com'
    assert 'password reset' in delivered['subject'].lower()
    assert 'reset-token' in delivered['text_body']
