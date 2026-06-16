from django.contrib import admin

from .models import ChannelMessage


@admin.register(ChannelMessage)
class ChannelMessageAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'canal', 'direction', 'external_id', 'contact_name',
                    'requiere_atencion', 'cliente_id')
    list_filter = ('canal', 'direction', 'requiere_atencion')
    search_fields = ('external_id', 'contact_name', 'body', 'external_message_id')
    readonly_fields = ('created_at',)
    date_hierarchy = 'timestamp'
    ordering = ('-timestamp',)
