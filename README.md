# BonNet — Gestion Vouchers WiFi Haiti

Application Django pour la gestion des coupons de connexion internet
sur les sites Starlink/UniFi déployés en zones reculées d'Haiti.

## Stack
- **Backend** : Django 4.2 + PostgreSQL
- **API UniFi** : pyunifi (connexion au contrôleur p989.cloudunifi.com)
- **Export** : reportlab (PDF), openpyxl (Excel), csv natif
- **Frontend** : Bootstrap 5 + Chart.js (inclus via CDN)

## Installation

```bash
# 1. Cloner / extraire le projet
cd bonnet_project

# 2. Environnement virtuel
python -m venv venv
source venv/bin/activate      # Linux/Mac
venv\Scripts\activate         # Windows

# 3. Dépendances
pip install -r requirements.txt

# 4. Configuration
cp .env.example .env
# → Remplir .env avec vos infos UniFi et base de données

# 5. Base de données
createdb bonnet_db
python manage.py migrate

# 6. Super-admin
python manage.py createsuperuser

# 7. Lancer
python manage.py runserver
```

## Structure des rôles

| Rôle | Droits |
|------|--------|
| **Super Admin** | Tous les sites, définir les tarifs, rapports financiers complets, exporter |
| **Site Admin** | Sites assignés uniquement, créer/voir les vouchers, export filtré |

## Tarifs vouchers (exemple)

| Forfait | Durée | Prix |
|---------|-------|------|
| Forfait 6h  | 0–360 min   | 25 HTG |
| Forfait 12h | 361–720 min | 50 HTG |
| Forfait 24h | 721–1440 min | 75 HTG |
| Forfait 72h | 1441–4320 min | 150 HTG |

Les tranches sont configurables dans l'interface Super Admin → **Tarifs**.

## API UniFi utilisée

- `GET  /api/s/<site>/stat/voucher`  → liste des vouchers
- `POST /api/s/<site>/cmd/hotspot`   → créer / supprimer un voucher
- Auth via `/api/login` avec session cookie

## Exports disponibles

- **CSV** : données brutes (compatible Excel, Google Sheets)
- **Excel** : rapport multi-feuilles (détail + résumé par site)
- **PDF** : rapport formaté pour impression / archivage comptable

## Prochaines étapes suggérées

- [ ] Sync automatique via Celery Beat (toutes les 15 min)
- [ ] Notifications WhatsApp/SMS quand un device passe offline
- [ ] QR codes sur les vouchers imprimés
- [ ] App mobile légère pour les vendeurs terrain
- [ ] Tableau comparatif performance entre sites (RevPAR WiFi)
