# 🔧 Configuración de Google Cloud Storage para Aremko

## 📋 Resumen del Problema
Las imágenes del sistema no están cargando debido a problemas con la configuración de Google Cloud Storage:
- URLs malformadas en el bucket actual
- Error 500 al intentar subir nuevas imágenes
- Necesidad de reconfigurar o crear una nueva cuenta de GCS

## 🎯 Objetivo
Configurar correctamente Google Cloud Storage para que el sistema pueda:
- Subir imágenes desde el admin de Django
- Servir imágenes en las gift cards y el sitio web
- Mantener las imágenes accesibles públicamente

## 📝 Paso 1: Crear Proyecto en Google Cloud Platform

### 1.1 Acceder a Google Cloud Console
1. Ir a https://console.cloud.google.com
2. Iniciar sesión con tu cuenta de Google
3. Si es primera vez, aceptar los términos de servicio

### 1.2 Crear un Nuevo Proyecto
1. Click en el selector de proyectos (arriba a la izquierda)
2. Click en "Nuevo Proyecto"
3. Configurar:
   - **Nombre del proyecto**: `aremko-media`
   - **ID del proyecto**: Se generará automáticamente (ejemplo: `aremko-media-123456`)
4. Click en "CREAR"
5. Esperar a que se cree el proyecto (30 segundos aproximadamente)

## 📦 Paso 2: Habilitar Cloud Storage API

1. En el menú lateral, ir a **"APIs y servicios"** > **"Biblioteca"**
2. Buscar **"Cloud Storage API"**
3. Click en el resultado
4. Click en **"HABILITAR"**
5. Esperar a que se active (10-15 segundos)

## 🪣 Paso 3: Crear un Bucket de Storage

### 3.1 Acceder a Cloud Storage
1. En el menú lateral, ir a **"Storage"** > **"Buckets"**
2. Click en **"CREAR BUCKET"**

### 3.2 Configurar el Bucket
1. **Nombre del bucket**: `aremko-media-prod`
   - Nota: El nombre debe ser único globalmente
   - Si no está disponible, prueba: `aremko-cl-media-prod`
2. **Ubicación**:
   - Tipo: **"Region"**
   - Seleccionar: **"southamerica-west1 (Santiago)"** para menor latencia
3. **Clase de almacenamiento**: **"Standard"**
4. **Control de acceso**:
   - Seleccionar: **"Uniforme"**
   - NO marcar "Aplicar prevención de acceso público"
5. **Protección de datos**: Dejar valores por defecto
6. Click en **"CREAR"**

### 3.3 Configurar Permisos Públicos del Bucket
1. Una vez creado, click en el nombre del bucket
2. Ir a la pestaña **"PERMISOS"**
3. Click en **"OTORGAR ACCESO"**
4. En "Principales nuevos", escribir: `allUsers`
5. En "Rol", seleccionar: **"Storage Object Viewer"**
6. Click en **"GUARDAR"**
7. Confirmar que queremos hacer el bucket público

## 🔑 Paso 4: Crear Cuenta de Servicio

### 4.1 Crear la Cuenta de Servicio
1. En el menú lateral, ir a **"IAM y administración"** > **"Cuentas de servicio"**
2. Click en **"CREAR CUENTA DE SERVICIO"**
3. Configurar:
   - **Nombre**: `django-media-uploader`
   - **ID de cuenta de servicio**: Se auto-genera
   - **Descripción**: "Cuenta para que Django suba imágenes a GCS"
4. Click en **"CREAR Y CONTINUAR"**

### 4.2 Asignar Roles
1. En "Otorgar a esta cuenta de servicio acceso al proyecto"
2. Agregar los siguientes roles:
   - **"Storage Admin"** (para crear y eliminar objetos)
   - **"Storage Object Admin"** (para administrar objetos)
3. Click en **"CONTINUAR"**
4. Click en **"LISTO"**

### 4.3 Generar Clave JSON
1. Click en la cuenta de servicio recién creada
2. Ir a la pestaña **"CLAVES"**
3. Click en **"AGREGAR CLAVE"** > **"Crear clave nueva"**
4. Seleccionar formato: **"JSON"**
5. Click en **"CREAR"**
6. Se descargará automáticamente un archivo JSON
7. **IMPORTANTE**: Guardar este archivo de forma segura

## 🔧 Paso 5: Configurar Variables de Entorno en Render

### 5.1 Preparar el Archivo de Credenciales
1. Abrir el archivo JSON descargado
2. Copiar TODO su contenido
3. Minificarlo (eliminar saltos de línea y espacios innecesarios)
   - Puedes usar: https://www.minifyjson.org/
4. Copiar el JSON minificado

### 5.2 Configurar en Render
1. Ir a https://dashboard.render.com
2. Seleccionar tu servicio web de Django
3. Ir a **"Environment"**
4. Agregar las siguientes variables de entorno:

```bash
# Credenciales de Google Cloud Storage
GS_BUCKET_NAME=aremko-media-prod
GS_PROJECT_ID=aremko-media-123456  # Usar tu ID de proyecto real
GOOGLE_APPLICATION_CREDENTIALS=gcs-credentials.json

# Contenido del archivo de credenciales (JSON minificado)
GCS_CREDENTIALS_JSON={"type":"service_account","project_id":"aremko-media-123456",...}
```

## 📂 Paso 6: Actualizar Configuración de Django

### 6.1 Crear Script para Manejar Credenciales
Crear un archivo para generar el archivo de credenciales desde la variable de entorno:

```python
# scripts/setup_gcs_credentials.py
import os
import json
from pathlib import Path

def setup_gcs_credentials():
    """
    Crea el archivo de credenciales de GCS desde la variable de entorno.
    Se ejecuta al inicio del servidor en Render.
    """
    credentials_json = os.getenv('GCS_CREDENTIALS_JSON')

    if not credentials_json:
        print("⚠️ GCS_CREDENTIALS_JSON no configurado - usando almacenamiento local")
        return False

    try:
        # Parsear el JSON para validarlo
        credentials_data = json.loads(credentials_json)

        # Crear el archivo de credenciales
        credentials_path = Path('/tmp/gcs-credentials.json')
        with open(credentials_path, 'w') as f:
            json.dump(credentials_data, f)

        # Configurar la variable de entorno para que Google Cloud la encuentre
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = str(credentials_path)

        print(f"✅ Credenciales de GCS configuradas exitosamente")
        print(f"   Proyecto: {credentials_data.get('project_id')}")
        print(f"   Cuenta: {credentials_data.get('client_email')}")
        return True

    except json.JSONDecodeError as e:
        print(f"❌ Error al parsear GCS_CREDENTIALS_JSON: {e}")
        return False
    except Exception as e:
        print(f"❌ Error configurando credenciales GCS: {e}")
        return False

if __name__ == "__main__":
    setup_gcs_credentials()
```

### 6.2 Actualizar settings.py
Modificar el archivo `aremko_project/settings.py`:

```python
# Al inicio del archivo, después de los imports
from pathlib import Path
import dj_database_url

# Agregar setup de credenciales GCS
import sys
if 'runserver' in sys.argv or 'gunicorn' in sys.argv[0]:
    try:
        from scripts.setup_gcs_credentials import setup_gcs_credentials
        setup_gcs_credentials()
    except ImportError:
        pass

# ... resto del código ...

# Actualizar la configuración de Media files (línea ~152)
# Media files configuration (Local vs GCS)
GCS_CREDENTIALS_JSON = os.getenv('GCS_CREDENTIALS_JSON')
if GCS_CREDENTIALS_JSON:
    # Setup de credenciales en tiempo de ejecución
    try:
        import json
        credentials_data = json.loads(GCS_CREDENTIALS_JSON)
        credentials_path = Path('/tmp/gcs-credentials.json')
        with open(credentials_path, 'w') as f:
            json.dump(credentials_data, f)
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = str(credentials_path)

        # Configurar Django Storages
        DEFAULT_FILE_STORAGE = 'storages.backends.gcloud.GoogleCloudStorage'
        GS_BUCKET_NAME = os.getenv('GS_BUCKET_NAME', 'aremko-media-prod')
        GS_PROJECT_ID = credentials_data.get('project_id')
        GS_FILE_OVERWRITE = False
        GS_QUERYSTRING_AUTH = False
        GS_DEFAULT_ACL = 'publicRead'  # Hacer archivos públicos por defecto

        # URLs públicas
        MEDIA_URL = f'https://storage.googleapis.com/{GS_BUCKET_NAME}/'

        logger.info(f"✅ GCS configurado: bucket={GS_BUCKET_NAME}, proyecto={GS_PROJECT_ID}")
    except Exception as e:
        logger.error(f"❌ Error configurando GCS: {e}")
        # Fallback a almacenamiento local
        MEDIA_URL = '/media/'
        MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
else:
    # Almacenamiento local por defecto
    MEDIA_URL = '/media/'
    MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
    logger.warning("⚠️ GCS no configurado - usando almacenamiento local")
```

## 🧪 Paso 7: Pruebas y Verificación

### 7.1 Script de Prueba
Crear un script para verificar la configuración:

```python
# scripts/test_gcs_upload.py
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
import logging

logger = logging.getLogger(__name__)

def test_gcs_upload():
    """Prueba la subida de archivos a Google Cloud Storage"""

    print("🧪 Iniciando prueba de GCS...")

    # 1. Verificar configuración
    from django.conf import settings
    print(f"✓ Storage backend: {settings.DEFAULT_FILE_STORAGE}")
    print(f"✓ Bucket: {getattr(settings, 'GS_BUCKET_NAME', 'No configurado')}")
    print(f"✓ Project ID: {getattr(settings, 'GS_PROJECT_ID', 'No configurado')}")

    # 2. Crear archivo de prueba
    test_content = b"Test de subida a GCS - Aremko"
    test_file = ContentFile(test_content, name='test/gcs_test.txt')

    try:
        # 3. Subir archivo
        print("📤 Subiendo archivo de prueba...")
        path = default_storage.save('test/gcs_test.txt', test_file)
        print(f"✅ Archivo subido: {path}")

        # 4. Verificar URL
        url = default_storage.url(path)
        print(f"🔗 URL pública: {url}")

        # 5. Verificar existencia
        exists = default_storage.exists(path)
        print(f"✓ Archivo existe: {exists}")

        # 6. Limpiar
        print("🗑️ Eliminando archivo de prueba...")
        default_storage.delete(path)
        print("✅ Prueba completada exitosamente!")

        return True

    except Exception as e:
        print(f"❌ Error en la prueba: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_gcs_upload()
```

### 7.2 Ejecutar Prueba en Render
1. Acceder al Shell de Render
2. Ejecutar:
```bash
cd /app
python scripts/test_gcs_upload.py
```

## 🔄 Paso 8: Migrar Imágenes Existentes (Opcional)

Si tienes imágenes en el bucket antiguo que quieres migrar:

```python
# scripts/migrate_images_to_new_bucket.py
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from ventas.models import Servicio, Cabaña, Tina, Masaje
from django.core.files.storage import default_storage
import requests

def migrate_model_images(model_class, image_field='imagen'):
    """Migra imágenes de un modelo al nuevo bucket"""

    model_name = model_class.__name__
    print(f"\n📦 Migrando imágenes de {model_name}...")

    migrated = 0
    failed = 0

    for obj in model_class.objects.all():
        image = getattr(obj, image_field, None)
        if not image:
            continue

        try:
            # Si la imagen ya está en el nuevo bucket, skip
            if 'aremko-media-prod' in str(image.url):
                print(f"  ✓ {obj}: Ya migrado")
                continue

            # Descargar imagen del bucket antiguo
            old_url = image.url
            response = requests.get(old_url)
            if response.status_code == 200:
                # Subir al nuevo bucket
                from django.core.files.base import ContentFile
                new_image = ContentFile(response.content)
                image.save(image.name, new_image, save=True)
                print(f"  ✅ {obj}: Migrado exitosamente")
                migrated += 1
            else:
                print(f"  ❌ {obj}: No se pudo descargar imagen antigua")
                failed += 1

        except Exception as e:
            print(f"  ❌ {obj}: Error - {e}")
            failed += 1

    print(f"  Resumen: {migrated} migradas, {failed} fallidas")
    return migrated, failed

def main():
    """Migra todas las imágenes al nuevo bucket"""

    print("🔄 MIGRACIÓN DE IMÁGENES A NUEVO BUCKET GCS")
    print("=" * 50)

    total_migrated = 0
    total_failed = 0

    # Migrar cada modelo
    for model in [Servicio, Cabaña, Tina, Masaje]:
        migrated, failed = migrate_model_images(model)
        total_migrated += migrated
        total_failed += failed

    print("\n" + "=" * 50)
    print(f"✅ MIGRACIÓN COMPLETADA")
    print(f"   Total migradas: {total_migrated}")
    print(f"   Total fallidas: {total_failed}")

if __name__ == "__main__":
    main()
```

## ✅ Paso 9: Verificación Final

### 9.1 Verificar en Django Admin
1. Acceder a https://aremko.cl/admin
2. Ir a cualquier servicio (Tinas, Masajes, Cabañas)
3. Intentar subir una nueva imagen
4. Verificar que se sube sin error 500

### 9.2 Verificar en Gift Cards
1. Generar una nueva gift card
2. Verificar que las imágenes de servicios aparecen correctamente

### 9.3 Verificar en el Sitio Web
1. Navegar por las páginas de servicios
2. Confirmar que todas las imágenes cargan correctamente

## 🚨 Troubleshooting

### Error: "Permission denied"
- Verificar que la cuenta de servicio tiene rol "Storage Admin"
- Verificar que el bucket permite acceso público

### Error: "Invalid credentials"
- Verificar que el JSON de credenciales está correctamente minificado
- Verificar que no hay caracteres extra al copiar/pegar

### Error: "Bucket not found"
- Verificar que el nombre del bucket en GS_BUCKET_NAME coincide exactamente
- Verificar que el bucket existe en el proyecto correcto

### Las imágenes no son públicas
- Verificar que `allUsers` tiene rol "Storage Object Viewer" en el bucket
- Verificar que GS_DEFAULT_ACL = 'publicRead' está configurado

## 📚 Referencias

- [Documentación de Google Cloud Storage](https://cloud.google.com/storage/docs)
- [Django Storages - GCS Backend](https://django-storages.readthedocs.io/en/latest/backends/gcloud.html)
- [Render Environment Variables](https://render.com/docs/environment-variables)

## 🔐 Seguridad

⚠️ **IMPORTANTE**:
- Nunca compartir el archivo JSON de credenciales públicamente
- Nunca commitear credenciales en Git
- Rotar las claves periódicamente
- Usar el principio de menor privilegio para los roles

---

**Última actualización**: 2025-12-09
**Autor**: Sistema de Booking Aremko