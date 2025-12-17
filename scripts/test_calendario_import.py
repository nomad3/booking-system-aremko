#!/usr/bin/env python3
"""
Script para verificar la importación del calendario matriz
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

print("✅ Django configurado correctamente")

try:
    from ventas.views.calendario_matriz_view import calendario_matriz_view
    print("✅ Vista calendario_matriz_view importada correctamente")

    from ventas.views.calendario_matriz_view import calendario_matriz_api
    print("✅ Vista calendario_matriz_api importada correctamente")

    from ventas.views.calendario_matriz_view import calendario_matriz_reservar
    print("✅ Vista calendario_matriz_reservar importada correctamente")

    from ventas.models import CategoriaServicio, Servicio, ReservaServicio, VentaReserva
    print("✅ Modelos importados correctamente")

    print("\n✨ TODO CORRECTO - El módulo calendario_matriz funciona correctamente")

except ImportError as e:
    print(f"❌ Error de importación: {e}")
    import traceback
    traceback.print_exc()
except Exception as e:
    print(f"❌ Error general: {e}")
    import traceback
    traceback.print_exc()