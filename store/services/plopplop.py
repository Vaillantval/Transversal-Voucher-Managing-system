import requests
from django.conf import settings

PLOPPLOP_BASE = 'https://plopplop.solutionip.app'


def create_transaction(order_ref: str, montant: float, method: str = 'all') -> dict:
    payload = {
        'client_id':      settings.PLOPPLOP_CLIENT_ID,
        'refference_id':  order_ref,
        'montant':        montant,
        'payment_method': method,
    }
    resp = requests.post(f'{PLOPPLOP_BASE}/api/paiement-marchand', json=payload, timeout=15)
    resp.raise_for_status()
    return resp.json()


def verify_transaction(order_ref: str) -> dict:
    payload = {
        'client_id':     settings.PLOPPLOP_CLIENT_ID,
        'refference_id': order_ref,
    }
    resp = requests.post(f'{PLOPPLOP_BASE}/api/paiement-verify', json=payload, timeout=10)
    resp.raise_for_status()
    return resp.json()
