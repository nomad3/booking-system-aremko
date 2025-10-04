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
    # ... aplicaciones de Django ...
    # Aplicaciones de Django por defecto
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize', # Add humanize app
    'django.contrib.sitemaps', # Enable sitemaps
    'ventas',
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',
    'storages', # Add django-storages
    'solo',     # Add django-solo
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
    'default': dj_database_url.config(default=os.getenv('DATABASE_URL'))
}

# Configuraciones adicionales...
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True
LANGUAGE_CODE = 'es-cl'
TIME_ZONE = 'America/Santiago'
USE_I18N = True
USE_L10N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files configuration (Local vs GCS)
# Check if GOOGLE_APPLICATION_CREDENTIALS is set (indicating GCS usage)
if os.getenv('GOOGLE_APPLICATION_CREDENTIALS') and os.path.exists(os.getenv('GOOGLE_APPLICATION_CREDENTIALS', '')):
    DEFAULT_FILE_STORAGE = 'storages.backends.gcloud.GoogleCloudStorage'
    GS_BUCKET_NAME = os.getenv('GS_BUCKET_NAME', 'aremkoweb') # Use env var or default
    GS_PROJECT_ID = os.getenv('GS_PROJECT_ID', 'aremko-e51ae') # Use env var or default
    # Construct the full path to the credentials file relative to BASE_DIR
    GS_CREDENTIALS_PATH = BASE_DIR / os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    # Check if the credentials file exists before setting GS_CREDENTIALS
    if GS_CREDENTIALS_PATH.is_file():
        # Note: django-storages expects the *path* to the credentials file,
        # not the content, when using GS_CREDENTIALS setting directly like this.
        # However, it's often more robust to rely on the GOOGLE_APPLICATION_CREDENTIALS
        # environment variable being set correctly in the deployment environment,
        # which google-cloud-storage library picks up automatically.
        # Setting GS_CREDENTIALS explicitly might be needed in some setups.
        # For now, we'll rely on the environment variable being set.
        pass # GS_CREDENTIALS = str(GS_CREDENTIALS_PATH) # Uncomment if needed

    # Make uploaded files publicly readable by default
    # GS_DEFAULT_ACL = 'publicRead'  # Temporarily disabled to test
    GS_FILE_OVERWRITE = False # Prevent overwriting files with the same name
    GS_QUERYSTRING_AUTH = False # Keep this: Generate plain public URLs

    # Update MEDIA_URL for GCS
    MEDIA_URL = f'https://storage.googleapis.com/{GS_BUCKET_NAME}/media/'
    MEDIA_ROOT = f'gs://{GS_BUCKET_NAME}/media' # Optional: For management commands

else:
    # Default to local file storage if GOOGLE_APPLICATION_CREDENTIALS is not set
    MEDIA_URL = '/media/'
    MEDIA_ROOT = os.path.join(BASE_DIR, 'media')


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
if not os.getenv('EMAIL_HOST_USER') or not os.getenv('EMAIL_HOST_PASSWORD'):
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'  # Muestra emails en logs
    logger.warning("⚠️ EMAIL_HOST_USER/PASSWORD no configurados - usando console backend")
else:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
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
