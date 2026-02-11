"""
Configuración de caché para mejorar rendimiento
Agregar estas configuraciones a settings.py
"""

# Configuración de caché recomendada para agregar a settings.py

CACHE_CONFIG = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
        'OPTIONS': {
            'MAX_ENTRIES': 1000,
            'CULL_FREQUENCY': 3,
        }
    },
    'cliente_cache': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'cliente-cache',
        'TIMEOUT': 300,  # 5 minutos
        'OPTIONS': {
            'MAX_ENTRIES': 500,
        }
    }
}

# Para producción con Redis:
CACHE_CONFIG_REDIS = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'PARSER_CLASS': 'redis.connection.HiredisParser',
            'CONNECTION_POOL_CLASS': 'redis.connection.BlockingConnectionPool',
            'CONNECTION_POOL_CLASS_KWARGS': {
                'max_connections': 50,
                'timeout': 20,
            },
            'MAX_CONNECTIONS': 1000,
            'PICKLE_VERSION': -1,
        },
        'KEY_PREFIX': 'aremko',
        'TIMEOUT': 300,
    },
    'cliente_cache': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/2',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
        'KEY_PREFIX': 'cliente',
        'TIMEOUT': 300,
    }
}

# Configuración de sesiones en caché
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'

# Caché de vistas
CACHE_MIDDLEWARE_ALIAS = 'default'
CACHE_MIDDLEWARE_SECONDS = 600
CACHE_MIDDLEWARE_KEY_PREFIX = ''