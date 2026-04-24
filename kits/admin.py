"""Admin para Kits: inline de componentes dentro del Kit."""

from django.contrib import admin

from .models import Kit, KitComponente


class KitComponenteInline(admin.TabularInline):
    model = KitComponente
    extra = 1
    autocomplete_fields = ['producto_componente']
    fields = ('producto_componente', 'cantidad_por_unidad', 'activo', 'notas')


@admin.register(Kit)
class KitAdmin(admin.ModelAdmin):
    list_display = (
        'producto_compuesto',
        'activo',
        'descontar_componentes_auto',
        'cantidad_componentes',
        'updated_at',
    )
    list_filter = ('activo', 'descontar_componentes_auto')
    search_fields = (
        'producto_compuesto__nombre',
        'notas',
    )
    autocomplete_fields = ['producto_compuesto']
    inlines = [KitComponenteInline]
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': (
                'producto_compuesto',
                'activo',
                'descontar_componentes_auto',
                'notas',
            ),
        }),
        ('Metadatos', {
            'classes': ('collapse',),
            'fields': ('created_at', 'updated_at'),
        }),
    )

    def cantidad_componentes(self, obj):
        return obj.componentes.filter(activo=True).count()
    cantidad_componentes.short_description = '# componentes'


@admin.register(KitComponente)
class KitComponenteAdmin(admin.ModelAdmin):
    list_display = (
        'kit',
        'producto_componente',
        'cantidad_por_unidad',
        'activo',
    )
    list_filter = ('activo',)
    search_fields = (
        'kit__producto_compuesto__nombre',
        'producto_componente__nombre',
    )
    autocomplete_fields = ['kit', 'producto_componente']
