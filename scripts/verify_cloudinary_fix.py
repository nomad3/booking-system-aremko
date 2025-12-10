#!/usr/bin/env python
"""
Script para verificar que las credenciales de Cloudinary están correctas.
"""

import os
import sys
from pathlib import Path

# Agregar el directorio raíz del proyecto al path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

print("=" * 60)
print("VERIFICACIÓN DE CREDENCIALES CLOUDINARY")
print("=" * 60)

# Verificar variables de entorno
cloud_name = os.getenv('CLOUDINARY_CLOUD_NAME')
api_key = os.getenv('CLOUDINARY_API_KEY')
api_secret = os.getenv('CLOUDINARY_API_SECRET')

print("\n📋 VARIABLES DE ENTORNO:")
print("-" * 40)
print(f"CLOUDINARY_CLOUD_NAME: {cloud_name}")
print(f"CLOUDINARY_API_KEY: {api_key}")

if api_secret:
    # Mostrar solo parte del secret por seguridad
    masked = api_secret[:4] + "..." + api_secret[-4:] if len(api_secret) > 8 else "***"
    print(f"CLOUDINARY_API_SECRET: {masked} ({len(api_secret)} caracteres)")
else:
    print(f"CLOUDINARY_API_SECRET: NO CONFIGURADO")

# Verificar si las credenciales coinciden con las esperadas
print("\n🔍 VERIFICACIÓN DE CREDENCIALES:")
print("-" * 40)

expected_cloud = "dtuncr1pi"
expected_key = "493892349837672"  # La nueva API key

issues = []

if cloud_name != expected_cloud:
    issues.append(f"Cloud name incorrecto. Esperado: {expected_cloud}, Actual: {cloud_name}")
else:
    print(f"✅ Cloud name correcto: {cloud_name}")

if api_key != expected_key:
    issues.append(f"API Key incorrecta. Deberías usar: {expected_key}, Actual: {api_key}")
    if api_key == "177483515722245":
        issues.append("   ⚠️ Estás usando la API Key antigua (Root). Usa la nueva (Untitled)")
else:
    print(f"✅ API Key correcta: {api_key}")

if not api_secret:
    issues.append("API Secret no está configurado")
elif len(api_secret) < 20:
    issues.append(f"API Secret parece muy corto ({len(api_secret)} caracteres)")
else:
    print(f"✅ API Secret configurado ({len(api_secret)} caracteres)")

# Probar conexión con Cloudinary
print("\n🧪 PRUEBA DE CONEXIÓN:")
print("-" * 40)

try:
    import cloudinary
    import cloudinary.api

    # Configurar con las credenciales actuales
    cloudinary.config(
        cloud_name=cloud_name,
        api_key=api_key,
        api_secret=api_secret,
        secure=True
    )

    # Intentar ping
    try:
        result = cloudinary.api.ping()
        print("✅ Conexión exitosa con Cloudinary API")
    except Exception as e:
        print(f"❌ Error conectando con API: {e}")
        issues.append(f"No se puede conectar a Cloudinary: {e}")

    # Intentar subir un archivo de prueba pequeño
    try:
        import cloudinary.uploader

        test_result = cloudinary.uploader.upload(
            "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==",
            public_id="test_pixel",
            folder="test"
        )
        print(f"✅ Subida de prueba exitosa: {test_result.get('public_id')}")

        # Eliminar archivo de prueba
        cloudinary.uploader.destroy(test_result.get('public_id'))

    except Exception as e:
        print(f"❌ Error en subida de prueba: {e}")
        issues.append(f"No se puede subir archivos: {e}")

except ImportError:
    print("❌ Cloudinary no está instalado")
    issues.append("Módulo cloudinary no encontrado")

# Resumen
print("\n" + "=" * 60)
print("RESUMEN")
print("=" * 60)

if issues:
    print("❌ PROBLEMAS ENCONTRADOS:")
    for issue in issues:
        print(f"  • {issue}")

    print("\n💡 SOLUCIÓN:")
    print("1. Ve a https://console.cloudinary.com")
    print("2. Usa la API Key: 493892349837672 (Untitled)")
    print("3. Revela y copia el API Secret de esa key")
    print("4. Actualiza en Render:")
    print("   CLOUDINARY_API_KEY=493892349837672")
    print("   CLOUDINARY_API_SECRET=[el secret revelado]")
else:
    print("✅ TODO ESTÁ CONFIGURADO CORRECTAMENTE")
    print("\nSi aún hay error 500, puede ser un problema con:")
    print("  • El formulario de Django Admin")
    print("  • Configuración de django-cloudinary-storage")
    print("  • Revisar si hay algún hook o signal que interfiera")

print("\n" + "=" * 60)