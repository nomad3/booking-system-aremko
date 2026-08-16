from django.contrib import admin
from django.utils import timezone

from .models import ChannelMessage, InstagramTokenConfig


@admin.register(ChannelMessage)
class ChannelMessageAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'canal', 'direction', 'external_id', 'contact_name',
                    'requiere_atencion', 'cliente_id')
    list_filter = ('canal', 'direction', 'requiere_atencion')
    search_fields = ('external_id', 'contact_name', 'body', 'external_message_id')
    readonly_fields = ('created_at',)
    date_hierarchy = 'timestamp'
    ordering = ('-timestamp',)


@admin.register(InstagramTokenConfig)
class InstagramTokenConfigAdmin(admin.ModelAdmin):
    """H-107: singleton. Jorge pega aquí el token generado en developers.facebook.com;
    desde ahí el sistema lo refresca solo (~7 días) vía el fetch del backend Go."""
    list_display = ('__str__', 'ultimo_refresh_at', 'ultimo_intento_at', 'updated_at')
    readonly_fields = ('token_actualizado_at', 'expira_estimado', 'ultimo_refresh_at',
                       'ultimo_intento_at', 'ultimo_error', 'ultimo_aviso_at', 'updated_at')
    fieldsets = (
        (None, {'fields': ('token',)}),
        ('Estado del auto-refresh (solo lectura)', {'fields': (
            'token_actualizado_at', 'expira_estimado', 'ultimo_refresh_at',
            'ultimo_intento_at', 'ultimo_error', 'ultimo_aviso_at', 'updated_at')}),
    )

    def save_model(self, request, obj, form, change):
        # Token nuevo pegado a mano → resetear el estado del anterior: el primer
        # refresh espera 7 días desde ACÁ (Meta exige que el token tenga ≥24 h).
        if 'token' in form.changed_data:
            obj.token_actualizado_at = timezone.now()
            obj.expira_estimado = None
            obj.ultimo_refresh_at = None
            obj.ultimo_intento_at = None
            obj.ultimo_error = ''
        super().save_model(request, obj, form, change)

    def has_add_permission(self, request):
        # Singleton: permitir "agregar" solo si aún no existe la fila.
        return not InstagramTokenConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
