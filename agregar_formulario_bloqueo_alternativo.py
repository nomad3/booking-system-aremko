#!/usr/bin/env python
"""
Script para agregar el formulario alternativo de bloqueo al admin
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

print("=== AGREGANDO FORMULARIO ALTERNATIVO DE BLOQUEO ===\n")

codigo_a_agregar = '''
# --- Formulario Alternativo para ServicioBloqueo ---
# Importar la vista personalizada
from ventas.admin_bloqueo_alternativo import crear_bloqueo_servicio_view, get_admin_urls

# Modificar el admin de ServicioBloqueo para agregar botón
class ServicioBloqueoAdminMejorado(ServicioBloqueoAdmin):
    """Admin mejorado con formulario alternativo"""

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['has_alternative_add'] = True
        extra_context['alternative_add_url'] = '/admin/ventas/serviciobloqueo/crear-alternativo/'
        return super().changelist_view(request, extra_context=extra_context)

    def get_urls(self):
        return get_admin_urls(super().get_urls())

# Re-registrar con el admin mejorado
admin.site.unregister(ServicioBloqueo)
admin.site.register(ServicioBloqueo, ServicioBloqueoAdminMejorado)
'''

print("Código a agregar al final de ventas/admin.py:")
print("="*60)
print(codigo_a_agregar)
print("="*60)

# Crear template para el botón
template_boton = '''
<!-- Agregar esto a admin/ventas/serviciobloqueo/change_list.html -->
{% extends "admin/change_list.html" %}

{% block content %}
    {% if has_alternative_add %}
    <div style="margin-bottom: 20px;">
        <a href="{{ alternative_add_url }}" class="button" style="background-color: #28a745; color: white;">
            ✅ Crear Bloqueo (Formulario Alternativo)
        </a>
        <span style="margin-left: 10px; color: #666;">
            Use este formulario si el formulario normal da error 500
        </span>
    </div>
    {% endif %}
    {{ block.super }}
{% endblock %}
'''

# Guardar template
template_path = 'ventas/templates/admin/ventas/serviciobloqueo/change_list.html'
print(f"\n2. Crear template en: {template_path}")
print("Contenido del template:")
print(template_boton)

print("\n3. Pasos para implementar:")
print("   a) Agrega el código al final de ventas/admin.py")
print("   b) Crea el template change_list.html")
print("   c) Reinicia el servidor")
print("\n✅ El formulario alternativo estará disponible en:")
print("   /admin/ventas/serviciobloqueo/crear-alternativo/")

# Crear un acceso directo más simple
print("\n" + "="*60)
print("ALTERNATIVA RÁPIDA - Management Command:")
print("="*60)
print("Crea el archivo: ventas/management/commands/crear_bloqueo.py")

comando_content = '''
from django.core.management.base import BaseCommand
from django.db import connection
from ventas.models import Servicio
from datetime import datetime

class Command(BaseCommand):
    help = 'Crear bloqueo de servicio de forma segura'

    def add_arguments(self, parser):
        parser.add_argument('servicio_id', type=int, help='ID del servicio')
        parser.add_argument('fecha_inicio', help='Fecha inicio YYYY-MM-DD')
        parser.add_argument('fecha_fin', help='Fecha fin YYYY-MM-DD')
        parser.add_argument('motivo', help='Motivo del bloqueo')

    def handle(self, *args, **options):
        try:
            servicio = Servicio.objects.get(id=options['servicio_id'])

            with connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO ventas_serviciobloqueo
                    (servicio_id, fecha_inicio, fecha_fin, motivo, activo,
                     creado_en, creado_por_id, fecha, hora_slot)
                    VALUES (%s, %s, %s, %s, true, NOW(), 1, %s, 'N/A')
                    RETURNING id
                """, [
                    servicio.id,
                    options['fecha_inicio'],
                    options['fecha_fin'],
                    options['motivo'],
                    options['fecha_inicio']
                ])

                bloqueo_id = cursor.fetchone()[0]
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✅ Bloqueo creado: ID {bloqueo_id} - {servicio.nombre}'
                    )
                )

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {str(e)}'))
'''

print("\nContenido del comando:")
print(comando_content)
print("\nUso: python manage.py crear_bloqueo 12 2026-04-01 2026-04-05 'Mantenimiento'")

print("\n✅ SOLUCIONES PREPARADAS")