# BonNet — WiFi Haïti · Gestion Vouchers + Store E-commerce

Application Django en deux volets :
- **Espace admin** — gestion des vouchers WiFi UniFi, sites, tarifs, rapports
- **Store public** — vente de forfaits WiFi en ligne (MonCash / NatCash via PlopPlop)

Déployé sur Railway · Domaine : **bon.net.ht**

---

## Stack technique

| Composant | Détail |
|-----------|--------|
| **Backend** | Django 5.2 + PostgreSQL (Railway) |
| **Cache / Sessions** | Redis (Railway) via django-redis |
| **Tâches async** | Celery + Redis (livraison vouchers) |
| **API UniFi** | pyunifi — contrôleur p989.cloudunifi.com |
| **Paiement** | PlopPlop (MonCash / NatCash) |
| **SMS** | Twilio (envoi des codes après paiement) |
| **Emails** | Resend (API HTTP) |
| **Auth store** | Google OAuth2 custom (sans django-allauth) |
| **Scheduler** | APScheduler + django-apscheduler |
| **Export** | reportlab (PDF), openpyxl (Excel), csv natif |
| **Frontend** | Bootstrap 5.3 + Chart.js 4.4 + Swiper.js (CDN) |
| **Thème admin** | django-jazzmin (dark) |
| **Déploiement** | Docker multi-stage + Railway.app + Gunicorn + WhiteNoise |

---

## Installation locale

```bash
# 1. Cloner
git clone <repo> && cd bonnet

# 2. Environnement virtuel
python -m venv .venv
source .venv/bin/activate      # Linux/Mac
.venv\Scripts\activate         # Windows

# 3. Dépendances
pip install -r requirements.txt

# 4. Configuration
cp .env.example .env
# → Remplir .env (voir Variables d'environnement ci-dessous)

# 5. Migrations
python manage.py migrate

# 6. Super-admin
python manage.py ensure_superadmin

# 7. Lancer
python manage.py runserver
```

---

## Variables d'environnement

### Core
| Variable | Obligatoire | Description |
|----------|-------------|-------------|
| `SECRET_KEY` | Prod | Clé secrète Django |
| `DEBUG` | Non | `True` en dev, `False` en prod |
| `DATABASE_URL` | Prod | URL PostgreSQL Railway (auto-injectée) |
| `REDIS_URL` | Prod | URL Redis Railway |
| `ALLOWED_HOSTS` | Prod | Domaines autorisés (virgule-séparés) |
| `CSRF_TRUSTED_ORIGINS` | Prod | Origins CSRF (ex: `https://bon.net.ht`) |

### UniFi
| Variable | Description |
|----------|-------------|
| `UNIFI_HOST` | Hôte contrôleur UniFi |
| `UNIFI_PORT` | Port (défaut 8443) |
| `UNIFI_USERNAME` | Identifiant UniFi |
| `UNIFI_PASSWORD` | Mot de passe UniFi |

### Emails & Notifications
| Variable | Description |
|----------|-------------|
| `RESEND_API_KEY` | Clé API Resend |
| `RESEND_FROM_EMAIL` | Expéditeur (domaine vérifié Resend) |
| `ADMIN_NOTIFY` | Emails admins pour alertes/rapports (virgule-séparés) |

### Store (paiement + auth)
| Variable | Description |
|----------|-------------|
| `PLOPPLOP_CLIENT_ID` | Client ID marchand PlopPlop |
| `TWILIO_ACCOUNT_SID` | Account SID Twilio |
| `TWILIO_AUTH_TOKEN` | Auth Token Twilio |
| `TWILIO_FROM_NUMBER` | Numéro expéditeur SMS (ex: `+1XXXXXXXXXX`) |
| `GOOGLE_CLIENT_ID` | OAuth2 client ID Google Cloud Console |
| `GOOGLE_CLIENT_SECRET` | OAuth2 client secret Google Cloud Console |

---

## Apps Django

| App | Rôle |
|-----|------|
| `accounts` | Auth UniFi backend + rôles + gestion utilisateurs + formulaire partenaire public |
| `sites_mgmt` | HotspotSite (GPS) + VoucherTier + SiteConfig + PartnerProduct |
| `vouchers` | VoucherLog — stock de vouchers actifs (source prioritaire pour le store) + recherche code PIN |
| `dashboard` | KPIs + charts temps réel + widget recherche voucher + répartition forfaits scrollable |
| `reports` | Export PDF / Excel / CSV |
| `unifi_api` | Client pyunifi avec cache Redis (TTL 3–6min, pre-warm /2min) |
| `notifications` | Alertes stock, génération auto, rapports mensuels, AdminVoucherGenLog |
| `store` | Store public + espace admin boutique (commandes, clients, bannières, paniers) |

---

## Architecture du store public

### Deux types d'utilisateurs (totalement séparés)

| | Admin (`User`) | Client (`StoreUser`) |
|---|---|---|
| Auth | UniFi backend / Django | Google OAuth2 custom |
| Session | `request.user` Django | `request.session['store_user_id']` |
| Accès | `/dashboard/` + `/admin/` | `/` + `/mon-compte/` |

### Workflow d'achat

```
1. Storefront → clic plan → modal 2 étapes
   └─ Étape 1 : choix du site
   └─ Étape 2 : vrais tiers du site (/site/<id>/tiers/)
       → pré-sélection du tier le plus proche de la durée approximative

2. Panier → checkout POST → PlopPlop create_transaction
   → redirect page paiement (MonCash ou NatCash)

3. PlopPlop → return URL : https://bon.net.ht/commande/
   → redirect /commande/BONNET-XXXX/

4. Polling JS /3s → verify_transaction
   → si payé : Redis lock (cache.add) → deliver_order.delay (Celery)

5. Celery deliver_order :
   └─ Priorité : VoucherLog stock actif (select_for_update skip_locked)
   └─ Fallback : unifi.create_vouchers()
   → SMS Twilio avec les codes → page affiche les codes
```

---

## Forfaits (VoucherTier)

| Type | Prix | Usage |
|------|------|-------|
| **Standard** | Libre (HTG) | Vente admin + store public |
| **Remplacement** | 0 HTG | Offert — créé à la volée |
| **Admin** | 0 HTG | Accès admin — régénération automatique |

- Assignation par site via M2M
- Forfait Admin par défaut créé automatiquement pour tout nouveau site

---

## Notifications & Emails

### Partenaires
- Soumission → email confirmation au candidat + alerte `ADMIN_NOTIFY`
- Approbation → email identifiants + création compte + site UniFi
- Rejet → email poli au candidat (motif si renseigné)

### Stock & Génération automatique
- Alerte stock < 30 vouchers par forfait standard par site (toutes les 12h)
- Génération auto selon les toggles AutoGen / Notifications dans Configuration
- Génération admin quand `today >= expires_at` (AdminVoucherGenLog)

### Rapport mensuel
- Dernier jour du mois à 8h00 (heure Haïti) → Excel + PDF → `ADMIN_NOTIFY`

```bash
# Envoi manuel
python manage.py send_report_now
python manage.py send_report_now --days 60
```

---

## Architecture Railway

```
┌─────────────────────────────────────────────────────────┐
│  Railway Project : BonNet                               │
│                                                         │
│  [web]         Django + Gunicorn  → pages & API         │
│  [redis]       Redis              → cache + Celery      │
│  [postgresql]  PostgreSQL         → données             │
│                                                         │
│  web ──REDIS_URL──► Redis    (cache UniFi + Celery)     │
│  web ──DATABASE_URL──► PostgreSQL  (users, orders…)     │
│  web ──HTTPS──► p989.cloudunifi.com  (UniFi API)        │
│  web ──HTTPS──► PlopPlop / Twilio / Google / Resend     │
└─────────────────────────────────────────────────────────┘
```

```toml
# railway.toml
startCommand = "python manage.py migrate --noinput && python manage.py ensure_superadmin && gunicorn bonnet.wsgi --bind 0.0.0.0:$PORT --workers 1 --timeout 120"
```

> ⚠️ `--workers 1` obligatoire — APScheduler démarre dans chaque worker ; plusieurs workers = jobs en double.

### Configuration Google Cloud Console
Dans **APIs & Services → Credentials → OAuth Client ID** :
- Authorized redirect URIs : `https://bon.net.ht/auth/google/callback/`
- Authorized JavaScript origins : `https://bon.net.ht`

### Return URL PlopPlop
```
https://bon.net.ht/commande/
```
(PlopPlop redirige vers `?refference_id=BONNET-XXXX`, la vue lit et redirige vers la page de confirmation)

---

## Structure des rôles admin

| Rôle | Droits |
|------|--------|
| **superadmin** | Tous les sites, tarifs, rapports complets, gestion utilisateurs, partenaires |
| **site_admin** | Sites assignés uniquement, vouchers, export filtré |

---

## Espace admin boutique (`/boutique/`)

Section du dashboard custom dédiée à la gestion du store public, accessible depuis le drawer.

| Page | URL | Accès |
|------|-----|-------|
| Commandes | `/boutique/` | Tous admins |
| Détail commande | `/boutique/commandes/<ref>/` | Tous admins |
| Clients | `/boutique/clients/` | Tous admins |
| Comptes Google | `/boutique/utilisateurs/` | Tous admins |
| Paniers actifs | `/boutique/paniers/` | Tous admins |
| Bannières | `/boutique/bannieres/` | Superadmin |

Les vues site_admin filtrent automatiquement sur `user.managed_sites`.  
Fichiers : `store/boutique_views.py` + `store/boutique_urls.py` (namespace `boutique`).

---

## Prochaines étapes suggérées

- [ ] Vérification du domaine `bon.net.ht` sur Resend pour l'envoi production
- [ ] Exposer Django comme backend REST pour app mobile (JWT, endpoints)
- [ ] MEDIA_ROOT depuis env var sur Railway (logos/PDF perdus sinon)
- [ ] QR codes sur les vouchers imprimés
- [ ] Notifications WhatsApp/SMS quand un device passe offline
