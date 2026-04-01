from __future__ import annotations

import smtplib
from email.message import EmailMessage
from typing import Any

from .config import (
    AUTH_EMAIL_DELIVERY_MODE,
    AUTH_EMAIL_FROM_ADDRESS,
    AUTH_EMAIL_FROM_NAME,
    AUTH_SMTP_HOST,
    AUTH_SMTP_PASSWORD,
    AUTH_SMTP_PORT,
    AUTH_SMTP_USE_SSL,
    AUTH_SMTP_USE_STARTTLS,
    AUTH_SMTP_USERNAME,
    PUBLIC_API_BASE_URL,
    PUBLIC_WEB_BASE_URL,
    auth_email_delivery_ready,
)


def _from_header() -> str:
    if AUTH_EMAIL_FROM_NAME:
        return f'{AUTH_EMAIL_FROM_NAME} <{AUTH_EMAIL_FROM_ADDRESS}>'
    return AUTH_EMAIL_FROM_ADDRESS


def _open_smtp_client():
    if AUTH_SMTP_USE_SSL:
        return smtplib.SMTP_SSL(AUTH_SMTP_HOST, AUTH_SMTP_PORT, timeout=20)
    client = smtplib.SMTP(AUTH_SMTP_HOST, AUTH_SMTP_PORT, timeout=20)
    if AUTH_SMTP_USE_STARTTLS:
        client.ehlo()
        client.starttls()
        client.ehlo()
    return client


def send_email(*, recipient: str, subject: str, text_body: str, html_body: str | None = None) -> None:
    if AUTH_EMAIL_DELIVERY_MODE != 'smtp':
        raise RuntimeError('SMTP delivery is not enabled')
    if not auth_email_delivery_ready():
        raise RuntimeError('SMTP settings are incomplete')

    message = EmailMessage()
    message['Subject'] = subject
    message['From'] = _from_header()
    message['To'] = recipient
    message.set_content(text_body)
    if html_body:
        message.add_alternative(html_body, subtype='html')

    with _open_smtp_client() as client:
        if AUTH_SMTP_USERNAME:
            client.login(AUTH_SMTP_USERNAME, AUTH_SMTP_PASSWORD)
        client.send_message(message)

def _public_url(path: str) -> str:
    base = PUBLIC_WEB_BASE_URL or PUBLIC_API_BASE_URL
    if base:
        return f'{base.rstrip("/")}{path}'
    return path


def _email_template(title: str, intro: str, primary_value: str, expires_at: str, action_path: str) -> tuple[str, str]:
    action_url = _public_url(action_path)
    text_body = (
        f'{title}\n\n'
        f'{intro}\n\n'
        f'Token: {primary_value}\n'
        f'Expires At: {expires_at}\n'
        f'Action URL: {action_url}\n'
    )
    html_body = (
        '<html><body style="font-family:Segoe UI,sans-serif;color:#102033;">'
        f'<h2>{title}</h2>'
        f'<p>{intro}</p>'
        f'<p><strong>Token:</strong> <code>{primary_value}</code></p>'
        f'<p><strong>Expires At:</strong> {expires_at}</p>'
        f'<p><strong>Action URL:</strong> <a href="{action_url}">{action_url}</a></p>'
        '</body></html>'
    )
    return text_body, html_body


def send_email_verification(*, recipient: str, token: str, expires_at: str) -> dict[str, Any]:
    if AUTH_EMAIL_DELIVERY_MODE != 'smtp' or not auth_email_delivery_ready():
        return {'delivery': 'preview'}
    text_body, html_body = _email_template(
        'Verify Your Signal Flow Email',
        'Use the token below to confirm your email address.',
        token,
        expires_at,
        '/api/auth/email-verification/confirm',
    )
    send_email(
        recipient=recipient,
        subject='Signal Flow email verification',
        text_body=text_body,
        html_body=html_body,
    )
    return {'delivery': 'email'}


def send_password_reset(*, recipient: str, token: str, expires_at: str) -> dict[str, Any]:
    if AUTH_EMAIL_DELIVERY_MODE != 'smtp' or not auth_email_delivery_ready():
        return {'delivery': 'preview'}
    text_body, html_body = _email_template(
        'Reset Your Signal Flow Password',
        'Use the token below to complete your password reset.',
        token,
        expires_at,
        '/api/auth/password-reset/confirm',
    )
    send_email(
        recipient=recipient,
        subject='Signal Flow password reset',
        text_body=text_body,
        html_body=html_body,
    )
    return {'delivery': 'email'}
