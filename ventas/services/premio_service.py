"""
PremioService - Servicio para gestión de premios del sistema de fidelización
Maneja la lógica de asignación y gestión de premios a clientes
"""
from django.utils import timezone
from django.db import transaction
from ventas.models import Cliente, Premio, ClientePremio
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class PremioService:
    """Servicio para asignación y gestión de premios"""

    @classmethod
    @transaction.atomic
    def generar_premio_cliente_nuevo(cls, cliente: Cliente, gasto_total: Decimal) -> ClientePremio:
        """
        Genera premio para cliente nuevo (primera compra)

        Premio: 20% descuento tinas/cabañas, 10% masajes, 30 días

        Args:
            cliente: Objeto Cliente
            gasto_total: Gasto total al momento de generar el premio

        Returns:
            ClientePremio creado o None si no se pudo crear
        """
        try:
            # Buscar el premio de bienvenida en la base de datos
            premio = Premio.objects.filter(
                tipo='descuento_bienvenida',
                activo=True
            ).first()

            if not premio:
                logger.error("No existe premio de tipo 'descuento_bienvenida' activo")
                return None

            # Verificar que no tenga ya un premio de bienvenida
            existe = ClientePremio.objects.filter(
                cliente=cliente,
                premio__tipo='descuento_bienvenida'
            ).exists()

            if existe:
                logger.info(f"Cliente {cliente.id} ya tiene premio de bienvenida")
                return None

            # Crear el premio
            cliente_premio = ClientePremio.objects.create(
                cliente=cliente,
                premio=premio,
                estado='pendiente_aprobacion',
                tramo_al_ganar=1,  # Primera compra = Tramo 1
                gasto_total_al_ganar=gasto_total,
                fecha_expiracion=timezone.now() + timezone.timedelta(days=premio.dias_validez)
            )

            logger.info(f"Premio de bienvenida creado para cliente {cliente.id}")
            return cliente_premio

        except Exception as e:
            logger.error(f"Error generando premio de bienvenida para cliente {cliente.id}: {e}")
            return None

    @classmethod
    @transaction.atomic
    def generar_premio_por_hito(
        cls,
        cliente: Cliente,
        tramo_actual: int,
        tramo_anterior: int,
        gasto_total: Decimal
    ) -> ClientePremio:
        """
        Genera premio por alcanzar un hito (Tramo 5, 10, 15, 20, etc.)

        Premios por tramo:
        - Tramo 5: Vale $60K en tinas con masajes x2
        - Tramo 10: 1 noche gratis en cabaña (VIP)
        - Tramo 15+: Premios escalonados

        Args:
            cliente: Objeto Cliente
            tramo_actual: Tramo alcanzado
            tramo_anterior: Tramo anterior
            gasto_total: Gasto total al momento

        Returns:
            ClientePremio creado o None
        """
        try:
            # Determinar tipo de premio según el tramo
            tipo_premio = cls._determinar_tipo_premio_hito(tramo_actual)

            if not tipo_premio:
                logger.info(f"Tramo {tramo_actual} no genera premio automático")
                return None

            # Buscar el premio en la base de datos
            premio = Premio.objects.filter(
                tipo=tipo_premio,
                activo=True
            ).first()

            if not premio:
                logger.error(f"No existe premio de tipo '{tipo_premio}' activo")
                return None

            # Crear el premio
            cliente_premio = ClientePremio.objects.create(
                cliente=cliente,
                premio=premio,
                estado='pendiente_aprobacion',
                tramo_al_ganar=tramo_actual,
                tramo_anterior=tramo_anterior,
                gasto_total_al_ganar=gasto_total,
                fecha_expiracion=timezone.now() + timezone.timedelta(days=premio.dias_validez)
            )

            logger.info(
                f"Premio de hito creado: Cliente {cliente.id}, "
                f"Tramo {tramo_anterior} → {tramo_actual}, Premio: {premio.nombre}"
            )
            return cliente_premio

        except Exception as e:
            logger.error(
                f"Error generando premio de hito para cliente {cliente.id}, "
                f"tramo {tramo_actual}: {e}"
            )
            return None

    @classmethod
    def _determinar_tipo_premio_hito(cls, tramo: int) -> str:
        """
        Determina el tipo de premio según el tramo alcanzado

        Args:
            tramo: Número de tramo

        Returns:
            Tipo de premio ('tinas_gratis', 'noche_gratis', etc.) o None
        """
        if tramo == 5:
            return 'tinas_gratis'  # Vale $60K en tinas con masajes
        elif tramo == 10:
            return 'noche_gratis'  # 1 noche en cabaña (VIP)
        elif tramo == 15:
            return 'tinas_gratis'  # Vale premium
        elif tramo == 20:
            return 'noche_gratis'  # 1 noche elite
        else:
            return None

    @classmethod
    def aprobar_premio(cls, premio_id: int) -> bool:
        """
        Aprueba un premio pendiente

        Args:
            premio_id: ID del ClientePremio

        Returns:
            True si se aprobó, False en caso contrario
        """
        try:
            premio = ClientePremio.objects.get(id=premio_id)

            if premio.estado != 'pendiente_aprobacion':
                logger.warning(f"Premio {premio_id} no está pendiente de aprobación")
                return False

            premio.estado = 'aprobado'
            premio.fecha_aprobacion = timezone.now()
            premio.save()

            logger.info(f"Premio {premio_id} aprobado")
            return True

        except ClientePremio.DoesNotExist:
            logger.error(f"Premio {premio_id} no existe")
            return False
        except Exception as e:
            logger.error(f"Error aprobando premio {premio_id}: {e}")
            return False

    @classmethod
    def aprobar_premios_lote(cls, premio_ids: list) -> dict:
        """
        Aprueba múltiples premios en lote

        Args:
            premio_ids: Lista de IDs de ClientePremio

        Returns:
            Dict con resultado:
            {
                'aprobados': int,
                'errores': int,
                'detalles': []
            }
        """
        resultado = {
            'aprobados': 0,
            'errores': 0,
            'detalles': []
        }

        for premio_id in premio_ids:
            if cls.aprobar_premio(premio_id):
                resultado['aprobados'] += 1
                resultado['detalles'].append({'id': premio_id, 'estado': 'aprobado'})
            else:
                resultado['errores'] += 1
                resultado['detalles'].append({'id': premio_id, 'estado': 'error'})

        return resultado

    @classmethod
    def marcar_premio_enviado(cls, premio_id: int, asunto: str, cuerpo: str) -> bool:
        """
        Marca un premio como enviado

        Args:
            premio_id: ID del ClientePremio
            asunto: Asunto del email enviado
            cuerpo: Cuerpo del email enviado

        Returns:
            True si se marcó, False en caso contrario
        """
        try:
            premio = ClientePremio.objects.get(id=premio_id)

            if premio.estado != 'aprobado':
                logger.warning(f"Premio {premio_id} no está aprobado")
                return False

            premio.estado = 'enviado'
            premio.fecha_enviado = timezone.now()
            premio.asunto_email = asunto
            premio.cuerpo_email = cuerpo
            premio.save()

            logger.info(f"Premio {premio_id} marcado como enviado")
            return True

        except ClientePremio.DoesNotExist:
            logger.error(f"Premio {premio_id} no existe")
            return False
        except Exception as e:
            logger.error(f"Error marcando premio {premio_id} como enviado: {e}")
            return False

    @classmethod
    def usar_premio(cls, codigo_unico: str, venta=None) -> bool:
        """
        Marca un premio como usado

        Args:
            codigo_unico: Código único del premio
            venta: Venta donde se usó (opcional)

        Returns:
            True si se usó, False en caso contrario
        """
        try:
            premio = ClientePremio.objects.get(codigo_unico=codigo_unico)

            if premio.estado not in ['aprobado', 'enviado']:
                logger.warning(f"Premio {codigo_unico} no está aprobado o enviado")
                return False

            if not premio.esta_vigente():
                logger.warning(f"Premio {codigo_unico} no está vigente")
                return False

            premio.marcar_como_usado(venta)
            logger.info(f"Premio {codigo_unico} marcado como usado")
            return True

        except ClientePremio.DoesNotExist:
            logger.error(f"Premio con código {codigo_unico} no existe")
            return False
        except Exception as e:
            logger.error(f"Error usando premio {codigo_unico}: {e}")
            return False

    @classmethod
    def verificar_premio(cls, codigo_unico: str) -> dict:
        """
        Verifica el estado y validez de un premio

        Args:
            codigo_unico: Código único del premio

        Returns:
            Dict con información del premio:
            {
                'valido': bool,
                'estado': str,
                'premio': Premio,
                'cliente': Cliente,
                'fecha_expiracion': datetime,
                'vigente': bool
            }
        """
        try:
            premio = ClientePremio.objects.get(codigo_unico=codigo_unico)

            return {
                'valido': True,
                'estado': premio.estado,
                'premio': premio.premio,
                'cliente': premio.cliente,
                'fecha_expiracion': premio.fecha_expiracion,
                'vigente': premio.esta_vigente()
            }

        except ClientePremio.DoesNotExist:
            return {
                'valido': False,
                'estado': 'no_existe',
                'premio': None,
                'cliente': None,
                'fecha_expiracion': None,
                'vigente': False
            }

    @classmethod
    def obtener_premios_pendientes(cls, limit=100) -> list:
        """
        Obtiene lista de premios pendientes de aprobación

        Args:
            limit: Número máximo de premios a retornar

        Returns:
            Lista de ClientePremio pendientes
        """
        return ClientePremio.objects.filter(
            estado='pendiente_aprobacion'
        ).select_related('cliente', 'premio').order_by('fecha_ganado')[:limit]

    @classmethod
    def obtener_premios_aprobados(cls, limit=100) -> list:
        """
        Obtiene lista de premios aprobados listos para enviar

        Args:
            limit: Número máximo de premios a retornar

        Returns:
            Lista de ClientePremio aprobados
        """
        return ClientePremio.objects.filter(
            estado='aprobado'
        ).select_related('cliente', 'premio').order_by('fecha_aprobacion')[:limit]

    @classmethod
    def expirar_premios_vencidos(cls) -> int:
        """
        Marca como expirados todos los premios que pasaron su fecha de vigencia

        Returns:
            Número de premios expirados
        """
        premios_a_expirar = ClientePremio.objects.filter(
            estado__in=['aprobado', 'enviado'],
            fecha_expiracion__lt=timezone.now()
        )

        count = premios_a_expirar.update(estado='expirado')
        logger.info(f"{count} premios marcados como expirados")

        return count

    @classmethod
    def obtener_estadisticas_premios(cls) -> dict:
        """
        Obtiene estadísticas generales del sistema de premios

        Returns:
            Dict con estadísticas
        """
        from django.db.models import Count

        stats = ClientePremio.objects.values('estado').annotate(total=Count('id'))
        stats_dict = {item['estado']: item['total'] for item in stats}

        total = sum(stats_dict.values())

        return {
            'total_premios': total,
            'por_estado': stats_dict,
            'pendientes': stats_dict.get('pendiente_aprobacion', 0),
            'aprobados': stats_dict.get('aprobado', 0),
            'enviados': stats_dict.get('enviado', 0),
            'usados': stats_dict.get('usado', 0),
            'expirados': stats_dict.get('expirado', 0),
            'cancelados': stats_dict.get('cancelado', 0)
        }
