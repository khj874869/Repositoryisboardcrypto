from app import auth


def test_password_hash_and_verify_roundtrip():
    password_hash = auth.hash_password('strong-pass-123')
    assert auth.verify_password('strong-pass-123', password_hash) is True
    assert auth.verify_password('wrong-pass', password_hash) is False


def test_access_token_roundtrip():
    token = auth.create_access_token('demo', expires_minutes=5)
    payload = auth.decode_access_token(token)
    assert payload['sub'] == 'demo'
