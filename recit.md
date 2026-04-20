# BonNet — Récit fonctionnel

## Rôles utilisateurs

### Superadmin
Accès total à l'application. Synchronisé depuis le compte UniFi (marqué `is_super`).

| Fonctionnalité | Détail |
|----------------|--------|
| Tableau de bord | Tous les sites, KPIs globaux et par site, clients connectés live |
| Vouchers | Créer, supprimer, voir le stock sur tous les sites |
| Rapports | Exporter PDF / Excel / CSV pour n'importe quel site ou tous les sites |
| Gestion utilisateurs | Voir, modifier le rôle, assigner des sites, supprimer des comptes |
| Tarifs (VoucherTier) | Créer / modifier les forfaits (durée, prix HTG) via l'admin Django |
| Sites | Activer / désactiver des sites, activer la génération automatique par site |
| Configuration | Modifier le footer de la page de connexion, uploader les logos (PNG/JPG) |
| Notifications | Voir toutes les alertes (tous les sites) |

### Site Admin
Accès limité aux sites qui lui sont assignés. Synchronisé depuis les admins UniFi du site.

| Fonctionnalité | Détail |
|----------------|--------|
| Tableau de bord | Uniquement ses sites assignés, mêmes KPIs mais filtrés |
| Vouchers | Créer et supprimer des vouchers sur ses sites uniquement |
| Rapports | Exporter PDF / Excel / CSV filtré sur ses sites |
| Notifications | Alertes de ses sites uniquement |
| Gestion utilisateurs | ✗ Pas d'accès |
| Tarifs / Sites / Configuration | ✗ Pas d'accès |

---

## Fonctionnalités du site

### Tableau de bord
- KPIs en temps réel : sessions vendues, sessions actives, stock disponible, revenus (HTG)
- Période configurable : 7j / 30j / 90j / 12 mois, ou valeur+unité personnalisée
- Graphique des revenus par jour (Chart.js)
- Répartition par forfait (camembert)
- Tableau par site : sessions, stock, revenus, clients live
- Revenus par site (top 10, histogramme)
- Liste des clients connectés live (mode site unique)
- Liste des devices UniFi (online / offline) avec statut en couleur
- Admins assignés au site sélectionné
- Avertissement si le contrôleur UniFi est inaccessible

### Gestion des vouchers
- Création par forfait (durée + prix HTG) avec note personnalisée
- Sélection du site (superadmin) ou site automatique (site_admin)
- Suppression unitaire
- Synchronisation avec UniFi en temps réel
- Affichage du stock disponible par site
- Filtrage par site

### Exports & Rapports
- **CSV** : données brutes, compatible tout tableur
- **Excel** : 3 feuilles (résumé global, détail sessions, répartition par forfait + graphique en barres)
- **PDF** : rapport formaté paysage, KPIs en bannière, tableau des sessions, total en bas de page
- Logos de l'organisation en en-tête PDF (si format PNG/JPG)
- Filtres : site + période (du … au …)
- Téléchargement uniquement sur clic — pas de déclenchement automatique

### Notifications
- Centre de notifications avec badges non-lus
- Types : alerte stock faible, génération automatique, rapport mensuel
- Cliquables : redirige vers la page vouchers du site concerné
- Filtres : Toutes / Non lues / Auto-générées
- Marquage lu individuel ou tout marquer

### Génération automatique de vouchers
- **Activation** : par site, option `auto_generate_vouchers` activée par le superadmin
- **Déclencheur** : si un site a ≤ 30 vouchers disponibles depuis plus de 36h sans intervention manuelle
- **Quantité** : 100 vouchers × chaque forfait actif
- **Nom** : `{Forfait}_{Nom du site}_{Date en français}` — ex : `Forfait 12h_Kay Valcin_20 Avril 2026`
- **Conditions** : le site doit avoir ≥ 1 device ET des sessions dans les 2 dernières semaines
- **Email** : notification envoyée aux emails `ADMIN_NOTIFY` avec détail par forfait
- **Notification** : entrée créée dans le centre de notifications

### Alerte stock faible
- **Seuil** : ≤ 30 vouchers disponibles
- **Cooldown** : 1 alerte maximum par site toutes les 24h
- **Destinataires** : les site_admins du site concerné (email)
- **Conditions** : site actif avec device et sessions récentes (2 dernières semaines)
- **Fréquence de vérification** : toutes les 12h (APScheduler)

### Rapport mensuel automatique
- **Déclencheur** : dernier jour du mois à 8h00 (heure Haïti)
- **Contenu** : fichier Excel multi-feuilles + PDF récapitulatif
- **Destinataires** : emails listés dans `ADMIN_NOTIFY`
- **Envoi manuel** : `python manage.py send_report_now [--days N]`

### Cache & Performance
- Cache Redis partagé entre tous les workers Gunicorn
- Job de pré-chargement toutes les 2 minutes (vouchers, guests, stats de tous les sites)
- TTL : vouchers 3 min, guests 6 min — le dashboard lit toujours depuis le cache
- Appels UniFi effectués uniquement par le job de pre-warm, pas lors des requêtes utilisateurs

### Configuration du site (superadmin)
- Footer personnalisable de la page de connexion
- Upload de 2 logos (PNG/JPG) affichés sur la page de connexion et dans le drawer
- Les logos apparaissent en en-tête des exports PDF (formats raster uniquement)

### Authentification
- Login avec identifiants UniFi (synchronisation automatique des admins)
- Option "Se souvenir de moi" (session 30 jours) ou session 8h par défaut
- Déconnexion depuis la page Profil
- Redirection vers la page demandée après login

### Thème
- Mode clair / sombre basculable depuis la barre de navigation
- Préférence mémorisée en `localStorage`
- Compatible tous les écrans (sidebar scrollable sur mobile)
