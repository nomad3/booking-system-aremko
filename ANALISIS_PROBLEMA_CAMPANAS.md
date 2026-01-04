# Análisis: Por qué las campañas se detienen después de 2 lotes

## 🔍 Síntomas observados

Del log:
```
📤 Enviando lote 7: 50 emails
📧✅ pamela.romero.m@gmail.com
📧✅ anibalfs.ingeniero@gmail.com
...
📧✅ gallegosa1220@gmail.com
⏸️ Pausa de 12 minutos...
```

**Después de esto, el proceso se detiene** y no continúa enviando más lotes.

## 🎯 Causas identificadas

### 1. **Proceso background sin supervisión** ⚠️ CAUSA PRINCIPAL

Cuando ejecutamos la campaña desde el admin con:

```python
subprocess.Popen(
    ['python', 'manage.py', 'enviar_campana_email', '--campaign-id=X'],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    start_new_session=True
)
```

**Problemas:**

- ✅ El proceso se desacopla del worker HTTP (evita timeout)
- ❌ El proceso NO está supervisado por Gunicorn
- ❌ Si el proceso muere, nadie lo reinicia
- ❌ Los logs van a `DEVNULL` - no podemos ver qué pasó
- ❌ **Render puede matar procesos background no supervisados**

### 2. **Render Free Tier - Limitaciones de recursos**

En Render free tier:
- Solo se garantiza el proceso web principal
- Los procesos background pueden ser matados por:
  - Uso excesivo de memoria
  - Tiempo de ejecución prolongado
  - Políticas de inactividad
  - Reinicio del dyno/container

### 3. **Pérdida de contexto durante time.sleep()**

Línea 189 del comando:
```python
time.sleep(campaign_interval * 60)  # Duerme 6-15 minutos
```

Durante este tiempo:
- El proceso está "idle" (no hace nada visible)
- Render puede interpretarlo como inactivo y matarlo
- Si el container se reinicia, el proceso se pierde

### 4. **Sin persistencia de estado**

El comando actual:
- No guarda progreso intermedio
- Si muere, no sabe desde dónde continuar
- Los recipients marcados como 'pending' no se actualizan hasta el final

## 📊 Flujo actual del comando

```
1. Inicio: Obtiene todos los recipients pendientes
2. Loop: For each batch
   a. Envía 50 emails
   b. Marca como enviados
   c. DUERME 12 minutos  ← AQUÍ PUEDE SER MATADO
3. Fin: Marca campaña como completada
```

**Si el proceso muere en el paso 2c:**
- Los emails del lote actual ya fueron enviados ✅
- Los siguientes lotes NO se enviarán ❌
- La campaña queda en estado 'sending' ⚠️
- No hay logs del error porque stdout=DEVNULL

## 🔧 Posibles soluciones

### Solución A: Cron Job Periódico (RECOMENDADA) ⭐

**Crear un cron job que ejecute cada 5 minutos:**

```bash
*/5 * * * * python manage.py enviar_campana_email --auto --ignore-schedule
```

**Ventajas:**
- ✅ El comando se ejecuta periódicamente
- ✅ Si una ejecución muere, la siguiente continúa
- ✅ Render soporta cron jobs nativamente
- ✅ Los recipients 'pending' se procesan en cada ejecución
- ✅ No requiere cambios en el código

**Desventajas:**
- ⚠️ Puede haber pequeñas demoras entre lotes
- ⚠️ Requiere configurar cron en Render

### Solución B: Mejorar el proceso background actual

**Cambios necesarios:**

1. **Guardar logs en archivo en lugar de DEVNULL:**
```python
log_file = open('/tmp/campaign_{campaign.id}.log', 'a')
subprocess.Popen(
    ['python', 'manage.py', 'enviar_campana_email', ...],
    stdout=log_file,
    stderr=log_file,
    start_new_session=True
)
```

2. **Procesar en chunks más pequeños con reinicio automático:**
```python
# En lugar de procesar TODOS los lotes en un comando
# Procesar solo 2-3 lotes y salir
# El cron job lo reiniciará
```

3. **Marcar progreso en cada lote:**
```python
# Actualizar campaign.last_batch_sent después de cada lote
# Permitir reanudar desde el último lote enviado
```

### Solución C: Worker dedicado (Celery/RQ)

**Requiere:**
- Instalar Redis
- Configurar Celery/RQ
- Mover lógica de envío a tasks asíncronas
- **No disponible en Render free tier**

## 🎯 Solución recomendada inmediata

**OPCIÓN 1: Configurar Cron Job en Render**

1. Ir a Render Dashboard → Tu servicio → Settings → Cron Jobs
2. Agregar nuevo cron job:
   - **Nombre:** `Enviar campañas de email`
   - **Comando:** `python manage.py enviar_campana_email --auto`
   - **Schedule:** `*/5 * * * *` (cada 5 minutos)

**OPCIÓN 2: Usar cron externo (cron-job.org)**

Ya tienes configurado cron-job.org para otros endpoints. Agregar:
```
URL: https://www.aremko.cl/ventas/cron/enviar-campanas/?token=aremko_cron_secret_2025
Intervalo: Cada 5 minutos
```

Crear el endpoint:
```python
# ventas/views/cron_views.py
@require_GET
def enviar_campanas_cron(request):
    if request.GET.get('token') != 'aremko_cron_secret_2025':
        return HttpResponseForbidden()

    # Ejecutar en background
    subprocess.Popen(
        ['python', 'manage.py', 'enviar_campana_email', '--auto'],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True
    )

    return JsonResponse({'status': 'ok', 'message': 'Campañas iniciadas'})
```

## 📝 Diagnóstico adicional necesario

Para confirmar que el proceso está muriendo:

1. **Ver logs del proceso background:**
```python
# Cambiar temporalmente DEVNULL por archivo:
log_file = open('/tmp/campaign_debug.log', 'a')
subprocess.Popen(..., stdout=log_file, stderr=log_file)
```

2. **Verificar estado del proceso:**
```bash
ps aux | grep "enviar_campana_email"
```

3. **Revisar logs de Render:**
- Ver si hay mensajes de "killed" o "OOM"
- Verificar uso de memoria del proceso

## ⚡ Acción inmediata

**Mientras implementamos la solución permanente:**

1. **Reducir intervalo entre lotes** (de 12 min a 3 min):
   - Menos tiempo "idle" = menos probabilidad de ser matado
   - Modificar `schedule_config` de la campaña

2. **Reducir tamaño de lote** (de 50 a 10-20):
   - Procesos más cortos
   - Menos memoria usada

3. **Ejecutar manualmente cuando se detenga:**
```bash
python manage.py enviar_campana_email --auto
```

## 🎬 Conclusión

**El problema NO es del código**, sino de la **arquitectura de ejecución**.

El uso de `subprocess.Popen()` fue correcto para evitar el WORKER TIMEOUT, pero ahora necesitamos:
- **Supervisión del proceso** (cron job)
- **Logging visible** (no DEVNULL)
- **Reintentos automáticos** (cron cada 5 min)

La solución más simple y efectiva es **agregar un cron job** que ejecute el comando cada 5 minutos. El comando ya está diseñado para manejar múltiples ejecuciones concurrentes de forma segura.
