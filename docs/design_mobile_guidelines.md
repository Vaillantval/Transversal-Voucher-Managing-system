# BonNet Mobile — Design Guidelines Flutter

> Document de référence pour le design de l'application mobile client BonNet.  
> Objectif : cohérence totale avec le site store web (`bon.net.ht`) — même atmosphère, même professionnalisme, adapté au mobile.

---

## 1. Identité visuelle

### Logotype
```
Bon  → blanc   #FFFFFF   font-weight: 900
Net  → bleu    #3B82F6   font-weight: 900
```
- Police : **Inter** (Google Fonts) — à charger via `google_fonts` Flutter
- Toujours affiché côte à côte, pas de séparation, pas de tiret

### Signature de marque
- WiFi · Haïti
- Tagline optionnelle : *"Connectez votre quartier"*

---

## 2. Palette de couleurs

### Couleurs primaires (extraites du site)

| Token | Hex | Usage |
|-------|-----|-------|
| `bnBg` | `#07101F` | Fond global de l'app |
| `bnSurface` | `#0D1B2E` | Cards secondaires, bottom sheets |
| `bnCard` | `#111F33` | Cards principales, tiles, list items |
| `bnBorder` | `rgba(255,255,255, 0.08)` | Séparateurs, bordures de cards |
| `bnBlue` | `#3B82F6` | Couleur primaire — boutons, accents, liens |
| `bnBlueDark` | `#2563EB` | Pressed state, gradient end |
| `bnGreen` | `#10B981` | Succès, livraison, prix (gradient) |
| `bnText` | `#E2E8F0` | Texte principal |
| `bnMuted` | `#64748B` | Texte secondaire, labels, placeholders |
| `bnDanger` | `#EF4444` | Erreur, déconnexion |
| `bnAmber` | `#FBBF24` | Zone admin/partenaires uniquement |
| `bnPurple` | `#8B5CF6` | Accent décoratif (orbes, gradients) |

### Gradients clés

```dart
// Gradient principal (fond de slides, hero)
LinearGradient(
  begin: Alignment.topLeft,
  end: Alignment.bottomRight,
  colors: [Color(0xFF07101F), Color(0xFF0D2145)],
)

// Gradient prix / CTA principal
LinearGradient(
  begin: Alignment.topLeft,
  end: Alignment.bottomRight,
  colors: [Color(0xFF3B82F6), Color(0xFF10B981)],
)

// Gradient bouton primaire
LinearGradient(
  begin: Alignment.topLeft,
  end: Alignment.bottomRight,
  colors: [Color(0xFF3B82F6), Color(0xFF2563EB)],
)

// Gradient avatar / initiales utilisateur
LinearGradient(
  begin: Alignment.topLeft,
  end: Alignment.bottomRight,
  colors: [Color(0xFF3B82F6), Color(0xFF6366F1)],
)
```

### Mode sombre exclusif
L'app est **dark-only**. Pas de light mode — le site web est 100% sombre et l'app doit l'être aussi.

---

## 3. Typographie

**Police principale : Inter**

```dart
// pubspec.yaml
google_fonts: ^6.x
```

| Rôle | Taille | Weight | Couleur |
|------|--------|--------|---------|
| Logo / Brand | 26sp | 900 (Black) | white + blue |
| Titre écran | 22sp | 800 (ExtraBold) | `bnText` |
| Titre section | 18sp | 700 (Bold) | `bnText` |
| Prix plan | 32sp | 900 | gradient bleu→vert |
| Corps texte | 15sp | 400 | `bnText` |
| Label bouton | 15sp | 600 (SemiBold) | white |
| Texte secondaire | 13sp | 400 | `bnMuted` |
| Caption / Badge | 11sp | 600 | selon contexte |
| Durée plan | 13sp | 400 | `bnMuted` |

---

## 4. Composants UI

### 4.1 Cartes (Cards)

```
background : #111F33
border     : 1px solid rgba(255,255,255, 0.08)
borderRadius : 16px
elevation  : 0 (pas de shadow Material par défaut)
```

**Hover / pressed state :**
```
border-color : #3B82F6
box-shadow   : 0 20px 60px rgba(59,130,246, 0.18)
translateY   : -4px (AnimatedContainer)
```

Exemple Flutter :
```dart
Container(
  decoration: BoxDecoration(
    color: Color(0xFF111F33),
    borderRadius: BorderRadius.circular(16),
    border: Border.all(color: Colors.white.withOpacity(0.08)),
  ),
)
```

---

### 4.2 Boutons

**Bouton primaire (gradient)**
```
gradient    : #3B82F6 → #2563EB (135°)
borderRadius : 10px
padding     : 14px vertical, 24px horizontal
font        : Inter 15sp SemiBold white
```

**Bouton outline**
```
border      : 1.5px solid #3B82F6
color       : #3B82F6
borderRadius : 10px
→ pressed : fond #3B82F6, texte white
```

**Bouton Google Sign-In**  
Utiliser le vrai logo SVG Google multicolore (comme sur le site).  
Background : `linear-gradient(#1D4ED8, #6366F1)` avec animation de glow pulsante.

---

### 4.3 Inputs / Champs de texte

```
background  : #111F33
border      : 1px solid rgba(255,255,255,0.08)
borderRadius : 10px
focusedBorder : 1px solid #3B82F6 + ring rgba(59,130,246,0.2)
textColor   : #E2E8F0
hintColor   : #64748B
```

---

### 4.4 Sélection de forfait (Tier Cards)

Petites cartes horizontalement scrollables :
```
minWidth    : 90px
padding     : 12px 8px
border      : 1.5px solid rgba(255,255,255,0.08)
borderRadius : 10px

— Selected —
border-color : #3B82F6
background   : rgba(59,130,246, 0.14)
```

Structure interne :
```
[durée]   → 12sp muted (ex: "24h")
[prix]    → 17sp 800 blue (ex: "150 HTG")
```

---

### 4.5 Badges / Pills

```dart
// Badge statut commande
'pending'    → amber    background rgba(251,191,36,.15)
'processing' → blue     background rgba(59,130,246,.15)
'paid'       → blue     background rgba(59,130,246,.15)
'delivered'  → green    background rgba(16,185,129,.15)
'failed'     → red      background rgba(239,68,68,.15)
```

---

### 4.6 Codes voucher (affichage post-livraison)

C'est l'écran le plus important — les codes WiFi que l'utilisateur vient d'acheter.

```
card background  : #111F33
border           : 1px solid rgba(59,130,246,0.3)
code font        : monospace (JetBrains Mono ou Roboto Mono), 22sp, bold
code color       : #3B82F6
padding          : 20px
borderRadius     : 12px
```

Bouton copier code : icon clipboard, tap → feedback SnackBar vert "Code copié !"  
Bouton partager : `Share.share()` natif Flutter.

---

### 4.7 Avatar utilisateur

```
shape       : Circle
size        : 40px (navbar), 56px (profil)
fallback    : initiale du prénom sur gradient bleu→indigo
border      : 2px solid rgba(255,255,255,0.08)
```

---

## 5. Navigation

### Bottom Navigation Bar (recommandée)
4 onglets :

| # | Icône | Label | Route |
|---|-------|-------|-------|
| 1 | `wifi` | Accueil | Storefront — plans + sites |
| 2 | `receipt_long` | Commandes | Historique achats |
| 3 | `bell_outline` | Notifs | (phase ultérieure) |
| 4 | `person` | Compte | Profil + paramètres |

```
background      : #0D1B2E
selectedColor   : #3B82F6
unselectedColor : #64748B
indicator       : rgba(59,130,246,0.15) pill
borderTop       : 1px solid rgba(255,255,255,0.08)
```

### AppBar
```
background      : rgba(7,16,31,0.92) + backdrop blur
elevation       : 0
titleStyle      : Inter 18sp Bold white
leading         : back arrow en #E2E8F0
```

---

## 6. Écrans — recommandations par page

### 6.1 Splash / Onboarding
- Fond `#07101F`
- Logo centré animé (fade-in + scale 0.8→1)
- Optionnel : orbe bleue floue en arrière-plan (positioned, blur 80, opacity 0.25)
- Transition vers login après 1.5s ou vérification du token JWT

### 6.2 Login (Google Sign-In)
- Fond dégradé `#07101F → #0D2145`
- Logo grand centré
- Tagline en `bnMuted`
- Bouton Google Sign-In avec animation de glow pulsante (comme le site)
- Pas de formulaire email/mot de passe

### 6.3 Storefront — Accueil
- **Hero slider** : Swiper/PageView avec bannières (fetch `/store/banners/`)
  - Fond slide : gradient `#07101F → #0D2145`
  - Image en opacité 0.18 en fond
  - Titre bold blanc, sous-titre muted
  - Indicateurs (dots) en bas, bleu pour le actif
- **Sélection de site** : dropdown ou bottom sheet — chercher par nom/GPS
- **Grille de forfaits** : 2 colonnes, tier cards avec animation hover
  - Prix en gradient bleu→vert, `32sp 900`
  - Durée en muted
  - CTA "Acheter" bouton primaire pleine largeur

### 6.4 Checkout / Paiement
- Récap commande : site, forfait, quantité, total HTG
- Saisie nom + téléphone (pré-remplis si profil existant)
- Choix méthode : MonCash / NatCash (2 cartes sélectionnables)
- Bouton "Payer — XXX HTG" → ouvre WebView PlopPlop
- WebView : intercepter URL `bon.net.ht/commande/` pour fermer et démarrer le polling

### 6.5 Confirmation de paiement (Polling)
- Indicateur de chargement animé (spinner bleu)
- Texte : "Vérification du paiement…"
- Poll toutes les 3s sur `/orders/{ref}/status/`
- Transition automatique vers 6.6 quand `status = delivered`

### 6.6 Codes voucher (écran clé)
- Fond `#07101F`
- ✅ checkmark animé (scale pop) en vert `#10B981`
- Titre : "Tes codes sont prêts !"
- Card(s) par voucher avec code en monospace bleu
- Bouton "Copier" sur chaque code
- Bouton "Partager tous les codes"
- Bouton secondaire "Voir mes commandes"

### 6.7 Historique commandes
- Liste / ListView.builder
- Chaque item : référence, date, statut (badge coloré), total HTG
- Tap → détail commande (6.6 pour les delivered)
- Pull-to-refresh

### 6.8 Profil / Compte
- Avatar (photo Google ou initiale)
- Nom + email (non modifiables)
- Téléphone (modifiable via PATCH /account/me/)
- Toggles : Notifications promos / Notifications transactions
- Bouton Déconnexion (danger, rouge)

---

## 7. Animations & Motion

Garder les mêmes patterns que le site :

| Élément | Animation |
|---------|-----------|
| Cards au chargement | Fade-in + slide up 24px, durée 400ms |
| Tap sur card | Scale 0.97 + légère surbrillance de bordure |
| Bouton primaire hover | Scale 1.02, durée 150ms |
| Codes voucher apparition | Scale 0→1 pop (élastique), delayé par index |
| Spinner de polling | Rotation continue, couleur `bnBlue` |
| SnackBar copie code | Slide-in bas, fond `bnGreen`, durée 1.5s |
| Orbes décoratives (optionnel) | Drift lent 8s ease-in-out infinite alternate |
| Glow bouton Google | Pulse 2.8s (shadow 0→8px→0) |

---

## 8. Iconographie

- Pack recommandé : **Material Symbols** (outlined) ou **Phosphor Icons** Flutter
- Taille standard : 22px
- Couleur active : `bnBlue #3B82F6`
- Couleur inactive : `bnMuted #64748B`

Icônes clés à utiliser :
```
wifi          → signal WiFi (marque)
receipt_long  → commandes
copy          → copier code voucher
share         → partager codes
check_circle  → livraison réussie
timer         → durée forfait
payments      → paiement / MonCash
person        → compte
bell          → notifications
arrow_back    → retour
```

---

## 9. Espacements & Grille

```
Margin horizontal global : 16px (mobile), 24px (tablette)
Padding card interne     : 16px
Gap entre cards          : 12px
Gap entre sections       : 32px
Border radius standard   : 16px (cards), 10px (boutons/inputs), 8px (badges)
```

---

## 10. Structure projet Flutter recommandée

```
lib/
  core/
    theme/
      app_colors.dart     ← toutes les constantes de couleur
      app_text_styles.dart
      app_theme.dart      ← ThemeData dark
    widgets/
      bn_card.dart        ← Card réutilisable avec style BonNet
      bn_button.dart      ← Bouton gradient primaire
      bn_badge.dart       ← Badge statut coloré
      voucher_code_card.dart
  features/
    auth/
    store/
    orders/
    account/
  services/
    api_service.dart      ← HTTP client → https://bon.net.ht/api/mobile/v1/
    auth_service.dart     ← JWT storage (flutter_secure_storage)
```

---

## 11. Packages Flutter recommandés

| Package | Rôle |
|---------|------|
| `google_sign_in` | Auth Google natif |
| `flutter_secure_storage` | Stocker access + refresh JWT |
| `dio` ou `http` | Appels API REST |
| `google_fonts` | Police Inter |
| `card_swiper` ou `carousel_slider` | Slider bannières |
| `webview_flutter` | WebView paiement PlopPlop |
| `share_plus` | Partager les codes voucher |
| `firebase_messaging` | Réception push FCM |
| `flutter_local_notifications` | Afficher les push en foreground |
| `cached_network_image` | Images bannières avec cache |
| `shimmer` | Skeleton loading (chargement listes) |

---

## 12. Cohérence avec le site web

| Élément web | Équivalent mobile |
|-------------|-------------------|
| Slider Swiper.js | PageView + PageViewDotIndicator |
| Modal sélection site + tier | Bottom Sheet + tier cards |
| Compte panel dropdown | Drawer ou Bottom Sheet profil |
| `.plan-card:hover` translateY(-6px) | AnimatedContainer scale sur tap |
| `.btn-bn-primary` gradient | `DecoratedBox` + gradient + InkWell |
| `.plan-price` gradient text | `ShaderMask` + LinearGradient |
| Orbes animées partenaires | `AnimatedBuilder` + `BackdropFilter` (optionnel) |
| Dark theme global | `ThemeData.dark()` + couleurs custom |

---

*Généré le 2026-04-27 — à mettre à jour lors d'évolutions du design web.*
