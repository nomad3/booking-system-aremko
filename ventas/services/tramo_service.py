"""
TramoService - Servicio para cálculo y gestión de tramos de clientes
Maneja la lógica de negocio para el sistema de tramos y premios
"""
from django.utils import timezone
from django.db import transaction
from ventas.models import Cliente, HistorialTramo, ClientePremio
from ventas.services.crm_service import CRMService
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class TramoService:
    """Servicio para cálculo y gestión de tramos de clientes"""

    # Configuración de tramos
    TRAMO_SIZE = 50000  # Cada tramo es de $50,000

    # Hitos especiales que generan premios
    HITOS_PREMIO = [5, 10, 15, 20]  # Tramos que generan premios automáticamente
    HITO_VIP = 10  # Tramo $500,000 (premio especial)

    @classmethod
    def calcular_tramo(cls, gasto_total: float) -> int:
        """
        Calcula el tramo basado en el gasto total

        Tramo 1: $0 - $50,000
        Tramo 2: $50,001 - $100,000
        Tramo 3: $100,001 - $150,000
        ...

        Args:
            gasto_total: Gasto total del cliente

        Returns:
            Número de tramo (1, 2, 3, ...)
        """
        if gasto_total <= 0:
            return 0  # Sin tramo

        # Calcular tramo
        tramo = int(gasto_total / cls.TRAMO_SIZE)
        if gasto_total % cls.TRAMO_SIZE > 0:
            tramo += 1

        return tramo

    @classmethod
    def calcular_gasto_cliente(cls, cliente: Cliente) -> Decimal:
        """
        Calcula el gasto total de un cliente (histórico + actual)
        Usa CRMService para obtener datos consistentes

        Args:
            cliente: Objeto Cliente

        Returns:
            Gasto total como Decimal
        """
        try:
            datos_360 = CRMService.get_customer_360(cliente.id)
            gasto_total = datos_360['metricas']['gasto_total']
            return Decimal(str(gasto_total))
        except Exception as e:
            logger.error(f"Error calculando gasto de cliente {cliente.id}: {e}")
            return Decimal('0')

    @classmethod
    @transaction.atomic
    def actualizar_tramo_cliente(cls, cliente: Cliente) -> dict:
        """
        Actualiza el tramo de un cliente y registra el cambio

        Args:
            cliente: Objeto Cliente

        Returns:
            Dict con información del cambio:
            {
                'tramo_anterior': int,
                'tramo_actual': int,
                'cambio': bool,
                'gasto_total': Decimal,
                'hito_alcanzado': bool,
                'premio_generado': ClientePremio o None
            }
        """
        # Calcular gasto total y tramo actual
        gasto_total = cls.calcular_gasto_cliente(cliente)
        tramo_actual = cls.calcular_tramo(float(gasto_total))

        # Obtener tramo anterior del historial
        ultimo_historial = HistorialTramo.objects.filter(
            cliente=cliente
        ).order_by('-fecha_cambio').first()

        tramo_anterior = ultimo_historial.tramo_hasta if ultimo_historial else 0

        result = {
            'tramo_anterior': tramo_anterior,
            'tramo_actual': tramo_actual,
            'cambio': tramo_actual != tramo_anterior,
            'gasto_total': gasto_total,
            'hito_alcanzado': False,
            'premio_generado': None
        }

        # Si no hay cambio, retornar
        if not result['cambio']:
            return result

        # Registrar cambio en historial
        historial = HistorialTramo.objects.create(
            cliente=cliente,
            tramo_desde=tramo_anterior,
            tramo_hasta=tramo_actual,
            gasto_en_momento=gasto_total
        )

        # Verificar si alcanzó un hito
        if tramo_actual in cls.HITOS_PREMIO and tramo_actual > tramo_anterior:
            result['hito_alcanzado'] = True

            # Generar premio correspondiente (delegar a PremioService)
            from ventas.services.premio_service import PremioService
            premio = PremioService.generar_premio_por_hito(
                cliente=cliente,
                tramo_actual=tramo_actual,
                tramo_anterior=tramo_anterior,
                gasto_total=gasto_total
            )

            if premio:
                historial.premio_generado = premio
                historial.save()
                result['premio_generado'] = premio

        logger.info(f"Tramo actualizado: Cliente {cliente.id} - Tramo {tramo_anterior} → {tramo_actual}")

        return result

    @classmethod
    def es_cliente_nuevo(cls, cliente: Cliente) -> bool:
        """
        Determina si un cliente es "nuevo" para el sistema de premios

        Definición: Cliente sin servicios previos (ni actuales ni históricos)

        Args:
            cliente: Objeto Cliente

        Returns:
            True si es cliente nuevo, False en caso contrario
        """
        try:
            datos_360 = CRMService.get_customer_360(cliente.id)
            total_servicios = datos_360['metricas']['total_servicios']
            return total_servicios == 0
        except Exception as e:
            logger.error(f"Error verificando si cliente {cliente.id} es nuevo: {e}")
            return False

    @classmethod
    def obtener_tramo_actual(cls, cliente: Cliente) -> int:
        """
        Obtiene el tramo actual de un cliente sin actualizarlo

        Args:
            cliente: Objeto Cliente

        Returns:
            Número de tramo actual
        """
        gasto_total = cls.calcular_gasto_cliente(cliente)
        return cls.calcular_tramo(float(gasto_total))

    @classmethod
    def obtener_rango_tramo(cls, tramo: int) -> tuple:
        """
        Obtiene el rango de gasto de un tramo

        Args:
            tramo: Número de tramo

        Returns:
            Tuple (min, max) con el rango de gasto
        """
        if tramo <= 0:
            return (0, 0)

        min_gasto = (tramo - 1) * cls.TRAMO_SIZE + 1
        max_gasto = tramo * cls.TRAMO_SIZE

        # Tramo 1 empieza en 0
        if tramo == 1:
            min_gasto = 0

        return (min_gasto, max_gasto)

    @classmethod
    def obtener_progreso_tramo(cls, cliente: Cliente) -> dict:
        """
        Obtiene el progreso del cliente dentro de su tramo actual

        Args:
            cliente: Objeto Cliente

        Returns:
            Dict con información de progreso:
            {
                'tramo_actual': int,
                'gasto_actual': Decimal,
                'min_tramo': int,
                'max_tramo': int,
                'porcentaje_progreso': float,
                'falta_para_siguiente': Decimal
            }
        """
        gasto_total = cls.calcular_gasto_cliente(cliente)
        tramo_actual = cls.calcular_tramo(float(gasto_total))
        min_tramo, max_tramo = cls.obtener_rango_tramo(tramo_actual)

        # Calcular progreso dentro del tramo
        gasto_en_tramo = float(gasto_total) - min_tramo
        size_tramo = max_tramo - min_tramo
        porcentaje = (gasto_en_tramo / size_tramo * 100) if size_tramo > 0 else 0

        # Cuánto falta para el siguiente tramo
        falta = Decimal(str(max_tramo)) - gasto_total

        return {
            'tramo_actual': tramo_actual,
            'gasto_actual': gasto_total,
            'min_tramo': min_tramo,
            'max_tramo': max_tramo,
            'porcentaje_progreso': round(porcentaje, 2),
            'falta_para_siguiente': falta
        }

    @classmethod
    def obtener_estadisticas_tramos(cls) -> dict:
        """
        Obtiene estadísticas generales del sistema de tramos

        Returns:
            Dict con estadísticas:
            {
                'clientes_por_tramo': {1: 100, 2: 50, ...},
                'total_clientes_con_tramo': int,
                'tramo_promedio': float,
                'clientes_en_hitos': {5: 20, 10: 10, ...}
            }
        """
        from collections import defaultdict

        clientes_por_tramo = defaultdict(int)
        clientes_en_hitos = defaultdict(int)

        # Obtener todos los clientes con historial de tramos
        clientes_con_historial = HistorialTramo.objects.values_list(
            'cliente_id', flat=True
        ).distinct()

        for cliente_id in clientes_con_historial:
            try:
                cliente = Cliente.objects.get(id=cliente_id)
                tramo = cls.obtener_tramo_actual(cliente)

                clientes_por_tramo[tramo] += 1

                if tramo in cls.HITOS_PREMIO:
                    clientes_en_hitos[tramo] += 1
            except Cliente.DoesNotExist:
                continue

        total_clientes = sum(clientes_por_tramo.values())
        tramo_promedio = (
            sum(tramo * count for tramo, count in clientes_por_tramo.items()) / total_clientes
            if total_clientes > 0 else 0
        )

        return {
            'clientes_por_tramo': dict(clientes_por_tramo),
            'total_clientes_con_tramo': total_clientes,
            'tramo_promedio': round(tramo_promedio, 2),
            'clientes_en_hitos': dict(clientes_en_hitos)
        }
