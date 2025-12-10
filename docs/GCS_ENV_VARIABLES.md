# 🔐 Variables de Entorno para Google Cloud Storage

## Variables Requeridas en Render

Copia y pega estas variables en la configuración de entorno de tu servicio en Render:

```bash
# Nombre del bucket de Google Cloud Storage
GS_BUCKET_NAME=aremko-media-prod

# ID del proyecto de Google Cloud (obtener del JSON de credenciales)
GS_PROJECT_ID=tu-proyecto-id-aqui

# Credenciales JSON minificadas (todo en una línea)
GCS_CREDENTIALS_JSON={"type":"service_account","project_id":"tu-proyecto","private_key_id":"xxx","private_key":"-----BEGIN PRIVATE KEY-----\nxxx\n-----END PRIVATE KEY-----\n","client_email":"django-media@tu-proyecto.iam.gserviceaccount.com","client_id":"xxx","auth_uri":"https://accounts.google.com/o/oauth2/auth","token_uri":"https://oauth2.googleapis.com/token","auth_provider_x509_cert_url":"https://www.googleapis.com/oauth2/v1/certs","client_x509_cert_url":"xxx"}
```

## 📝 Instrucciones Paso a Paso

### 1. Obtener el JSON de Credenciales
1. Descargar el archivo JSON de tu cuenta de servicio desde Google Cloud Console
2. Abrir el archivo con un editor de texto
3. Copiar TODO el contenido

### 2. Minificar el JSON
1. Ir a https://www.minifyjson.org/
2. Pegar el JSON completo
3. Click en "Minify"
4. Copiar el resultado (todo estará en una línea)

### 3. Configurar en Render
1. Ir a https://dashboard.render.com
2. Seleccionar tu servicio web
3. Ir a "Environment"
4. Agregar cada variable:
   - `GS_BUCKET_NAME`: El nombre de tu bucket (ejemplo: `aremko-media-prod`)
   - `GS_PROJECT_ID`: El ID de tu proyecto (se encuentra en el JSON, campo "project_id")
   - `GCS_CREDENTIALS_JSON`: El JSON completo minificado

### 4. Guardar y Desplegar
1. Click en "Save Changes"
2. El servicio se redesplegará automáticamente
3. Verificar los logs para confirmar: "✅ GCS configurado"

## 🧪 Verificación

Después de configurar, ejecuta en el Shell de Render:

```bash
python scripts/test_gcs_upload.py
```

Deberías ver:
```
✅ PRUEBA COMPLETADA EXITOSAMENTE
La configuración de almacenamiento está funcionando correctamente.
```

## ⚠️ Importante

- **NUNCA** compartir el contenido de `GCS_CREDENTIALS_JSON`
- **NUNCA** commitear estas credenciales en Git
- Mantener el JSON minificado en una sola línea
- Si hay errores de parsing, verificar que no hay saltos de línea

## 🔄 Actualizar Credenciales

Si necesitas rotar las credenciales:

1. Crear nueva clave en Google Cloud Console
2. Descargar el nuevo JSON
3. Minificarlo
4. Actualizar `GCS_CREDENTIALS_JSON` en Render
5. El servicio se redesplegará automáticamente

## 📚 Referencias

- [Google Cloud Console](https://console.cloud.google.com)
- [Render Dashboard](https://dashboard.render.com)
- [Minify JSON Tool](https://www.minifyjson.org/)

---

**Última actualización**: 2025-12-09