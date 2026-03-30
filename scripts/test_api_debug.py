#!/usr/bin/env python
"""
Script de diagnóstico para la API
Ejecutar desde la shell de Django en Render
"""

import os
import sys
import traceback

print("\n" + "="*60)
print("DIAGNÓSTICO DE LA API")
print("="*60)

# Test 1: Importaciones
print("\n1. Verificando importaciones...")
try:
    from api.views import availability_summary
    from api.authentication import APIKeyAuthentication
    from api.serializers import TubAvailabilityResponseSerializer
    print("✅ Importaciones OK")
except Exception as e:
    print(f"❌ Error en importaciones: {e}")
    traceback.print_exc()
    sys.exit(1)

# Test 2: API Key
print("\n2. Verificando API Key...")
from django.conf import settings
api_key = getattr(settings, 'LUNA_API_KEY', None)
if api_key:
    print(f"✅ API Key configurada: {api_key[:20]}...")
else:
    print("❌ No hay API Key configurada")

# Test 3: Modelos
print("\n3. Verificando modelos...")
try:
    from ventas.models import CategoriaServicio, Servicio, ServicioBloqueo

    # Contar categorías
    categorias = CategoriaServicio.objects.all()
    print(f"   Categorías encontradas: {categorias.count()}")
    for cat in categorias[:5]:
        print(f"   - {cat.nombre}")

    # Buscar categoría de tinajas
    try:
        from django.db.models import Q
        cat_tinajas = CategoriaServicio.objects.filter(
            Q(nombre__icontains='tinaja') | Q(nombre__icontains='tina')
        ).first()
        if cat_tinajas:
            print(f"✅ Categoría Tinajas encontrada: {cat_tinajas.nombre}")
            servicios_tina = Servicio.objects.filter(categoria=cat_tinajas, activo=True)
            print(f"   Tinajas activas: {servicios_tina.count()}")
        else:
            print("⚠️  No se encontró categoría de Tinajas")
    except Exception as e:
        print(f"❌ Error buscando tinajas: {e}")

    # Buscar categoría de masajes
    try:
        cat_masajes = CategoriaServicio.objects.filter(
            nombre__icontains='masaje'
        ).first()
        if cat_masajes:
            print(f"✅ Categoría Masajes encontrada: {cat_masajes.nombre}")
            servicios_masaje = Servicio.objects.filter(categoria=cat_masajes, activo=True)
            print(f"   Masajes activos: {servicios_masaje.count()}")
        else:
            print("⚠️  No se encontró categoría de Masajes")
    except Exception as e:
        print(f"❌ Error buscando masajes: {e}")

except Exception as e:
    print(f"❌ Error con modelos: {e}")
    traceback.print_exc()

# Test 4: Llamar función directamente
print("\n4. Probando función de disponibilidad...")
try:
    from datetime import datetime
    from api.views import get_available_slots_for_service

    # Obtener un servicio de prueba
    servicio = Servicio.objects.filter(activo=True).first()
    if servicio:
        print(f"   Probando con servicio: {servicio.nombre}")
        fecha = datetime.now().date()
        slots = get_available_slots_for_service(servicio, fecha)
        print(f"✅ Función ejecutada. Slots disponibles: {len(slots)}")
    else:
        print("⚠️  No hay servicios activos")

except Exception as e:
    print(f"❌ Error en función: {e}")
    traceback.print_exc()

print("\n" + "="*60)
print("FIN DEL DIAGNÓSTICO")
print("="*60)