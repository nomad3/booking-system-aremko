#!/usr/bin/env python3
"""
Script para diagnosticar errores en la vista de resumen
Ejecutar: python scripts/test_resumen_view.py
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

from ventas.models import VentaReserva, ConfiguracionResumen
from ventas.views.resumen_reserva_view import _generar_texto_resumen

print("\n" + "=" * 80)
print("DIAGNÓSTICO DE VISTA DE RESUMEN")
print("=" * 80)

# Obtener una reserva de prueba
print("\n1. Buscando reserva de prueba...")
reserva = VentaReserva.objects.filter(id=4218).first()

if not reserva:
    print("   ❌ No se encontró la reserva 4218")
    print("   Intentando con cualquier reserva...")
    reserva = VentaReserva.objects.first()

if not reserva:
    print("   ❌ No hay reservas en el sistema")
    sys.exit(1)

print(f"   ✅ Reserva encontrada: #{reserva.id} - {reserva.cliente.nombre}")

# Obtener configuración
print("\n2. Obteniendo configuración...")
try:
    config = ConfiguracionResumen.get_solo()
    print(f"   ✅ Configuración obtenida: {config.encabezado}")
except Exception as e:
    print(f"   ❌ Error al obtener configuración: {e}")
    sys.exit(1)

# Intentar generar el texto
print("\n3. Generando texto de resumen...")
try:
    texto = _generar_texto_resumen(reserva, config)
    print(f"   ✅ Texto generado exitosamente ({len(texto)} caracteres)")
    print("\n" + "-" * 80)
    print("PREVIEW DEL TEXTO:")
    print("-" * 80)
    print(texto[:500] + "...")
    print("-" * 80)
except Exception as e:
    print(f"   ❌ Error al generar texto: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 80)
print("DIAGNÓSTICO COMPLETADO")
print("=" * 80)
print("\n✨ La función _generar_texto_resumen funciona correctamente")
print("   El problema debe estar en la vista o en el decorador\n")
