# BonNet — Gestion Vouchers WiFi Haïti

Application Django de gestion des coupons de connexion internet
sur les sites Starlink/UniFi déployés en Haïti.

## Stack technique

| Composant | Détail |
|-----------|--------|
| **Backend** | Django 5.2 + PostgreSQL (Railway) |
| **Cache** | Redis (Railway) via django-redis — partagé entre workers |
| **API UniFi** | pyunifi — contrôleur p989.cloudunifi.com |
| **Emails** | Resend (API HTTP) |
| **Scheduler** | APScheduler + django-apscheduler |
| **Export** | reportlab (PDF), openpyxl (Excel), csv natif |
| **Frontend** | Bootstrap 5.3 + Chart.js 4.4 (CDN) |
| **Thème admin** | django-jazzmin (dark) |
| **Déploiement** | Docker multi-stage + Railway.app + Gunicorn + WhiteNoise |

## Installation locale

```bash
# 1. Cloner le projet
git clone <repo>
cd bonnet

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

## Variables d'environnement

| Variable | Obligatoire | Description |
|----------|-------------|-------------|
| `SECRET_KEY` | Prod | Clé secrète Django |
| `DEBUG` | Non | `True` en dev, `False` en prod |
| `DATABASE_URL` | Prod | URL PostgreSQL Railway (auto-injectée) |
| `UNIFI_HOST` | Oui | Hôte contrôleur UniFi |
| `UNIFI_PORT` | Oui | Port (défaut 8443) |
| `UNIFI_USERNAME` | Oui | Identifiant UniFi |
| `UNIFI_PASSWORD` | Oui | Mot de passe UniFi |
| `RESEND_API_KEY` | Prod | Clé API Resend (emails) |
| `RESEND_FROM_EMAIL` | Prod | Expéditeur email (domaine vérifié Resend) |
| `REDIS_URL` | Prod | URL Redis Railway (copier depuis le service Redis) |
| `ADMIN_NOTIFY` | Prod | Emails destinataires rapports (virgule-séparés) |

## Structure des rôles

| Rôle | Droits |
|------|--------|
| **superadmin** | Tous les sites, tarifs, rapports complets, gestion utilisateurs |
| **site_admin** | Sites assignés uniquement, vouchers, export filtré |

## Apps Django

| App | Rôle |
|-----|------|
| `accounts` | Auth UniFi backend + rôles + gestion utilisateurs + espace partenaire |
| `sites_mgmt` | HotspotSite + VoucherTier (Standard / Remplacement / Admin) |
| `vouchers` | VoucherLog — créer / sync / supprimer via UniFi API |
| `dashboard` | KPIs + charts Chart.js (temps réel) |
| `reports` | Export PDF / Excel / CSV |
| `unifi_api` | Client HTTP pyunifi avec cache Redis (3–6 min TTL, pre-warm /2min) |
| `notifications` | Alertes stock (par forfait), génération auto, rapports mensuels, AdminVoucherGenLog |

## Forfaits (VoucherTier)

Trois types gérés depuis `/sites/tarifs/` :

| Type | Prix | Usage |
|------|------|-------|
| **Standard** | Libre (HTG) | Vente normale |
| **Remplacement** | 0 HTG | Offert — VoucherTier horodaté créé à la volée |
| **Admin** | 0 HTG | Accès admin — quantité limitée, régénération automatique à expiration |

- Assignation par site via M2M — un forfait peut couvrir plusieurs sites
- Forfait Admin par défaut créé automatiquement pour tout nouveau site (signal `post_save`)

## Notifications & Emails automatiques

### Alerte stock faible
- **Déclencheur** : < 30 vouchers disponibles **par forfait standard** sur un site
- **Filtre** : site doit avoir ≥ 1 device ET des sessions dans les 2 dernières semaines
- **Destinataires** : site_admins du site concerné (si notifications activées dans Configuration)
- **Cooldown** : 1 alerte maximum par forfait par site toutes les 24h
- **Fréquence de vérification** : toutes les 12 heures

### Génération automatique
Comportement selon les deux toggles dans Configuration :

| AutoGen | Notifications | Résultat |
|---------|--------------|----------|
| ON | OFF | Génération immédiate dès la 1ère détection |
| ON | ON | Alerte → délai configurable → génération |
| OFF | ON | Alerte uniquement |
| OFF | OFF | Bloqué en configuration |

- Génération **standard** : `count_per_tier` vouchers (défaut 100) par forfait standard sous le seuil
- Génération **admin** : `tier.max_vouchers` vouchers par forfait admin quand `today >= expires_at` (`AdminVoucherGenLog`)

### Rapport mensuel automatique
- **Déclencheur** : dernier jour du mois à 8h00 (heure Haïti)
- **Contenu** : 1 fichier Excel (feuille résumé global + 1 feuille par site) + 1 PDF (tableau récap + détail par site)
- **Destinataires** : emails dans `ADMIN_NOTIFY`

### Envoi manuel d'un rapport
```bash
python manage.py send_report_now           # 30 derniers jours
python manage.py send_report_now --days 60 # 60 derniers jours
```

## Exports disponibles

- **CSV** : données brutes (compatible Excel, Google Sheets)
- **Excel** : rapport multi-feuilles (résumé global + détail + par forfait + graphique)
- **PDF** : rapport formaté avec tableau récap par site + détail transactions

## Architecture Railway (3 services)

```
┌─────────────────────────────────────────────────────────┐
│  Railway Project : BonNet                               │
│                                                         │
│  [web]         Django + Gunicorn  → pages & API         │
│  [redis]       Redis              → cache partagé       │
│  [postgresql]  PostgreSQL         → données             │
│                                                         │
│  web ──REDIS_URL──► Redis    (cache vouchers/guests)    │
│  web ──DATABASE_URL──► PostgreSQL  (users, logs…)       │
│  web ──HTTPS──► p989.cloudunifi.com  (UniFi API)        │
│                 (appelé seulement par le pre-warm /2min) │
└─────────────────────────────────────────────────────────┘
```

```toml
# railway.toml
startCommand = "python manage.py migrate --noinput && python manage.py ensure_superadmin && gunicorn bonnet.wsgi --bind 0.0.0.0:$PORT --workers 1 --timeout 120"
```

> ⚠️ `--workers 1` obligatoire — APScheduler démarre dans chaque worker Gunicorn ; plusieurs workers créeraient des jobs en double.

### Ajout du service Redis
1. Railway → **Add Service → Database → Redis**
2. Copier la valeur de `REDIS_URL` depuis le service Redis
3. L'ajouter manuellement dans les variables du service web
4. Redéployer → le cache bascule automatiquement sur Redis

## Prochaines étapes suggérées

- [ ] Vérification du domaine `bon.net.ht` sur Resend pour l'envoi production
- [ ] QR codes sur les vouchers imprimés
- [ ] Notifications WhatsApp/SMS quand un device passe offline
- [ ] App mobile légère pour les vendeurs terrain
- [ ] Tableau comparatif performance entre sites
