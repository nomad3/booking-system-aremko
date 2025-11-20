#!/usr/bin/env python
"""
Script para diagnosticar SOLO servicios publicados en web
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from ventas.models import Servicio

def main():
    print("=== SERVICIOS PUBLICADOS EN WEB ===\n")

    # Solo servicios publicados en web
    servicios_web = Servicio.objects.filter(publicado_web=True).order_by('nombre')

    print(f"Total servicios publicados en web: {servicios_web.count()}")
    print("\n=== DETALLE DE TODOS LOS SERVICIOS WEB ===")

    for servicio in servicios_web:
        estado = []
        if servicio.activo:
            estado.append("✓ Activo")
        else:
            estado.append("✗ Inactivo")

        print(f"\n- {servicio.nombre}")
        print(f"  ID: {servicio.id}")
        print(f"  Tipo: '{servicio.tipo_servicio}' (display: {servicio.get_tipo_servicio_display()})")
        print(f"  Precio: ${servicio.precio_base:,.0f}")
        print(f"  Estado: {', '.join(estado)}")

        # Analizar el nombre para sugerir tipo correcto
        nombre_lower = servicio.nombre.lower()
        if any(word in nombre_lower for word in ['tina', 'tinaja', 'termas']):
            if servicio.tipo_servicio != 'tina':
                print(f"  ⚠️  POSIBLE TIPO INCORRECTO: debería ser 'tina'")
        elif any(word in nombre_lower for word in ['cabaña', 'cabana', 'torre', 'refugio', 'lodge']):
            if servicio.tipo_servicio != 'cabana':
                print(f"  ⚠️  POSIBLE TIPO INCORRECTO: debería ser 'cabana'")
        elif any(word in nombre_lower for word in ['masaje', 'spa', 'relajación', 'descontracturante']):
            if servicio.tipo_servicio != 'masaje':
                print(f"  ⚠️  POSIBLE TIPO INCORRECTO: debería ser 'masaje'")

    # Resumen por tipo
    print("\n=== RESUMEN POR TIPO (SOLO WEB) ===")
    for tipo, display in Servicio.TIPO_SERVICIO_CHOICES:
        count = servicios_web.filter(tipo_servicio=tipo).count()
        print(f"{display}: {count} servicios")

if __name__ == "__main__":
    main()