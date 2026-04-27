# Prompt — Claude Code : API REST Mobile (Django)

## Contexte du projet

Tu travailles sur **BonNet**, une application Django 5.2 déployée sur Railway (domaine `bon.net.ht`).
BonNet gère la vente de vouchers WiFi UniFi dans des sites ruraux en Haïti.
La base de données est PostgreSQL en production, SQLite en dev.
Le cache est Redis (django-redis). Les tâches async tournent sur Celery.

Le projet Django contient déjà les apps suivantes :
- `accounts` — utilisateurs admin (UniFi backend) + `StoreUser` (Google OAuth2, session-based)
- `sites_mgmt` — `HotspotSite`, `VoucherTier`, `SiteConfig`
- `vouchers` — `VoucherLog` (stock de vouchers actifs)
- `store` — `Order`, `OrderItem`, `CustomerProfile`, `Cart`, `StoreBanner`
- `unifi_api` — client pyunifi avec cache Redis
- `notifications` — alertes stock, génération auto

Les clients du store (`StoreUser`) sont actuellement authentifiés via **session Django** (`request.session['store_user_id']`).
Pour l'API mobile, on bascule sur **JWT** — les sessions existantes ne sont pas touchées (le store web continue de fonctionner).

---

## Ce que tu dois construire

Crée une nouvelle app Django appelée **`api_mobile`** qui expose une API REST versionnée sous `/api/mobile/v1/`.

Utilise **Django Ninja** (`django-ninja`) pour tous les endpoints. Django Ninja génère automatiquement le schéma OpenAPI, supporte Pydantic pour la validation, et s'intègre proprement sans toucher aux vues existantes.

---

## Auth — Google Sign-In natif → JWT

### Modèles à créer ou modifier

```python
# Dans store/models.py ou api_mobile/models.py
class DeviceToken(models.Model):
    """FCM token Firebase par appareil mobile."""
    store_user = models.ForeignKey(StoreUser, on_delete=models.CASCADE, related_name='device_tokens')
    fcm_token = models.TextField()
    platform = models.CharField(max_length=10, choices=[('android', 'Android'), ('ios', 'iOS')])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('store_user', 'fcm_token')
```

### Flow d'authentification

1. Flutter effectue le Google Sign-In natif → obtient un `id_token` Google (JWT signé par Google)
2. Flutter envoie ce `id_token` à `POST /api/mobile/v1/auth/google/`
3. Le backend **vérifie** le `id_token` via `google-auth` Python (`google.oauth2.id_token.verify_oauth2_token`)
4. Si valide : trouve ou crée le `StoreUser` correspondant (par `google_id` ou email)
5. Génère et retourne un `access_token` (durée 1h) + `refresh_token` (durée 30j) via `djangorestframework-simplejwt` ou PyJWT
6. Tous les autres endpoints mobiles utilisent `Authorization: Bearer <access_token>`

### Endpoints auth

```
POST /api/mobile/v1/auth/google/
  Body: { "id_token": "...", "platform": "android" | "ios" }
  Response: { "access_token": "...", "refresh_token": "...", "user": { ... } }

POST /api/mobile/v1/auth/refresh/
  Body: { "refresh_token": "..." }
  Response: { "access_token": "..." }

POST /api/mobile/v1/auth/device-token/
  Auth: Bearer required
  Body: { "fcm_token": "...", "platform": "android" | "ios" }
  Response: { "ok": true }

DELETE /api/mobile/v1/auth/device-token/
  Auth: Bearer required
  Body: { "fcm_token": "..." }
  → Supprime le token (logout ou désinscription notifs)
```

---

## Endpoints Store

### Sites & Forfaits

```
GET /api/mobile/v1/store/sites/
  → Liste des HotspotSite actifs (id, nom, ville, GPS lat/lng)
  → Filtrer : site.is_active=True ET site a au moins 1 VoucherTier standard actif

GET /api/mobile/v1/store/sites/{site_id}/tiers/
  → VoucherTier standards assignés à ce site
  → Champs : id, name, duration_minutes, price_htg, description
  → Exclure les tiers de type Remplacement et Admin
```

### Commandes & Paiement

```
POST /api/mobile/v1/orders/checkout/
  Auth: Bearer required
  Body: {
    "site_id": 1,
    "items": [{ "tier_id": 3, "quantity": 2 }]
  }
  → Crée une Order avec statut "pending"
  → Appelle PlopPlop create_transaction (réutilise la logique existante du store web)
  → Retourne { "order_ref": "BONNET-XXXX", "payment_url": "https://..." }
  (Flutter ouvre payment_url dans un WebView)

GET /api/mobile/v1/orders/{ref}/status/
  Auth: Bearer required
  → Retourne { "status": "pending"|"paid"|"failed"|"delivered", "voucher_codes": [...] }
  → Flutter poll cette route toutes les 3s après le WebView PlopPlop
  → Si statut "paid" et codes pas encore livrés : déclenche deliver_order.delay(order_ref) si pas déjà fait (utilise Redis lock comme le store web)

GET /api/mobile/v1/orders/
  Auth: Bearer required
  → Historique des commandes du StoreUser connecté
  → Pagination : page + page_size (défaut 20)
  → Champs : ref, created_at, status, total_htg, items_count

GET /api/mobile/v1/orders/{ref}/
  Auth: Bearer required
  → Détail complet d'une commande
  → Inclut les items avec les voucher_codes en clair
  → Vérifie que la commande appartient bien au StoreUser connecté
```

---

## Endpoints Compte

```
GET /api/mobile/v1/account/me/
  Auth: Bearer required
  → Profil du StoreUser : id, email, display_name, avatar_url, phone, notif_promo, notif_transac, created_at

PATCH /api/mobile/v1/account/me/
  Auth: Bearer required
  Body (tous optionnels) : {
    "phone": "+50912345678",
    "notif_promo": true,
    "notif_transac": true
  }
  → Met à jour CustomerProfile lié au StoreUser
```

---

## Notifications Push Firebase

### Setup backend

Installe `firebase-admin` Python SDK.
Configure via variable d'environnement `FIREBASE_CREDENTIALS_JSON` (contenu JSON du service account).

```python
# api_mobile/firebase.py
import firebase_admin
from firebase_admin import credentials, messaging
import json, os

cred = credentials.Certificate(json.loads(os.environ['FIREBASE_CREDENTIALS_JSON']))
firebase_admin.initialize_app(cred)

def send_push(fcm_tokens: list[str], title: str, body: str, data: dict = None):
    """Envoie une notification push à une liste de FCM tokens."""
    if not fcm_tokens:
        return
    message = messaging.MulticastMessage(
        notification=messaging.Notification(title=title, body=body),
        data=data or {},
        tokens=fcm_tokens,
    )
    response = messaging.send_each_for_multicast(message)
    # Logger les tokens invalides (expired) et les supprimer de DeviceToken
    ...
```

### Quand envoyer une push

| Événement | Titre | Corps |
|-----------|-------|-------|
| Livraison voucher (deliver_order) | "Tes codes sont prêts ✅" | "Ta commande BONNET-XXXX est livrée. Ouvre l'app pour voir tes codes." |
| Campagne promo (voir ci-dessous) | Configurable depuis admin | Configurable depuis admin |

Intègre l'envoi push dans la tâche Celery `deliver_order` existante : après avoir livré les codes, récupère tous les `DeviceToken` du `StoreUser` concerné et appelle `send_push(...)`.

### Campagnes promo depuis l'admin

Crée un modèle `PushCampaign` et une page dans l'espace admin boutique (`/boutique/`) :

```python
class PushCampaign(models.Model):
    title = models.CharField(max_length=100)
    body = models.TextField()
    target = models.CharField(max_length=20, choices=[
        ('all', 'Tous les clients'),
        ('site', 'Par site'),
    ])
    target_site = models.ForeignKey('sites_mgmt.HotspotSite', null=True, blank=True, on_delete=models.SET_NULL)
    notif_promo_only = models.BooleanField(default=True, help_text="Envoyer uniquement aux clients ayant activé les notifs promo")
    sent_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

Page `/boutique/campagnes/` (superadmin uniquement) :
- Formulaire : titre, corps, cible (tous / par site), toggle notif_promo_only
- Bouton **Envoyer maintenant** → tâche Celery `send_push_campaign.delay(campaign_id)`
- Liste des campagnes envoyées avec date et nombre de destinataires

La tâche Celery `send_push_campaign` :
1. Récupère tous les `DeviceToken` selon le ciblage
2. Filtre sur `notif_promo=True` dans `CustomerProfile` si `notif_promo_only=True`
3. Envoie par batch de 500 (limite Firebase MulticastMessage)
4. Met à jour `campaign.sent_at`

---

## Variables d'environnement à ajouter dans `.env.example`

```
GOOGLE_CLIENT_ID_MOBILE=       # Client ID OAuth2 Google pour l'app mobile (peut être différent du web)
FIREBASE_CREDENTIALS_JSON=     # JSON complet du service account Firebase (minifié, une seule ligne)
JWT_SECRET_KEY=                 # Clé secrète pour signer les JWT mobiles
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60
JWT_REFRESH_TOKEN_EXPIRE_DAYS=30
```

---

## Structure de fichiers cible

```
api_mobile/
  __init__.py
  apps.py
  urls.py          # router Django Ninja
  auth.py          # endpoints /auth/
  store.py         # endpoints /store/
  orders.py        # endpoints /orders/
  account.py       # endpoints /account/
  firebase.py      # Firebase Admin SDK init + send_push()
  schemas.py       # Tous les schémas Pydantic (Input / Output)
  models.py        # DeviceToken, PushCampaign
  tasks.py         # send_push_campaign Celery task
  migrations/
```

Dans `bonnet/urls.py`, ajouter :
```python
from api_mobile.urls import api as mobile_api
urlpatterns += [path("api/mobile/v1/", mobile_api.urls)]
```

---

## Contraintes importantes

- **Ne pas modifier** les vues store web existantes ni les sessions Django — l'API mobile est additive
- **Réutiliser** la logique PlopPlop et `deliver_order` existante — ne pas dupliquer
- Le Redis lock anti-doublon de livraison (`cache.add`) doit fonctionner aussi depuis le polling mobile
- Tous les montants sont en **HTG (gourdes haïtiennes)**, entiers
- Les `voucher_codes` dans les réponses API sont les codes PIN à 10 chiffres
- Respecter le filtre `user.managed_sites` pour les site_admin (les endpoints mobiles concernent uniquement les clients `StoreUser`, pas les admins — mais les données retournées doivent correspondre aux sites actifs)
- Ajouter des tests unitaires minimaux pour les endpoints auth et orders/status
