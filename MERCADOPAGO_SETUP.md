# 🔧 Configuración de Mercado Pago Link

## 📋 Variables de Entorno Requeridas

Para que la integración con Mercado Pago Link funcione correctamente, necesitas configurar las siguientes variables de entorno:

### 🔑 Variables Obligatorias

```bash
# Mercado Pago API
MERCADOPAGO_ACCESS_TOKEN=tu_access_token_aqui
MERCADOPAGO_SANDBOX=true  # true para pruebas, false para producción
```

### 🌐 Variables de URL (Opcionales)

```bash
# URLs base para callbacks (se configuran automáticamente si no se especifican)
BASE_URL=https://tu-dominio.com  # URL base de tu aplicación
```

### 🔐 Cómo Obtener las Credenciales

1. **Crear cuenta en Mercado Pago Developers:**
   - Ve a [developers.mercadopago.com](https://developers.mercadopago.com)
   - Inicia sesión con tu cuenta de Mercado Pago

2. **Crear una aplicación:**
   - Ve a "Tus integraciones" → "Crear aplicación"
   - Completa los datos de tu aplicación
   - Selecciona "Mercado Pago" como plataforma

3. **Obtener credenciales:**
   - En la sección "Credenciales de prueba" encontrarás:
     - `ACCESS_TOKEN` (para pruebas)
   - En la sección "Credenciales de producción" encontrarás:
     - `ACCESS_TOKEN` (para producción)

### 🧪 Configuración para Pruebas

```bash
# Sandbox (Pruebas)
MERCADOPAGO_ACCESS_TOKEN=TEST-1234567890-abcdef-1234567890-abcdef-1234567890
MERCADOPAGO_SANDBOX=true
```

### 🚀 Configuración para Producción

```bash
# Producción
MERCADOPAGO_ACCESS_TOKEN=APP-1234567890-abcdef-1234567890-abcdef-1234567890
MERCADOPAGO_SANDBOX=false
```

### 📱 Configuración de Webhooks

1. **En Mercado Pago Developers:**
   - Ve a tu aplicación → "Webhooks"
   - Agrega la URL: `https://tu-dominio.com/payment/mercadopago/webhook/`
   - Selecciona eventos: `payment`

2. **Verificar webhook:**
   - Mercado Pago enviará un POST a tu webhook
   - El sistema procesará automáticamente los pagos

### 🔍 Verificación de Configuración

Para verificar que la configuración es correcta, puedes usar el comando de prueba:

```bash
# Probar creación de link de pago
python manage.py test_mercadopago_link --booking-id 123 --test-type confirmation
```

### ⚠️ Consideraciones Importantes

1. **Seguridad:**
   - Nunca expongas tus credenciales en el código
   - Usa variables de entorno siempre
   - Mantén separadas las credenciales de prueba y producción

2. **Webhooks:**
   - Asegúrate de que tu servidor sea accesible desde internet
   - Usa HTTPS en producción
   - Configura el webhook correctamente

3. **Testing:**
   - Usa siempre el sandbox para pruebas
   - Verifica que los pagos se procesen correctamente
   - Revisa los logs para errores

### 🐛 Solución de Problemas

**Error: "Mercado Pago no configurado"**
- Verifica que `MERCADOPAGO_ACCESS_TOKEN` esté configurado
- Asegúrate de que la variable esté en el archivo `.env` o en las variables de entorno del servidor

**Error: "Error API Mercado Pago: 401"**
- Verifica que el `ACCESS_TOKEN` sea correcto
- Asegúrate de que no haya espacios extra en la variable

**Error: "Error API Mercado Pago: 400"**
- Verifica que los datos del pago sean correctos
- Revisa que el monto sea válido (mayor a 0)

**Webhook no funciona:**
- Verifica que la URL del webhook sea accesible
- Revisa que el endpoint esté configurado correctamente
- Verifica los logs del servidor

### 📞 Soporte

Si tienes problemas con la configuración:
- Revisa la [documentación oficial de Mercado Pago](https://www.mercadopago.cl/developers)
- Contacta al soporte técnico de Mercado Pago
- Revisa los logs de la aplicación para más detalles