"""Admin del Catálogo de Clips — curación humana ("IA propone, humano cura").

Solo superuser: es la mesa de trabajo interna del banco de material.
"""
from django.contrib import admin
from django.utils.html import format_html

from .models import Clip


@admin.register(Clip)
class ClipAdmin(admin.ModelAdmin):
    list_display = ('miniatura', 'archivo', 'area', 'nombre_comercial', 'momento',
                    'vapor', 'decoracion', 'keeper', 'calidad', 'estado', 'actualizado')
    list_filter = ('area', 'keeper', 'estado', 'vapor', 'momento', 'estacion',
                   'calidad', 'decoracion', 'personas', 'permiso', 'tipo')
    search_fields = ('archivo', 'nombre_comercial', 'descripcion', 'nota', 'origen')
    list_editable = ('keeper', 'estado')
    readonly_fields = ('creado', 'actualizado', 'preview')
    list_per_page = 50
    fieldsets = (
        ('Archivo', {'fields': ('archivo', 'imagen', 'cloud_url', 'preview', 'tipo', 'fuente', 'origen')}),
        ('Taxonomía', {'fields': ('area', 'nombre_comercial', 'momento', 'estacion',
                                  'vapor', 'decoracion', 'personas', 'permiso')}),
        ('Curación', {'fields': ('calidad', 'keeper', 'estado', 'descripcion',
                                 'orientacion', 'nota')}),
        ('Flexibles', {'fields': ('etiquetas', 'apto_para', 'atributos')}),
        ('Metadatos', {'fields': ('creado', 'actualizado')}),
    )

    def has_module_permission(self, request):
        return bool(request.user and request.user.is_superuser)

    def has_view_permission(self, request, obj=None):
        return bool(request.user and request.user.is_superuser)

    def has_change_permission(self, request, obj=None):
        return bool(request.user and request.user.is_superuser)

    def has_add_permission(self, request):
        return bool(request.user and request.user.is_superuser)

    def has_delete_permission(self, request, obj=None):
        return bool(request.user and request.user.is_superuser)

    @admin.display(description='Foto')
    def miniatura(self, obj):
        if obj.cloud_url:
            return format_html('<img src="{}" style="height:44px;border-radius:6px;">', obj.cloud_url)
        return '—'

    @admin.display(description='Vista previa')
    def preview(self, obj):
        if obj.cloud_url:
            return format_html('<img src="{}" style="max-width:420px;border-radius:10px;">', obj.cloud_url)
        return '—'
