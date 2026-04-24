def store_user(request):
    uid = request.session.get('store_user_id')
    if not uid:
        return {'store_user': None}
    try:
        from .models import StoreUser
        return {'store_user': StoreUser.objects.get(pk=uid)}
    except StoreUser.DoesNotExist:
        request.session.pop('store_user_id', None)
        return {'store_user': None}
