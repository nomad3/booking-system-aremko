# Optimizaciones para el modelo Cliente
from django.db import models
from django.core.cache import cache
from django.db import transaction
import logging

logger = logging.getLogger(__name__)

class ClienteOptimizadoMixin:
    """
    Mixin con optimizaciones para el modelo Cliente
    """

    def save(self, *args, **kwargs):
        """
        Save optimizado que evita normalización innecesaria
        """
        # Skip normalización si se indica explícitamente
        skip_normalization = getattr(self, '_skip_phone_normalization', False)

        if self.telefono and not skip_normalization:
            # Solo normalizar si el teléfono cambió
            if self.pk:
                old_telefono = Cliente.objects.filter(pk=self.pk).values_list('telefono', flat=True).first()
                if old_telefono == self.telefono:
                    skip_normalization = True

            if not skip_normalization:
                try:
                    # Normalización básica sin importar servicio pesado
                    telefono_limpio = self._normalizar_telefono_basico(self.telefono)
                    self.telefono = telefono_limpio
                except Exception as e:
                    logger.warning(f"Error normalizando teléfono: {e}")

        # Guardar con transacción
        with transaction.atomic():
            super().save(*args, **kwargs)

        # Limpiar caché relacionado
        self._invalidar_cache()

    def _normalizar_telefono_basico(self, telefono):
        """
        Normalización básica sin dependencias pesadas
        """
        if not telefono:
            return telefono

        # Quitar espacios y caracteres comunes
        telefono = telefono.strip()
        telefono = telefono.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')

        # Si empieza con 56, es chileno
        if telefono.startswith('56') and len(telefono) > 10:
            telefono = '+' + telefono
        # Si empieza con 9 y tiene 9 dígitos, es móvil chileno
        elif telefono.startswith('9') and len(telefono) == 9:
            telefono = '+569' + telefono[1:]
        # Si no tiene +, agregarlo
        elif not telefono.startswith('+'):
            # Asumir Chile si tiene 9 dígitos
            if len(telefono) == 9:
                telefono = '+569' + telefono[1:]

        return telefono

    def _invalidar_cache(self):
        """
        Invalida caché relacionado con el cliente
        """
        cache_keys = [
            f"cliente_{self.pk}",
            f"cliente_gasto_{self.pk}",
            f"cliente_visitas_{self.pk}",
            f"cliente_search_{self.telefono[:10]}",
            f"cliente_search_{self.nombre[:10]}"
        ]

        cache.delete_many(cache_keys)

    @property
    def numero_visitas_cached(self):
        """
        Número de visitas con caché
        """
        cache_key = f"cliente_visitas_{self.pk}"
        visitas = cache.get(cache_key)

        if visitas is None:
            visitas = self.ventareserva_set.count()
            cache.set(cache_key, visitas, 3600)  # 1 hora

        return visitas

    @property
    def gasto_total_cached(self):
        """
        Gasto total con caché
        """
        cache_key = f"cliente_gasto_{self.pk}"
        gasto = cache.get(cache_key)

        if gasto is None:
            # Cálculo optimizado con una sola query
            from django.db.models import Sum

            gasto_actual = self.ventareserva_set.filter(
                estado_pago__in=['pagado', 'parcial']
            ).aggregate(total=Sum('total'))['total'] or 0

            # Si hay ServiceHistory, agregarlo
            try:
                from ventas.models import ServiceHistory
                gasto_historico = ServiceHistory.objects.filter(
                    cliente_id=self.pk
                ).aggregate(total=Sum('amount'))['total'] or 0
                gasto = gasto_actual + gasto_historico
            except:
                gasto = gasto_actual

            cache.set(cache_key, gasto, 3600)  # 1 hora

        return gasto


# Manager optimizado para Cliente
class ClienteManagerOptimizado(models.Manager):
    """
    Manager con queries optimizadas para Cliente
    """

    def buscar_rapido(self, termino):
        """
        Búsqueda rápida con límite y caché
        """
        if not termino:
            return self.none()

        # Intentar caché primero
        cache_key = f"cliente_busqueda_{termino[:30]}"
        resultados = cache.get(cache_key)

        if resultados is None:
            # Búsqueda con límite
            resultados = list(
                self.filter(
                    models.Q(nombre__icontains=termino) |
                    models.Q(telefono__icontains=termino) |
                    models.Q(email__icontains=termino)
                )[:20].values('id', 'nombre', 'telefono', 'email')
            )

            # Cachear por 5 minutos
            cache.set(cache_key, resultados, 300)

        return resultados

    def con_estadisticas(self):
        """
        Queryset con estadísticas pre-calculadas
        """
        from django.db.models import Count, Sum, Q

        return self.annotate(
            num_visitas=Count('ventareserva'),
            gasto_total=Sum(
                'ventareserva__total',
                filter=Q(ventareserva__estado_pago__in=['pagado', 'parcial'])
            )
        )

    def activos_recientes(self, dias=90):
        """
        Clientes con actividad reciente
        """
        from datetime import datetime, timedelta

        fecha_limite = datetime.now().date() - timedelta(days=dias)

        return self.filter(
            ventareserva__fecha__gte=fecha_limite
        ).distinct()