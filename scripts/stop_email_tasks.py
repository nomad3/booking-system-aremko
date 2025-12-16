#!/usr/bin/env python3
"""
Script para detener tareas de envío de emails que están bloqueando el servidor
Ejecutar desde Render: python scripts/stop_email_tasks.py
"""

import os
import sys
from pathlib import Path

# Agregar el directorio raíz del proyecto al path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')

import django
django.setup()

print("\n" + "=" * 70)
print("BUSCANDO Y DETENIENDO TAREAS DE EMAIL")
print("=" * 70)

# Verificar si hay tareas pendientes en alguna cola
# Nota: Este script asume que no hay un sistema de colas configurado
# Si los emails se están enviando desde una vista web, no hay forma de detenerlos
# excepto reiniciando el servidor

print("\n⚠️  INFORMACIÓN IMPORTANTE:")
print("-" * 70)
print("Si los emails se están enviando desde una vista web o comando,")
print("la única forma de detenerlos es:")
print()
print("1. REINICIAR EL SERVICIO en Render:")
print("   - Ve a tu Dashboard de Render")
print("   - Click en 'Manual Deploy' → 'Restart'")
print()
print("2. O MATAR el proceso manualmente:")
print("   - Ejecuta: ps aux | grep python")
print("   - Identifica el proceso con alto uso de CPU/memoria")
print("   - Ejecuta: kill -9 [PID]")
print()
print("3. PREVENIR en el futuro:")
print("   - Implementar cola de tareas (Celery)")
print("   - Enviar emails en lotes pequeños")
print("   - Usar rate limiting")
print()
print("=" * 70)
print()

# Intentar limpiar la sesión de Django si hay algo pendiente
try:
    from django.core.cache import cache
    cache.clear()
    print("✅ Cache de Django limpiado")
except Exception as e:
    print(f"⚠️  No se pudo limpiar cache: {e}")

print("\n" + "=" * 70)
print("RECOMENDACIÓN: REINICIA EL SERVICIO EN RENDER")
print("=" * 70 + "\n")
