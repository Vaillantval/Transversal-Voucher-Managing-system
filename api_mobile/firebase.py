import json
import logging
import os

logger = logging.getLogger(__name__)

_firebase_app = None


def _get_app():
    global _firebase_app
    if _firebase_app is not None:
        return _firebase_app

    creds_json = os.getenv('FIREBASE_CREDENTIALS_JSON')
    if not creds_json:
        return None

    try:
        import firebase_admin
        from firebase_admin import credentials
        cred = credentials.Certificate(json.loads(creds_json))
        _firebase_app = firebase_admin.initialize_app(cred)
    except Exception as exc:
        logger.error(f'Firebase init error: {exc}')

    return _firebase_app


def send_push(fcm_tokens: list, title: str, body: str, data: dict = None) -> int:
    """Send a push notification to a list of FCM tokens.

    Batches into groups of 500 (Firebase limit).
    Deletes invalid/expired tokens automatically.
    Returns total success count.
    """
    if not fcm_tokens:
        return 0

    app = _get_app()
    if app is None:
        logger.warning('Firebase not configured — push skipped')
        return 0

    from firebase_admin import messaging

    str_data = {k: str(v) for k, v in (data or {}).items()}
    total_sent = 0

    for i in range(0, len(fcm_tokens), 500):
        batch = fcm_tokens[i: i + 500]
        msg = messaging.MulticastMessage(
            notification=messaging.Notification(title=title, body=body),
            data=str_data,
            tokens=batch,
        )
        try:
            response = messaging.send_each_for_multicast(msg)
            total_sent += response.success_count
            if response.failure_count:
                bad = [batch[j] for j, r in enumerate(response.responses) if not r.success]
                if bad:
                    from .models import DeviceToken
                    DeviceToken.objects.filter(fcm_token__in=bad).delete()
                    logger.info(f'Firebase: removed {len(bad)} invalid token(s)')
        except Exception as exc:
            logger.error(f'Firebase multicast error: {exc}')

    return total_sent
