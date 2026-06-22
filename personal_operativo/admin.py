# -*- coding: utf-8 -*-
from django.contrib import admin
from django.utils.html import format_html

from .models import PersonalOperativo, NotificacionStaff


@admin.register(PersonalOperativo)
class PersonalOperativoAdmin(admin.ModelAdmin):
    """Whitelist de staff para Luna Interna — SOLO superusuarios.

    El campo `responde_auto` da autonomía a Luna sobre ese número, por eso el
    acceso queda restringido a superusuarios.
    """
    list_display = ('nombre', 'telefono', 'rol', 'turno', 'auto_col', 'avisos_col', 'activo', 'usuario')
    list_filter = ('rol', 'turno', 'responde_auto', 'recibe_avisos_operacion', 'activo')
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
        ('Avisos de operación', {
            'fields': ('recibe_avisos_operacion',),
            'description': '📥 Recibe por WhatsApp los avisos de tareas de Recepción/Operación apenas '
                           'se generan. Marca esto en quien esté cubriendo recepción ("de turno").'
        }),
        ('Notas', {'fields': ('notas',)}),
    )

    @admin.display(description='Avisos op.')
    def avisos_col(self, obj):
        if obj.recibe_avisos_operacion:
            return format_html('<span style="background:#dbeafe;color:#1e40af;padding:2px 9px;'
                               'border-radius:999px;font-weight:600;font-size:12px;">📥 de turno</span>')
        return '—'

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


@admin.register(NotificacionStaff)
class NotificacionStaffAdmin(admin.ModelAdmin):
    """Cola de avisos salientes a staff (Luna Interna). Solo lectura/monitoreo."""
    list_display = ('creada', 'telefono', 'estado', 'origen', 'ref_id', 'intentos')
    list_filter = ('estado', 'origen')
    search_fields = ('telefono', 'dedup_key', 'texto')
    readonly_fields = ('telefono', 'texto', 'origen', 'ref_tipo', 'ref_id', 'dedup_key',
                       'intentos', 'error', 'creada', 'enviada_at')
    ordering = ('-creada',)

    def has_add_permission(self, request):
        return False

    def has_module_permission(self, request):
        return bool(request.user and request.user.is_superuser)

    def has_view_permission(self, request, obj=None):
        return bool(request.user and request.user.is_superuser)
