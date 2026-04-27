# Prompt — Claude Code : App Mobile Flutter (Android Studio)

## Contexte

Tu construis **BonNet Mobile**, l'application Flutter pour les clients finaux de BonNet — un service de vente de vouchers WiFi en Haïti (monnaie : HTG, gourdes haïtiennes).

L'API backend est Django Ninja, accessible à `https://bon.net.ht/api/mobile/v1/`.
L'auth est Google Sign-In natif → JWT (access + refresh token).
Les paiements passent par **PlopPlop** (MonCash / NatCash) via WebView.
Les notifications push utilisent **Firebase Cloud Messaging (FCM)**.

---

## Stack Flutter

```yaml
# pubspec.yaml — dépendances principales
dependencies:
  flutter:
    sdk: flutter

  # Auth
  google_sign_in: ^6.2.1
  flutter_secure_storage: ^9.0.0   # Stocker JWT access + refresh token

  # HTTP
  dio: ^5.4.0                      # Client HTTP avec intercepteurs JWT

  # Navigation
  go_router: ^13.0.0

  # State management
  flutter_riverpod: ^2.5.0
  riverpod_annotation: ^2.3.0

  # UI
  cached_network_image: ^3.3.1     # Avatars Google
  flutter_svg: ^2.0.10
  shimmer: ^3.0.0                  # Loading skeletons

  # Paiement WebView
  webview_flutter: ^4.7.0

  # Notifications
  firebase_core: ^2.27.0
  firebase_messaging: ^14.7.0
  flutter_local_notifications: ^17.0.0

  # Utils
  intl: ^0.19.0                    # Formatage dates + montants HTG
  url_launcher: ^6.2.5             # Lien WhatsApp support
  package_info_plus: ^5.0.1

dev_dependencies:
  riverpod_generator: ^2.3.0
  build_runner: ^2.4.0
  flutter_lints: ^3.0.0
```

---

## Architecture — Structure des dossiers

```
lib/
  main.dart
  firebase_options.dart            # Généré par flutterfire configure

  core/
    api/
      api_client.dart              # Instance Dio + intercepteur JWT
      api_endpoints.dart           # Constantes des URLs
    auth/
      auth_service.dart            # Google Sign-In + échange token backend
      token_storage.dart           # flutter_secure_storage wrapper
    models/                        # Modèles Dart (fromJson/toJson)
      user_model.dart
      site_model.dart
      tier_model.dart
      order_model.dart
      order_item_model.dart
      voucher_code_model.dart
      campaign_model.dart
    providers/
      auth_provider.dart
      user_provider.dart
    router/
      app_router.dart              # go_router configuration
    theme/
      app_theme.dart               # Couleurs, typographie, thème global

  features/
    auth/
      screens/
        splash_screen.dart         # Vérif token → redirect
        login_screen.dart          # Bouton Google Sign-In
      providers/
        auth_state_provider.dart

    home/
      screens/
        home_screen.dart           # Shell avec bottom nav
      widgets/
        bottom_nav_bar.dart

    store/
      screens/
        sites_screen.dart          # Liste des sites WiFi
        tiers_screen.dart          # Forfaits d'un site
        checkout_screen.dart       # Récap panier avant paiement
        payment_webview_screen.dart # WebView PlopPlop
        order_confirmation_screen.dart # Codes livrés
      providers/
        sites_provider.dart
        tiers_provider.dart
        cart_provider.dart
        checkout_provider.dart

    orders/
      screens/
        orders_screen.dart         # Historique commandes
        order_detail_screen.dart   # Détail + codes vouchers
      providers/
        orders_provider.dart

    account/
      screens/
        account_screen.dart        # Profil + préférences
        edit_profile_screen.dart
      providers/
        account_provider.dart

    notifications/
      service/
        push_notification_service.dart  # Init FCM + handlers
      screens/
        notifications_screen.dart  # Liste notifications reçues (local)
```

---

## Auth — Google Sign-In → JWT

### Flux complet

```dart
// core/auth/auth_service.dart

class AuthService {
  final GoogleSignIn _googleSignIn = GoogleSignIn(
    scopes: ['email', 'profile'],
    // Utiliser le GOOGLE_CLIENT_ID de l'app mobile (fourni dans .env / dart-define)
  );

  Future<AuthResult> signInWithGoogle() async {
    // 1. Google Sign-In natif
    final account = await _googleSignIn.signIn();
    if (account == null) throw AuthCancelledException();

    // 2. Obtenir l'id_token Google
    final auth = await account.authentication;
    final idToken = auth.idToken;

    // 3. Envoyer au backend
    final response = await apiClient.post('/auth/google/', data: {
      'id_token': idToken,
      'platform': Platform.isAndroid ? 'android' : 'ios',
    });

    // 4. Stocker les tokens JWT
    await tokenStorage.saveTokens(
      access: response.data['access_token'],
      refresh: response.data['refresh_token'],
    );

    return AuthResult.fromJson(response.data['user']);
  }

  Future<void> signOut() async {
    // Supprimer le FCM token du backend avant de déconnecter
    final fcmToken = await FirebaseMessaging.instance.getToken();
    if (fcmToken != null) {
      await apiClient.delete('/auth/device-token/', data: {'fcm_token': fcmToken});
    }
    await _googleSignIn.signOut();
    await tokenStorage.clearTokens();
  }
}
```

### Intercepteur Dio — refresh automatique

```dart
// core/api/api_client.dart

// L'intercepteur doit :
// 1. Ajouter Authorization: Bearer <access_token> à chaque requête
// 2. Sur 401 : tenter un refresh automatique via /auth/refresh/
// 3. Si refresh échoue : déconnecter l'utilisateur et rediriger vers login
// 4. Retry la requête originale avec le nouveau access_token

class JwtInterceptor extends Interceptor {
  // ... implémenter la logique décrite ci-dessus
}
```

---

## Écrans — Comportement détaillé

### SplashScreen
- Vérifier si un access_token valide existe dans flutter_secure_storage
- Si oui → HomeScreen
- Si non mais refresh_token existe → tenter refresh → HomeScreen ou LoginScreen
- Si aucun token → LoginScreen
- Afficher le logo BonNet pendant le check (500ms minimum)

### LoginScreen
- Fond avec dégradé aux couleurs de BonNet
- Logo centré
- Bouton "Continuer avec Google" (style officiel Google Sign-In)
- Texte légal discret en bas

### HomeScreen (Shell)
Bottom navigation bar avec 4 onglets :
- 🌐 **Acheter** — `StoreTab` (sites → forfaits → paiement)
- 📋 **Mes commandes** — `OrdersTab`
- 🔔 **Notifications** — `NotificationsTab` (avec badge compteur)
- 👤 **Compte** — `AccountTab`

### StoreTab — Parcours d'achat

**SitesScreen**
- Grille de cards des sites actifs
- Chaque card : nom du site, ville, badge "X forfaits disponibles"
- Barre de recherche en haut (filtre local)
- Pull-to-refresh

**TiersScreen** (après sélection d'un site)
- Liste des forfaits du site sélectionné
- Card par forfait : durée formatée (ex: "1 heure", "24 heures", "7 jours"), prix en HTG
- Sélecteur de quantité (1–10) par forfait
- Bouton flottant "Voir le panier (X)" qui apparaît dès qu'un item est sélectionné

**CheckoutScreen**
- Récap des items sélectionnés (forfait, quantité, sous-total)
- Total en HTG bien visible
- Bouton "Payer avec MonCash / NatCash"
- Appel `POST /orders/checkout/` → récupère `payment_url`

**PaymentWebViewScreen**
- WebView qui charge `payment_url` PlopPlop
- Barre de progression en haut
- Détecter quand PlopPlop redirige vers `https://bon.net.ht/commande/` (la return URL)
- À cette détection : fermer le WebView → démarrer le polling

**OrderConfirmationScreen**
- Polling `GET /orders/{ref}/status/` toutes les 3 secondes
- Pendant le polling : animation de chargement avec message "Paiement en cours de vérification..."
- Timeout après 5 minutes → message d'erreur avec bouton "Contacter le support"
- Quand statut = "delivered" : afficher les codes vouchers en chips copiables (tap → copier dans le presse-papier + SnackBar "Code copié !")
- Animation de succès (confetti ou checkmark animé)

### OrdersScreen
- Liste des commandes passées, triées par date décroissante
- Card par commande : référence BONNET-XXXX, date, montant, statut coloré (badge)
- Pull-to-refresh + pagination infinie (load more au scroll bas)

### OrderDetailScreen
- En-tête : référence, date, statut, montant total
- Liste des items avec les codes vouchers
- Chaque code dans un chip avec bouton copie
- Bouton "Partager les codes" (share sheet natif)

### AccountScreen
- Avatar Google + nom + email
- Section **Préférences notifications** : deux toggles (notifs transactionnelles, notifs promo)
- Champ téléphone éditable
- Lien **Support WhatsApp** → `wa.me/+509XXXXXXXX` (numéro configurable)
- Bouton **Se déconnecter** (confirmation dialog)
- Version de l'app en bas

---

## Notifications Push Firebase

### Initialisation

```dart
// features/notifications/service/push_notification_service.dart

class PushNotificationService {
  Future<void> initialize() async {
    // 1. Demander les permissions (iOS + Android 13+)
    await FirebaseMessaging.instance.requestPermission(
      alert: true, badge: true, sound: true,
    );

    // 2. Récupérer le FCM token et l'envoyer au backend
    final token = await FirebaseMessaging.instance.getToken();
    if (token != null) await _registerTokenOnBackend(token);

    // 3. Écouter le renouvellement de token
    FirebaseMessaging.instance.onTokenRefresh.listen(_registerTokenOnBackend);

    // 4. Handler quand l'app est en foreground
    FirebaseMessaging.onMessage.listen(_handleForegroundMessage);

    // 5. Handler tap sur notif quand app en background/terminée
    FirebaseMessaging.onMessageOpenedApp.listen(_handleNotificationTap);
  }

  void _handleForegroundMessage(RemoteMessage message) {
    // Afficher via flutter_local_notifications
    // Incrémenter le badge sur l'onglet Notifications
  }

  void _handleNotificationTap(RemoteMessage message) {
    // Si data contient order_ref → naviguer vers OrderDetailScreen
    // Si data contient type=promo → naviguer vers StoreTab
  }
}
```

### Données FCM attendues du backend

```json
{
  "notification": { "title": "Tes codes sont prêts ✅", "body": "Ta commande BONNET-0042 est livrée." },
  "data": { "type": "order_delivered", "order_ref": "BONNET-0042" }
}
```

---

## Thème & Design

- **Couleurs primaires** : à définir en cohérence avec le dashboard web BonNet (bootstrap dark) — utiliser une palette bleue/verte tropicale
- **Typographie** : Inter ou Poppins (Google Fonts)
- **Mode** : Light mode uniquement pour la v1
- **Composants** :
  - Cards avec ombre légère et coins arrondis (radius 12)
  - Boutons pleins avec coins arrondis (radius 8)
  - Badges de statut colorés : vert (delivered), orange (pending), rouge (failed)
- Les montants HTG sont formatés : `1 500 HTG` (espace comme séparateur de milliers)
- Les durées sont humanisées : 60 min → "1 heure", 1440 min → "24 heures", 10080 min → "7 jours"

---

## Gestion d'erreurs

- **Pas de connexion** : SnackBar "Pas de connexion internet" + retry button
- **401 non récupérable** : redirect login + message "Session expirée"
- **500 backend** : message générique + lien support WhatsApp
- **Paiement timeout** : message clair + bouton "Vérifier mes commandes" (redirige vers OrdersScreen où la commande apparaîtra si elle a abouti)
- Tous les providers Riverpod doivent avoir un état `error` géré dans l'UI (pas de crash silencieux)

---

## Configuration Firebase

- Créer le projet Firebase : `bonnet-mobile`
- Activer **Cloud Messaging**
- Télécharger `google-services.json` (Android) et `GoogleService-Info.plist` (iOS)
- Exécuter `flutterfire configure` pour générer `firebase_options.dart`
- Le **FIREBASE_CREDENTIALS_JSON** (service account) est côté backend Django uniquement — Flutter n'a besoin que du `google-services.json`

---

## Variables de configuration Flutter

Utiliser `--dart-define` pour injecter les configs sensibles (pas de hardcode) :

```bash
flutter run \
  --dart-define=API_BASE_URL=https://bon.net.ht/api/mobile/v1 \
  --dart-define=GOOGLE_CLIENT_ID=XXXX.apps.googleusercontent.com \
  --dart-define=SUPPORT_WHATSAPP=+50912345678
```

```dart
// core/config.dart
class AppConfig {
  static const apiBaseUrl = String.fromEnvironment('API_BASE_URL', defaultValue: 'https://bon.net.ht/api/mobile/v1');
  static const googleClientId = String.fromEnvironment('GOOGLE_CLIENT_ID');
  static const supportWhatsapp = String.fromEnvironment('SUPPORT_WHATSAPP');
}
```

---

## Points d'attention

- **Offline first** : les commandes livrées doivent être lisibles même sans connexion (cache local avec Riverpod + keepAlive, ou Hive si besoin de persistence)
- **Sécurité** : les codes vouchers ne sont JAMAIS stockés en clair dans SharedPreferences — utiliser flutter_secure_storage ou ne pas les cacher localement du tout (rechargement depuis l'API)
- **Haiti context** : connexion souvent lente → timeouts Dio généreux (30s), images optimisées, pas de vidéo, skeleton loaders partout
- **Android prioritaire** pour la v1 (marché cible), iOS secondaire
- Le WebView PlopPlop doit désactiver le cache pour éviter des redirects en boucle
- Tester le polling sur une vraie connexion mobile lente (simulation 3G dans les device tools)
