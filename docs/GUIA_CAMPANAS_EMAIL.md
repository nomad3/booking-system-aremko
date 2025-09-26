# 📧 Guía de Campañas de Email - Aremko CRM

## 🎯 Resumen del Problema y Solución

### ❌ El Problema
Los logs muestran que el sistema de campañas drip se detuvo porque:
1. **Comando faltante**: `send_next_campaign_drip` no existía
2. **Cola vacía**: No había `CommunicationLog` pendientes para procesar
3. **Sin nuevos datos**: No se estaban agregando nuevos emails a la cola

### ✅ La Solución
He creado un sistema completo de campañas drip con los siguientes componentes:

## 🛠️ Comandos Creados

### 1. `send_next_campaign_drip`
**Propósito**: Envía el siguiente email pendiente de la cola (se ejecuta cada 10 minutos en cron)

```bash
python manage.py send_next_campaign_drip
```

**Salida esperada**:
- `"Sin pendientes."` - No hay emails por enviar
- `"Enviado a: email@ejemplo.cl"` - Email enviado exitosamente
- `"Error enviando a: email@ejemplo.cl"` - Falló el envío

### 2. `diagnose_campaign_queue`
**Propósito**: Diagnostica el estado actual de la cola de emails

```bash
python manage.py diagnose_campaign_queue
```

**Información que proporciona**:
- Estado de la cola (pendientes, enviados, fallidos)
- Total de contactos y empresas
- Actividad reciente (últimas 24 horas)
- Últimos 10 logs
- Estado del cache
- Próximo email a enviar

### 3. `seed_campaign_from_csv`
**Propósito**: Carga contactos desde CSV y crea la cola de emails

```bash
# Ejemplo básico
python manage.py seed_campaign_from_csv \
  --csv-file docs/campaign_csv_example.csv \
  --subject "🏨 Reuniones que Inspiran: Descubre el Secreto de los Equipos Más Exitosos en Los Lagos" \
  --template-file templates/emails/prospecting_campaign.html

# Modo simulación (para probar sin crear registros)
python manage.py seed_campaign_from_csv \
  --csv-file docs/campaign_csv_example.csv \
  --subject "Asunto de prueba" \
  --email-body "<h1>Email de prueba</h1><p>Hola {{ nombre }}!</p>" \
  --dry-run
```

### 4. `send_campaign_test_email`
**Propósito**: Envía un email de prueba con la plantilla de campaña

```bash
python manage.py send_campaign_test_email \
  --email jorge@aremko.cl \
  --nombre "Jorge Aguilera" \
  --empresa "Aremko Hotel Spa"
```

## 📊 Flujo de Trabajo Completo

### Paso 1: Preparar Datos
1. **Crear archivo CSV** con formato:
   ```csv
   email,nombre,empresa
   contacto@empresa.cl,Nombre Contacto,Nombre Empresa
   ```
   
2. **Validar formato**: El CSV debe tener al menos `email` y `nombre`

### Paso 2: Sembrar la Cola
```bash
python manage.py seed_campaign_from_csv \
  --csv-file mi_campana.csv \
  --subject "Mi asunto personalizado" \
  --template-file templates/emails/prospecting_campaign.html
```

### Paso 3: Verificar Estado
```bash
python manage.py diagnose_campaign_queue
```

### Paso 4: Activar Cron (Ya configurado en Render)
El cron ejecuta cada 10 minutos:
```bash
python manage.py send_next_campaign_drip
```

## 🎨 Personalización de Emails

### Variables Disponibles en la Plantilla:
- `{{ nombre }}` - Nombre del contacto
- `{{ empresa }}` - Nombre de la empresa
- `{{ email }}` - Email del contacto

### Crear Plantilla Personalizada:
```html
<!DOCTYPE html>
<html>
<body>
    <h1>Hola {{ nombre }}!</h1>
    <p>Nos dirigimos a {{ empresa }} con una propuesta especial...</p>
    <p>Contacto: {{ email }}</p>
</body>
</html>
```

## 📈 Monitoreo y Métricas

### Verificar Progreso:
```bash
python manage.py diagnose_campaign_queue
```

### Estados de Email:
- **PENDING**: En cola, esperando envío
- **SENT**: Enviado exitosamente
- **FAILED**: Falló el envío

### Cache de Progreso:
El sistema mantiene métricas en cache que incluyen:
- Total de emails
- Enviados vs pendientes
- Porcentaje de completado
- Última actualización

## 🚨 Solución de Problemas

### Problema: "Sin pendientes" pero debería haber emails
```bash
# 1. Verificar estado actual
python manage.py diagnose_campaign_queue

# 2. Si no hay pendientes, sembrar nueva cola
python manage.py seed_campaign_from_csv --csv-file nuevo_archivo.csv --subject "Nuevo asunto" --template-file template.html
```

### Problema: Emails no se envían
```bash
# 1. Probar envío manual
python manage.py send_campaign_test_email --email test@ejemplo.cl --nombre "Prueba"

# 2. Verificar configuración de email en settings
# EMAIL_HOST_USER, EMAIL_HOST_PASSWORD, VENTAS_FROM_EMAIL
```

### Problema: Errores en CSV
```bash
# Usar modo simulación para detectar errores
python manage.py seed_campaign_from_csv --csv-file archivo.csv --subject "Test" --email-body "Test" --dry-run
```

## 🔧 Configuración de Render

El cron job está configurado para ejecutar cada 10 minutos:
```bash
*/10 * * * * cd /opt/render/project/src && python manage.py send_next_campaign_drip >> /tmp/cron.log 2>&1
```

## 📝 Ejemplo Completo

```bash
# 1. Probar plantilla
python manage.py send_campaign_test_email \
  --email jorge@aremko.cl \
  --nombre "Jorge" \
  --empresa "Aremko"

# 2. Sembrar campaña real
python manage.py seed_campaign_from_csv \
  --csv-file campana_los_lagos.csv \
  --subject "🏨 Reuniones que Inspiran: Descubre el Secreto de los Equipos Más Exitosos en Los Lagos" \
  --template-file templates/emails/prospecting_campaign.html

# 3. Verificar cola
python manage.py diagnose_campaign_queue

# 4. El cron se encargará de enviar 1 email cada 10 minutos automáticamente
```

## 🎯 Siguiente Paso Recomendado

Para reiniciar la campaña inmediatamente:

1. **Subir un nuevo CSV** con los contactos pendientes
2. **Ejecutar el comando de siembra** 
3. **Verificar que la cola se llenó**
4. **El cron enviará automáticamente 1 email cada 10 minutos**

¡Tu sistema de campañas drip está ahora completamente funcional! 🚀