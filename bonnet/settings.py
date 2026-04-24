import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

_secret_key = os.getenv('SECRET_KEY', '')
if not _secret_key:
    if os.getenv('DEBUG', 'True') == 'True':
        import warnings
        _secret_key = 'dev-insecure-key-not-for-production'
        warnings.warn('SECRET_KEY non définie — clé de dev utilisée, NE PAS déployer en prod sans SECRET_KEY.')
    else:
        raise RuntimeError('La variable SECRET_KEY doit être définie en production.')
SECRET_KEY = _secret_key
DEBUG = os.getenv('DEBUG', 'True') == 'True'
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')
RAILWAY_STATIC_URL = os.getenv('RAILWAY_STATIC_URL')
if RAILWAY_STATIC_URL or os.getenv('RAILWAY_ENVIRONMENT'):
    ALLOWED_HOSTS += ['.railway.app', '.up.railway.app', 'healthcheck.railway.app']
    if RAILWAY_STATIC_URL:
        ALLOWED_HOSTS.append(RAILWAY_STATIC_URL)

CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv('CSRF_TRUSTED_ORIGINS', 'http://localhost').split(',')
    if origin.strip()
]

# ─── Jazzmin (Django Admin customization) ────────────────────────��────────────
JAZZMIN_SETTINGS = {
    # ── Branding ──────────────────────────────────────────���───────────────────
    "site_title":  "BonNet Admin",
    "site_header": "BonNet",
    "site_brand":  "BonNet",
    "welcome_sign": "Administration BonNet",
    "copyright": "Transversal Haiti",
    "site_icon": None,
    "site_logo": None,

    # ── Navigation ────────────────────────────────────────────────────────────
    "topmenu_links": [
        {"name": "← Retour au site", "url": "/dashboard/", "new_window": False,
         "icon": "fas fa-arrow-left"},
    ],
    "usermenu_links": [
        {"name": "Profil BonNet", "url": "/accounts/profil/", "icon": "fas fa-user"},
    ],

    # ── Sidebar ───────────────────────────────────────────────────────────────
    "show_sidebar": True,
    "navigation_expanded": True,
    "hide_apps": [],
    "hide_models": [],
    "order_with_respect_to": [
        "accounts", "sites_mgmt", "vouchers", "dashboard", "reports",
    ],
    "icons": {
        "accounts":                    "fas fa-users-cog",
        "accounts.User":               "fas fa-user",
        "sites_mgmt":                  "fas fa-network-wired",
        "sites_mgmt.HotspotSite":      "fas fa-wifi",
        "sites_mgmt.PricingTier":      "fas fa-tags",
        "vouchers":                    "fas fa-ticket-alt",
        "auth":                        "fas fa-lock",
        "auth.Group":                  "fas fa-users",
    },
    "default_icon_parents": "fas fa-folder",
    "default_icon_children": "fas fa-circle",

    # ── UI ────────────────────────────────────────────────────────────────────
    "related_modal_active": True,
    "custom_css": None,
    "custom_js":  None,
    "use_google_fonts_cdn": False,
    "show_ui_builder": False,
    "changeform_format": "horizontal_tabs",
    "language_chooser": False,
}

JAZZMIN_UI_TWEAKS = {
    "navbar_small_text":    False,
    "footer_small_text":    False,
    "body_small_text":      False,
    "brand_small_text":     False,
    "brand_colour":         "navbar-dark",
    "accent":               "accent-primary",
    "navbar":               "navbar-dark",
    "no_navbar_border":     True,
    "navbar_fixed":         True,
    "layout_boxed":         False,
    "footer_fixed":         False,
    "sidebar_fixed":        True,
    "sidebar":              "sidebar-dark-primary",
    "sidebar_nav_small_text":  False,
    "sidebar_disable_expand":  False,
    "sidebar_nav_child_indent": True,
    "sidebar_nav_compact_style": False,
    "sidebar_nav_legacy_style":  False,
    "sidebar_nav_flat_style":    False,
    "theme":                "darkly",
    "dark_mode_theme":      None,
    "button_classes": {
        "primary":   "btn-primary",
        "secondary": "btn-secondary",
        "info":      "btn-info",
        "warning":   "btn-warning",
        "danger":    "btn-danger",
        "success":   "btn-success",
    },
}

INSTALLED_APPS = [
    'jazzmin',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Apps BonNet
    'accounts',
    'sites_mgmt',
    'vouchers',
    'dashboard',
    'reports',
    'notifications.apps.NotificationsConfig',
    'unifi_api',
    'store',
    'django_apscheduler',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'bonnet.middleware.RateLimitMiddleware',
]

ROOT_URLCONF = 'bonnet.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'notifications.context_processors.unread_notifications',
                'sites_mgmt.context_processors.site_config',
            ],
        },
    },
]

WSGI_APPLICATION = 'bonnet.wsgi.application'

# Base de données
# - En dev (DEBUG=True)  : SQLite, zéro config
# - En prod (Railway)    : PostgreSQL via DATABASE_URL injecté automatiquement
DATABASE_URL = os.getenv('DATABASE_URL')

if DATABASE_URL:
    # Railway injecte DATABASE_URL automatiquement → PostgreSQL
    import dj_database_url
    DATABASES = {
        'default': dj_database_url.config(
            default=DATABASE_URL,
            conn_max_age=600,   # connexions persistantes (évite reconnexion à chaque requête)
            ssl_require=True,
            conn_health_checks=True,  # Django 5.2 : ping avant réutilisation (évite connexions mortes)
        )
    }
else:
    # Dev local → SQLite, aucune installation nécessaire
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

AUTH_USER_MODEL = 'accounts.User'
LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/accounts/login/'

AUTHENTICATION_BACKENDS = [
    'accounts.backends.UniFiAuthBackend',
    'django.contrib.auth.backends.ModelBackend',
]

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = 'America/Port-au-Prince'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
_static_dir = BASE_DIR / 'static'
STATICFILES_DIRS = [_static_dir] if _static_dir.exists() else []
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# PlopPlop & Twilio
PLOPPLOP_CLIENT_ID  = os.getenv('PLOPPLOP_CLIENT_ID', '')
TWILIO_ACCOUNT_SID  = os.getenv('TWILIO_ACCOUNT_SID', '')
TWILIO_AUTH_TOKEN   = os.getenv('TWILIO_AUTH_TOKEN', '')
TWILIO_FROM_NUMBER  = os.getenv('TWILIO_FROM_NUMBER', '')

# UniFi Controller
UNIFI_HOST = os.getenv('UNIFI_HOST', 'p989.cloudunifi.com')
UNIFI_PORT = int(os.getenv('UNIFI_PORT', '8443'))
UNIFI_USERNAME = os.getenv('UNIFI_USERNAME', '')
UNIFI_PASSWORD = os.getenv('UNIFI_PASSWORD', '')
UNIFI_VERIFY_SSL = os.getenv('UNIFI_VERIFY_SSL', 'False') == 'True'

# Cache (Redis en prod, FileBasedCache en dev)
_REDIS_URL = os.getenv('REDIS_URL', '')
if _REDIS_URL:
    CACHES = {
        'default': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': _REDIS_URL,
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
                'IGNORE_EXCEPTIONS': True,
                'SOCKET_CONNECT_TIMEOUT': 5,
                'SOCKET_TIMEOUT': 5,
                'CONNECTION_POOL_KWARGS': {'max_connections': 50},
            },
            'TIMEOUT': 600,
        }
    }
    # Sessions dans Redis (pas en base) — réduit les queries DB de ~100% par requête
    SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
    SESSION_CACHE_ALIAS = 'default'
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
            'LOCATION': BASE_DIR / 'cache',
            'TIMEOUT': 300,
        }
    }

# Sessions : 8h, survit aux redéploiements
SESSION_COOKIE_AGE = 28800
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_SAVE_EVERY_REQUEST = False

# Sécurité HTTPS (activé uniquement en prod)
# Railway termine le SSL au niveau du proxy — on NE redirige PAS (SECURE_SSL_REDIRECT
# causerait une boucle de redirections sur les health checks internes HTTP de Railway).
# SECURE_PROXY_SSL_HEADER dit à Django que X-Forwarded-Proto: https = requête sécurisée.
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

# Messages
MESSAGE_STORAGE = 'django.contrib.messages.storage.session.SessionStorage'

# ── Resend (emails transactionnels) ──────────────────────────────────────────
RESEND_API_KEY = os.getenv('RESEND_API_KEY', '')
RESEND_FROM_EMAIL = os.getenv('RESEND_FROM_EMAIL', 'BonNet <noreply@bonnet.ht>')

# Emails destinataires du rapport mensuel (virgule-séparés)
ADMIN_NOTIFY = os.getenv('ADMIN_NOTIFY', '')

# APScheduler (fallback dev — désactivé en prod si Celery est configuré)
APSCHEDULER_DATETIME_FORMAT = "d/m/Y H:i:s"
APSCHEDULER_RUN_NOW_TIMEOUT = 25

# ── Celery ────────────────────────────────────────────────────────────────────
if _REDIS_URL:
    CELERY_BROKER_URL = _REDIS_URL
    CELERY_RESULT_BACKEND = _REDIS_URL
    CELERY_ACCEPT_CONTENT = ['json']
    CELERY_TASK_SERIALIZER = 'json'
    CELERY_RESULT_SERIALIZER = 'json'
    CELERY_TIMEZONE = TIME_ZONE
    CELERY_TASK_TRACK_STARTED = True
    CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

    # Beat schedule — remplace APScheduler en prod
    from celery.schedules import crontab
    CELERY_BEAT_SCHEDULE = {
        'prewarm-cache': {
            'task': 'unifi_api.prewarm_all_sites',
            'schedule': 120,                     # toutes les 2 min
        },
        'check-stock': {
            'task': 'notifications.tasks.check_stock_levels',
            'schedule': crontab(minute=0, hour='*/12'),
        },
        'send-monthly-report': {
            'task': 'notifications.tasks.send_monthly_reports',
            'schedule': crontab(minute=0, hour=8, day_of_month='28-31'),
        },
    }
