from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from datetime import datetime, timedelta
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import db, mailer
from .config import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    AUTH_TOKEN_PREVIEW_ENABLED,
    EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS,
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS,
    SECRET_KEY,
)

security = HTTPBearer(auto_error=False)


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b'=').decode('utf-8')


def _b64url_decode(value: str) -> bytes:
    padding = '=' * ((4 - len(value) % 4) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _unix_time() -> int:
    return int(time.time())


def hash_password(password: str, *, iterations: int = 200_000) -> str:
    salt = secrets.token_hex(16)
    derived = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), iterations)
    return f'pbkdf2_sha256${iterations}${salt}${derived.hex()}'


def verify_password(password: str, password_hash: str) -> bool:
    try:
        scheme, iterations_raw, salt, expected = password_hash.split('$', 3)
    except ValueError:
        return False
    if scheme != 'pbkdf2_sha256':
        return False
    iterations = int(iterations_raw)
    candidate = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), iterations)
    return hmac.compare_digest(candidate.hex(), expected)


def create_access_token(
    username: str,
    *,
    session_id: int | None = None,
    expires_minutes: int = ACCESS_TOKEN_EXPIRE_MINUTES,
) -> str:
    header = {'alg': 'HS256', 'typ': 'JWT'}
    payload = {
        'sub': username,
        'sid': session_id,
        'token_type': 'access',
        'iat': _unix_time(),
        'exp': int(_unix_time() + expires_minutes * 60),
    }
    encoded_header = _b64url_encode(json.dumps(header, separators=(',', ':'), sort_keys=True).encode('utf-8'))
    encoded_payload = _b64url_encode(json.dumps(payload, separators=(',', ':'), sort_keys=True).encode('utf-8'))
    signing_input = f'{encoded_header}.{encoded_payload}'.encode('utf-8')
    signature = hmac.new(SECRET_KEY.encode('utf-8'), signing_input, hashlib.sha256).digest()
    return f'{encoded_header}.{encoded_payload}.{_b64url_encode(signature)}'


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        encoded_header, encoded_payload, encoded_signature = token.split('.')
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid token') from exc

    signing_input = f'{encoded_header}.{encoded_payload}'.encode('utf-8')
    expected_signature = hmac.new(SECRET_KEY.encode('utf-8'), signing_input, hashlib.sha256).digest()
    actual_signature = _b64url_decode(encoded_signature)
    if not hmac.compare_digest(expected_signature, actual_signature):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid token signature')

    payload = json.loads(_b64url_decode(encoded_payload).decode('utf-8'))
    if payload.get('exp', 0) < _unix_time():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Token expired')
    if payload.get('token_type') not in {None, 'access'}:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid token type')
    if not payload.get('sub'):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid token payload')
    return payload


def create_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def create_action_token() -> str:
    return secrets.token_urlsafe(32)


def _public_user(user: dict[str, Any]) -> dict[str, Any]:
    return {
        'id': user['id'],
        'username': user['username'],
        'email': user['email'],
        'email_verified': bool(user.get('email_verified_at')),
        'email_verified_at': user.get('email_verified_at'),
        'created_at': user['created_at'],
    }


def _request_client_meta(request: Request, client_name: str | None = None) -> dict[str, str | None]:
    return {
        'client_name': client_name,
        'user_agent': request.headers.get('user-agent'),
        'ip_address': request.client.host if request.client else None,
    }


def _is_session_active(session: dict[str, Any]) -> bool:
    if session.get('revoked_at'):
        return False
    expires_at = session.get('expires_at')
    if not expires_at:
        return False
    return db.utc_now() < time_from_iso(expires_at)


def time_from_iso(value: str):
    return datetime.fromisoformat(value)


def _require_active_session(payload: dict[str, Any], expected_user_name: str | None = None) -> dict[str, Any] | None:
    session_id = payload.get('sid')
    if session_id is None:
        return None
    session = db.get_refresh_session_by_id(int(session_id))
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Session not found')
    if expected_user_name and session['user_name'] != expected_user_name:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Session mismatch')
    if not _is_session_active(session):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Session expired or revoked')
    return session


def build_auth_response(user: dict[str, Any], request: Request, *, client_name: str | None = None) -> dict[str, Any]:
    refresh_token = create_refresh_token()
    expires_at = db.isoformat(db.utc_now() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS))
    session = db.create_refresh_session(
        user_name=user['username'],
        token_hash=hash_refresh_token(refresh_token),
        expires_at=expires_at,
        **_request_client_meta(request, client_name),
    )
    access_token = create_access_token(user['username'], session_id=session['id'])
    return {
        'access_token': access_token,
        'refresh_token': refresh_token,
        'token_type': 'bearer',
        'expires_in': ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        'refresh_expires_at': session['expires_at'],
        'user': _public_user(user),
    }


def refresh_auth_response(refresh_token: str, request: Request, *, client_name: str | None = None) -> dict[str, Any]:
    session = db.get_refresh_session_by_token_hash(hash_refresh_token(refresh_token))
    if not session or not _is_session_active(session):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid refresh token')

    user = db.get_user_by_username(session['user_name'])
    if not user:
        db.revoke_refresh_session(session['id'])
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='User not found')

    db.touch_refresh_session(session['id'])
    db.revoke_refresh_session(session['id'])
    return build_auth_response(user, request, client_name=client_name or session.get('client_name'))


def revoke_refresh_token(refresh_token: str) -> None:
    session = db.get_refresh_session_by_token_hash(hash_refresh_token(refresh_token))
    if session:
        db.revoke_refresh_session(session['id'])


def _token_preview_payload(token: str) -> dict[str, str] | None:
    if not AUTH_TOKEN_PREVIEW_ENABLED:
        return None
    return {'token': token}


def create_email_verification(user: dict[str, Any]) -> dict[str, Any]:
    token = create_action_token()
    db.revoke_auth_action_tokens(user['username'], 'email_verification')
    record = db.create_auth_action_token(
        user_name=user['username'],
        token_hash=hash_refresh_token(token),
        token_type='email_verification',
        email=user['email'],
        expires_at=db.isoformat(db.utc_now() + timedelta(hours=EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS)),
    )
    delivery = mailer.send_email_verification(
        recipient=user['email'],
        token=token,
        expires_at=record['expires_at'],
    )
    return {
        'status': 'ok',
        'expires_at': record['expires_at'],
        'delivery': delivery['delivery'] if delivery['delivery'] != 'preview' or AUTH_TOKEN_PREVIEW_ENABLED else 'accepted',
        'preview': _token_preview_payload(token) if delivery['delivery'] == 'preview' else None,
    }


def verify_email_token(token: str) -> dict[str, Any]:
    record = db.get_auth_action_token(hash_refresh_token(token), 'email_verification')
    if not record or record.get('consumed_at') or time_from_iso(record['expires_at']) <= db.utc_now():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid or expired verification token')

    user = db.mark_user_email_verified(record['user_name'])
    db.consume_auth_action_token(record['id'])
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found')
    return _public_user(user)


def create_password_reset(email: str) -> dict[str, Any]:
    user = db.get_user_by_email(email)
    if not user:
        return {'status': 'ok', 'delivery': 'accepted'}

    token = create_action_token()
    db.revoke_auth_action_tokens(user['username'], 'password_reset')
    record = db.create_auth_action_token(
        user_name=user['username'],
        token_hash=hash_refresh_token(token),
        token_type='password_reset',
        email=user['email'],
        expires_at=db.isoformat(db.utc_now() + timedelta(minutes=PASSWORD_RESET_TOKEN_EXPIRE_MINUTES)),
    )
    delivery = mailer.send_password_reset(
        recipient=user['email'],
        token=token,
        expires_at=record['expires_at'],
    )
    return {
        'status': 'ok',
        'expires_at': record['expires_at'],
        'delivery': delivery['delivery'] if delivery['delivery'] != 'preview' or AUTH_TOKEN_PREVIEW_ENABLED else 'accepted',
        'preview': _token_preview_payload(token) if delivery['delivery'] == 'preview' else None,
    }


def reset_password_with_token(token: str, new_password: str) -> dict[str, Any]:
    record = db.get_auth_action_token(hash_refresh_token(token), 'password_reset')
    if not record or record.get('consumed_at') or time_from_iso(record['expires_at']) <= db.utc_now():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid or expired reset token')

    user = db.update_user_password(record['user_name'], hash_password(new_password))
    db.consume_auth_action_token(record['id'])
    for session in db.list_refresh_sessions(record['user_name']):
        if not session.get('revoked_at'):
            db.revoke_refresh_session(session['id'])
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found')
    return _public_user(user)


def get_current_auth_context(credentials: HTTPAuthorizationCredentials | None = Depends(security)) -> dict[str, Any]:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Authentication required')
    payload = decode_access_token(credentials.credentials)
    user = db.get_user_by_username(payload['sub'])
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='User not found')
    session = _require_active_session(payload, expected_user_name=user['username'])
    return {'user': _public_user(user), 'token': payload, 'session': session}


def get_current_user(context: dict[str, Any] = Depends(get_current_auth_context)) -> dict[str, Any]:
    return context['user']


def get_optional_user(credentials: HTTPAuthorizationCredentials | None = Depends(security)) -> dict[str, Any] | None:
    if credentials is None:
        return None
    try:
        payload = decode_access_token(credentials.credentials)
        user = db.get_user_by_username(payload['sub'])
        if not user:
            return None
        _require_active_session(payload, expected_user_name=user['username'])
        return _public_user(user)
    except HTTPException:
        return None
