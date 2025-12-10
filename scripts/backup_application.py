#!/usr/bin/env python
"""
Script para crear respaldo completo de la aplicación Aremko.
Este script NO incluye la base de datos (usar Render para eso).
"""

import os
import sys
from pathlib import Path
from datetime import datetime
import json
import shutil

# Agregar el directorio raíz del proyecto al path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')

import django
django.setup()

from django.conf import settings
from ventas.models import Servicio, CategoriaServicio, Cabana, GiftCardExperiencia

print("=" * 60)
print("BACKUP DE APLICACIÓN AREMKO")
print("=" * 60)

# Crear directorio de backup con timestamp
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
backup_dir = BASE_DIR / 'backups' / f'backup_{timestamp}'
backup_dir.mkdir(parents=True, exist_ok=True)

print(f"\n📁 Directorio de backup: {backup_dir}")
print("-" * 40)

# 1. Backup de configuración
print("\n1️⃣ RESPALDANDO CONFIGURACIÓN...")
print("-" * 40)

config_backup = {
    'timestamp': timestamp,
    'python_version': sys.version,
    'django_version': django.__version__,
    'environment_vars': {
        'DEBUG': os.getenv('DEBUG'),
        'ALLOWED_HOSTS': os.getenv('ALLOWED_HOSTS'),
        'CLOUDINARY_CLOUD_NAME': os.getenv('CLOUDINARY_CLOUD_NAME'),
        'DATABASE_URL': '***' if os.getenv('DATABASE_URL') else None,
        'SENDGRID_API_KEY': '***' if os.getenv('SENDGRID_API_KEY') else None,
    },
    'installed_apps': list(settings.INSTALLED_APPS),
    'middleware': list(settings.MIDDLEWARE),
}

config_file = backup_dir / 'config_backup.json'
with open(config_file, 'w') as f:
    json.dump(config_backup, f, indent=2)

print(f"✅ Configuración guardada en: config_backup.json")

# 2. Backup de datos de modelos (estructura, no contenido)
print("\n2️⃣ RESPALDANDO ESTADÍSTICAS DE DATOS...")
print("-" * 40)

data_stats = {
    'servicios': {
        'total': Servicio.objects.count(),
        'con_imagen': Servicio.objects.exclude(imagen='').exclude(imagen__isnull=True).count(),
        'categorias': list(CategoriaServicio.objects.values_list('nombre', flat=True)),
    },
    'cabanas': {
        'total': Cabana.objects.count(),
    },
    'giftcards': {
        'total': GiftCardExperiencia.objects.count(),
    }
}

stats_file = backup_dir / 'data_statistics.json'
with open(stats_file, 'w') as f:
    json.dump(data_stats, f, indent=2, ensure_ascii=False)

print(f"✅ Estadísticas guardadas en: data_statistics.json")
print(f"   Servicios: {data_stats['servicios']['total']}")
print(f"   Cabañas: {data_stats['cabanas']['total']}")
print(f"   Gift Cards: {data_stats['giftcards']['total']}")

# 3. Backup de lista de imágenes actuales en Cloudinary
print("\n3️⃣ RESPALDANDO LISTA DE IMÁGENES...")
print("-" * 40)

images_list = []

for servicio in Servicio.objects.exclude(imagen='').exclude(imagen__isnull=True):
    try:
        images_list.append({
            'servicio_id': servicio.id,
            'servicio_nombre': servicio.nombre,
            'imagen_name': servicio.imagen.name,
            'imagen_url': servicio.imagen.url,
        })
    except Exception as e:
        print(f"⚠️ Error con {servicio.nombre}: {e}")

images_file = backup_dir / 'images_list.json'
with open(images_file, 'w') as f:
    json.dump(images_list, f, indent=2, ensure_ascii=False)

print(f"✅ Lista de imágenes guardada: {len(images_list)} imágenes")

# 4. Backup de archivos importantes
print("\n4️⃣ RESPALDANDO ARCHIVOS IMPORTANTES...")
print("-" * 40)

important_files = [
    'requirements.txt',
    'Dockerfile',
    'render.yaml',
    '.gitignore',
    'README.md',
]

files_dir = backup_dir / 'important_files'
files_dir.mkdir(exist_ok=True)

copied = 0
for file in important_files:
    source = BASE_DIR / file
    if source.exists():
        shutil.copy2(source, files_dir / file)
        print(f"   ✓ {file}")
        copied += 1
    else:
        print(f"   ⚠️ {file} no encontrado")

print(f"✅ Archivos copiados: {copied}/{len(important_files)}")

# 5. Lista de scripts disponibles
print("\n5️⃣ LISTANDO SCRIPTS DISPONIBLES...")
print("-" * 40)

scripts_dir = BASE_DIR / 'scripts'
scripts_list = []

if scripts_dir.exists():
    for script in scripts_dir.glob('*.py'):
        scripts_list.append({
            'nombre': script.name,
            'tamaño': script.stat().st_size,
            'modificado': datetime.fromtimestamp(script.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')
        })

scripts_file = backup_dir / 'scripts_list.json'
with open(scripts_file, 'w') as f:
    json.dump(scripts_list, f, indent=2)

print(f"✅ Scripts listados: {len(scripts_list)}")

# 6. Crear archivo README del backup
print("\n6️⃣ CREANDO README DEL BACKUP...")
print("-" * 40)

readme_content = f"""# BACKUP AREMKO - {timestamp}

## Información del Backup

- **Fecha**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- **Versión Django**: {django.__version__}
- **Versión Python**: {sys.version.split()[0]}

## Contenido del Backup

1. **config_backup.json**: Configuración de Django y variables de entorno
2. **data_statistics.json**: Estadísticas de datos en la base de datos
3. **images_list.json**: Lista completa de imágenes en Cloudinary
4. **important_files/**: Archivos importantes del proyecto
5. **scripts_list.json**: Lista de scripts disponibles

## Estadísticas

- Servicios totales: {data_stats['servicios']['total']}
- Servicios con imagen: {data_stats['servicios']['con_imagen']}
- Cabañas totales: {data_stats['cabanas']['total']}
- Gift Cards totales: {data_stats['giftcards']['total']}
- Imágenes en Cloudinary: {len(images_list)}

## Notas Importantes

⚠️ **Este backup NO incluye:**
- Base de datos (usar Render Database Backups)
- Archivos de media locales
- Variables de entorno secretas (API keys, passwords)
- Logs del sistema

✅ **Este backup SÍ incluye:**
- Configuración de la aplicación
- Lista de imágenes y sus URLs
- Estadísticas de datos
- Archivos de configuración importantes

## Restauración

Para restaurar desde este backup:

1. Restaurar la base de datos desde Render
2. Verificar que las variables de entorno estén configuradas
3. Verificar que las imágenes en Cloudinary estén accesibles
4. Comparar configuración actual con config_backup.json

## Verificación de Imágenes

Para verificar que todas las imágenes estén accesibles:
```bash
python scripts/verify_images_from_backup.py backups/backup_{timestamp}/images_list.json
```
"""

readme_file = backup_dir / 'README.md'
with open(readme_file, 'w') as f:
    f.write(readme_content)

print(f"✅ README creado")

# Resumen final
print("\n" + "=" * 60)
print("✅ BACKUP COMPLETADO")
print("=" * 60)

total_size = sum(f.stat().st_size for f in backup_dir.rglob('*') if f.is_file())
total_size_mb = total_size / (1024 * 1024)

print(f"\n📊 RESUMEN:")
print(f"   Ubicación: {backup_dir}")
print(f"   Tamaño total: {total_size_mb:.2f} MB")
print(f"   Archivos creados: {len(list(backup_dir.rglob('*')))}")

print(f"\n💡 PRÓXIMOS PASOS:")
print(f"   1. ✅ Hacer backup de la base de datos en Render")
print(f"   2. ✓ Comprimir el directorio de backup:")
print(f"      tar -czf backup_{timestamp}.tar.gz backups/backup_{timestamp}")
print(f"   3. ✓ Guardar el archivo comprimido en un lugar seguro")
print(f"   4. ✓ Verificar que las imágenes en Cloudinary estén respaldadas")

print("\n" + "=" * 60)
