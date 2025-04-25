import os
from pathlib import Path
import dj_database_url

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
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '').split(',')

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
if os.getenv('GOOGLE_APPLICATION_CREDENTIALS'):
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

    # Make uploaded files publicly readable by default - REMOVE OR COMMENT OUT THIS LINE
    GS_DEFAULT_ACL = 'publicRead'
    GS_FILE_OVERWRITE = False # Prevent overwriting files with the same name

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
