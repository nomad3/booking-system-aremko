#!/usr/bin/env python3
"""
Script para diagnosticar el problema con Masaje Deportivo
Ejecutar desde Render: python scripts/diagnose_masaje_deportivo.py
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

from ventas.models import Servicio, CategoriaServicio

print("\n" + "=" * 70)
print("DIAGNÓSTICO: MASAJE DEPORTIVO")
print("=" * 70)

# Buscar el servicio de Masaje Deportivo
print("\n🔍 Buscando servicio 'Masaje Deportivo'...")
print("-" * 70)

try:
    masaje_deportivo = Servicio.objects.filter(nombre__icontains='deportivo').first()

    if not masaje_deportivo:
        print("❌ No se encontró servicio con 'deportivo' en el nombre")
        print("\n📋 Todos los servicios de Masajes:")
        masajes = Servicio.objects.filter(categoria__nombre__icontains='masaj')
        for m in masajes:
            print(f"   - {m.nombre} (ID: {m.id})")
    else:
        print(f"✅ Encontrado: {masaje_deportivo.nombre} (ID: {masaje_deportivo.id})")
        print(f"\n📋 DATOS DEL SERVICIO:")
        print(f"   ID: {masaje_deportivo.id}")
        print(f"   Nombre: {masaje_deportivo.nombre}")
        print(f"   Categoría: {masaje_deportivo.categoria.nombre if masaje_deportivo.categoria else 'Sin categoría'}")
        print(f"   Precio base: ${masaje_deportivo.precio_base:,.0f}")
        print(f"   Duración: {masaje_deportivo.duracion_minutos} minutos")
        print(f"   Activo: {masaje_deportivo.activo}")
        print(f"   Publicado en web: {masaje_deportivo.publicado_web}")
        print(f"   Requiere aprobación: {masaje_deportivo.requiere_aprobacion}")
        print(f"   Descripción: {masaje_deportivo.descripcion[:100] if masaje_deportivo.descripcion else 'Sin descripción'}...")

        # Verificar imagen
        print(f"\n🖼️  IMAGEN:")
        if masaje_deportivo.imagen:
            try:
                print(f"   Path: {masaje_deportivo.imagen.name}")
                print(f"   URL: {masaje_deportivo.imagen.url}")
            except Exception as e:
                print(f"   ⚠️ ERROR generando URL: {e}")
        else:
            print(f"   ⚠️ Sin imagen configurada")

        # Comparar con otros masajes
        print(f"\n📊 COMPARACIÓN CON OTROS MASAJES:")
        print("-" * 70)

        otros_masajes = Servicio.objects.filter(
            categoria__nombre__icontains='masaj',
            publicado_web=True
        ).exclude(id=masaje_deportivo.id)

        print(f"Otros {otros_masajes.count()} masajes publicados:\n")
        for m in otros_masajes:
            print(f"   {m.nombre} (ID: {m.id})")
            print(f"      - Precio: ${m.precio_base:,.0f}")
            print(f"      - Duración: {m.duracion_minutos} min")
            print(f"      - Imagen: {'✅' if m.imagen else '❌'}")
            if m.imagen:
                try:
                    url = m.imagen.url
                    print(f"      - URL imagen: {url[:60]}...")
                except Exception as e:
                    print(f"      - ⚠️ Error URL: {e}")
            print()

        # Verificar diferencias críticas
        print(f"\n⚠️  POSIBLES PROBLEMAS:")
        print("-" * 70)

        problemas = []

        # 1. Imagen
        if not masaje_deportivo.imagen:
            problemas.append("❌ No tiene imagen configurada")
        else:
            try:
                url = masaje_deportivo.imagen.url
            except Exception as e:
                problemas.append(f"❌ Error generando URL de imagen: {e}")

        # 2. Descripción
        if not masaje_deportivo.descripcion:
            problemas.append("⚠️ No tiene descripción")

        # 3. Precio
        if masaje_deportivo.precio_base <= 0:
            problemas.append(f"❌ Precio inválido: ${masaje_deportivo.precio_base}")

        # 4. Duración
        if masaje_deportivo.duracion_minutos <= 0:
            problemas.append(f"❌ Duración inválida: {masaje_deportivo.duracion_minutos} min")

        # 5. Categoría
        if not masaje_deportivo.categoria:
            problemas.append("❌ No tiene categoría asignada")
        else:
            # Verificar si la categoría tiene imagen
            if not masaje_deportivo.categoria.imagen:
                problemas.append(f"⚠️ La categoría '{masaje_deportivo.categoria.nombre}' no tiene imagen hero")

        if problemas:
            for p in problemas:
                print(f"   {p}")
        else:
            print("   ✅ No se detectaron problemas obvios")

        print(f"\n🔬 DIAGNÓSTICO TÉCNICO:")
        print("-" * 70)
        print("""
        El error 500 ocurre DESPUÉS de completar la reserva, al intentar enviar
        emails de confirmación automáticamente.

        CAUSA PROBABLE:
        - El signal 'handle_booking_confirmation' se dispara cuando se crea la reserva
        - El servicio 'communication_service.send_booking_confirmation_dual()' intenta
          generar el email con información del servicio
        - Si falta algún campo (imagen, descripción, etc.) el email puede fallar
        - El error 500 bloquea la redirección a la página de confirmación

        SOLUCIÓN RECOMENDADA:
        1. Asegúrate de que el servicio tenga:
           - Imagen válida (subida a Cloudinary)
           - Descripción completa
           - Precio > 0
           - Duración > 0

        2. O DESACTIVA temporalmente el envío automático de emails en
           communication_triggers.py líneas 24-60
        """)

except Exception as e:
    print(f"❌ Error en diagnóstico: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
print("FIN DEL DIAGNÓSTICO")
print("=" * 70 + "\n")
