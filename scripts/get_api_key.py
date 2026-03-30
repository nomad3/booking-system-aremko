#!/usr/bin/env python
"""
Script para obtener la API Key actual en producción
Ejecutar desde la shell de Django en Render
"""

from django.conf import settings

print("\n" + "="*60)
print("API KEY ACTUAL EN PRODUCCIÓN")
print("="*60)

api_key = getattr(settings, 'LUNA_API_KEY', None)

if api_key:
    print(f"\nAPI Key configurada:")
    print(f"  {api_key}")
    print(f"\nPara usar esta API Key:")
    print(f"  Header: X-API-Key")
    print(f"  Value: {api_key}")
else:
    print("\n❌ No hay API Key configurada")
    print("   Agrega LUNA_API_KEY en las variables de entorno")

print("\n" + "="*60)