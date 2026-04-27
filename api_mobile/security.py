import jwt
from ninja.security import HttpBearer

from .auth_helpers import decode_token


class MobileBearer(HttpBearer):
    def authenticate(self, request, token: str):
        try:
            payload = decode_token(token, 'access')
        except jwt.PyJWTError:
            return None  # Ninja treats None as 401

        from store.models import StoreUser
        try:
            return StoreUser.objects.get(pk=payload['sub'])
        except StoreUser.DoesNotExist:
            return None


mobile_auth = MobileBearer()
