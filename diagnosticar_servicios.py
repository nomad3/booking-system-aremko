#!/usr/bin/env python
"""
Script para diagnosticar servicios en la base de datos
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from ventas.models import Servicio
from django.db.models import Count

def main():
    print("=== DIAGNÓSTICO DE SERVICIOS ===\n")

    # Total de servicios
    total = Servicio.objects.count()
    print(f"Total de servicios en la BD: {total}")
    print(f"Servicios activos: {Servicio.objects.filter(activo=True).count()}")
    print(f"Servicios publicados web: {Servicio.objects.filter(publicado_web=True).count()}")

    print("\n=== SERVICIOS POR TIPO ===")

    # Agrupar por tipo
    tipos = Servicio.objects.values('tipo_servicio').annotate(
        total=Count('id'),
        activos=Count('id', filter=models.Q(activo=True)),
        publicados=Count('id', filter=models.Q(publicado_web=True))
    ).order_by('tipo_servicio')

    for tipo in tipos:
        print(f"\nTipo: {tipo['tipo_servicio']}")
        print(f"  Total: {tipo['total']}")
        print(f"  Activos: {tipo['activos']}")
        print(f"  Publicados: {tipo['publicados']}")

    # Detalles por categoría
    print("\n=== DETALLE DE SERVICIOS ===")

    for tipo in ['cabana', 'tina', 'masaje']:
        print(f"\n{tipo.upper()}:")
        servicios = Servicio.objects.filter(tipo_servicio=tipo).order_by('nombre')

        if not servicios:
            print("  No hay servicios de este tipo")
            continue

        for s in servicios:
            estado = []
            if s.activo:
                estado.append("✓ Activo")
            else:
                estado.append("✗ Inactivo")
            if s.publicado_web:
                estado.append("Web")

            print(f"  - {s.nombre} (${s.precio_base:,.0f}) [{', '.join(estado)}]")

    # Verificar valores únicos de tipo_servicio
    print("\n=== VALORES ÚNICOS DE tipo_servicio ===")
    tipos_unicos = Servicio.objects.values_list('tipo_servicio', flat=True).distinct()
    for tipo in tipos_unicos:
        count = Servicio.objects.filter(tipo_servicio=tipo).count()
        print(f"  '{tipo}': {count} servicios")

if __name__ == "__main__":
    from django.db import models
    main()