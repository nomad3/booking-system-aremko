# Scripts de Diagnóstico para SendGrid

Estos scripts te ayudan a diagnosticar problemas con el envío de correos a través de SendGrid.

## Scripts Disponibles

### 1. `test_sendgrid_simple.py` (Recomendado)
Script básico que no requiere librerías adicionales. Solo usa módulos estándar de Python.

**Características:**
- Verifica variables de entorno
- Prueba conexión SMTP
- Opción de enviar correo de prueba
- No requiere instalaciones adicionales

### 2. `test_sendgrid_full.py`
Script completo con pruebas exhaustivas de la API de SendGrid.

**Características:**
- Todo lo del script simple, más:
- Verificación directa de la API de SendGrid
- Obtiene información de la cuenta
- Muestra estadísticas recientes
- Envío de correos via API y SMTP

**Requiere:** `pip install requests`

## Uso en Render Shell

### Opción 1: Ejecutar Script Simple (Recomendado)

```bash
# En la shell de Render, ejecutar:
python scripts/diagnostics/test_sendgrid_simple.py
```

### Opción 2: Ejecutar Script Completo

```bash
# Primero instalar dependencias (si es necesario)
pip install requests

# Luego ejecutar:
python scripts/diagnostics/test_sendgrid_full.py
```

### Opción 3: Test Rápido de Variables

Si solo quieres verificar las variables de entorno:

```bash
python -c "import os; vars=['SENDGRID_API_KEY','EMAIL_HOST','EMAIL_PORT','DEFAULT_FROM_EMAIL']; [print(f'{v}: {os.getenv(v, \"NO SET\")}') for v in vars]"
```

### Opción 4: Test Rápido de Conexión

Para una prueba rápida de conexión SMTP:

```bash
python -c "import os,smtplib;k=os.getenv('SENDGRID_API_KEY')or os.getenv('EMAIL_HOST_PASSWORD');s=smtplib.SMTP('smtp.sendgrid.net',587);s.starttls();s.login('apikey',k);print('✅ SendGrid OK');s.quit()"
```

## Variables de Entorno Requeridas

Configura estas variables en Render (Settings → Environment Variables):

```env
# API Key de SendGrid (obligatorio)
SENDGRID_API_KEY=SG.xxxxxxxxxxxxxx...

# Configuración SMTP
EMAIL_HOST=smtp.sendgrid.net
EMAIL_PORT=587
EMAIL_HOST_USER=apikey
EMAIL_HOST_PASSWORD=SG.xxxxxxxxxxxxxx...  # Mismo valor que SENDGRID_API_KEY

# Correo remitente por defecto
DEFAULT_FROM_EMAIL=ventas@aremko.cl
```

## Configuración en Django

### Opción A: SendGrid via SMTP

En tu `settings.py`:

```python
import os

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.sendgrid.net'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'apikey'  # Siempre 'apikey' para SendGrid
EMAIL_HOST_PASSWORD = os.environ.get('SENDGRID_API_KEY')
DEFAULT_FROM_EMAIL = 'ventas@aremko.cl'
SERVER_EMAIL = 'ventas@aremko.cl'
```

### Opción B: SendGrid via API

Instalar: `pip install django-sendgrid-v5`

En tu `settings.py`:

```python
import os

EMAIL_BACKEND = 'sendgrid_backend.SendgridBackend'
SENDGRID_API_KEY = os.environ.get('SENDGRID_API_KEY')
SENDGRID_SANDBOX_MODE_IN_DEBUG = False
DEFAULT_FROM_EMAIL = 'ventas@aremko.cl'
```

## Solución de Problemas Comunes

### Error: "Authentication failed"
- Verifica que la API Key empiece con `SG.`
- Regenera la API Key en el dashboard de SendGrid
- Asegúrate de que tenga permisos de "Mail Send"

### Error: "No API Key found"
- Agrega `SENDGRID_API_KEY` en las variables de entorno de Render
- O usa `EMAIL_HOST_PASSWORD` con el valor de la API Key

### Los correos no llegan
- Verifica el Activity Feed en SendGrid: https://app.sendgrid.com/email_activity
- Revisa que el dominio esté verificado en Sender Authentication
- Verifica los filtros de spam en el correo destino

### Error de conexión timeout
- Verifica que Render tenga acceso a internet externo
- Revisa si hay restricciones de firewall

## Verificación en SendGrid Dashboard

1. **API Keys**: https://app.sendgrid.com/settings/api_keys
   - Verifica que tu API Key tenga permisos de "Mail Send"

2. **Sender Authentication**: https://app.sendgrid.com/settings/sender_auth
   - Verifica que el dominio aremko.cl esté verificado

3. **Activity Feed**: https://app.sendgrid.com/email_activity
   - Revisa el estado de los correos enviados

4. **Statistics**: https://app.sendgrid.com/statistics
   - Verifica las estadísticas de envío

## Contacto y Soporte

- SendGrid Support: https://support.sendgrid.com/
- SendGrid Status: https://status.sendgrid.com/
- API Documentation: https://docs.sendgrid.com/