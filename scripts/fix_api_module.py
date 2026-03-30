#!/usr/bin/env python
"""
Script para arreglar el módulo api si no está instalado
Ejecutar desde la shell de Django en Render
"""

import os
import sys

print("\n" + "="*60)
print("ARREGLANDO MÓDULO API")
print("="*60)

# Verificar si existe la carpeta api
if not os.path.exists('/app/api'):
    print("❌ La carpeta /app/api no existe")
    print("   Creando estructura de la app...")

    # Crear la carpeta
    os.makedirs('/app/api', exist_ok=True)

    # Crear __init__.py
    with open('/app/api/__init__.py', 'w') as f:
        f.write('')

    print("✅ Carpeta api creada")
else:
    print("✅ La carpeta /app/api existe")

# Verificar archivos necesarios
files_needed = {
    '__init__.py': '',
    'apps.py': '''from django.apps import AppConfig

class ApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api'
''',
    'models.py': '''from django.db import models

# Create your models here.
''',
    'views.py': '''# Temporarily empty - will be replaced
from django.http import JsonResponse

def availability_summary(request):
    return JsonResponse({"error": "API being configured"})
''',
}

for filename, content in files_needed.items():
    filepath = f'/app/api/{filename}'
    if not os.path.exists(filepath):
        print(f"   Creando {filename}...")
        with open(filepath, 'w') as f:
            f.write(content)
        print(f"   ✅ {filename} creado")
    else:
        print(f"   ✅ {filename} existe")

# Verificar INSTALLED_APPS
from django.conf import settings

if 'api' not in settings.INSTALLED_APPS:
    print("\n⚠️  'api' no está en INSTALLED_APPS")
    print("   Necesitas agregarlo manualmente en aremko_project/settings.py")
    print("   En la sección INSTALLED_APPS, agrega: 'api',")
else:
    print("\n✅ 'api' está en INSTALLED_APPS")

print("\n" + "="*60)
print("Ahora copia los archivos de la API desde GitHub:")
print("="*60)
print("""
# Ejecuta estos comandos:

# 1. Descargar archivos de la API
cd /app
git pull

# 2. Si api/ no se actualiza, copia manualmente:
curl -o api/views.py https://raw.githubusercontent.com/nomad3/booking-system-aremko/main/api/views.py
curl -o api/serializers.py https://raw.githubusercontent.com/nomad3/booking-system-aremko/main/api/serializers.py
curl -o api/authentication.py https://raw.githubusercontent.com/nomad3/booking-system-aremko/main/api/authentication.py
curl -o api/urls.py https://raw.githubusercontent.com/nomad3/booking-system-aremko/main/api/urls.py

# 3. Reiniciar el servicio
# (Render lo hace automáticamente al detectar cambios)
""")