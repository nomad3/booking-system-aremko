#!/usr/bin/env python
"""
Script para diagnosticar configuración de slots de servicios
Ejecutar desde la shell de Django
"""

import os
import sys
import django
from datetime import datetime, timedelta

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from ventas.models import Servicio, CategoriaServicio
from django.db.models import Q

def check_tina_slots():
    print("\n" + "="*60)
    print("DIAGNÓSTICO DE SLOTS DE TINAJAS")
    print("="*60)

    # Buscar categoría de tinajas
    try:
        cat_tinajas = CategoriaServicio.objects.filter(
            Q(nombre__icontains='tinaja') |
            Q(nombre__icontains='tina') |
            Q(nombre__icontains='caliente')
        ).first()

        if not cat_tinajas:
            print("❌ No se encontró categoría de Tinajas")
            # Listar todas las categorías
            print("\nCategorías disponibles:")
            for cat in CategoriaServicio.objects.all():
                print(f"  ID {cat.id}: {cat.nombre}")
            return

        print(f"✅ Categoría encontrada: {cat_tinajas.nombre} (ID: {cat_tinajas.id})")

        # Buscar servicios de tinajas
        tinajas = Servicio.objects.filter(categoria=cat_tinajas)
        print(f"\nTinajas encontradas: {tinajas.count()}")

        # Fecha de mañana
        tomorrow = datetime.now().date() + timedelta(days=1)
        day_name = tomorrow.strftime('%A').lower()
        print(f"\nFecha de mañana: {tomorrow} ({day_name})")

        for tina in tinajas[:10]:  # Primeras 10 tinajas
            print(f"\n--- {tina.nombre} (ID: {tina.id}) ---")
            print(f"  Activo: {tina.activo}")
            print(f"  Publicado web: {tina.publicado_web}")
            print(f"  Precio: ${tina.precio_base:,.0f}")
            print(f"  Duración: {tina.duracion} minutos")
            print(f"  Max simultáneos: {getattr(tina, 'max_servicios_simultaneos', 1)}")

            # Verificar slots_disponibles
            if hasattr(tina, 'slots_disponibles'):
                slots = tina.slots_disponibles
                print(f"  Tipo de slots_disponibles: {type(slots)}")

                if isinstance(slots, dict):
                    print(f"  Días configurados: {list(slots.keys())}")
                    if day_name in slots:
                        print(f"  Slots para {day_name}: {slots[day_name]}")
                    else:
                        print(f"  ⚠️  No hay slots para {day_name}")
                elif isinstance(slots, list):
                    print(f"  Slots (lista): {slots[:5]}...")  # Primeros 5
                else:
                    print(f"  Slots: {slots}")
            else:
                print("  ⚠️  No tiene campo slots_disponibles")

            # Buscar el servicio específico Calbuco
            if 'calbuco' in tina.nombre.lower():
                print("\n  🎯 ESTA ES LA TINA CALBUCO")
                print(f"     URL de prueba:")
                print(f"     https://www.aremko.cl/ventas/get-available-hours/?servicio_id={tina.id}&fecha={tomorrow}")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

def list_all_services():
    print("\n" + "="*60)
    print("TODOS LOS SERVICIOS")
    print("="*60)

    services = Servicio.objects.filter(activo=True, publicado_web=True).order_by('categoria', 'nombre')

    current_category = None
    for service in services:
        if service.categoria != current_category:
            current_category = service.categoria
            print(f"\n--- {current_category.nombre if current_category else 'Sin categoría'} ---")

        slots_info = "No configurado"
        if hasattr(service, 'slots_disponibles'):
            slots = service.slots_disponibles
            if isinstance(slots, dict):
                days_with_slots = [day for day, s in slots.items() if s]
                if days_with_slots:
                    slots_info = f"Días: {', '.join(days_with_slots)}"
            elif isinstance(slots, list) and slots:
                slots_info = f"{len(slots)} slots"

        print(f"  ID {service.id}: {service.nombre} - {slots_info}")

if __name__ == "__main__":
    print("\n🔍 Iniciando diagnóstico de slots de servicios\n")

    # Verificar tinajas específicamente
    check_tina_slots()

    # Listar todos los servicios
    list_all_services()

    print("\n✅ Diagnóstico completado")