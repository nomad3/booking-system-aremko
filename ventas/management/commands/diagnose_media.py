from django.core.management.base import BaseCommand
from django.conf import settings
import os

class Command(BaseCommand):
    help = 'Diagnóstica la configuración de archivos media/GCS'

    def handle(self, *args, **options):
        self.stdout.write("🔍 DIAGNÓSTICO DE ARCHIVOS MEDIA")
        self.stdout.write("=" * 50)
        
        # Variables de entorno
        self.stdout.write("\n📋 VARIABLES DE ENTORNO:")
        gcs_creds = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        self.stdout.write(f"GOOGLE_APPLICATION_CREDENTIALS: {gcs_creds}")
        self.stdout.write(f"GS_BUCKET_NAME: {os.getenv('GS_BUCKET_NAME')}")
        self.stdout.write(f"GS_PROJECT_ID: {os.getenv('GS_PROJECT_ID')}")
        
        # Configuración Django
        self.stdout.write("\n⚙️ CONFIGURACIÓN DJANGO:")
        self.stdout.write(f"DEFAULT_FILE_STORAGE: {getattr(settings, 'DEFAULT_FILE_STORAGE', 'No configurado')}")
        self.stdout.write(f"MEDIA_URL: {settings.MEDIA_URL}")
        self.stdout.write(f"MEDIA_ROOT: {getattr(settings, 'MEDIA_ROOT', 'No configurado')}")
        
        # Verificar archivo de credenciales
        self.stdout.write("\n🔑 VERIFICACIÓN DE CREDENCIALES:")
        if gcs_creds:
            if os.path.exists(gcs_creds):
                self.stdout.write(f"✅ Archivo existe: {gcs_creds}")
                # Verificar permisos
                try:
                    with open(gcs_creds, 'r') as f:
                        content = f.read()
                        if 'project_id' in content:
                            self.stdout.write("✅ Archivo parece válido (contiene project_id)")
                        else:
                            self.stdout.write("❌ Archivo no parece válido")
                except Exception as e:
                    self.stdout.write(f"❌ Error leyendo archivo: {e}")
            else:
                self.stdout.write(f"❌ Archivo NO existe: {gcs_creds}")
        else:
            self.stdout.write("❌ GOOGLE_APPLICATION_CREDENTIALS no configurado")
        
        # Probar conexión a GCS
        self.stdout.write("\n🌐 PRUEBA DE CONEXIÓN A GCS:")
        try:
            from google.cloud import storage
            client = storage.Client()
            bucket_name = getattr(settings, 'GS_BUCKET_NAME', os.getenv('GS_BUCKET_NAME', 'aremkoweb'))
            bucket = client.bucket(bucket_name)
            
            # Listar algunos archivos
            blobs = list(bucket.list_blobs(max_results=5))
            self.stdout.write(f"✅ Conexión exitosa al bucket: {bucket_name}")
            self.stdout.write(f"📁 Archivos encontrados: {len(blobs)}")
            for blob in blobs:
                self.stdout.write(f"   - {blob.name}")
        except Exception as e:
            self.stdout.write(f"❌ Error conectando a GCS: {e}")
        
        # Estado del storage backend
        self.stdout.write("\n💾 STORAGE BACKEND:")
        storage_backend = getattr(settings, 'DEFAULT_FILE_STORAGE', 'django.core.files.storage.FileSystemStorage')
        self.stdout.write(f"Backend activo: {storage_backend}")
        
        if 'gcloud' in storage_backend.lower():
            self.stdout.write("✅ Usando Google Cloud Storage")
        else:
            self.stdout.write("⚠️ Usando almacenamiento local (archivos no persistirán en Render)")
        
        self.stdout.write("\n" + "=" * 50)
        self.stdout.write("✅ Diagnóstico completado")