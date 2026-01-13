import os
import logging
from pathlib import Path
import dj_database_url

# Configuración para despliegue en Render
logger = logging.getLogger(__name__)

# Ruta base del proyecto
BASE_DIR = Path(__file__).resolve().parent.parent

# Secret key y debug obtenidos de variables de entorno
SECRET_KEY = os.getenv('SECRET_KEY')
DEBUG = os.getenv('DEBUG') == 'True'

# Configuraciones de seguridad
SECURE_SSL_REDIRECT = not DEBUG
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# ALLOWED_HOSTS configurado a partir de variable de entorno
ALLOWED_HOSTS_ENV = os.getenv('ALLOWED_HOSTS', '')
if ALLOWED_HOSTS_ENV:
    ALLOWED_HOSTS = ALLOWED_HOSTS_ENV.split(',')
else:
    # Fallback para producción en Render
    ALLOWED_HOSTS = [
        'aremko-booking-system.onrender.com', 
        'aremko-booking-system-prod.onrender.com',  # Dominio de producción actual
        'www.aremko.cl',  # Dominio personalizado
        'aremko.cl',  # Dominio personalizado sin www
        '.onrender.com', 
        'localhost', 
        '127.0.0.1',
        'testserver'  # Para testing
    ]

# CSRF_TRUSTED_ORIGINS para HTTPS
CSRF_TRUSTED_ORIGINS_ENV = os.getenv('CSRF_TRUSTED_ORIGINS', '')
if CSRF_TRUSTED_ORIGINS_ENV:
    CSRF_TRUSTED_ORIGINS = CSRF_TRUSTED_ORIGINS_ENV.split(',')
else:
    # Fallback para producción en Render
    CSRF_TRUSTED_ORIGINS = [
        'https://www.aremko.cl',
        'https://aremko.cl',
        'https://aremko-booking-system-prod.onrender.com',
    ]

# Aplicaciones instaladas
INSTALLED_APPS = [
    # Aplicaciones de Django por defecto
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize', # Add humanize app
    'django.contrib.sitemaps', # Enable sitemaps

    # Aplicaciones propias
    'ventas',
    'control_gestion',  # Módulo de Control de Gestión

    # Aplicaciones de terceros
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',
    'storages', # Add django-storages
    'solo',     # Add django-solo
    'anymail',  # Email integration

    # Cloudinary al final para no interferir con static files
    'cloudinary_storage',  # Cloudinary storage
    'cloudinary',  # Cloudinary
]

# MIDDLEWARE
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',  # Debe ir antes de AuthenticationMiddleware
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'ventas.middleware.ThreadLocalMiddleware',  # Agregar aquí el nuevo middleware
    'ventas.middleware_debug.DebugImageUploadMiddleware',  # Debug temporal
]

ROOT_URLCONF = 'aremko_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        # Standard practice: Point DIRS to a project-level templates directory
        # Even if it doesn't exist, APP_DIRS=True will still find app templates.
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True, # This allows Django to find templates in installed apps (like admin)
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',  # Necesario para la barra de navegación del admin
                'django.contrib.auth.context_processors.auth',  # Necesario
                'django.template.context_processors.i18n',
                'django.template.context_processors.media',
                'django.template.context_processors.static',
                'django.template.context_processors.tz',
                'django.contrib.messages.context_processors.messages',  # Necesario
                'ventas.context_processors.categorias_processor', # Add category processor
            ],
        },
    },
]

WSGI_APPLICATION = 'aremko_project.wsgi.application'

# Configuración de la base de datos
DATABASES = {
    'default': {
        **dj_database_url.config(default=os.getenv('DATABASE_URL')),
        'CONN_MAX_AGE': 600,  # Reutilizar conexiones por 10 minutos (reduce overhead de handshake)
        'OPTIONS': {
            'connect_timeout': 10,  # Timeout de conexión a 10 segundos
        }
    }
}

# Configuraciones adicionales...
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True

# Cache configuration (reduce queries repetidas)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
        'OPTIONS': {
            'MAX_ENTRIES': 1000
        }
    }
}

LANGUAGE_CODE = 'es-cl'
TIME_ZONE = 'America/Santiago'
USE_I18N = True
USE_L10N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files configuration (Cloudinary > GCS > Local)
# Configuración de Cloudinary (Prioridad 1)
CLOUDINARY_CLOUD_NAME = os.getenv('CLOUDINARY_CLOUD_NAME')
CLOUDINARY_API_KEY = os.getenv('CLOUDINARY_API_KEY')
CLOUDINARY_API_SECRET = os.getenv('CLOUDINARY_API_SECRET')

if CLOUDINARY_CLOUD_NAME and CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET:
    # Usar Cloudinary SOLO para archivos media, NO para static
    DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'

    # IMPORTANTE: Mantener WhiteNoise para archivos estáticos
    # (No cambiar STATICFILES_STORAGE)

    # Configuración de Cloudinary
    CLOUDINARY_STORAGE = {
        'CLOUD_NAME': CLOUDINARY_CLOUD_NAME,
        'API_KEY': CLOUDINARY_API_KEY,
        'API_SECRET': CLOUDINARY_API_SECRET,
        'SECURE': True,  # Usar HTTPS
    }

    # IMPORTANTE: MEDIA_URL debe configurarse explícitamente
    # django-cloudinary-storage NO lo configura automáticamente
    MEDIA_URL = f'https://res.cloudinary.com/{CLOUDINARY_CLOUD_NAME}/'

    logger.info(f"✅ Cloudinary configurado para media: cloud_name={CLOUDINARY_CLOUD_NAME}")

# Fallback a GCS (Prioridad 2 - Retrocompatibilidad)
elif os.getenv('GCS_CREDENTIALS_JSON'):
    try:
        import json
        credentials_data = json.loads(os.getenv('GCS_CREDENTIALS_JSON'))
        credentials_path = Path('/tmp/gcs-credentials.json')
        with open(credentials_path, 'w') as f:
            json.dump(credentials_data, f)
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = str(credentials_path)

        DEFAULT_FILE_STORAGE = 'storages.backends.gcloud.GoogleCloudStorage'
        GS_BUCKET_NAME = os.getenv('GS_BUCKET_NAME', 'aremko-media-prod')
        GS_PROJECT_ID = credentials_data.get('project_id', os.getenv('GS_PROJECT_ID'))
        GS_FILE_OVERWRITE = False
        GS_QUERYSTRING_AUTH = False
        GS_DEFAULT_ACL = 'publicRead'
        MEDIA_URL = f'https://storage.googleapis.com/{GS_BUCKET_NAME}/'

        logger.info(f"✅ GCS configurado: bucket={GS_BUCKET_NAME}")
    except Exception as e:
        logger.error(f"❌ Error configurando GCS: {e}")
        MEDIA_URL = '/media/'
        MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Fallback a almacenamiento local (Prioridad 3)
else:
    MEDIA_URL = '/media/'
    MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
    logger.warning("⚠️ Cloudinary/GCS no configurados - usando almacenamiento local")


REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ]
}

# For development
CORS_ALLOW_ALL_ORIGINS = True  # Only use this in development!

# For production, specify allowed origins:
# CORS_ALLOWED_ORIGINS = [
#     "http://localhost:8000",
#     "http://127.0.0.1:8000",
#     "https://your-production-domain.com",
# ]

# --- Configuración SMS Redvoiss ---
REDVOISS_API_URL = os.getenv('REDVOISS_API_URL', 'https://sms.lanube.cl/services/rest')
REDVOISS_USERNAME = os.getenv('REDVOISS_USERNAME', '')
REDVOISS_PASSWORD = os.getenv('REDVOISS_PASSWORD', '')

# --- Configuración IA para Campañas de Email ---
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY', '')
DEEPSEEK_MODEL = os.getenv('DEEPSEEK_MODEL', 'deepseek-chat')
AI_VARIATION_PROVIDER = os.getenv('AI_VARIATION_PROVIDER', 'deepseek')
AI_VARIATION_ENABLED = os.getenv('AI_VARIATION_ENABLED', 'true').lower() == 'true'
AI_ANTI_SPAM_ENABLED = os.getenv('AI_ANTI_SPAM_ENABLED', 'true').lower() == 'true'

# --- Límites Anti-Spam Comunicación ---
SMS_DAILY_LIMIT_PER_CLIENT = int(os.getenv('SMS_DAILY_LIMIT_PER_CLIENT', '2'))
SMS_MONTHLY_LIMIT_PER_CLIENT = int(os.getenv('SMS_MONTHLY_LIMIT_PER_CLIENT', '8'))
EMAIL_WEEKLY_LIMIT_PER_CLIENT = int(os.getenv('EMAIL_WEEKLY_LIMIT_PER_CLIENT', '1'))
EMAIL_MONTHLY_LIMIT_PER_CLIENT = int(os.getenv('EMAIL_MONTHLY_LIMIT_PER_CLIENT', '4'))

# Configuración mejorada de Email
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'comunicaciones@aremko.cl')
VENTAS_FROM_EMAIL = os.getenv('VENTAS_FROM_EMAIL', 'ventas@aremko.cl')
# Email Backend - usar console para desarrollo si no hay credenciales
# Email Backend - SendGrid (Anymail)
if os.getenv('SENDGRID_API_KEY'):
    EMAIL_BACKEND = "anymail.backends.sendgrid.EmailBackend"
    ANYMAIL = {
        "SENDGRID_API_KEY": os.getenv('SENDGRID_API_KEY'),
    }
    logger.info("✅ Usando SendGrid para envío de correos")
elif not os.getenv('EMAIL_HOST_USER') or not os.getenv('EMAIL_HOST_PASSWORD'):
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
    logger.warning("⚠️ SENDGRID_API_KEY ni SMTP configurados - usando console backend")
else:
    # Fallback a SMTP si no hay SendGrid pero sí SMTP
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    logger.info("ℹ️ Usando SMTP clásico (Gmail) como fallback")

EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True').lower() == 'true'
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')

# Flags globales de comunicación
COMMUNICATION_SMS_ENABLED = os.getenv('COMMUNICATION_SMS_ENABLED', 'true').lower() == 'true'
COMMUNICATION_EMAIL_ENABLED = os.getenv('COMMUNICATION_EMAIL_ENABLED', 'true').lower() == 'true'

# URLs externas para encuestas/opiniones
SURVEY_PUBLIC_BASE_URL = os.getenv('SURVEY_PUBLIC_BASE_URL', 'https://aremko-booking-system.onrender.com/encuesta')
TRIPADVISOR_URL = os.getenv('TRIPADVISOR_URL', 'https://www.tripadvisor.com/')

# URL del sitio para generar links completos (GiftCards, etc.)
SITE_URL = os.getenv('SITE_URL', 'https://aremko-booking-system.onrender.com')

# --- Logging Configuration ---
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': 'aremko.log',
            'formatter': 'verbose',
        },
        'console': {
            'level': 'DEBUG' if DEBUG else 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'loggers': {
        'ventas': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
        'ventas.services': {
            'handlers': ['file', 'console'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': True,
        },
    },
}
