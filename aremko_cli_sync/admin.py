from django.contrib import admin

from .models import WeeklyBriefSnapshot


@admin.register(WeeklyBriefSnapshot)
class WeeklyBriefSnapshotAdmin(admin.ModelAdmin):
    """Solo lectura: los snapshots los crea únicamente el management command
    sync_aremko_cli_weekly_brief (vía el cron externo), nunca a mano."""

    list_display = ('fetched_at', 'success', 'error_message')
    ordering = ('-fetched_at',)
    readonly_fields = ('fetched_at', 'success', 'google_ads', 'meta_ads', 'error_message')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
