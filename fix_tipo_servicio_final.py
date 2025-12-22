#!/usr/bin/env python
"""
Script para corregir errores específicos en tipo_servicio:
- Servicios de Valentina que fueron marcados como 'tina' pero son masajes
- Desayuno que fue marcado como 'cabana' pero debería ser 'otro'
"""

import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.db import transaction
from ventas.models import Servicio

def corregir_errores_especificos():
    """
    Corrige errores específicos en el tipo_servicio
    """
    print("=" * 60)
    print("CORRECCIÓN FINAL DE TIPO_SERVICIO")
    print("=" * 60)
    print("")

    corregidos = []

    with transaction.atomic():
        # 1. Corregir servicios de Valentina (son masajes, no tinas)
        print("1. Corrigiendo servicios de Valentina...")
        print("-" * 40)

        valentina_services = Servicio.objects.filter(nombre__icontains='valentina')
        for servicio in valentina_services:
            tipo_anterior = servicio.tipo_servicio
            if tipo_anterior == 'tina':
                servicio.tipo_servicio = 'masaje'
                servicio.save()
                print(f"  ✓ {servicio.nombre}: 'tina' → 'masaje'")
                corregidos.append(servicio.nombre)
            else:
                print(f"  • {servicio.nombre}: ya es '{tipo_anterior}' (sin cambios)")

        print("")

        # 2. Corregir Desayuno (no es cabaña, es otro)
        print("2. Corrigiendo servicios de Desayuno...")
        print("-" * 40)

        desayuno_services = Servicio.objects.filter(nombre__icontains='desayuno')
        for servicio in desayuno_services:
            tipo_anterior = servicio.tipo_servicio
            if tipo_anterior == 'cabana':
                servicio.tipo_servicio = 'otro'
                servicio.save()
                print(f"  ✓ {servicio.nombre}: 'cabana' → 'otro'")
                corregidos.append(servicio.nombre)
            else:
                print(f"  • {servicio.nombre}: ya es '{tipo_anterior}' (sin cambios)")

        print("")

        # 3. Corregir Drenaje Linfático (no es tina, es masaje)
        print("3. Corrigiendo Drenaje Linfático...")
        print("-" * 40)

        drenaje_services = Servicio.objects.filter(nombre__icontains='drenaje')
        for servicio in drenaje_services:
            tipo_anterior = servicio.tipo_servicio
            # Solo corregir si está marcado como 'tina'
            if tipo_anterior == 'tina':
                servicio.tipo_servicio = 'masaje'
                servicio.save()
                print(f"  ✓ {servicio.nombre}: 'tina' → 'masaje'")
                corregidos.append(servicio.nombre)
            elif tipo_anterior == 'otro':
                # Drenaje linfático debe ser masaje
                servicio.tipo_servicio = 'masaje'
                servicio.save()
                print(f"  ✓ {servicio.nombre}: 'otro' → 'masaje'")
                corregidos.append(servicio.nombre)
            else:
                print(f"  • {servicio.nombre}: ya es '{tipo_anterior}' (sin cambios)")

        print("")

        # 4. Asegurar que todas las terapias sean masajes
        print("4. Corrigiendo Terapias...")
        print("-" * 40)

        terapia_services = Servicio.objects.filter(nombre__icontains='terapia')
        for servicio in terapia_services:
            tipo_anterior = servicio.tipo_servicio
            if tipo_anterior != 'masaje':
                servicio.tipo_servicio = 'masaje'
                servicio.save()
                print(f"  ✓ {servicio.nombre}: '{tipo_anterior}' → 'masaje'")
                corregidos.append(servicio.nombre)
            else:
                print(f"  • {servicio.nombre}: ya es 'masaje' (sin cambios)")

        print("")

        # 5. Asegurar que reflexología sea masaje
        print("5. Corrigiendo Reflexología...")
        print("-" * 40)

        reflexologia_services = Servicio.objects.filter(nombre__icontains='reflexo')
        for servicio in reflexologia_services:
            tipo_anterior = servicio.tipo_servicio
            if tipo_anterior != 'masaje':
                servicio.tipo_servicio = 'masaje'
                servicio.save()
                print(f"  ✓ {servicio.nombre}: '{tipo_anterior}' → 'masaje'")
                corregidos.append(servicio.nombre)
            else:
                print(f"  • {servicio.nombre}: ya es 'masaje' (sin cambios)")

    # Verificación final
    print("")
    print("=" * 60)
    print("VERIFICACIÓN FINAL")
    print("=" * 60)

    # Contar por tipo
    tinas = Servicio.objects.filter(tipo_servicio='tina')
    masajes = Servicio.objects.filter(tipo_servicio='masaje')
    cabanas = Servicio.objects.filter(tipo_servicio='cabana')
    otros = Servicio.objects.filter(tipo_servicio='otro')

    print(f"\n📊 RESUMEN DE TIPOS:")
    print(f"  ♨️  Tinas: {tinas.count()} servicios")
    print(f"  💆 Masajes: {masajes.count()} servicios")
    print(f"  🏠 Cabañas: {cabanas.count()} servicios")
    print(f"  📦 Otros: {otros.count()} servicios")
    print(f"  ─────────────────────")
    print(f"  Total: {tinas.count() + masajes.count() + cabanas.count() + otros.count()} servicios")

    # Mostrar algunos ejemplos de cada tipo
    print("\n📋 EJEMPLOS DE CADA TIPO:")

    print("\n♨️ TINAS:")
    for t in tinas[:5]:
        print(f"  • {t.nombre}")
    if tinas.count() > 5:
        print(f"  ... y {tinas.count() - 5} más")

    print("\n💆 MASAJES:")
    for m in masajes[:5]:
        print(f"  • {m.nombre}")
    if masajes.count() > 5:
        print(f"  ... y {masajes.count() - 5} más")

    print("\n🏠 CABAÑAS:")
    for c in cabanas[:5]:
        print(f"  • {c.nombre}")
    if cabanas.count() > 5:
        print(f"  ... y {cabanas.count() - 5} más")

    print("\n📦 OTROS:")
    for o in otros[:5]:
        print(f"  • {o.nombre}")
    if otros.count() > 5:
        print(f"  ... y {otros.count() - 5} más")

    # Resumen de correcciones
    print("")
    print("=" * 60)
    print("CORRECCIONES APLICADAS")
    print("=" * 60)
    print(f"✅ Total de servicios corregidos: {len(corregidos)}")
    if corregidos:
        print("\nServicios corregidos:")
        for nombre in corregidos:
            print(f"  • {nombre}")

    print("")
    print("=" * 60)
    print("✨ ¡CORRECCIÓN COMPLETADA CON ÉXITO!")
    print("=" * 60)
    print("\nAhora los tips deberían mostrar información específica según el tipo de servicio:")
    print("• Cabañas: WiFi específico, normas, check-out")
    print("• Tinas: Uso correcto, alternancia caliente/frío, prohibiciones")
    print("• Masajes: Recomendaciones, vestidores, ducha post-masaje")

if __name__ == "__main__":
    corregir_errores_especificos()