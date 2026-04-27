import jwt
from django.db import transaction
from ninja import Router

from .auth_helpers import (
    decode_token, make_access_token, make_refresh_token, verify_google_id_token,
)
from .schemas import AccessTokenOut, AuthOut, DeviceTokenIn, GoogleAuthIn, OkOut, RefreshIn, UserOut
from .security import mobile_auth

router = Router(tags=['Auth'])


def _user_out(user) -> UserOut:
    return UserOut(
        id=user.pk,
        email=user.email,
        full_name=user.full_name,
        avatar_url=user.avatar_url,
        phone=user.phone,
        notif_promo=user.notif_promo,
        notif_transac=user.notif_transac,
        created_at=user.created_at,
    )


@router.post('/google/', response={200: AuthOut, 401: dict})
def google_auth(request, data: GoogleAuthIn):
    try:
        idinfo = verify_google_id_token(data.id_token)
    except Exception as exc:
        return 401, {'detail': f'Token Google invalide : {exc}'}

    google_id = idinfo['sub']
    email     = idinfo.get('email', '')
    full_name = idinfo.get('name', '')
    avatar    = idinfo.get('picture', '')

    from store.models import StoreUser
    with transaction.atomic():
        user, created = StoreUser.objects.get_or_create(
            google_id=google_id,
            defaults={'email': email, 'full_name': full_name, 'avatar_url': avatar},
        )
        if not created:
            update_fields = []
            if avatar and user.avatar_url != avatar:
                user.avatar_url = avatar
                update_fields.append('avatar_url')
            if full_name and not user.full_name:
                user.full_name = full_name
                update_fields.append('full_name')
            if update_fields:
                user.save(update_fields=update_fields)

    return 200, AuthOut(
        access_token=make_access_token(user.pk),
        refresh_token=make_refresh_token(user.pk),
        user=_user_out(user),
    )


@router.post('/refresh/', response={200: AccessTokenOut, 401: dict})
def refresh_token(request, data: RefreshIn):
    try:
        payload = decode_token(data.refresh_token, 'refresh')
    except jwt.PyJWTError:
        return 401, {'detail': 'Refresh token invalide ou expiré'}
    return 200, AccessTokenOut(access_token=make_access_token(payload['sub']))


@router.post('/device-token/', auth=mobile_auth, response={200: OkOut, 400: dict})
def register_device_token(request, data: DeviceTokenIn):
    if data.platform not in ('android', 'ios'):
        return 400, {'detail': 'platform doit être android ou ios'}
    from .models import DeviceToken
    DeviceToken.objects.get_or_create(
        store_user=request.auth,
        fcm_token=data.fcm_token,
        defaults={'platform': data.platform},
    )
    return 200, OkOut()


@router.delete('/device-token/', auth=mobile_auth, response={200: OkOut})
def unregister_device_token(request, data: DeviceTokenIn):
    from .models import DeviceToken
    DeviceToken.objects.filter(store_user=request.auth, fcm_token=data.fcm_token).delete()
    return 200, OkOut()
