# 📧 Configurar Email Gmail para Envío de Premios

## 🔍 Problema Identificado

Los premios aprobados **NO se están enviando por email** porque las credenciales de Gmail no están configuradas en Render.

### ¿Qué está pasando actualmente?

El código en `settings.py` (líneas 204-206) tiene un **fallback automático** a modo consola:

```python
if not os.getenv('EMAIL_HOST_USER') or not os.getenv('EMAIL_HOST_PASSWORD'):
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
    logger.warning("⚠️ EMAIL_HOST_USER/PASSWORD no configurados - usando console backend")
```

**Resultado:** Los emails se escriben en los logs de Render pero **NO se envían** a los clientes reales.

---

## ✅ Solución: Configurar Gmail SMTP en Render

### Paso 1: Generar App Password en Gmail

Gmail requiere una **App Password** (no tu contraseña normal) para aplicaciones de terceros.

1. **Ve a tu cuenta de Gmail**:
   - Ir a: https://myaccount.google.com/apppasswords

2. **Verificación de dos factores (requerida)**:
   - Si no está activada, actívala primero en:
     https://myaccount.google.com/security

3. **Crear App Password**:
   - Nombre de la aplicación: `Aremko Premios`
   - Google generará una contraseña de 16 caracteres (ej: `abcd efgh ijkl mnop`)
   - **⚠️ IMPORTANTE:** Copia esta contraseña, solo se muestra una vez

### Paso 2: Configurar Variables de Entorno en Render

1. **Ir al Dashboard de Render**:
   - Ir a: https://dashboard.render.com/
   - Seleccionar el servicio: `aremko-booking-system-prod`

2. **Ir a Environment**:
   - En el menú lateral: **Environment**

3. **Agregar estas 3 variables**:

   ```bash
   EMAIL_HOST_USER=comunicaciones@aremko.cl
   EMAIL_HOST_PASSWORD=abcd efgh ijkl mnop  # La App Password de Gmail
   DEFAULT_FROM_EMAIL=comunicaciones@aremko.cl
   ```

   **Valores recomendados:**
   - `EMAIL_HOST_USER`: El email de Gmail que enviará los correos (ej: `comunicaciones@aremko.cl`)
   - `EMAIL_HOST_PASSWORD`: La App Password de 16 caracteres generada en Paso 1
   - `DEFAULT_FROM_EMAIL`: El remitente que verán los clientes (puede ser el mismo que EMAIL_HOST_USER)

4. **Guardar Cambios**:
   - Click en **Save Changes**
   - Render hará un **redeploy automático**

### Paso 3: Verificar Configuración

Una vez que Render termine el redeploy (aprox. 5-10 minutos):

1. **Revisar logs**:
   - En Render Dashboard → **Logs**
   - Buscar línea de inicio: Deberías ver que NO aparece el warning:
     ```
     ⚠️ EMAIL_HOST_USER/PASSWORD no configurados - usando console backend
     ```
   - Si no aparece el warning = **configuración correcta** ✅

2. **Probar envío de premio**:
   - Aprobar un premio en el admin
   - Esperar a que el cron job `cron-enviar-premios-aprobados` se ejecute (cada 30 min)
   - O ejecutar manualmente en Render Shell:
     ```bash
     python manage.py enviar_premios_aprobados --limit 1
     ```

3. **Verificar email recibido**:
   - Revisar la bandeja de entrada del cliente
   - También revisar **spam/correo no deseado** en la primera prueba

---

## 📋 Configuración Actual en settings.py

El código ya está listo para Gmail SMTP (líneas 200-214):

```python
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
```

**✅ No requiere cambios de código** - Solo configurar variables de entorno en Render.

---

## 🔒 Seguridad

- **NUNCA** subas la App Password a Git
- Solo configúrala en Render Dashboard como variable de entorno
- Si la App Password se compromete, revócala desde: https://myaccount.google.com/apppasswords

---

## 🧪 Testing Manual (Opcional)

Si quieres probar el envío inmediatamente después de configurar:

1. **Conectar a Render Shell**:
   ```bash
   # En Render Dashboard → Shell
   python manage.py shell
   ```

2. **Enviar email de prueba**:
   ```python
   from django.core.mail import send_mail

   send_mail(
       subject='Prueba de Email - Aremko',
       message='Este es un email de prueba',
       from_email='comunicaciones@aremko.cl',
       recipient_list=['tu-email@gmail.com'],  # Cambia por tu email
       fail_silently=False,
   )
   ```

3. **Verificar**:
   - Si no hay errores = **Email enviado** ✅
   - Revisar tu bandeja de entrada (y spam)

---

## 📚 Recursos

- **Gmail App Passwords**: https://support.google.com/accounts/answer/185833
- **Django Email Backend**: https://docs.djangoproject.com/en/4.2/topics/email/
- **Render Environment Variables**: https://render.com/docs/environment-variables

---

## ⚠️ Troubleshooting

### Error: "Username and Password not accepted"
- **Causa:** App Password incorrecta o autenticación de 2 factores no activada
- **Solución:** Regenerar App Password y verificar que 2FA esté activo

### Error: "SMTPAuthenticationError"
- **Causa:** Credenciales incorrectas
- **Solución:** Verificar EMAIL_HOST_USER y EMAIL_HOST_PASSWORD en Render

### Emails llegan a spam
- **Causa:** Gmail nuevo o bajo volumen de envíos
- **Solución:** Los clientes deben marcar como "No es spam" las primeras veces
- **Mejora futura:** Configurar SPF, DKIM, DMARC en el dominio @aremko.cl

---

## ✅ Checklist de Configuración

- [ ] Activar autenticación de 2 factores en Gmail
- [ ] Generar App Password en Gmail
- [ ] Agregar EMAIL_HOST_USER en Render
- [ ] Agregar EMAIL_HOST_PASSWORD en Render
- [ ] Agregar DEFAULT_FROM_EMAIL en Render
- [ ] Esperar redeploy automático
- [ ] Verificar logs (no debe aparecer warning de console backend)
- [ ] Probar envío con premio aprobado
- [ ] Verificar recepción de email

---

**Creado:** 2025-01-24
**Última actualización:** 2025-01-24
**Autor:** Claude Code Assistant
