from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parents[2]

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
    CORS_ALLOWED_ORIGINS=(list, ["http://localhost:3000"]),
    CSRF_TRUSTED_ORIGINS=(list, ["http://localhost:3000"]),
)
environ.Env.read_env(BASE_DIR.parent / ".env")

SECRET_KEY = env(
    "DJANGO_SECRET_KEY",
    default="unsafe-development-key-change-before-production-1234567890",
)
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "drf_spectacular",
    "common",
    "organizations",
    "accounts",
    "audit",
    "reference",
    "customers",
    "documents",
    "travelers",
    "catalog",
    "trips",
    "pricing",
    "bookings",
    "finance",
    "partners",
    "notifications",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

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
    }
]

DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default="postgresql://travel_erp:travel_erp@localhost:35432/travel_erp",
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = ["accounts.backends.RolePermissionBackend"]

CORS_ALLOWED_ORIGINS = env("CORS_ALLOWED_ORIGINS")
CSRF_TRUSTED_ORIGINS = env("CSRF_TRUSTED_ORIGINS")

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["accounts.authentication.CookieJWTAuthentication"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
}

AUTH_COOKIE_ACCESS = "travel_erp_access"
AUTH_COOKIE_REFRESH = "travel_erp_refresh"
AUTH_COOKIE_SECURE = not DEBUG
AUTH_COOKIE_SAMESITE = "Lax"
AUTH_COOKIE_PATH = "/"
CORS_ALLOW_CREDENTIALS = True
MAX_DOCUMENT_SIZE_BYTES = 10 * 1024 * 1024
PRIVATE_PASSPORT_ROOT = BASE_DIR / "private-passports"
ALLOWED_DOCUMENT_MIME_TYPES = ["application/pdf", "image/jpeg", "image/png", "image/webp"]

SPECTACULAR_SETTINGS = {
    "TITLE": "Travel ERP API",
    "DESCRIPTION": "Tenant-isolated API for the Travel ERP.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "ENUM_NAME_OVERRIDES": {
        "PassportStatusEnum": "travelers.models.Passport.Status",
        "TripStatusEnum": "trips.models.Trip.Status",
        "CustomerKindEnum": "customers.models.Customer.Kind",
        "QuoteLineKindEnum": "pricing.models.QuoteLine.Kind",
        "FinancialTransactionKindEnum": "finance.models.FinancialTransaction.Kind",
        "PartnerAllocationKindEnum": "partners.models.PartnerAllocation.Kind",
        "CommissionPaymentKindEnum": "partners.models.CommissionPayment.Kind",
    },
}
