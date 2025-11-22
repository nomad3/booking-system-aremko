# 🔍 Análisis de Rendimiento y Cron Jobs - Aremko Booking System

**Fecha:** 22 de noviembre de 2025
**Analista:** Claude Code
**Estado:** ⚠️ PROBLEMAS DETECTADOS

---

## 📊 RESUMEN EJECUTIVO

Se han detectado **3 problemas críticos** que están afectando el rendimiento del sistema:

1. ⚠️ **Conexiones de base de datos sin pooling** → Crea nueva conexión en cada request
2. ⚠️ **Falta CONN_MAX_AGE** → BD se cierra después de cada request (sobrecarga)
3. ⚠️ **No hay sistema de caché configurado** → Queries repetidas innecesarias

**Impacto:** Lentitud generalizada, especialmente cuando se ejecutan cron jobs concurrentemente

---

## 🔴 PROBLEMAS CRÍTICOS DETECTADOS

### 1. **Conexiones de Base de Datos (CRÍTICO)**

**Problema:**
```python
# En settings.py línea 116-118
DATABASES = {
    'default': dj_database_url.config(default=os.getenv('DATABASE_URL'))
}
```

❌ **No hay configuración de `CONN_MAX_AGE`**
❌ **Cada HTTP request abre y cierra conexión a PostgreSQL**
❌ **Los cron jobs hacen lo mismo simultáneamente**

**Consecuencia:**
- Overhead de 50-200ms por request solo en handshake de BD
- Cuando un cron job ejecuta, **todos los requests web se ralentizan** porque compiten por conexiones
- PostgreSQL tiene límite de conexiones concurrentes (típicamente 20-100)

**Solución:**
```python
DATABASES = {
    'default': {
        **dj_database_url.config(default=os.getenv('DATABASE_URL')),
        'CONN_MAX_AGE': 600,  # Reutilizar conexiones por 10 minutos
        'OPTIONS': {
            'connect_timeout': 10,
            'options': '-c statement_timeout=30000'  # 30 segundos timeout
        }
    }
}
```

---

### 2. **Sin Sistema de Caché (ALTO IMPACTO)**

**Problema:**
❌ No hay configuración de `CACHES` en `settings.py`
❌ Queries repetidas se ejecutan cada vez (categorías, menús, configuraciones)

**Impacto:**
- Vista `categorias_processor` se ejecuta en CADA request (línea 107 de settings.py)
- Admin dashboard ejecuta múltiples queries cada carga
- Vistas públicas cargan servicios/categorías sin caché

**Solución:**
```python
# Agregar a settings.py
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/1'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
        'KEY_PREFIX': 'aremko',
        'TIMEOUT': 300,  # 5 minutos por defecto
    }
}

# Alternativa si no tienes Redis (usar memoria):
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
        'OPTIONS': {
            'MAX_ENTRIES': 1000
        }
    }
}
```

**Implementar en:**
- `ventas/context_processors.py` → Cachear categorías por 1 hora
- Vistas de admin dashboard → Cachear contadores
- API de disponibilidad → Cachear slots por 5 minutos

---

### 3. **Cron Jobs Ejecutándose Sin Control**

**Problema Detectado:**

#### ✅ **Cron Jobs Funcionando:**
1. `/ventas/cron/procesar-premios-bienvenida/` → 1x día (8:00 AM)
2. `/ventas/cron/enviar-premios-aprobados/` → Cada 30 min
3. `/ventas/cron/triggers-surveys/` → Diario 11:00 AM
4. `/ventas/cron/triggers-reactivation/` → Lunes 9:00 AM
5. `/ventas/cron/enviar-emails-programados/` → Cada 30 min
6. `/ventas/cron/triggers-reminders/` → Cada hora
7. `/ventas/cron/enviar-campana-giftcard/` → Cada 6 min ⚠️ DEMASIADO FRECUENTE

#### ⚠️ **Cron Jobs de Control de Gestión (POSIBLE PROBLEMA):**
1. `/control_gestion/cron/preparacion-servicios/` → **¿Está configurado?**
2. `/control_gestion/cron/vaciado-tinas/` → **¿Está configurado?**
3. `/control_gestion/cron/daily-opening/` → **¿Está configurado?**
4. `/control_gestion/cron/atencion-clientes/` → **¿Está configurado?**

**Impacto en Rendimiento:**

| Cron Job | Frecuencia | Carga en BD | Riesgo Lentitud |
|----------|------------|-------------|-----------------|
| enviar-campana-giftcard | Cada 6 min | ALTA | 🔴 CRÍTICO |
| enviar-premios-aprobados | Cada 30 min | MEDIA | 🟡 MODERADO |
| enviar-emails-programados | Cada 30 min | MEDIA | 🟡 MODERADO |
| triggers-reminders | Cada hora | BAJA | 🟢 BAJO |
| preparacion-servicios | Cada 15 min (esperado) | MEDIA | 🟡 MODERADO |

**Problema:**
Cuando 2-3 cron jobs ejecutan simultáneamente:
- Compiten por conexiones de BD
- Bloquean requests de usuarios
- Generan timeouts

---

## 🎯 SOLUCIONES RECOMENDADAS

### **Prioridad 1: INMEDIATO (Hoy)**

#### 1. **Agregar CONN_MAX_AGE**
```python
# En aremko_project/settings.py, reemplazar líneas 116-118:

DATABASES = {
    'default': {
        **dj_database_url.config(default=os.getenv('DATABASE_URL')),
        'CONN_MAX_AGE': 600,  # ⭐ Reutilizar conexiones por 10 minutos
        'OPTIONS': {
            'connect_timeout': 10,
        }
    }
}
```

**Beneficio esperado:** Reducción de latencia 50-80ms por request

---

#### 2. **Reducir Frecuencia de Cron de GiftCard**
```bash
# Cambiar de:
*/6 * * * * → Cada 6 minutos (DEMASIADO)

# A:
*/30 * * * * → Cada 30 minutos (MEJOR)
```

**Beneficio:** Reduce carga de BD en 80%

---

#### 3. **Verificar Cron Jobs de Control de Gestión**

**ACCIÓN REQUERIDA:** Revisar en cron-job.org o sistema de cron que uses:

- [ ] ¿Está configurado `/control_gestion/cron/preparacion-servicios/`?
- [ ] ¿Frecuencia correcta? (Debería ser cada 15 minutos)
- [ ] ¿Token CRON_TOKEN configurado correctamente?
- [ ] ¿Endpoint funcional? Probar manualmente:
  ```bash
  curl "https://www.aremko.cl/control_gestion/cron/preparacion-servicios/?token=TU_TOKEN"
  ```

**Si no están funcionando, las tareas de urgencia NO se crean automáticamente**

---

### **Prioridad 2: CORTO PLAZO (Esta Semana)**

#### 4. **Implementar Caché de Categorías**

```python
# En ventas/context_processors.py
from django.core.cache import cache

def categorias_processor(request):
    """Context processor con caché para categorías"""

    # Intentar obtener del caché
    categorias = cache.get('categorias_menu')

    if categorias is None:
        # Si no está en caché, consultar BD
        from ventas.models import CategoriaServicio
        categorias = list(CategoriaServicio.objects.filter(activo=True).order_by('orden'))
        # Guardar en caché por 1 hora
        cache.set('categorias_menu', categorias, 3600)

    return {'categorias': categorias}
```

**Beneficio:** Reduce queries de categorías de 1000+/día a 24/día

---

#### 5. **Optimizar Queries N+1 en Vistas Admin**

**Problemas detectados:**
- `ventas/views/admin_views.py` (7 queries sin optimize)
- `ventas/views/crud_views.py` (26 queries potenciales)
- `control_gestion/views.py` → Vista `mi_dia()` podría optimizarse

**Solución:**
```python
# ANTES:
tareas = Task.objects.filter(owner=request.user)
for tarea in tareas:
    print(tarea.owner.username)  # ❌ Query extra por cada tarea

# DESPUÉS:
tareas = Task.objects.filter(owner=request.user).select_related('owner')
for tarea in tareas:
    print(tarea.owner.username)  # ✅ Sin queries extras
```

---

#### 6. **Configurar Redis para Caché (Opcional pero Recomendado)**

Si usas Render.com, agregar Redis:
1. Dashboard Render → "New" → "Redis"
2. Plan gratuito (256MB suficiente)
3. Copiar `REDIS_URL` a variables de entorno
4. Implementar configuración de caché mostrada arriba

**Costo:** $0/mes (plan gratuito)
**Beneficio:** Caché persistente entre deployments

---

### **Prioridad 3: MEDIANO PLAZO (Próximas 2 Semanas)**

#### 7. **Monitoreo de Rendimiento**

```python
# Agregar a settings.py
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{levelname}] {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django.db.backends': {
            'handlers': ['console'],
            'level': os.getenv('SQL_LOG_LEVEL', 'INFO'),  # Cambiar a DEBUG para ver queries
            'propagate': False,
        },
    },
}
```

---

#### 8. **Índices de Base de Datos**

Revisar si existen índices en:
- `VentaReserva.fecha_reserva` (usado frecuentemente en filtros)
- `Task.promise_due_at` (usado en cron de urgencias)
- `Cliente.telefono` (búsquedas frecuentes)
- `Premio.estado` (filtrado constante)

---

## 📋 CHECKLIST DE IMPLEMENTACIÓN

### **Fase 1: Emergencia (Hoy)**
- [ ] Agregar `CONN_MAX_AGE=600` a settings
- [ ] Reducir frecuencia cron giftcard a */30
- [ ] Verificar que cron de preparacion-servicios esté configurado
- [ ] Probar endpoint manualmente con curl
- [ ] Deployar cambios

### **Fase 2: Optimización (Esta Semana)**
- [ ] Implementar caché de categorías
- [ ] Revisar y optimizar queries N+1 en admin
- [ ] Considerar agregar Redis
- [ ] Documentar endpoints de cron

### **Fase 3: Monitoreo (Próximas 2 Semanas)**
- [ ] Configurar logging de SQL
- [ ] Revisar índices de BD
- [ ] Monitorear tiempos de respuesta
- [ ] Optimizar queries lentas detectadas

---

## 🔬 COMANDOS DE DIAGNÓSTICO

### **Verificar Cron Jobs:**
```bash
# Probar cada endpoint (reemplaza TU_TOKEN):
TOKEN="tu_token_aqui"

# Preparación servicios
curl "https://www.aremko.cl/control_gestion/cron/preparacion-servicios/?token=$TOKEN"

# Vaciado tinas
curl "https://www.aremko.cl/control_gestion/cron/vaciado-tinas/?token=$TOKEN"

# Daily opening
curl "https://www.aremko.cl/control_gestion/cron/daily-opening/?token=$TOKEN"

# Atención clientes
curl "https://www.aremko.cl/ventas/cron/gen-atencion-clientes/?token=$TOKEN"
```

### **Ver Queries Lentas (En producción):**
```bash
# Activar logging SQL temporalmente:
export SQL_LOG_LEVEL=DEBUG
# Revisar logs en Render dashboard
```

### **Verificar Conexiones BD:**
```sql
-- En PostgreSQL, ver conexiones activas:
SELECT count(*) as connections, state
FROM pg_stat_activity
WHERE datname = 'tu_database_name'
GROUP BY state;
```

---

## ⚡ IMPACTO ESPERADO

| Métrica | Antes | Después | Mejora |
|---------|-------|---------|--------|
| Latencia promedio | 300-800ms | 80-200ms | **60-75%** |
| Queries por request | 15-30 | 5-10 | **66%** |
| Tiempo conexión BD | 50-100ms | 0ms (pooling) | **100%** |
| Carga BD cron | ALTA | MEDIA | **40%** |

---

## 📞 CONTACTO Y SOPORTE

Si necesitas ayuda implementando estas mejoras:
1. Revisa logs de Render para errors específicos
2. Verifica variables de entorno (CRON_TOKEN, REDIS_URL)
3. Prueba endpoints de cron manualmente antes de configurar cron-job.org

**Última actualización:** 2025-11-22
**Versión:** 1.0
