import secrets
import logging
from urllib.parse import urlencode

import requests as http_requests
from django.conf import settings
from django.urls import reverse

logger = logging.getLogger(__name__)

GOOGLE_AUTH_URL     = 'https://accounts.google.com/o/oauth2/v2/auth'
GOOGLE_TOKEN_URL    = 'https://oauth2.googleapis.com/token'
GOOGLE_USERINFO_URL = 'https://www.googleapis.com/oauth2/v3/userinfo'


def get_redirect_uri(request):
    return request.build_absolute_uri(reverse('store:google_callback'))


def build_google_auth_url(request):
    state = secrets.token_urlsafe(16)
    request.session['google_oauth_state'] = state
    params = {
        'client_id':     settings.GOOGLE_CLIENT_ID,
        'redirect_uri':  get_redirect_uri(request),
        'response_type': 'code',
        'scope':         'openid email profile',
        'state':         state,
        'access_type':   'online',
    }
    return GOOGLE_AUTH_URL + '?' + urlencode(params)


def exchange_code(request, code):
    """Échange le code OAuth contre un access_token et retourne les infos user."""
    resp = http_requests.post(GOOGLE_TOKEN_URL, data={
        'code':          code,
        'client_id':     settings.GOOGLE_CLIENT_ID,
        'client_secret': settings.GOOGLE_CLIENT_SECRET,
        'redirect_uri':  get_redirect_uri(request),
        'grant_type':    'authorization_code',
    }, timeout=10)
    resp.raise_for_status()
    token_data   = resp.json()
    access_token = token_data.get('access_token')
    if not access_token:
        raise ValueError('Pas de access_token dans la réponse Google')

    info_resp = http_requests.get(
        GOOGLE_USERINFO_URL,
        headers={'Authorization': f'Bearer {access_token}'},
        timeout=10,
    )
    info_resp.raise_for_status()
    return info_resp.json()


def get_or_create_store_user(userinfo):
    from .models import StoreUser
    google_id = userinfo.get('sub')
    email     = userinfo.get('email', '')
    name      = userinfo.get('name', '')
    avatar    = userinfo.get('picture', '')

    store_user, _ = StoreUser.objects.update_or_create(
        google_id=google_id,
        defaults={
            'email':      email,
            'full_name':  name,
            'avatar_url': avatar,
        },
    )
    return store_user


def merge_session_cart(request, store_user):
    """Fusionne le panier anonyme de la session dans le panier du store_user."""
    from .models import Cart
    if not request.session.session_key:
        return
    session_cart = Cart.objects.filter(session_key=request.session.session_key).first()
    if not session_cart:
        return

    user_cart, _ = Cart.objects.get_or_create(store_user=store_user)
    for item in session_cart.items.all():
        existing = user_cart.items.filter(tier=item.tier, site=item.site).first()
        if existing:
            existing.quantity = min(10, existing.quantity + item.quantity)
            existing.save(update_fields=['quantity'])
        else:
            item.cart = user_cart
            item.save(update_fields=['cart'])
    session_cart.delete()
