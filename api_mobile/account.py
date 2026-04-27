from ninja import Router

from .schemas import AccountPatchIn, UserOut
from .security import mobile_auth

router = Router(tags=['Account'])


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


@router.get('/me/', auth=mobile_auth, response=UserOut)
def get_me(request):
    return _user_out(request.auth)


@router.patch('/me/', auth=mobile_auth, response=UserOut)
def patch_me(request, data: AccountPatchIn):
    user = request.auth
    update_fields = []
    if data.phone is not None:
        user.phone = data.phone
        update_fields.append('phone')
    if data.notif_promo is not None:
        user.notif_promo = data.notif_promo
        update_fields.append('notif_promo')
    if data.notif_transac is not None:
        user.notif_transac = data.notif_transac
        update_fields.append('notif_transac')
    if update_fields:
        user.save(update_fields=update_fields)
    return _user_out(user)
