# -*- coding: utf-8 -*-
from django.contrib import admin
from django.utils.html import format_html

from .models import PersonalOperativo


@admin.register(PersonalOperativo)
class PersonalOperativoAdmin(admin.ModelAdmin):
    """Whitelist de staff para Luna Interna — SOLO superusuarios.

    El campo `responde_auto` da autonomía a Luna sobre ese número, por eso el
    acceso queda restringido a superusuarios.
    """
    list_display = ('nombre', 'telefono', 'rol', 'turno', 'auto_col', 'activo', 'usuario')
    list_filter = ('rol', 'turno', 'responde_auto', 'activo')
    search_fields = ('nombre', 'telefono', 'usuario__username', 'usuario__email')
    autocomplete_fields = ('usuario',)
    ordering = ('nombre',)

    fieldsets = (
        ('Persona', {'fields': ('nombre', 'telefono', 'usuario', 'rol', 'turno', 'activo')}),
        ('Autonomía de Luna', {
            'fields': ('responde_auto',),
            'description': '⚙️ Si está activo, Luna le responde AUTOMÁTICAMENTE a este número, sin '
                           'pasar por la aprobación de Deborah. Actívalo solo para staff de confianza.'
        }),
        ('Notas', {'fields': ('notas',)}),
    )

    @admin.display(description='Responde auto')
    def auto_col(self, obj):
        if obj.responde_auto:
            return format_html('<span style="background:#dcfce7;color:#15803d;padding:2px 9px;'
                               'border-radius:999px;font-weight:600;font-size:12px;">AUTO ✅</span>')
        return format_html('<span style="background:#f3f4f6;color:#6b7280;padding:2px 9px;'
                           'border-radius:999px;font-size:12px;">borrador</span>')

    # --- Acceso SOLO superusuarios ---
    def has_module_permission(self, request):
        return bool(request.user and request.user.is_superuser)

    def has_view_permission(self, request, obj=None):
        return bool(request.user and request.user.is_superuser)

    def has_add_permission(self, request):
        return bool(request.user and request.user.is_superuser)

    def has_change_permission(self, request, obj=None):
        return bool(request.user and request.user.is_superuser)

    def has_delete_permission(self, request, obj=None):
        return bool(request.user and request.user.is_superuser)
