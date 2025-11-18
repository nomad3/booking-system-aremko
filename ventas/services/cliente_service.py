# -*- coding: utf-8 -*-
"""
Servicio para gestión robusta de clientes
Incluye búsqueda inteligente por teléfono con múltiples variantes
"""

import logging
from django.db.models import Q
from ..models import Cliente
from .phone_service import PhoneService

logger = logging.getLogger(__name__)


class ClienteService:
    """
    Servicio para operaciones avanzadas de clientes
    """

    @staticmethod
    def buscar_cliente_por_telefono(telefono_input):
        """
        Búsqueda robusta de cliente por teléfono
        Intenta múltiples variantes para garantizar encontrar clientes
        con diferentes formatos almacenados

        Args:
            telefono_input (str): Teléfono ingresado por usuario

        Returns:
            tuple: (cliente: Cliente|None, normalized_phone: str|None)
        """
        if not telefono_input:
            logger.warning("Búsqueda de cliente sin teléfono")
            return None, None

        # Generar variantes de búsqueda
        variants = PhoneService.generate_search_variants(telefono_input)

        if not variants:
            logger.warning(f"No se pudieron generar variantes para: {telefono_input}")
            return None, None

        logger.info(f"Buscando cliente con variantes: {variants}")

        # Intentar búsqueda con cada variante
        for variant in variants:
            try:
                # Usar select_related para traer región y comuna de una vez
                cliente = Cliente.objects.select_related('region', 'comuna').get(
                    telefono=variant
                )
                logger.info(f"✅ Cliente encontrado con variante '{variant}': {cliente.nombre}")

                # Devolver cliente y teléfono normalizado
                normalized = PhoneService.normalize_phone(telefono_input)
                return cliente, normalized

            except Cliente.DoesNotExist:
                logger.debug(f"Cliente no encontrado con variante: {variant}")
                continue
            except Cliente.MultipleObjectsReturned:
                logger.warning(f"Múltiples clientes con teléfono {variant} - usando el primero")
                cliente = Cliente.objects.select_related('region', 'comuna').filter(
                    telefono=variant
                ).first()
                normalized = PhoneService.normalize_phone(telefono_input)
                return cliente, normalized

        # No se encontró con ninguna variante
        logger.info(f"ℹ️ Cliente no encontrado con teléfono: {telefono_input}")
        normalized = PhoneService.normalize_phone(telefono_input)
        return None, normalized

    @staticmethod
    def buscar_clientes_similares(telefono_input):
        """
        Busca clientes con teléfonos similares para debugging/administración

        Args:
            telefono_input (str): Teléfono a buscar

        Returns:
            list: Lista de clientes con teléfonos similares
        """
        if not telefono_input:
            return []

        variants = PhoneService.generate_search_variants(telefono_input)

        # Crear query OR para buscar cualquier variante
        query = Q()
        for variant in variants:
            query |= Q(telefono__icontains=variant.replace('+', ''))

        clientes_similares = Cliente.objects.filter(query).distinct()

        logger.info(f"Clientes similares encontrados para {telefono_input}: {clientes_similares.count()}")
        return list(clientes_similares)

    @staticmethod
    def obtener_datos_completos_cliente(cliente):
        """
        Obtiene datos completos del cliente incluyendo relaciones
        Formato optimizado para formularios

        Args:
            cliente (Cliente): Instancia de cliente

        Returns:
            dict: Datos completos del cliente
        """
        if not cliente:
            return {
                'encontrado': False,
                'cliente': None
            }

        # Si no tiene región/comuna en la instancia actual, hacer query fresh
        if not hasattr(cliente, 'region') or not hasattr(cliente, 'comuna'):
            cliente = Cliente.objects.select_related('region', 'comuna').get(pk=cliente.pk)

        return {
            'encontrado': True,
            'cliente': {
                'id': cliente.id,
                'nombre': cliente.nombre,
                'email': cliente.email or '',
                'telefono': cliente.telefono,
                'telefono_display': PhoneService.format_phone_for_display(cliente.telefono),
                'documento_identidad': cliente.documento_identidad or '',
                'region_id': cliente.region.id if cliente.region else None,
                'region_nombre': cliente.region.nombre if cliente.region else None,
                'comuna_id': cliente.comuna.id if cliente.comuna else None,
                'comuna_nombre': cliente.comuna.nombre if cliente.comuna else None,
                'pais': cliente.pais or '',
                'created_at': cliente.created_at.isoformat() if cliente.created_at else None,

                # Datos calculados
                'numero_visitas': cliente.numero_visitas(),
                'gasto_total': float(cliente.gasto_total()),

                # Estado de los datos
                'tiene_region_comuna': bool(cliente.region and cliente.comuna),
                'datos_completos': bool(
                    cliente.nombre and
                    cliente.telefono and
                    cliente.region and
                    cliente.comuna
                )
            }
        }

    @staticmethod
    def crear_o_actualizar_cliente(datos_cliente):
        """
        Crea o actualiza cliente con normalización automática

        Args:
            datos_cliente (dict): Datos del cliente

        Returns:
            tuple: (cliente: Cliente, created: bool, errors: list)
        """
        errors = []

        # Validar teléfono
        telefono = datos_cliente.get('telefono')
        if not telefono:
            errors.append("Teléfono requerido")
            return None, False, errors

        # Normalizar teléfono
        telefono_normalizado = PhoneService.normalize_phone(telefono)
        if not telefono_normalizado:
            errors.append("Formato de teléfono inválido")
            return None, False, errors

        try:
            # Buscar cliente existente
            cliente_existente, _ = ClienteService.buscar_cliente_por_telefono(telefono)

            if cliente_existente:
                # Actualizar cliente existente
                for campo, valor in datos_cliente.items():
                    if campo == 'telefono':
                        valor = telefono_normalizado
                    if hasattr(cliente_existente, campo) and valor is not None:
                        setattr(cliente_existente, campo, valor)

                cliente_existente.save()
                logger.info(f"Cliente actualizado: {cliente_existente.nombre} ({telefono_normalizado})")
                return cliente_existente, False, []

            else:
                # Crear nuevo cliente
                datos_cliente['telefono'] = telefono_normalizado
                cliente_nuevo = Cliente.objects.create(**datos_cliente)
                logger.info(f"Cliente creado: {cliente_nuevo.nombre} ({telefono_normalizado})")
                return cliente_nuevo, True, []

        except Exception as e:
            error_msg = f"Error al crear/actualizar cliente: {str(e)}"
            logger.error(error_msg, exc_info=True)
            errors.append(error_msg)
            return None, False, errors