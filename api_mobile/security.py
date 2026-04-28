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


def get_optional_user(request):
    """Retourne le StoreUser si le token Bearer est valide, sinon None."""
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    if not auth_header.startswith('Bearer '):
        return None
    token = auth_header[7:]
    try:
        payload = decode_token(token, 'access')
    except jwt.PyJWTError:
        return None
    from store.models import StoreUser
    return StoreUser.objects.filter(pk=payload['sub']).first()
