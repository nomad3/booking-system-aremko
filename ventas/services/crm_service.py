"""
Servicio CRM - Análisis RFM y métricas de clientes
Integra datos históricos (ServiceHistory) y datos actuales (VentaReserva)
"""
from django.db.models import Sum, Count, Max, Min, Avg, Q, F
from django.utils import timezone
from datetime import datetime, timedelta, date
from typing import Dict, List, Tuple, Optional
from ventas.models import Cliente, ServiceHistory, VentaReserva, ReservaServicio
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

# Fecha placeholder usada en migración histórica (debe excluirse de cálculos)
FECHA_PLACEHOLDER_HISTORICA = date(2021, 1, 1)


class CRMService:
    """Servicio para análisis y métricas CRM con integración de datos históricos y actuales"""

    @staticmethod
    def _combine_service_data(cliente: Cliente) -> Dict:
        """
        Combina datos de servicios históricos y actuales en una estructura unificada

        Args:
            cliente: Objeto Cliente

        Returns:
            Dict con servicios combinados y métricas agregadas
        """
        servicios_combinados = []
        total_historicos = 0

        # 1. DATOS HISTÓRICOS - ServiceHistory (2020-2024)
        # Excluir fecha placeholder (2021-01-01) usada en migración
        try:
            historicos = ServiceHistory.objects.filter(
                cliente=cliente
            ).exclude(
                service_date=FECHA_PLACEHOLDER_HISTORICA
            )
            total_historicos = historicos.count()
            for h in historicos:
                servicios_combinados.append({
                    'fecha': h.service_date,
                    'servicio': h.service_name,
                    'tipo': h.service_type,
                    'precio': float(h.price_paid),
                    'cantidad': h.quantity,
                    'numero_reserva': 'N/A',  # Datos históricos sin número de reserva
                    'fuente': 'histórico',
                    'id': f'hist_{h.id}'
                })
        except Exception as e:
            logger.warning(f"No se pudieron cargar datos históricos: {e}. Tabla crm_service_history puede no existir aún.")
            # Continuar sin datos históricos

        # 2. DATOS ACTUALES - VentaReserva → ReservaServicio (2024-hoy)
        reservas_servicio = ReservaServicio.objects.filter(
            venta_reserva__cliente=cliente,
            venta_reserva__estado_pago__in=['pagado', 'parcial']  # Solo servicios pagados
        ).select_related('servicio', 'venta_reserva')

        for rs in reservas_servicio:
            # Calcular precio del servicio
            precio_unitario = float(rs.servicio.precio_base) if rs.servicio.precio_base else 0
            cantidad = rs.cantidad_personas or 1
            precio_total = precio_unitario * cantidad

            # Fecha del servicio (priorizar fecha_agendamiento, sino fecha_reserva de la venta)
            # fecha_agendamiento ya es un DateField, no necesita .date()
            fecha_servicio = rs.fecha_agendamiento if rs.fecha_agendamiento else rs.venta_reserva.fecha_reserva.date()

            servicios_combinados.append({
                'fecha': fecha_servicio,
                'servicio': rs.servicio.nombre,
                'tipo': rs.servicio.categoria.nombre if rs.servicio.categoria else 'Sin categoría',
                'precio': precio_total,
                'cantidad': cantidad,
                'numero_reserva': rs.venta_reserva.id,  # ID de la VentaReserva
                'fuente': 'actual',
                'id': f'res_{rs.id}'
            })

        # Ordenar por fecha descendente (más reciente primero)
        # reverse=True: fecha más actual arriba, más antigua abajo
        servicios_combinados.sort(key=lambda x: x['fecha'], reverse=True)

        return {
            'servicios': servicios_combinados,
            'total_historicos': total_historicos,
            'total_actuales': reservas_servicio.count(),
            'total_combinados': len(servicios_combinados)
        }

    @staticmethod
    def get_customer_360(customer_id: int) -> Dict:
        """
        Vista 360° del cliente con TODOS sus datos (históricos + actuales)

        Returns:
            Dict con perfil completo del cliente
        """
        try:
            cliente = Cliente.objects.get(id=customer_id)

            # Combinar datos de ambas fuentes
            datos_combinados = CRMService._combine_service_data(cliente)
            servicios = datos_combinados['servicios']
            total_servicios = datos_combinados['total_combinados']

            # Análisis temporal
            if servicios:
                primer_servicio = servicios[-1]['fecha']  # Último elemento (más antiguo)
                ultimo_servicio = servicios[0]['fecha']   # Primer elemento (más reciente)
                dias_cliente = (datetime.now().date() - primer_servicio).days
            else:
                primer_servicio = None
                ultimo_servicio = None
                dias_cliente = 0

            # Análisis de gasto
            gasto_total = sum(s['precio'] for s in servicios)
            ticket_promedio = gasto_total / total_servicios if total_servicios > 0 else 0

            # Servicios por categoría (combinados)
            servicios_por_categoria = {}
            for s in servicios:
                tipo = s['tipo']
                if tipo not in servicios_por_categoria:
                    servicios_por_categoria[tipo] = {'cantidad': 0, 'gasto': 0}
                servicios_por_categoria[tipo]['cantidad'] += 1
                servicios_por_categoria[tipo]['gasto'] += s['precio']

            # Convertir a lista ordenada por cantidad
            categorias_lista = [
                {
                    'service_type': tipo,
                    'cantidad': data['cantidad'],
                    'gasto': data['gasto']
                }
                for tipo, data in servicios_por_categoria.items()
            ]
            categorias_lista.sort(key=lambda x: x['cantidad'], reverse=True)

            # Servicios recientes (últimos 6 meses)
            seis_meses_atras = datetime.now().date() - timedelta(days=180)
            servicios_recientes = len([s for s in servicios if s['fecha'] >= seis_meses_atras])

            # Calcular segmento RFM
            recency_days = (datetime.now().date() - ultimo_servicio).days if ultimo_servicio else 9999
            rfm_segment = CRMService._calculate_rfm_segment(
                recency_days=recency_days,
                frequency=total_servicios,
                monetary=gasto_total
            )

            return {
                'cliente': {
                    'id': cliente.id,
                    'nombre': cliente.nombre,
                    'email': cliente.email,
                    'telefono': cliente.telefono,
                    'pais': cliente.pais,
                    'ciudad': cliente.ciudad,
                },
                'metricas': {
                    'total_servicios': total_servicios,
                    'servicios_historicos': datos_combinados['total_historicos'],
                    'servicios_actuales': datos_combinados['total_actuales'],
                    'servicios_recientes': servicios_recientes,
                    'gasto_total': float(gasto_total),
                    'ticket_promedio': float(ticket_promedio),
                    'primer_servicio': primer_servicio,  # Pass date object for Django template date filter
                    'ultimo_servicio': ultimo_servicio,  # Pass date object for Django template date filter
                    'dias_como_cliente': dias_cliente,
                },
                'segmentacion': {
                    'rfm_segment': rfm_segment,
                    'is_vip': rfm_segment in ['VIP', 'Champions'],
                    'en_riesgo': rfm_segment in ['At Risk', 'Hibernating'],
                },
                'categorias_favoritas': categorias_lista[:3],
                'historial_reciente': [
                    {
                        'id': s['id'],
                        'servicio': s['servicio'],
                        'tipo': s['tipo'],
                        'fecha': s['fecha'],  # Pass date object directly for Django template date filter
                        'precio': s['precio'],
                        'cantidad': s['cantidad'],
                        'numero_reserva': s.get('numero_reserva', 'N/A'),  # Agregar número de reserva
                        'fuente': s['fuente']
                    }
                    for s in servicios  # Mostrar TODOS los servicios, sin límite
                ]
            }
        except Cliente.DoesNotExist:
            raise ValueError(f"Cliente {customer_id} no existe")

    @staticmethod
    def _calculate_rfm_segment(recency_days: int, frequency: int, monetary: float) -> str:
        """
        Calcula segmento RFM simplificado

        Returns:
            Nombre del segmento: VIP, Champions, Loyal, etc.
        """
        # Scoring simple 1-3 (3 = mejor)
        r_score = 3 if recency_days <= 90 else (2 if recency_days <= 180 else 1)
        f_score = 3 if frequency >= 10 else (2 if frequency >= 5 else 1)
        m_score = 3 if monetary >= 1000000 else (2 if monetary >= 500000 else 1)

        # Determinar segmento
        if r_score == 3 and f_score == 3 and m_score == 3:
            return "VIP"
        elif r_score >= 2 and f_score >= 2 and m_score >= 2:
            return "Champions"
        elif r_score >= 2 and f_score >= 2:
            return "Loyal"
        elif r_score == 3 and f_score == 1:
            return "New"
        elif r_score == 3:
            return "Promising"
        elif r_score == 1 and f_score >= 2:
            return "At Risk"
        elif r_score == 1 and f_score == 1 and m_score >= 2:
            return "Hibernating"
        elif r_score == 1:
            return "Lost"
        else:
            return "Occasional"

    @staticmethod
    def get_dashboard_stats() -> Dict:
        """
        Obtiene estadísticas generales para el dashboard CRM
        Combina datos históricos y actuales

        Returns:
            Dict con métricas generales
        """
        # Clientes totales
        total_clientes = Cliente.objects.count()

        # Clientes con historial (histórico o actual)
        clientes_con_hist = 0
        try:
            clientes_con_hist = ServiceHistory.objects.values('cliente').distinct().count()
        except Exception as e:
            logger.warning(f"No se pudieron contar clientes con historial: {e}")

        clientes_con_actuales = VentaReserva.objects.values('cliente').distinct().count()
        # Unión de ambos (aproximado)
        clientes_con_historial = max(clientes_con_hist, clientes_con_actuales)

        # Servicios este mes (combinados)
        inicio_mes = datetime.now().replace(day=1).date()

        # Históricos este mes
        servicios_mes_hist = 0
        ingresos_mes_hist = 0
        try:
            servicios_mes_hist = ServiceHistory.objects.filter(service_date__gte=inicio_mes).count()
            ingresos_mes_hist = ServiceHistory.objects.filter(
                service_date__gte=inicio_mes
            ).aggregate(total=Sum('price_paid'))['total'] or 0
        except Exception as e:
            logger.warning(f"No se pudieron contar servicios históricos del mes: {e}")

        # Actuales este mes
        # fecha_agendamiento es DateField, no necesita __date
        reservas_mes = ReservaServicio.objects.filter(
            Q(fecha_agendamiento__gte=inicio_mes) |
            Q(venta_reserva__fecha_reserva__date__gte=inicio_mes),
            venta_reserva__estado_pago__in=['pagado', 'parcial']
        ).select_related('servicio')

        servicios_mes_actual = reservas_mes.count()
        ingresos_mes_actual = sum(
            float(rs.servicio.precio_base or 0) * (rs.cantidad_personas or 1)
            for rs in reservas_mes
        )

        # Totales combinados
        servicios_mes = servicios_mes_hist + servicios_mes_actual
        ingresos_mes = float(ingresos_mes_hist) + ingresos_mes_actual

        # Top servicios (solo históricos por performance)
        top_servicios = []
        por_categoria = []
        try:
            top_servicios = ServiceHistory.objects.values('service_name').annotate(
                cantidad=Count('id')
            ).order_by('-cantidad')[:5]

            # Servicios por categoría (solo históricos por performance)
            por_categoria = ServiceHistory.objects.values('service_type').annotate(
                cantidad=Count('id'),
                ingresos=Sum('price_paid')
            ).order_by('-cantidad')
        except Exception as e:
            logger.warning(f"No se pudieron cargar estadísticas de históricos: {e}")

        return {
            'clientes': {
                'total': total_clientes,
                'con_historial': clientes_con_historial,
                'sin_historial': total_clientes - clientes_con_historial,
            },
            'mes_actual': {
                'servicios': servicios_mes,
                'servicios_historicos': servicios_mes_hist,
                'servicios_actuales': servicios_mes_actual,
                'ingresos': float(ingresos_mes),
            },
            'top_servicios': list(top_servicios),
            'por_categoria': list(por_categoria),
        }

    @staticmethod
    def buscar_clientes(query: str, limit: int = 20) -> List[Dict]:
        """
        Busca clientes por nombre o teléfono
        Incluye métricas de ambas fuentes (históricos + actuales)

        Args:
            query: Texto a buscar
            limit: Número máximo de resultados

        Returns:
            Lista de clientes encontrados con info básica
        """
        # Si el query parece un teléfono, normalizarlo primero
        normalized_phone = None
        if query and any(c.isdigit() for c in query):
            try:
                normalized_phone = Cliente.normalize_phone(query)
            except:
                pass

        # Buscar por nombre, email, o teléfono (original + normalizado)
        q_filter = Q(nombre__icontains=query) | Q(email__icontains=query)

        # Buscar por teléfono original
        q_filter |= Q(telefono__icontains=query)

        # Si se normalizó el teléfono, buscar también por el normalizado
        if normalized_phone and normalized_phone != query:
            q_filter |= Q(telefono__icontains=normalized_phone)

        clientes = Cliente.objects.filter(q_filter).distinct()[:limit]

        resultados = []
        for cliente in clientes:
            # Combinar datos de ambas fuentes
            datos = CRMService._combine_service_data(cliente)
            servicios = datos['servicios']

            # Último servicio (el más reciente de ambas fuentes)
            ultimo_servicio = servicios[0]['fecha'] if servicios else None

            resultados.append({
                'id': cliente.id,
                'nombre': cliente.nombre,
                'telefono': cliente.telefono,
                'email': cliente.email,
                'total_servicios': datos['total_combinados'],
                'ultimo_servicio': ultimo_servicio,  # Pass date object for Django template date filter
            })

        return resultados

    @staticmethod
    def get_clientes_for_propuestas(segment: Optional[str] = None, limit: int = 100) -> List[int]:
        """
        Obtiene lista de IDs de clientes candidatos para propuestas

        Args:
            segment: Segmento RFM específico (opcional)
            limit: Número máximo de clientes

        Returns:
            Lista de customer IDs
        """
        # Obtener clientes con historial (histórico o actual)
        clientes_hist = set()
        try:
            clientes_hist = set(ServiceHistory.objects.values_list('cliente_id', flat=True).distinct())
        except Exception as e:
            logger.warning(f"No se pudieron obtener clientes con historial: {e}")

        clientes_actual = set(VentaReserva.objects.values_list('cliente_id', flat=True).distinct())

        # Unión de ambos
        customer_ids = list(clientes_hist.union(clientes_actual))[:limit]

        return customer_ids
