import os
from datetime import datetime, timedelta, timezone

import jwt
from django.conf import settings

_ACCESS_TTL  = timedelta(minutes=int(os.getenv('JWT_ACCESS_TOKEN_EXPIRE_MINUTES', '60')))
_REFRESH_TTL = timedelta(days=int(os.getenv('JWT_REFRESH_TOKEN_EXPIRE_DAYS', '30')))
_ALGORITHM   = 'HS256'


def _secret() -> str:
    return os.getenv('JWT_SECRET_KEY') or settings.SECRET_KEY


def _make_token(sub: int, kind: str, ttl: timedelta) -> str:
    now = datetime.now(tz=timezone.utc)
    return jwt.encode(
        {'sub': sub, 'kind': kind, 'iat': now, 'exp': now + ttl},
        _secret(),
        algorithm=_ALGORITHM,
    )


def make_access_token(user_id: int) -> str:
    return _make_token(user_id, 'access', _ACCESS_TTL)


def make_refresh_token(user_id: int) -> str:
    return _make_token(user_id, 'refresh', _REFRESH_TTL)


def decode_token(token: str, kind: str) -> dict:
    """Decode and validate a JWT. Raises jwt.PyJWTError on failure."""
    payload = jwt.decode(token, _secret(), algorithms=[_ALGORITHM])
    if payload.get('kind') != kind:
        raise jwt.InvalidTokenError('Wrong token type')
    return payload


def verify_google_id_token(id_token: str) -> dict:
    """Verify a Google ID token from the mobile app and return its claims."""
    from google.oauth2 import id_token as _google_id_token
    from google.auth.transport import requests as _google_requests

    client_id = os.getenv('GOOGLE_CLIENT_ID_MOBILE') or settings.GOOGLE_CLIENT_ID
    return _google_id_token.verify_oauth2_token(
        id_token,
        _google_requests.Request(),
        client_id,
    )
