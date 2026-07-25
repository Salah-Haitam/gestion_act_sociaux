"""
Configuration Django - Plateforme de Gestion des Actions Sociales (Marsa Maroc).
"""

import os
import sys
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def charger_env(chemin: Path) -> None:
    """
    Charge un fichier .env dans os.environ (sans ecraser l'existant).

    Volontairement minimal : evite une dependance supplementaire, et les
    variables reellement definies dans l'environnement restent prioritaires.
    """
    if not chemin.exists():
        return
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#") or "=" not in ligne:
            continue
        cle, _, valeur = ligne.partition("=")
        os.environ.setdefault(cle.strip(), valeur.strip().strip("\"'"))


charger_env(BASE_DIR / ".env")

SECRET_KEY = "django-insecure-marsa-maroc-actions-sociales-pfa-2026"
DEBUG = True
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "django_filters",
    "corsheaders",
    "core",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Africa/Casablanca"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Django REST Framework -------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_PAGINATION_CLASS": "core.pagination.StandardPagination",
    "PAGE_SIZE": 25,
    # Desactive la negociation de contenu par ?format= : le parametre est
    # utilise par nos vues d'export pour choisir entre Excel et PDF.
    "URL_FORMAT_OVERRIDE": None,
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=8),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# --- CORS (front React en dev) ---------------------------------------------
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
CORS_ALLOW_CREDENTIALS = True

# --- Metier ----------------------------------------------------------------
# Seuil (en %) de consommation du budget a partir duquel une alerte est levee.
BUDGET_ALERT_THRESHOLD = 80

# --- Assistant : renfort LLM (optionnel) -----------------------------------
# Sans clef, l'assistant fonctionne entierement avec son moteur a regles.
# Le LLM ne sert QU'A comprendre la question : il ne voit aucune donnee
# nominative et ne produit jamais de chiffre (voir core/llm.py).
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()
GROQ_MODELE = os.environ.get("GROQ_MODELE", "llama-3.3-70b-versatile").strip()
try:
    GROQ_TIMEOUT = float(os.environ.get("GROQ_TIMEOUT", "6"))
except ValueError:
    GROQ_TIMEOUT = 6.0
LLM_ACTIF = bool(GROQ_API_KEY)

# Garde-fou : la suite de tests ne doit jamais sortir sur le reseau, meme si un
# fichier .env est present. Sinon les tests deviennent non deterministes et
# consomment le quota de l'API.
if "test" in sys.argv:
    LLM_ACTIF = False
