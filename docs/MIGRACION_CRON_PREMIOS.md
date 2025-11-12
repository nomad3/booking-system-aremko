# 🔄 Migración de Cron Jobs de Premios a cron-job.org

**Fecha**: 11 de noviembre, 2025
**Objetivo**: Migrar cron jobs de premios desde Render Cron Jobs a cron-job.org (HTTP endpoints)

---

## 📊 Estado Actual de Cron Jobs

### ✅ YA MIGRADOS A cron-job.org (Control de Gestión)

| Cron Job | Frecuencia | Endpoint HTTP | Estado |
|----------|------------|---------------|--------|
| Preparación de Servicios | Cada 15 min | `/control_gestion/cron/preparacion-servicios/` | ✅ ACTIVO |
| Vaciado de Tinas | Cada 30 min | `/control_gestion/cron/vaciado-tinas/` | ✅ ACTIVO |
| Apertura Diaria | 7:00 AM | `/control_gestion/cron/daily-opening/` | ✅ ACTIVO |
| Reporte Matutino | 9:00 AM | `/control_gestion/cron/daily-reports/?momento=matutino` | ✅ ACTIVO |
| Reporte Vespertino | 6:00 PM | `/control_gestion/cron/daily-reports/?momento=vespertino` | ✅ ACTIVO |

**Ubicación**: `docs/ESTADO_CRON_JOBS.md`

---

### ⚠️ PENDIENTES DE MIGRAR (Premios)

#### 1️⃣ Procesamiento de Premios de Bienvenida

**Script actual**: `scripts/cron_premio_bienvenida.sh`

**Comando Django**: `python manage.py procesar_premios_bienvenida`

**Qué hace**:
- Detecta clientes con check-in hace 3 días
- Verifica si es cliente nuevo (servicios_historicos == 0)
- Genera Premio de Bienvenida automáticamente
- Calcula tramo y genera Premio por Hito si aplica

**Frecuencia recomendada**: **1 vez al día - 8:00 AM** (`0 8 * * *`)

**Endpoint a crear**: `/ventas/cron/procesar-premios-bienvenida/`

---

#### 2️⃣ Envío de Premios Aprobados

**Script actual**: `scripts/cron_premios.sh`

**Comando Django**: `python manage.py enviar_premios_aprobados`

**Qué hace**:
- Busca premios con estado='aprobado'
- Envía emails a clientes con código de premio
- Actualiza estado a 'enviado'
- Respeta rate limiting (30 min entre envíos)
- Envía 1 premio por ejecución (anti-spam)

**Frecuencia recomendada**: **Cada 30 minutos** (`*/30 * * * *`)

**Endpoint a crear**: `/ventas/cron/enviar-premios-aprobados/`

---

## 🔧 Cambios Necesarios

### 1. Crear endpoints HTTP en `ventas/views/cron_views.py` (nuevo archivo)

```python
from django.http import JsonResponse
from django.core.management import call_command
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from io import StringIO
import os
import logging

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def cron_procesar_premios_bienvenida(request):
    """
    Endpoint para ejecutar procesar_premios_bienvenida desde cron externo

    GET o POST: /ventas/cron/procesar-premios-bienvenida/?token=xxx
    """
    # Validar token
    expected_token = os.getenv('CRON_TOKEN')
    if expected_token:
        request_token = request.GET.get('token') or request.POST.get('token')
        if request_token != expected_token:
            return JsonResponse({"ok": False, "error": "Token inválido"}, status=403)

    try:
        output = StringIO()
        call_command('procesar_premios_bienvenida', stdout=output)

        logger.info("✅ Cron procesar_premios_bienvenida ejecutado vía HTTP")

        return JsonResponse({
            "ok": True,
            "message": "Procesamiento de premios de bienvenida ejecutado",
            "output": output.getvalue()
        })

    except Exception as e:
        logger.error(f"❌ Error en cron procesar_premios_bienvenida: {e}")
        return JsonResponse({
            "ok": False,
            "error": str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def cron_enviar_premios_aprobados(request):
    """
    Endpoint para ejecutar enviar_premios_aprobados desde cron externo

    GET o POST: /ventas/cron/enviar-premios-aprobados/?token=xxx
    """
    # Validar token
    expected_token = os.getenv('CRON_TOKEN')
    if expected_token:
        request_token = request.GET.get('token') or request.POST.get('token')
        if request_token != expected_token:
            return JsonResponse({"ok": False, "error": "Token inválido"}, status=403)

    try:
        output = StringIO()
        call_command('enviar_premios_aprobados', stdout=output)

        logger.info("✅ Cron enviar_premios_aprobados ejecutado vía HTTP")

        return JsonResponse({
            "ok": True,
            "message": "Envío de premios aprobados ejecutado",
            "output": output.getvalue()
        })

    except Exception as e:
        logger.error(f"❌ Error en cron enviar_premios_aprobados: {e}")
        return JsonResponse({
            "ok": False,
            "error": str(e)
        }, status=500)
```

---

### 2. Agregar rutas en `ventas/urls.py`

```python
# Importar vistas de cron
from ventas.views import cron_views

# Agregar al final de urlpatterns:
urlpatterns = [
    # ... rutas existentes ...

    # Endpoints para cron externo (premios)
    path("cron/procesar-premios-bienvenida/", cron_views.cron_procesar_premios_bienvenida, name="cron_procesar_premios"),
    path("cron/enviar-premios-aprobados/", cron_views.cron_enviar_premios_aprobados, name="cron_enviar_premios"),
]
```

---

## 🔐 Seguridad

**Token de autenticación**: `aremko_cron_secret_2025` (ya configurado en Render)

**Variables de entorno**:
```bash
CRON_TOKEN=aremko_cron_secret_2025
```

**URLs completas con token**:
```
https://www.aremko.cl/ventas/cron/procesar-premios-bienvenida/?token=aremko_cron_secret_2025
https://www.aremko.cl/ventas/cron/enviar-premios-aprobados/?token=aremko_cron_secret_2025
```

---

## 📅 Configuración en cron-job.org

### 1️⃣ Procesamiento de Premios de Bienvenida

**Título**: `Premio Bienvenida - Procesamiento Diario`

**URL**:
```
https://www.aremko.cl/ventas/cron/procesar-premios-bienvenida/?token=aremko_cron_secret_2025
```

**Configuración**:
- **Schedule**: `0 8 * * *` (8:00 AM todos los días)
- **Method**: GET
- **Timeout**: 60 seconds
- **Notifications**: On failure

**Descripción**:
```
Procesa premios de bienvenida para clientes con check-in hace 3 días.
Genera premios de bienvenida para clientes nuevos y premios por hito para clientes recurrentes.
```

---

### 2️⃣ Envío de Premios Aprobados

**Título**: `Premio - Envío de Emails Aprobados`

**URL**:
```
https://www.aremko.cl/ventas/cron/enviar-premios-aprobados/?token=aremko_cron_secret_2025
```

**Configuración**:
- **Schedule**: `*/30 * * * *` (Cada 30 minutos)
- **Method**: GET
- **Timeout**: 60 seconds
- **Notifications**: On failure

**Descripción**:
```
Envía emails de premios aprobados a clientes.
Respeta rate limiting (30 min entre envíos). Envía 1 premio por ejecución.
```

---

## ✅ Checklist de Migración

### Backend (Django):

- [ ] Crear archivo `ventas/views/cron_views.py`
- [ ] Implementar `cron_procesar_premios_bienvenida()`
- [ ] Implementar `cron_enviar_premios_aprobados()`
- [ ] Modificar `ventas/urls.py` para agregar rutas
- [ ] Commit y push a GitHub
- [ ] Verificar deploy en Render

### Configuración cron-job.org:

- [ ] Crear job "Premio Bienvenida - Procesamiento Diario" (8:00 AM)
- [ ] Crear job "Premio - Envío de Emails Aprobados" (cada 30 min)
- [ ] Habilitar ambos jobs
- [ ] Configurar notificaciones de fallo

### Testing:

- [ ] Probar endpoint manualmente: `/ventas/cron/procesar-premios-bienvenida/?token=...`
- [ ] Probar endpoint manualmente: `/ventas/cron/enviar-premios-aprobados/?token=...`
- [ ] Verificar logs en Render después de primera ejecución
- [ ] Verificar en cron-job.org que status = 200

### Limpieza (Opcional):

- [ ] Eliminar `scripts/cron_premio_bienvenida.sh`
- [ ] Eliminar `scripts/cron_premios.sh`
- [ ] Actualizar documentación

---

## 📊 Estado Final Esperado

### Todos los Cron Jobs en cron-job.org:

| Módulo | Cron Job | Frecuencia | Endpoint |
|--------|----------|------------|----------|
| Control Gestión | Preparación Servicios | Cada 15 min | `/control_gestion/cron/preparacion-servicios/` |
| Control Gestión | Vaciado Tinas | Cada 30 min | `/control_gestion/cron/vaciado-tinas/` |
| Control Gestión | Apertura Diaria | 7:00 AM | `/control_gestion/cron/daily-opening/` |
| Control Gestión | Reporte Matutino | 9:00 AM | `/control_gestion/cron/daily-reports/?momento=matutino` |
| Control Gestión | Reporte Vespertino | 6:00 PM | `/control_gestion/cron/daily-reports/?momento=vespertino` |
| **Premios** | **Procesar Bienvenida** | **8:00 AM** | **/ventas/cron/procesar-premios-bienvenida/** |
| **Premios** | **Enviar Aprobados** | **Cada 30 min** | **/ventas/cron/enviar-premios-aprobados/** |

**Total**: 7 cron jobs automatizados vía HTTP

---

## 🎯 Beneficios de la Migración

1. ✅ **Centralización**: Todos los cron jobs en cron-job.org (un solo panel)
2. ✅ **Monitoreo**: Dashboard visual con historial de ejecuciones
3. ✅ **Alertas**: Notificaciones automáticas si fallan
4. ✅ **Logs**: Cada ejecución registrada con status code y output
5. ✅ **Sin límites**: Render Cron Jobs limita a 1 job por servicio free
6. ✅ **Portabilidad**: Si migras de Render, los cron jobs siguen funcionando
7. ✅ **Testing**: Puedes ejecutar manualmente desde cron-job.org

---

## 🚨 Notas Importantes

### Rate Limiting del Comando `enviar_premios_aprobados`:

El comando internamente:
- Envía **máximo 1 premio** por ejecución
- Verifica que hayan pasado **30 minutos** desde el último envío
- Esto evita spam y problemas con proveedores de email

**Por eso ejecutamos cada 30 minutos**, así envía ~48 premios/día máximo.

### Timing del Comando `procesar_premios_bienvenida`:

- Ejecuta **1 vez al día** (8:00 AM)
- Procesa todos los clientes con check-in hace **exactamente 3 días**
- Si un cliente no se procesa, será procesado al día siguiente (4 días después)

---

## 📚 Documentación Relacionada

- `docs/ESTADO_CRON_JOBS.md` - Estado de cron jobs de control_gestion
- `docs/ANALISIS_PROBLEMA_PREMIOS.md` - Análisis de lógica de premios
- `ventas/management/commands/procesar_premios_bienvenida.py` - Comando procesamiento
- `ventas/management/commands/enviar_premios_aprobados.py` - Comando envío

---

**Última actualización**: 11 de noviembre, 2025
**Estado**: ⚠️ **PENDIENTE DE IMPLEMENTACIÓN**
**Prioridad**: 🔴 ALTA (automatización de premios es crítica)
