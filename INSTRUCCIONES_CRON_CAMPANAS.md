# ⏰ Configurar Cron Job para Campañas de Email

## 🎯 Objetivo

Configurar un cron job externo que ejecute automáticamente el procesamiento de campañas de email cada 5 minutos, asegurando que las campañas grandes se completen sin interrupciones.

## 📋 Pasos para configurar en cron-job.org

### 1. Acceder a cron-job.org

Ve a: https://cron-job.org/en/

### 2. Crear nuevo cron job

Click en "Create cronjob" o "New cronjob"

### 3. Configurar el cron job

**Título:**
```
Aremko - Procesar Campañas de Email
```

**URL:**
```
https://www.aremko.cl/ventas/cron/enviar-campanas-email/?token=aremko_cron_secret_2025
```

**Método:**
```
GET
```

**Schedule (Intervalo):**
```
*/5 * * * *
```

Esto significa: **Cada 5 minutos**

**Habilitado:**
```
✅ Sí
```

**Notificaciones:**
```
❌ Desactivar notificaciones de éxito
✅ Activar notificaciones solo en caso de error
```

### 4. Guardar y activar

Click en "Create" o "Save"

## ✅ Verificación

Para verificar que funciona:

1. **Ver logs en tiempo real:**
   - Ve a Render Dashboard → Tu servicio → Logs
   - Busca: `✅ Cron enviar_campanas_email iniciado`

2. **Ver historial de ejecuciones:**
   - En cron-job.org → Tu cron job → Execution history
   - Deberías ver status 200 cada 5 minutos

3. **Ver progreso de campaña:**
   - En Django Admin → Email Campaigns
   - La barra de progreso debe ir avanzando

## 📊 Qué hace este cron job

**Cada 5 minutos:**

1. ✅ Verifica si hay campañas en estado 'ready' o 'sending'
2. ✅ Si encuentra campañas, ejecuta el comando en background
3. ✅ El comando procesa los recipients 'pending'
4. ✅ Envía lotes respetando la configuración de la campaña
5. ✅ Si hay más emails pendientes, el siguiente cron continuará

**Ventajas:**

- ✅ Si el proceso background muere, el cron lo reinicia automáticamente
- ✅ Campañas grandes se procesan en múltiples ejecuciones
- ✅ No hay timeouts porque cada ejecución es rápida
- ✅ Compatible con Render free tier

## 🐛 Troubleshooting

### El cron job retorna error 500

**Posibles causas:**
- Token incorrecto en la URL
- El servidor está caído

**Solución:**
- Verificar que el token en la URL sea correcto
- Ver logs de Render para errores

### Las campañas no avanzan

**Posibles causas:**
- Fuera del horario configurado (8:00-21:00 por defecto)
- No hay recipients con status='pending'
- La campaña está en estado incorrecto

**Solución:**
- Verificar horario de la campaña en schedule_config
- Verificar estado de la campaña (debe ser 'ready' o 'sending')
- Ejecutar manualmente: `python manage.py enviar_campana_email --auto`

### Quiero procesar más rápido

**Opción 1:** Cambiar intervalo del cron a cada 3 minutos
```
*/3 * * * *
```

**Opción 2:** Aumentar batch_size en la configuración de la campaña
- Ve a Django Admin → EmailCampaign → Editar
- En schedule_config, cambia "batch_size" de 5 a 10-20

**Opción 3:** Reducir interval_minutes entre lotes
- En schedule_config, cambia "interval_minutes" de 6 a 3

## 📝 Notas importantes

1. **El cron job NO envía emails directamente**, solo inicia el proceso que los envía
2. **Múltiples ejecuciones del cron son seguras**, el comando maneja concurrencia
3. **El envío respeta siempre los horarios configurados** en cada campaña
4. **Los logs del proceso background no se ven** en Render logs (van a DEVNULL para evitar llenar disco)

## 🔗 URLs relacionadas

- **Endpoint:** `/ventas/cron/enviar-campanas-email/`
- **Admin Campañas:** `/admin/ventas/emailcampaign/`
- **Análisis completo:** Ver archivo `ANALISIS_PROBLEMA_CAMPANAS.md`
