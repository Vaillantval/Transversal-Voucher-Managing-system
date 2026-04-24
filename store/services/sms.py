from django.conf import settings


def send_voucher_sms(phone_number: str, voucher_codes: list, site_name: str) -> str:
    from twilio.rest import Client
    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    codes_text = '\n'.join(f'• {code}' for code in voucher_codes)
    body = (
        f'BonNet WiFi ✓\n'
        f'Site: {site_name}\n'
        f'Vos codes:\n{codes_text}\n'
        f'Connectez-vous au WiFi BonNet et entrez votre code.'
    )
    message = client.messages.create(
        body=body,
        from_=settings.TWILIO_FROM_NUMBER,
        to=phone_number,
    )
    return message.sid
