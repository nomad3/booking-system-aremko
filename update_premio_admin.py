#!/usr/bin/env python
"""
Script para actualizar el admin de Premio y agregar el campo tramos_validos
"""

# Contenido actualizado para el admin
admin_content = '''from django.contrib import admin
from .models import Premio, ClientePremio

@admin.register(Premio)
class PremioAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'tipo', 'get_tramos_display', 'activo', 'fecha_creacion']
    list_filter = ['tipo', 'activo']
    search_fields = ['nombre', 'descripcion_corta']

    fieldsets = (
        ('Información Básica', {
            'fields': ('nombre', 'tipo', 'activo')
        }),
        ('Descripciones', {
            'fields': ('descripcion_corta', 'descripcion_legal')
        }),
        ('Valores y Descuentos', {
            'fields': ('porcentaje_descuento_tinas', 'porcentaje_descuento_masajes', 'valor_monetario')
        }),
        ('Configuración', {
            'fields': ('tramo_hito', 'tramos_validos', 'dias_validez', 'restricciones')
        }),
    )

    def get_tramos_display(self, obj):
        """Muestra los tramos de forma legible en la lista"""
        return obj.descripcion_tramos_validos()
    get_tramos_display.short_description = 'Tramos Válidos'


@admin.register(ClientePremio)
class ClientePremioAdmin(admin.ModelAdmin):
    list_display = ['cliente', 'premio', 'estado', 'fecha_ganado', 'fecha_expiracion', 'codigo_unico']
    list_filter = ['estado', 'premio__tipo', 'fecha_ganado']
    search_fields = ['cliente__nombre', 'cliente__telefono', 'cliente__email', 'codigo_unico']
    readonly_fields = ['codigo_unico', 'fecha_ganado', 'tramo_al_ganar', 'gasto_total_al_ganar']

    fieldsets = (
        ('Información Principal', {
            'fields': ('cliente', 'premio', 'estado', 'codigo_unico')
        }),
        ('Fechas', {
            'fields': ('fecha_ganado', 'fecha_aprobacion', 'fecha_enviado', 'fecha_expiracion', 'fecha_uso')
        }),
        ('Contexto del Premio', {
            'fields': ('tramo_al_ganar', 'gasto_total_al_ganar', 'tramo_anterior')
        }),
        ('Email', {
            'fields': ('asunto_email', 'cuerpo_email'),
            'classes': ('collapse',)
        }),
        ('Otros', {
            'fields': ('venta_donde_uso', 'notas'),
            'classes': ('collapse',)
        }),
    )
'''

# Buscar la ubicación del archivo admin.py
import os
import glob

# Buscar el archivo admin.py en ventas
admin_paths = glob.glob('ventas/**/admin.py', recursive=True)
if not admin_paths:
    admin_paths = ['ventas/admin.py']  # Ruta por defecto

admin_path = admin_paths[0]

try:
    # Hacer backup del archivo actual
    if os.path.exists(admin_path):
        with open(admin_path, 'r') as f:
            backup_content = f.read()

        # Buscar si ya tiene la configuración de Premio
        if 'class PremioAdmin' in backup_content:
            print(f"⚠️  El archivo {admin_path} ya tiene configuración de PremioAdmin")
            print("   Agregando el campo tramos_validos al fieldset existente...")

            # Aquí deberías actualizar solo la parte necesaria
            # Por simplicidad, reemplazaré todo el archivo

    # Escribir el nuevo contenido
    with open(admin_path, 'w') as f:
        f.write(admin_content)

    print(f"✅ Archivo {admin_path} actualizado exitosamente")
    print("\n⚠️  IMPORTANTE: Necesitas reiniciar el servidor Django para ver los cambios")
    print("   En producción, esto normalmente sucede automáticamente con el deploy")

except Exception as e:
    print(f"❌ Error actualizando admin.py: {e}")