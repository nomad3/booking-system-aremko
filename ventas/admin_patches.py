"""
Parches de optimización para el admin de Clientes
Aplica mejoras de rendimiento sin modificar los archivos originales
"""
from django.contrib import admin
from django.db import transaction
from django.core.cache import cache
from django.db.models import Count, Sum, Q, Prefetch
from .models import Cliente
from .forms import ClienteAdminForm
import logging

logger = logging.getLogger(__name__)

# Desregistrar el admin actual
try:
    admin.site.unregister(Cliente)
except admin.sites.NotRegistered:
    pass

@admin.register(Cliente)
class ClienteAdminOptimizado(admin.ModelAdmin):
    """
    ClienteAdmin con optimizaciones de rendimiento
    """
    form = ClienteAdminForm
    search_fields = ('nombre', 'telefono', 'email')
    list_display = ('nombre', 'telefono', 'email', 'mostrar_visitas', 'mostrar_gasto')
    list_filter = ('created_at',)

    # Optimizaciones
    list_select_related = []  # Cliente no tiene FKs importantes
    list_per_page = 50
    show_full_result_count = False

    # Campos de solo lectura para cálculos costosos
    readonly_fields = ('numero_visitas', 'gasto_total')

    # Organización de campos en el formulario
    fieldsets = (
        ('Información Personal', {
            'fields': ('nombre', 'email', 'telefono_completo', 'codigo_pais_otro', 'documento_identidad')
        }),
        ('Ubicación', {
            'fields': ('pais', 'ciudad', 'region', 'comuna'),
            'classes': ('location-fields',),
        }),
        ('Estadísticas', {
            'fields': ('numero_visitas', 'gasto_total'),
            'classes': ('collapse',),
        }),
    )

    def get_queryset(self, request):
        """Optimiza queries con anotaciones"""
        qs = super().get_queryset(request)

        # Solo agregar anotaciones en la vista de lista
        if request.resolver_match.url_name == 'ventas_cliente_changelist':
            qs = qs.annotate(
                _visitas_count=Count('ventareserva', distinct=True),
                _gasto_sum=Sum(
                    'ventareserva__total',
                    filter=Q(ventareserva__estado_pago__in=['pagado', 'parcial'])
                )
            )

        return qs

    def mostrar_visitas(self, obj):
        """Muestra visitas usando anotación"""
        if hasattr(obj, '_visitas_count'):
            return obj._visitas_count
        # Fallback con caché
        cache_key = f"cliente_visitas_{obj.pk}"
        visitas = cache.get(cache_key)
        if visitas is None:
            visitas = obj.ventareserva_set.count()
            cache.set(cache_key, visitas, 300)
        return visitas
    mostrar_visitas.short_description = 'Visitas'
    mostrar_visitas.admin_order_field = '_visitas_count'

    def mostrar_gasto(self, obj):
        """Muestra gasto usando anotación"""
        if hasattr(obj, '_gasto_sum'):
            gasto = obj._gasto_sum or 0
        else:
            # Fallback con caché
            cache_key = f"cliente_gasto_{obj.pk}"
            gasto = cache.get(cache_key)
            if gasto is None:
                gasto = obj.gasto_total()
                cache.set(cache_key, gasto, 300)

        return f"${int(gasto):,}".replace(',', '.')
    mostrar_gasto.short_description = 'Gasto'
    mostrar_gasto.admin_order_field = '_gasto_sum'

    def get_search_results(self, request, queryset, search_term):
        """Búsqueda optimizada"""
        queryset, use_distinct = super().get_search_results(
            request, queryset, search_term
        )

        # Limitar resultados en autocomplete
        if 'autocomplete' in request.path:
            queryset = queryset[:20]

        return queryset, use_distinct

    def save_model(self, request, obj, form, change):
        """Guarda con optimizaciones y manejo de errores"""
        try:
            with transaction.atomic():
                # Marcar para skip de normalización si no cambió el teléfono
                if change and 'telefono' not in form.changed_data:
                    obj._skip_phone_normalization = True

                super().save_model(request, obj, form, change)

                # Limpiar caché
                cache.delete_many([
                    f"cliente_visitas_{obj.pk}",
                    f"cliente_gasto_{obj.pk}",
                ])

        except Exception as e:
            logger.error(f"Error guardando cliente {obj.pk}: {str(e)}")
            raise

    def changelist_view(self, request, extra_context=None):
        """Vista optimizada con warming de caché"""
        # Precalentar caché si está vacío
        if not cache.get('cliente_admin_warmed'):
            # Últimos 50 clientes más activos
            clientes_activos = Cliente.objects.annotate(
                ventas_count=Count('ventareserva')
            ).order_by('-ventas_count')[:50]

            for cliente in clientes_activos:
                cache.set(f"cliente_data_{cliente.pk}", {
                    'nombre': cliente.nombre,
                    'telefono': cliente.telefono,
                    'email': cliente.email
                }, 3600)

            cache.set('cliente_admin_warmed', True, 1800)

        return super().changelist_view(request, extra_context)

    def response_add(self, request, obj, post_url_continue=None):
        """Maneja la respuesta después de agregar un cliente desde un popup"""
        if "_popup" in request.POST:
            from django.http import HttpResponse
            return HttpResponse(
                '<script>opener.dismissAddRelatedObjectPopup(window, "%s", "%s");</script>' % (
                    obj.pk,
                    obj.nombre + ' - ' + obj.telefono
                )
            )
        return super().response_add(request, obj, post_url_continue)

    def response_change(self, request, obj):
        """Maneja la respuesta después de cambiar un cliente desde un popup"""
        if "_popup" in request.POST:
            from django.http import HttpResponse
            return HttpResponse(
                '<script>opener.dismissChangeRelatedObjectPopup(window, "%s", "%s", "%s");</script>' % (
                    obj.pk,
                    obj.nombre + ' - ' + obj.telefono,
                    obj.pk
                )
            )
        return super().response_change(request, obj)


# Monkey patch para optimizar el save del modelo
original_cliente_save = Cliente.save

def cliente_save_optimizado(self, *args, **kwargs):
    """Save optimizado que evita normalización costosa cuando no es necesaria"""

    # Skip si se indica
    if hasattr(self, '_skip_phone_normalization') and self._skip_phone_normalization:
        return original_cliente_save(self, *args, **kwargs)

    # Solo normalizar si el teléfono realmente cambió
    if self.pk and self.telefono:
        try:
            old_telefono = Cliente.objects.filter(pk=self.pk).values_list('telefono', flat=True).first()
            if old_telefono == self.telefono:
                return original_cliente_save(self, *args, **kwargs)
        except:
            pass

    # Normalización básica inline para evitar imports costosos
    if self.telefono:
        telefono = self.telefono.strip()
        telefono = telefono.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')

        # Formato básico Chile
        if telefono.startswith('9') and len(telefono) == 9:
            telefono = '+569' + telefono[1:]
        elif telefono.startswith('56') and len(telefono) > 10:
            telefono = '+' + telefono
        elif not telefono.startswith('+') and len(telefono) == 9:
            telefono = '+569' + telefono[1:]

        self.telefono = telefono

    return original_cliente_save(self, *args, **kwargs)

# Aplicar el monkey patch
Cliente.save = cliente_save_optimizado


# Agregar métodos optimizados al modelo
def numero_visitas_optimizado(self):
    """Versión optimizada con caché"""
    cache_key = f"cliente_visitas_{self.pk}"
    visitas = cache.get(cache_key)
    if visitas is None:
        visitas = self.ventareserva_set.count()
        cache.set(cache_key, visitas, 300)
    return visitas

def gasto_total_optimizado(self):
    """Versión optimizada con caché"""
    cache_key = f"cliente_gasto_{self.pk}"
    gasto = cache.get(cache_key)
    if gasto is None:
        # Una sola query optimizada
        gasto = self.ventareserva_set.filter(
            estado_pago__in=['pagado', 'parcial']
        ).aggregate(total=Sum('total'))['total'] or 0

        # Agregar histórico si existe
        try:
            from .models import ServiceHistory
            historico = ServiceHistory.objects.filter(
                cliente_id=self.pk
            ).aggregate(total=Sum('amount'))['total'] or 0
            gasto += historico
        except:
            pass

        cache.set(cache_key, gasto, 300)
    return gasto

# Reemplazar métodos originales
Cliente.numero_visitas_cached = numero_visitas_optimizado
Cliente.gasto_total_cached = gasto_total_optimizado