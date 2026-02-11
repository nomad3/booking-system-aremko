# Optimizaciones para ClienteAdmin
from django.contrib import admin
from django.db import transaction
from django.core.cache import cache
from django.db.models import Count, Sum, Q, Prefetch
from .models import Cliente, VentaReserva, ServiceHistory
import logging

logger = logging.getLogger(__name__)

class ClienteAdminOptimizado(admin.ModelAdmin):
    """
    ClienteAdmin optimizado para mejorar rendimiento
    """
    search_fields = ('nombre', 'telefono', 'email')
    list_display = ('nombre', 'telefono', 'email', 'ciudad', 'created_at')
    list_filter = ('created_at', 'ciudad', 'region')

    # Optimizaciones de queries
    list_select_related = ('region', 'comuna')
    list_per_page = 50  # Reducir de 100 por defecto

    # Campos de solo lectura para evitar cálculos innecesarios
    readonly_fields = ('created_at', 'mostrar_numero_visitas', 'mostrar_gasto_total')

    # Búsqueda optimizada
    show_full_result_count = False  # No contar todos los resultados

    def get_queryset(self, request):
        """
        Optimiza el queryset con anotaciones para evitar cálculos en propiedades
        """
        qs = super().get_queryset(request)

        # Anotar número de visitas y gasto total para evitar N+1
        qs = qs.annotate(
            _num_visitas=Count('ventareserva'),
            _gasto_actual=Sum(
                'ventareserva__total',
                filter=Q(ventareserva__estado_pago__in=['pagado', 'parcial'])
            )
        )

        return qs

    def mostrar_numero_visitas(self, obj):
        """Muestra número de visitas usando anotación"""
        return getattr(obj, '_num_visitas', 0)
    mostrar_numero_visitas.short_description = 'Visitas'
    mostrar_numero_visitas.admin_order_field = '_num_visitas'

    def mostrar_gasto_total(self, obj):
        """Muestra gasto total usando anotación"""
        gasto = getattr(obj, '_gasto_actual', 0) or 0
        return f"${gasto:,.0f}".replace(',', '.')
    mostrar_gasto_total.short_description = 'Gasto Total'
    mostrar_gasto_total.admin_order_field = '_gasto_actual'

    def get_search_results(self, request, queryset, search_term):
        """
        Búsqueda optimizada con límites y caché
        """
        # Caché de resultados frecuentes
        if search_term:
            cache_key = f"cliente_search_{search_term[:50]}"
            cached_ids = cache.get(cache_key)

            if cached_ids is not None:
                queryset = queryset.filter(id__in=cached_ids)
                use_distinct = False
            else:
                # Búsqueda normal
                queryset, use_distinct = super().get_search_results(
                    request, queryset, search_term
                )

                # Cachear los IDs por 5 minutos
                if queryset.count() < 100:
                    cache.set(cache_key, list(queryset.values_list('id', flat=True)), 300)
        else:
            queryset, use_distinct = super().get_search_results(
                request, queryset, search_term
            )

        # Limitar resultados en autocomplete
        if 'autocomplete' in request.path:
            queryset = queryset[:20]  # Reducir de 50 a 20

        return queryset, use_distinct

    def save_model(self, request, obj, form, change):
        """
        Guarda el modelo con optimizaciones
        """
        try:
            # Usar transacción para asegurar atomicidad
            with transaction.atomic():
                # Si el teléfono no cambió, saltar normalización
                if change and 'telefono' not in form.changed_data:
                    obj._skip_phone_normalization = True

                super().save_model(request, obj, form, change)

                # Registrar éxito
                logger.info(f"Cliente {obj.id} guardado exitosamente")

        except Exception as e:
            logger.error(f"Error guardando cliente: {str(e)}")
            raise

    def changelist_view(self, request, extra_context=None):
        """
        Vista de lista con optimizaciones
        """
        # Precalentar caché con clientes frecuentes
        if not cache.get('clientes_frecuentes_loaded'):
            clientes_frecuentes = Cliente.objects.filter(
                ventareserva__fecha__gte='2026-01-01'
            ).distinct()[:100].values_list('id', 'nombre', 'telefono')

            for cliente in clientes_frecuentes:
                cache.set(f"cliente_{cliente[0]}", cliente, 3600)

            cache.set('clientes_frecuentes_loaded', True, 3600)

        return super().changelist_view(request, extra_context)

# Formulario optimizado para Cliente
from django import forms
from .models import Cliente

class ClienteFormOptimizado(forms.ModelForm):
    """
    Formulario optimizado que valida sin normalizar en cada campo
    """
    class Meta:
        model = Cliente
        fields = '__all__'

    def clean_telefono(self):
        """
        Validación básica sin normalización completa
        """
        telefono = self.cleaned_data.get('telefono')

        if telefono:
            # Validación básica sin importar servicio pesado
            telefono = telefono.strip()

            # Verificar longitud mínima
            if len(telefono.replace(' ', '').replace('-', '')) < 8:
                raise forms.ValidationError("El teléfono debe tener al menos 8 dígitos")

            # Verificar unicidad sin normalizar
            qs = Cliente.objects.filter(telefono=telefono)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)

            if qs.exists():
                raise forms.ValidationError("Ya existe un cliente con este teléfono")

        return telefono