# BonNet — API Mobile : Bilan d'implémentation

**Date** : 2026-04-27  
**Branche** : `main` (pas encore pushé au moment de la rédaction)

---

## Vue d'ensemble

Nouvelle app Django **`api_mobile`** exposant une API REST versionnée sous `/api/mobile/v1/`  
via **Django Ninja** (OpenAPI auto-généré sur `/api/mobile/v1/docs`).

L'API est **additive** : aucune vue web existante n'a été modifiée, aucune session Django touchée.

---

## Fichiers créés

### App `api_mobile/`

| Fichier | Rôle |
|---------|------|
| `__init__.py` | — |
| `apps.py` | `ApiMobileConfig` |
| `models.py` | `DeviceToken`, `PushCampaign` |
| `schemas.py` | Tous les schémas Pydantic I/O |
| `auth_helpers.py` | JWT (PyJWT) — génération access/refresh + vérification Google ID token |
| `security.py` | `MobileBearer(HttpBearer)` — auth Ninja par Bearer JWT |
| `auth.py` | Router `/auth/` |
| `account.py` | Router `/account/` |
| `store.py` | Router `/store/` |
| `orders.py` | Router `/orders/` (+ `/checkout/`) |
| `firebase.py` | Firebase Admin SDK lazy-init + `send_push()` |
| `tasks.py` | Tâche Celery `send_push_campaign` |
| `urls.py` | `NinjaAPI` principal, monte les 4 routers |
| `migrations/0001_initial.py` | Crée `api_mobile_devicetoken` |
| `migrations/0002_pushcampaign.py` | Crée `api_mobile_pushcampaign` |

### Templates

| Fichier | Rôle |
|---------|------|
| `templates/boutique/campaigns.html` | Page superadmin `/boutique/campagnes/` — formulaire + historique |

---

## Fichiers modifiés

| Fichier | Changement |
|---------|------------|
| `bonnet/settings.py` | `api_mobile` dans `INSTALLED_APPS` + `GOOGLE_CLIENT_ID_MOBILE` |
| `bonnet/urls.py` | `path('api/mobile/v1/', mobile_api.urls)` |
| `store/models.py` | `notif_promo`, `notif_transac` (`BooleanField default=True`) sur `StoreUser` |
| `store/migrations/0004_…` | Migration des 2 nouveaux champs `StoreUser` |
| `store/tasks.py` | `deliver_order` : envoi push Firebase après SMS (silencieux si Firebase absent) |
| `store/boutique_views.py` | `campaigns_count` dans `boutique_hub` + vues `boutique_campaigns` / `boutique_campaign_create` |
| `store/boutique_urls.py` | `/boutique/campagnes/` + `/boutique/campagnes/envoyer/` |
| `templates/boutique/hub.html` | Carte "Campagnes push" (superadmin uniquement) |
| `requirements.txt` | `django-ninja`, `PyJWT`, `google-auth`, `firebase-admin` |

---

## Endpoints API

Base : `https://bon.net.ht/api/mobile/v1/`

### Auth

| Méthode | Path | Auth | Description |
|---------|------|------|-------------|
| `POST` | `/auth/google/` | — | Google ID token → access + refresh JWT |
| `POST` | `/auth/refresh/` | — | Refresh token → nouveau access token |
| `POST` | `/auth/device-token/` | Bearer | Enregistrer un FCM token |
| `DELETE` | `/auth/device-token/` | Bearer | Supprimer un FCM token (déconnexion) |

### Compte

| Méthode | Path | Auth | Description |
|---------|------|------|-------------|
| `GET` | `/account/me/` | Bearer | Profil du `StoreUser` connecté |
| `PATCH` | `/account/me/` | Bearer | Modifier `phone`, `notif_promo`, `notif_transac` |

### Store

| Méthode | Path | Auth | Description |
|---------|------|------|-------------|
| `GET` | `/store/banners/` | — | Bannières actives (slider Flutter) |
| `GET` | `/store/sites/` | — | Sites actifs ayant au moins 1 forfait standard |
| `GET` | `/store/sites/{id}/tiers/` | — | Forfaits disponibles pour un site |

### Commandes

| Méthode | Path | Auth | Description |
|---------|------|------|-------------|
| `POST` | `/checkout/` | Bearer | Crée commande + appelle PlopPlop → `payment_url` |
| `GET` | `/orders/{ref}/status/` | Bearer | Polling statut (Flutter toutes les 3s après WebView) |
| `GET` | `/orders/` | Bearer | Historique paginé (`?page=1&page_size=20`) |
| `GET` | `/orders/{ref}/` | Bearer | Détail complet + `voucher_codes` en clair |

---

## Modèles créés

### `DeviceToken` (app `api_mobile`)
```
store_user  → FK StoreUser
fcm_token   → TextField
platform    → 'android' | 'ios'
created_at, updated_at
unique_together: (store_user, fcm_token)
```

### `PushCampaign` (app `api_mobile`)
```
title, body
target          → 'all' | 'site'
target_site     → FK HotspotSite (nullable)
notif_promo_only → BooleanField (default True)
sent_at         → DateTimeField (nullable)
recipients_count → PositiveIntegerField
created_by      → FK AUTH_USER_MODEL
created_at
```

---

## Auth flow JWT

```
Flutter  ──[Google ID token]──►  POST /auth/google/
                                  │
                          verify_oauth2_token()  (google-auth)
                                  │
                          get_or_create StoreUser
                                  │
                          ◄──[ access_token (1h) + refresh_token (30j) ]──
```

- Algorithme : HS256, signé avec `JWT_SECRET_KEY`
- Les endpoints Bearer lisent `Authorization: Bearer <token>` via `MobileBearer(HttpBearer)`

---

## Flux achat mobile

```
1. Flutter affiche sites + tiers (GET /store/sites/ → /tiers/)
2. POST /checkout/ → { order_ref, payment_url }
3. Flutter ouvre payment_url dans WebView
4. WebView navigue vers https://bon.net.ht/commande/?refference_id=BONNET-XXXX
   → Flutter intercepte cette URL et ferme le WebView
5. Flutter poll GET /orders/{ref}/status/ toutes les 3s
6. Dès status='paid' : Redis lock + deliver_order.delay() (Celery)
7. Celery livre les codes (stock ou UniFi), envoie SMS + push Firebase
8. Flutter poll reçoit status='delivered' + voucher_codes → affiche les codes
```

---

## Push notifications

### Livraison automatique (dans `deliver_order`)
Après l'envoi SMS, si le `StoreUser` a des `DeviceToken` enregistrés :
- Titre : `"Tes codes sont prêts ✅"`
- Corps : `"Ta commande BONNET-XXXX est livrée. Ouvre l'app pour voir tes codes."`

### Campagnes marketing (`/boutique/campagnes/`)
- Page superadmin uniquement
- Ciblage : tous les clients ou par site
- Filtre optionnel `notif_promo_only`
- Envoi via tâche Celery `send_push_campaign` — batches de 500 tokens (limite Firebase)
- Tokens invalides supprimés automatiquement après chaque envoi

---

## Variables d'environnement à configurer

### Railway — À ajouter

| Variable | Priorité | Description |
|----------|----------|-------------|
| `JWT_SECRET_KEY` | **Obligatoire** | Clé de signature JWT — générer avec `python -c "import secrets; print(secrets.token_hex(32))"` |
| `GOOGLE_CLIENT_ID_MOBILE` | **Obligatoire** | Client ID web GCP utilisé comme `serverClientId` Flutter |
| `FIREBASE_CREDENTIALS_JSON` | Optionnel (push) | JSON service account Firebase, sur **une seule ligne** |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | Optionnel | Default : `60` |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | Optionnel | Default : `30` |

### Google Cloud Console — À faire

1. **Client Android** → APIs & Services → Credentials → OAuth client ID → type Android
   - Package name : ex `ht.bonnet.app`
   - SHA-1 : `keytool -list -v -keystore ~/.android/debug.keystore` (debug) ou keystore de release (prod)

2. **Client iOS** → même chemin → type iOS
   - Bundle ID : ex `ht.bonnet.app`

3. **`serverClientId` Flutter** = l'ID du client **Web** existant (`GOOGLE_CLIENT_ID`)
   - C'est lui que le backend utilise pour vérifier les `id_token`
   - Mettre cette valeur dans `GOOGLE_CLIENT_ID_MOBILE` sur Railway (peut être identique à `GOOGLE_CLIENT_ID`)

### Firebase — À faire (pour les push)

1. [console.firebase.google.com](https://console.firebase.google.com) → créer ou lier le projet GCP
2. Project Settings → Service accounts → **Generate new private key** → télécharger le JSON
3. Minifier : `python -c "import json,sys; print(json.dumps(json.load(open('creds.json'))))"`
4. Coller dans `FIREBASE_CREDENTIALS_JSON` sur Railway

---

## Ordre de déploiement recommandé

```
1. Ajouter JWT_SECRET_KEY sur Railway
2. Ajouter GOOGLE_CLIENT_ID_MOBILE sur Railway (= GOOGLE_CLIENT_ID pour commencer)
3. git push → Railway : migrate auto + install nouveaux packages
4. Vérifier https://bon.net.ht/api/mobile/v1/docs (Swagger UI)
5. Créer clients Android + iOS sur GCP (quand Flutter est prêt)
6. Configurer Firebase + FIREBASE_CREDENTIALS_JSON (quand push prioritaire)
```

---

## Impact sur le site web existant

| Composant | Impact |
|-----------|--------|
| Store web (panier, checkout, OAuth Google) | Aucun |
| Dashboard admin | Aucun |
| Page `/boutique/` hub | +1 carte "Campagnes push" (superadmin) |
| Livraison vouchers (`deliver_order`) | +push Firebase silencieux (try/except) |
| Base de données | +3 tables, +2 colonnes `StoreUser` (`default=True`) |
