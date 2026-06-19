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

# API Key para automatizaciones (cron-job.org, n8n, etc.)
# Usado por endpoints en /ventas/api/cron/* y /ventas/api/campaigns/*
AUTOMATION_API_KEY = os.getenv('AUTOMATION_API_KEY', '')

# ────────────────────────────────────────────────────────────────────────────
# Operación Vuelta a Casa — Etapa 5.5.1
# Clientes "proxy" / staff que deben ser excluidos del cron diario de
# bandeja WhatsApp. Estos son nombres que el staff usa cuando un cliente
# no se identifica al reservar (Aremko Hotel Spa, etc.) o cuentas del propio
# equipo (Jorge, Angélica, Deborah, Ernesto). Si llegan a la bandeja, se
# auto-envían mensajes de "vuelta a casa" raros.
# ────────────────────────────────────────────────────────────────────────────

# Match PARCIAL case-insensitive: cualquier nombre que CONTENGA estos strings
# se excluye. Usar solo para palabras inequívocas (ej. "aremko" siempre indica
# empresa o test).
OVC_CLIENTES_EXCLUIDOS_ICONTAINS = [
    'aremko',
    'carabineros',  # Geo.2: "Carabineros Rio Pescado", "Carabineros de Ensenada"
                    # son cuentas institucionales, no personas físicas a contactar 1-a-1
]

# Match EXACTO case-insensitive: el nombre completo debe coincidir.
# Usar para nombres de personas (evita falsos positivos con homónimos
# legítimos: un cliente real llamado "Jorge Mendoza" NO se excluye).
OVC_CLIENTES_EXCLUIDOS_IEXACT = [
    'Jorge Aguilera',
    'Angélica Toloza Poblete',
    'Angèlica Toloza',  # variante tilde grave en BD (cliente_id 360)
    'Deborah',
    'Ernesto',
]

# IDs de Servicios cuyo consumo marca al cliente como "Pareja Romántica"
# en la heurística de eje_contexto (recalcular_taxonomia_clientes).
# Validado con el reporte analizar_pareja_romantica 2026-05-25:
#   22 = Ambientación romántica R1 (96 reservas históricas)
#   23 = Ambientación romántica R2 (12)
#   77 = San Valentin 2026 (35)
#   24 = Decoración Simple · Azul (20)
#   66 = Decoración Simple · Rosado (8)
# Total: ~171 reservas. Se excluyen intencionalmente Ambientación Mamá
# y Decoración Cumpleaños (no son románticos, son Día de la Madre y
# Cumpleaños respectivamente).
OVC_SERVICIOS_ROMANTICOS_IDS = [22, 23, 24, 66, 77]

# ────────────────────────────────────────────────────────────────────────────
# Días MÍNIMOS desde última visita para entrar a bandeja WhatsApp
# ────────────────────────────────────────────────────────────────────────────
# Bugfix urgente 2026-05-25: Campeones con visita hace 4 días estaban
# entrando a P0 (mesa chica) porque ultimo_contacto_outbound era NULL.
# Resultado: mensaje "te echamos de menos" a clientes recién visitados.
#
# Esta tabla aplica un filtro adicional a calcular_prioridad: si la persona
# vino hace menos del mínimo configurado para su clasificación, NO entra a
# bandeja sin importar qué prioridad ganaría.
#
# Valores 0 = sin filtro (las heurísticas P1/P3/P4 ya tienen su propio chequeo
# de inactividad, no necesitan refuerzo).
OVC_DIAS_MINIMO_DESDE_ULTIMA_VISITA = {
    'Campeón': 45,                   # 1.5 meses post-visita
    'Leal': 60,                       # 2 meses post-visita
    'Regular': 30,                    # 1 mes post-visita
    'Gran Gastador Ocasional': 45,    # 1.5 meses post-visita
    'En Prueba': 0,                   # heurística P2 ya define ventanas (30/60/80)
    'En Riesgo': 0,                   # heurística P1/P5 ya define
    'Dormido': 0,                     # heurística P3/P6 ya define
    'Pre-sistema': 0,
}

# ────────────────────────────────────────────────────────────────────────────
# Acumulación de pendientes entre días (cron generar_bandeja_whatsapp_diaria)
# ────────────────────────────────────────────────────────────────────────────
# Feature 2026-05-26: cuando un ContactoWhatsApp queda en estado='pendiente'
# al cierre del día, se arrastra al día siguiente para presionar a Deborah
# a completar su meta diaria. Sin esto, los pendientes quedaban invisibles
# (filtros por fecha_sugerido=hoy en endpoints) y se perdía oportunidad.
#
# Comportamiento del cron diario:
#   1. Expirar pendientes con fecha_sugerido < hoy - DIAS_MAX_ACUMULACION
#      (estado pasa a 'expirado_acumulacion' — el cliente puede volver a
#      entrar más adelante si su clasificación lo selecciona)
#   2. Arrastrar pendientes restantes [hoy - DIAS_MAX_ACUMULACION, hoy-1]
#      a fecha_sugerido=hoy
#   3. Generar nuevos del día con dedupe (excluyendo clientes ya arrastrados)
OVC_DIAS_MAX_ACUMULACION = int(os.getenv('OVC_DIAS_MAX_ACUMULACION', '7'))

# ────────────────────────────────────────────────────────────────────────────
# Target diario de contactos en bandeja (piso operativo + tope)
# ────────────────────────────────────────────────────────────────────────────
# Feature 2026-05-27: garantizar volumen estable. Si los óptimos P0-P4 no
# llenan el target, el cron completa con P5/P6 (En Riesgo/Dormido resto)
# marcándolos como es_relleno=True para análisis diferenciado.
# Si el universo total es menor al target, NO inventa — toma lo que hay.
OVC_TARGET_DIARIO = int(os.getenv('OVC_TARGET_DIARIO', '50'))

# ────────────────────────────────────────────────────────────────────────────
# Conexión-Masajes — envío de emails de seguimiento de bienestar (F6)
# ────────────────────────────────────────────────────────────────────────────
# APAGADO por defecto: los seguimientos se PROGRAMAN al completar la ficha, pero
# el comando `enviar_seguimientos_masaje` NO los envía hasta poner esto en True
# (env var MASAJE_SEGUIMIENTOS_ACTIVOS=true). Permite revisar/aprobar los textos
# antes de mandar correos a clientes reales.
MASAJE_SEGUIMIENTOS_ACTIVOS = os.getenv('MASAJE_SEGUIMIENTOS_ACTIVOS', 'false').lower() == 'true'
# Remitente de los correos de masaje (dominio autenticado en SendGrid → sin "via
# sendgrid.net" y mejor deliverability). Configurable por env.
MASAJE_FROM_EMAIL = os.getenv('MASAJE_FROM_EMAIL', 'ventas@aremko.cl')

# ────────────────────────────────────────────────────────────────────────────
# Disparo de la campaña de plantillas Meta (aremko-cli / Go)
# ────────────────────────────────────────────────────────────────────────────
# Tras generar_bandeja_whatsapp_diaria, Django llama a este endpoint de Go para
# que envíe las plantillas de salva 1 (Cloud API): pull pending-template-sends →
# SendTemplate → mark-template-sent/failed. Es SÍNCRONO (~decenas de seg para 50).
# Seguro: si ningún script tiene meta_template_name cargado, Go responde total:0
# y no manda nada. Vaciar la URL (o --no-campaign) para desactivar el disparo.
OVC_RUN_TEMPLATE_CAMPAIGN_URL = os.getenv(
    'OVC_RUN_TEMPLATE_CAMPAIGN_URL',
    'https://aremko-cli-backend.onrender.com/api/v1/whatsapp/run-template-campaign',
)
OVC_TEMPLATE_CAMPAIGN_TIMEOUT = int(os.getenv('OVC_TEMPLATE_CAMPAIGN_TIMEOUT', '120'))

# ────────────────────────────────────────────────────────────────────────────
# Operación Vuelta a Casa — Variaciones IA on-demand
# ────────────────────────────────────────────────────────────────────────────
# Toggle global para que los endpoints /siguiente/ y /marcar-enviado/ devuelvan
# un mensaje_variado generado por LLM (Gemini Flash Lite vía OpenRouter).
# Cuando está apagado, mensaje_variado siempre = null en el response y el
# frontend usa mensaje_renderizado original.
# Costo estimado: ~$4/mes con Gemini Flash Lite a ~50 envíos/día.
# Reversible en cualquier momento via env var sin redeploy.
OVC_USAR_VARIACIONES_IA = os.getenv('OVC_USAR_VARIACIONES_IA', 'false').lower() == 'true'

# Timeout en segundos. Si el LLM tarda más, el endpoint hace fallback a
# mensaje_variado=null y devuelve el response normal — no bloquea al operador.
OVC_VARIACION_TIMEOUT_SECONDS = int(os.getenv('OVC_VARIACION_TIMEOUT_SECONDS', '3'))

# Modelo de OpenRouter a usar. Default: Gemini 2.0 Flash Lite (más barato).
# Otros candidatos sin renombrar settings: anthropic/claude-haiku-4 o
# google/gemini-flash-1.5.
OVC_VARIACION_LLM_MODEL = os.getenv(
    'OVC_VARIACION_LLM_MODEL', 'google/gemini-2.0-flash-lite-001',
)

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
    'api',  # API para Luna AI Assistant
    'destino_puerto_varas',  # DPV: catálogo turístico + motor de recomendación + lead capture
    'kits.apps.KitsConfig',  # Productos compuestos (Bill of Materials)
    'aremko_blog.apps.AremkoBlogConfig',  # Blog editorial aremko.cl (DPV-SEO-002 #6 mirror, app aislada)
    'whatsapp_agent.apps.WhatsappAgentConfig',  # Agente IA WhatsApp (H-007, app aislada drift-safe)
    'inbox_omnicanal.apps.InboxOmnicanalConfig',  # Bandeja omnicanal: Instagram DM (H-016, app aislada drift-safe)
    'carrito_reservas.apps.CarritoReservasConfig',  # Carrito multi-servicio (H-029 FASE 2, app aislada drift-safe)

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
    'aremko_project.host_routing.HostBasedURLConfMiddleware',  # Antes de Security para que urlconf esté seteado
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
                'ventas.context_processors.social_proof_processor', # AR-028: TA + Google badges
                'ventas.context_processors.meta_pixel_processor', # Meta Pixel ID parametrizable
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

    # NOTA: NO configurar MEDIA_URL cuando se usa django-cloudinary-storage
    # El backend ya devuelve URLs completas (https://res.cloudinary.com/...)
    # Si se configura MEDIA_URL, las URLs se duplican incorrectamente
    # MEDIA_URL = f'https://res.cloudinary.com/{CLOUDINARY_CLOUD_NAME}/'  # COMENTADO

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

# Destinatarios de notificación cuando entra un lead nuevo en /refugio/.
# Configurable vía env REFUGIO_LEAD_NOTIFICACIONES (coma-separados) para
# poder ajustar sin redeploy. Default: 3 cuentas del equipo Aremko.
#   - comunicaciones@aremko.cl: bandeja general
#   - aremkospa@gmail.com:      Jorge (dueño)
#   - ventas@aremko.cl:         Deborah (operadora comercial Refugio)
REFUGIO_LEAD_NOTIFICACIONES = [
    e.strip() for e in os.getenv(
        'REFUGIO_LEAD_NOTIFICACIONES',
        'comunicaciones@aremko.cl,aremkospa@gmail.com,ventas@aremko.cl',
    ).split(',') if e.strip()
]
# Email Backend - usar console para desarrollo si no hay credenciales
# Email Backend - SendGrid (Anymail)
if os.getenv('SENDGRID_API_KEY'):
    # Usar SMTP directo de SendGrid en lugar de anymail
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = 'smtp.sendgrid.net'
    EMAIL_PORT = 587
    EMAIL_USE_TLS = True
    EMAIL_HOST_USER = 'apikey'  # Literal 'apikey', no cambiar
    EMAIL_HOST_PASSWORD = os.getenv('SENDGRID_API_KEY')
    logger.info("✅ Usando SendGrid SMTP directo")
elif not os.getenv('EMAIL_HOST_USER') or not os.getenv('EMAIL_HOST_PASSWORD'):
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
    logger.warning("⚠️ SENDGRID_API_KEY ni SMTP configurados - usando console backend")
else:
    # Fallback a SMTP si no hay SendGrid pero sí SMTP
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    logger.info("ℹ️ Usando SMTP clásico (Gmail) como fallback")

# Configuración SMTP de respaldo (si no se usa SendGrid)
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True').lower() == 'true'
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')

# Flags globales de comunicación
COMMUNICATION_SMS_ENABLED = os.getenv('COMMUNICATION_SMS_ENABLED', 'true').lower() == 'true'
COMMUNICATION_EMAIL_ENABLED = os.getenv('COMMUNICATION_EMAIL_ENABLED', 'true').lower() == 'true'

# URLs externas para encuestas/opiniones
SURVEY_PUBLIC_BASE_URL = os.getenv('SURVEY_PUBLIC_BASE_URL', 'https://www.aremko.cl/encuesta-satisfaccion/')
TRIPADVISOR_URL = os.getenv('TRIPADVISOR_URL', 'https://www.tripadvisor.com/')
GOOGLE_REVIEWS_URL = os.getenv('GOOGLE_REVIEWS_URL', 'https://g.page/r/CbKKwbV5UmD_EBM/review')

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

# API Configuration for Luna AI Assistant
import secrets
LUNA_API_KEY = os.getenv('LUNA_API_KEY', secrets.token_urlsafe(32))

# ──────────────── DPV — Destino Puerto Varas ────────────────
# URLs de derivación hacia Aremko Spa
AREMKO_RESERVATION_URL = "https://www.aremko.cl/"
AREMKO_WHATSAPP_URL = "https://wa.me/56958655810"  # WhatsApp corporativo Aremko (piloto)

# Webhook tokens (placeholders; no se usan todavía porque WhatsApp va por neonize, ver apéndice DPV-002)
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "dpv_dev_verify_token")
INSTAGRAM_VERIFY_TOKEN = os.getenv("INSTAGRAM_VERIFY_TOKEN", "dpv_dev_verify_token")

# ──────────────── DPV — LLM (OpenRouter) ────────────────
DPV_LLM_ENABLED = os.getenv("DPV_LLM_ENABLED", "false").lower() == "true"
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
DPV_LLM_MODEL = os.getenv("DPV_LLM_MODEL", "anthropic/claude-haiku-4.5")

# Análisis IA semanal de encuestas de satisfacción (Tarea 1.4 Fase C)
SURVEY_ANALYSIS_LLM_MODEL = os.getenv(
    "SURVEY_ANALYSIS_LLM_MODEL", "anthropic/claude-sonnet-4.6"
)
SURVEY_ANALYSIS_RECIPIENT_EMAIL = os.getenv(
    "SURVEY_ANALYSIS_RECIPIENT_EMAIL", "aremkospa@gmail.com"
)

# Brief semanal de marketing (Tarea 2.4 plan maestro)
MARKETING_BRIEF_LLM_MODEL = os.getenv(
    "MARKETING_BRIEF_LLM_MODEL", "anthropic/claude-sonnet-4.6"
)
MARKETING_BRIEF_RECIPIENT_EMAIL = os.getenv(
    "MARKETING_BRIEF_RECIPIENT_EMAIL", "aremkospa@gmail.com"
)

# GA4 + GSC API integration (Tarea 2.3 plan maestro)
# Service account JSON puede venir como path al archivo o como JSON inline
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")  # JSON completo como string
GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "")  # Path al archivo (alternativa)
# GA4 Property ID (no Measurement ID). Está en Admin > Property settings, formato numérico
GA4_PROPERTY_ID = os.getenv("GA4_PROPERTY_ID", "535461209")  # Propiedad aremko.cl
# GSC site URL (con barra al final si es Domain property: "sc-domain:aremko.cl")
GSC_SITE_URL = os.getenv("GSC_SITE_URL", "sc-domain:aremko.cl")

# Flow.cl pasarela de pago (cuenta Datamatic, recibe fondos de Aremko)
# Las views leen de os.environ directo pero las definimos acá tambien para
# garantizar carga al boot (regla del proyecto: env vars requieren linea explicita)
FLOW_API_KEY = os.getenv("FLOW_API_KEY", "")
FLOW_SECRET_KEY = os.getenv("FLOW_SECRET_KEY", "")
FLOW_CREATE_API_URL = os.getenv("FLOW_CREATE_API_URL", "https://www.flow.cl/api/payment/create")
FLOW_STATUS_API_URL = os.getenv("FLOW_STATUS_API_URL", "https://www.flow.cl/api/payment/getStatus")
FLOW_CONFIRMATION_URL = os.getenv("FLOW_CONFIRMATION_URL", "https://www.aremko.cl/payment/confirmation/")
FLOW_RETURN_URL = os.getenv("FLOW_RETURN_URL", "https://www.aremko.cl/payment/return/")

# ──────────────── Meta (Facebook) Pixel + Conversions API ────────────────
# Pixel ID: se inyecta en templates via context processor (meta_pixel_processor).
# CAPI token: se genera en Meta Business → Events Manager → Settings → Generate Access Token.
# Test event code: usar durante pruebas, vaciar en produccion para que los eventos cuenten.
META_PIXEL_ID = os.getenv("META_PIXEL_ID", "478226496113915")
META_CAPI_ACCESS_TOKEN = os.getenv("META_CAPI_ACCESS_TOKEN", "")
META_CAPI_TEST_EVENT_CODE = os.getenv("META_CAPI_TEST_EVENT_CODE", "")
META_CAPI_API_VERSION = os.getenv("META_CAPI_API_VERSION", "v21.0")

DPV_LLM_MAX_TOKENS = int(os.getenv("DPV_LLM_MAX_TOKENS", "500"))
DPV_LLM_TEMPERATURE = float(os.getenv("DPV_LLM_TEMPERATURE", "0.7"))
DPV_LLM_TIMEOUT_SECONDS = int(os.getenv("DPV_LLM_TIMEOUT_SECONDS", "30"))
DPV_LLM_SITE_URL = os.getenv("DPV_LLM_SITE_URL", "https://www.aremko.cl")
DPV_LLM_SITE_NAME = os.getenv("DPV_LLM_SITE_NAME", "Destino Puerto Varas Piloto")

# ──────────────── DPV — CMS-IA: Perplexity (búsqueda web) ────────────────
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY", "")
PERPLEXITY_BASE_URL = os.getenv("PERPLEXITY_BASE_URL", "https://api.perplexity.ai")
PERPLEXITY_TIMEOUT_SECONDS = int(os.getenv("PERPLEXITY_TIMEOUT_SECONDS", "60"))
# Endpoint /search: cuántos resultados pedir y cuánto contenido por página.
PERPLEXITY_SEARCH_MAX_RESULTS = int(os.getenv("PERPLEXITY_SEARCH_MAX_RESULTS", "5"))
PERPLEXITY_SEARCH_MAX_TOKENS_PER_PAGE = int(
    os.getenv("PERPLEXITY_SEARCH_MAX_TOKENS_PER_PAGE", "512")
)

# ──────────────── DPV — Bot WhatsApp (DPV-006) ────────────────
DPV_BOT_ENABLED = os.getenv("DPV_BOT_ENABLED", "false").lower() == "true"
DPV_BOT_ENABLED_JIDS = [
    j.strip() for j in os.getenv("DPV_BOT_ENABLED_JIDS", "").split(",") if j.strip()
]
NEONIZE_SERVICE_URL = os.getenv("NEONIZE_SERVICE_URL", "")
NEONIZE_SERVICE_TOKEN = os.getenv("NEONIZE_SERVICE_TOKEN", "")
NEONIZE_SERVICE_TIMEOUT_SECONDS = int(os.getenv("NEONIZE_SERVICE_TIMEOUT_SECONDS", "15"))

# ──────────────── DPV — Bot Telegram (DPV-007) ────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")
TELEGRAM_API_BASE_URL = os.getenv("TELEGRAM_API_BASE_URL", "https://api.telegram.org")
TELEGRAM_SEND_TIMEOUT_SECONDS = int(os.getenv("TELEGRAM_SEND_TIMEOUT_SECONDS", "15"))
DPV_BOT_ENABLED_TELEGRAM_CHAT_IDS = [
    c.strip() for c in os.getenv("DPV_BOT_ENABLED_TELEGRAM_CHAT_IDS", "").split(",") if c.strip()
]
