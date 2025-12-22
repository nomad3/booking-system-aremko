#!/usr/bin/env python
"""
Script para actualizar el campo tipo_servicio en los servicios existentes
basándose en su nombre y categoría
"""

import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.db import transaction
from ventas.models import Servicio

def actualizar_tipo_servicio():
    """
    Actualiza el campo tipo_servicio basándose en el nombre del servicio
    """
    print("=" * 60)
    print("ACTUALIZACIÓN DE TIPO_SERVICIO")
    print("=" * 60)

    # Palabras clave para identificar cada tipo
    KEYWORDS_TINA = ['tina', 'termal', 'hidromasaje', 'jacuzzi', 'hot tub', 'tinaja']
    KEYWORDS_MASAJE = ['masaje', 'masajes', 'massage', 'terapia', 'relajación', 'descontracturante', 'piedras']
    KEYWORDS_CABANA = ['cabaña', 'cabana', 'torre', 'acantilado', 'laurel', 'tepa', 'arrayan', 'alojamiento', 'habitación']

    servicios = Servicio.objects.all()

    actualizados = {
        'tina': [],
        'masaje': [],
        'cabana': [],
        'sin_cambios': []
    }

    with transaction.atomic():
        for servicio in servicios:
            nombre_lower = servicio.nombre.lower()
            tipo_original = servicio.tipo_servicio
            tipo_nuevo = None

            # Determinar el tipo basándose en palabras clave
            if any(keyword in nombre_lower for keyword in KEYWORDS_TINA):
                tipo_nuevo = 'tina'
            elif any(keyword in nombre_lower for keyword in KEYWORDS_MASAJE):
                tipo_nuevo = 'masaje'
            elif any(keyword in nombre_lower for keyword in KEYWORDS_CABANA):
                tipo_nuevo = 'cabana'

            # Actualizar si es necesario
            if tipo_nuevo and tipo_original != tipo_nuevo:
                servicio.tipo_servicio = tipo_nuevo
                servicio.save()
                actualizados[tipo_nuevo].append(f"{servicio.nombre} (antes: {tipo_original})")
                print(f"✓ Actualizado: {servicio.nombre} → tipo_servicio='{tipo_nuevo}' (antes: '{tipo_original}')")
            else:
                actualizados['sin_cambios'].append(f"{servicio.nombre} (tipo: {tipo_original})")

    # Resumen
    print("\n" + "=" * 60)
    print("RESUMEN DE ACTUALIZACIÓN")
    print("=" * 60)

    if actualizados['tina']:
        print(f"\n📊 TINAS ({len(actualizados['tina'])} actualizados):")
        for item in actualizados['tina']:
            print(f"  • {item}")

    if actualizados['masaje']:
        print(f"\n💆 MASAJES ({len(actualizados['masaje'])} actualizados):")
        for item in actualizados['masaje']:
            print(f"  • {item}")

    if actualizados['cabana']:
        print(f"\n🏠 CABAÑAS ({len(actualizados['cabana'])} actualizados):")
        for item in actualizados['cabana']:
            print(f"  • {item}")

    if actualizados['sin_cambios']:
        print(f"\n❓ SIN CAMBIOS ({len(actualizados['sin_cambios'])} servicios):")
        for item in actualizados['sin_cambios']:
            print(f"  • {item}")

    total_actualizados = len(actualizados['tina']) + len(actualizados['masaje']) + len(actualizados['cabana'])
    print(f"\n✅ Total actualizados: {total_actualizados}")
    print(f"ℹ️ Sin cambios: {len(actualizados['sin_cambios'])}")

    print("\n" + "=" * 60)
    print("COMANDOS PARA EJECUTAR EN EL SERVIDOR:")
    print("=" * 60)
    print("""
# En la Shell de Render, ejecuta:
python fix_tipo_servicio.py

# O si prefieres hacerlo manualmente en el shell de Django:
python manage.py shell

from ventas.models import Servicio

# Ver servicios de tina
for s in Servicio.objects.filter(nombre__icontains='tina'):
    print(f"{s.nombre}: tipo_servicio='{s.tipo_servicio}'")
    if s.tipo_servicio != 'tina':
        s.tipo_servicio = 'tina'
        s.save()
        print(f"  → Actualizado a 'tina'")

# Ver servicios de masaje
for s in Servicio.objects.filter(nombre__icontains='masaje'):
    print(f"{s.nombre}: tipo_servicio='{s.tipo_servicio}'")
    if s.tipo_servicio != 'masaje':
        s.tipo_servicio = 'masaje'
        s.save()
        print(f"  → Actualizado a 'masaje'")
""")

if __name__ == "__main__":
    actualizar_tipo_servicio()