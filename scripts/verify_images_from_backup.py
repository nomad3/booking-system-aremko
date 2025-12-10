#!/usr/bin/env python
"""
Script para verificar que todas las imágenes de un backup estén accesibles.
"""

import sys
import json
import requests
from pathlib import Path

if len(sys.argv) < 2:
    print("Uso: python verify_images_from_backup.py <ruta_a_images_list.json>")
    sys.exit(1)

backup_file = Path(sys.argv[1])

if not backup_file.exists():
    print(f"❌ Error: {backup_file} no existe")
    sys.exit(1)

print("=" * 60)
print("VERIFICACIÓN DE IMÁGENES DESDE BACKUP")
print("=" * 60)

with open(backup_file, 'r') as f:
    images = json.load(f)

print(f"\n📋 Total de imágenes a verificar: {len(images)}")
print("-" * 40)

accesibles = 0
no_accesibles = 0
errores = []

for img in images:
    servicio = img['servicio_nombre']
    url = img['imagen_url']

    try:
        response = requests.head(url, timeout=10)
        if response.status_code == 200:
            accesibles += 1
            print(f"✅ {servicio[:40]}")
        else:
            no_accesibles += 1
            errores.append(f"{servicio}: HTTP {response.status_code}")
            print(f"❌ {servicio[:40]} - HTTP {response.status_code}")
    except Exception as e:
        no_accesibles += 1
        errores.append(f"{servicio}: {str(e)}")
        print(f"❌ {servicio[:40]} - Error: {e}")

print("\n" + "=" * 60)
print("RESUMEN")
print("=" * 60)
print(f"✅ Accesibles: {accesibles}/{len(images)}")
print(f"❌ No accesibles: {no_accesibles}/{len(images)}")

if errores:
    print(f"\n⚠️ IMÁGENES CON PROBLEMAS:")
    for error in errores:
        print(f"   • {error}")

if accesibles == len(images):
    print(f"\n🎉 ¡Todas las imágenes están accesibles!")
else:
    print(f"\n⚠️ Hay {no_accesibles} imágenes que necesitan atención")
