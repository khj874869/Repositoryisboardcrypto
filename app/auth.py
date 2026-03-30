from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import db
from .config import ACCESS_TOKEN_EXPIRE_MINUTES, SECRET_KEY

security = HTTPBearer(auto_error=False)


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b'=').decode('utf-8')


def _b64url_decode(value: str) -> bytes:
    padding = '=' * ((4 - len(value) % 4) % 4)
    return base64.urlsafe_b64decode(value + padding)


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


def create_access_token(username: str, *, expires_minutes: int = ACCESS_TOKEN_EXPIRE_MINUTES) -> str:
    header = {'alg': 'HS256', 'typ': 'JWT'}
    payload = {
        'sub': username,
        'iat': int(time.time()),
        'exp': int(time.time() + expires_minutes * 60),
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
    if payload.get('exp', 0) < int(time.time()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Token expired')
    if not payload.get('sub'):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid token payload')
    return payload


def _public_user(user: dict[str, Any]) -> dict[str, Any]:
    return {
        'id': user['id'],
        'username': user['username'],
        'email': user['email'],
        'created_at': user['created_at'],
    }


def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(security)) -> dict[str, Any]:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Authentication required')
    payload = decode_access_token(credentials.credentials)
    user = db.get_user_by_username(payload['sub'])
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='User not found')
    return _public_user(user)


def get_optional_user(credentials: HTTPAuthorizationCredentials | None = Depends(security)) -> dict[str, Any] | None:
    if credentials is None:
        return None
    payload = decode_access_token(credentials.credentials)
    user = db.get_user_by_username(payload['sub'])
    if not user:
        return None
    return _public_user(user)
