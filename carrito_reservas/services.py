"""
CarritoService — Lógica de carrito para H-029 FASE 2.

Maneja agregar/quitar items, recalcular totales con descuentos dinámicos.
"""

import logging
from decimal import Decimal
from datetime import datetime

from django.utils import timezone
from ventas.models import Servicio, Producto
from ventas.services.pack_descuento_service import PackDescuentoService
from .models import CarritoReserva

logger = logging.getLogger(__name__)


class CarritoService:
    """Servicio de carrito de reservas."""

    @staticmethod
    def obtener_o_crear(canal, external_id):
        """Obtiene o crea un carrito para una conversación."""
        return CarritoReserva.obtener_o_crear(canal, external_id)

    @staticmethod
    def agregar_servicio(canal, external_id, servicio_id, fecha, hora, cantidad_personas):
        """Agrega un servicio al carrito y recalcula totales.

        Args:
            canal: 'whatsapp', 'instagram', 'messenger'
            external_id: phone, IGSID, o PSID
            servicio_id: ID del servicio
            fecha: 'YYYY-MM-DD'
            hora: 'HH:MM'
            cantidad_personas: int

        Returns:
            {'success': bool, 'carrito': CarritoReserva|None, 'error': str|None, 'mensaje': str}
        """
        try:
            # Obtener o crear carrito
            carrito = CarritoReserva.obtener_o_crear(canal, external_id)

            # Validar que el servicio existe
            try:
                servicio = Servicio.objects.get(id=servicio_id)
            except Servicio.DoesNotExist:
                return {
                    'success': False,
                    'error': 'servicio_no_existe',
                    'mensaje': f'Servicio {servicio_id} no existe'
                }

            # Validar que está publicado y activo
            if not servicio.publicado_web or not servicio.activo:
                return {
                    'success': False,
                    'error': 'servicio_no_disponible',
                    'mensaje': f'{servicio.nombre} no está disponible'
                }

            precio_unitario = float(servicio.precio_base)
            subtotal = precio_unitario * cantidad_personas

            # DEDUP EN CÓDIGO: un mismo servicio en el mismo (fecha, hora) es UNA línea.
            # El LLM a veces repite agregar_servicio (la regla anti-duplicado del prompt es
            # probabilística → así se infló a $500k con tinas/masajes repetidos). Acá se fuerza:
            # si ya existe esa combinación, se ACTUALIZA la cantidad/subtotal en vez de duplicar.
            existente = next(
                (it for it in carrito.items
                 if it.get('tipo') == 'servicio'
                 and it.get('servicio_id') == servicio.id
                 and it.get('fecha') == fecha
                 and it.get('hora') == hora),
                None,
            )
            if existente is not None:
                existente['cantidad_personas'] = cantidad_personas
                existente['precio_unitario'] = precio_unitario
                existente['subtotal'] = subtotal
                carrito.save(update_fields=['items', 'updated_at'])
                CarritoService._recalcular_totales(carrito)
                logger.info(
                    f'[Carrito] Servicio {servicio.nombre} ya estaba ({fecha} {hora}); '
                    f'actualizado (NO duplicado) en {canal}:{external_id} (total: ${carrito.total})'
                )
                return {
                    'success': True,
                    'carrito': carrito,
                    'error': None,
                    'mensaje': f'✅ {servicio.nombre} actualizado en el carrito'
                }

            # Crear item (no existía esa combinación servicio+fecha+hora)
            item = {
                'tipo': 'servicio',
                'servicio_id': servicio.id,
                'nombre': servicio.nombre,
                'fecha': fecha,
                'hora': hora,
                'cantidad_personas': cantidad_personas,
                'precio_unitario': precio_unitario,
                'subtotal': subtotal,
            }

            # Agregar al carrito
            carrito.items.append(item)
            carrito.save(update_fields=['items', 'updated_at'])

            # Recalcular totales
            CarritoService._recalcular_totales(carrito)

            logger.info(
                f'[Carrito] Agregado servicio {servicio.nombre} a '
                f'{canal}:{external_id} (total: ${carrito.total})'
            )

            return {
                'success': True,
                'carrito': carrito,
                'error': None,
                'mensaje': f'✅ {servicio.nombre} agregado al carrito'
            }

        except Exception as exc:
            logger.exception(f'Error agregando servicio: {exc}')
            return {
                'success': False,
                'error': 'error_interno',
                'mensaje': f'Error: {str(exc)[:100]}'
            }

    @staticmethod
    def agregar_producto(canal, external_id, producto_id, cantidad):
        """Agrega un producto al carrito y recalcula totales.

        Args:
            canal: 'whatsapp', 'instagram', 'messenger'
            external_id: phone, IGSID, o PSID
            producto_id: ID del producto
            cantidad: int

        Returns:
            {'success': bool, 'carrito': CarritoReserva|None, 'error': str|None, 'mensaje': str}
        """
        try:
            # Obtener o crear carrito
            carrito = CarritoReserva.obtener_o_crear(canal, external_id)

            # Validar que el producto existe
            try:
                producto = Producto.objects.get(id=producto_id)
            except Producto.DoesNotExist:
                return {
                    'success': False,
                    'error': 'producto_no_existe',
                    'mensaje': f'Producto {producto_id} no existe'
                }

            # Validar que está publicado (Producto NO tiene campo `activo`; la baja se hace
            # con publicado_web / cantidad_disponible).
            if not producto.publicado_web:
                return {
                    'success': False,
                    'error': 'producto_no_disponible',
                    'mensaje': f'{producto.nombre} no está disponible'
                }

            # Stock real del producto = cantidad_disponible (no existe `stock_actual`).
            if producto.cantidad_disponible < cantidad:
                return {
                    'success': False,
                    'error': 'stock_insuficiente',
                    'mensaje': f'Solo hay {producto.cantidad_disponible} en stock'
                }

            # Crear item (el precio del producto es `precio_base`; no hay precio_venta/precio_costo).
            item = {
                'tipo': 'producto',
                'producto_id': producto.id,
                'nombre': producto.nombre,
                'cantidad': cantidad,
                'precio_unitario': float(producto.precio_base),
                'subtotal': float(producto.precio_base) * cantidad,
            }

            # Agregar al carrito
            carrito.items.append(item)
            carrito.save(update_fields=['items', 'updated_at'])

            # Recalcular totales
            CarritoService._recalcular_totales(carrito)

            logger.info(
                f'[Carrito] Agregado producto {producto.nombre} x{cantidad} a '
                f'{canal}:{external_id} (total: ${carrito.total})'
            )

            return {
                'success': True,
                'carrito': carrito,
                'error': None,
                'mensaje': f'✅ {producto.nombre} x{cantidad} agregado al carrito'
            }

        except Exception as exc:
            logger.exception(f'Error agregando producto: {exc}')
            return {
                'success': False,
                'error': 'error_interno',
                'mensaje': f'Error: {str(exc)[:100]}'
            }

    @staticmethod
    def quitar_item(canal, external_id, indice):
        """Quita un item del carrito por índice.

        Args:
            canal: 'whatsapp', 'instagram', 'messenger'
            external_id: phone, IGSID, o PSID
            indice: índice en la lista items (0-based)

        Returns:
            {'success': bool, 'carrito': CarritoReserva|None, 'error': str|None}
        """
        try:
            carrito = CarritoReserva.obtener_o_crear(canal, external_id)

            if indice < 0 or indice >= len(carrito.items):
                return {
                    'success': False,
                    'error': 'indice_invalido',
                    'mensaje': f'Item {indice} no existe'
                }

            item_removido = carrito.items.pop(indice)
            carrito.save(update_fields=['items', 'updated_at'])

            # Recalcular totales
            CarritoService._recalcular_totales(carrito)

            logger.info(
                f'[Carrito] Removido {item_removido.get("nombre")} de '
                f'{canal}:{external_id} (total: ${carrito.total})'
            )

            return {
                'success': True,
                'carrito': carrito,
                'error': None,
                'mensaje': f'✅ {item_removido.get("nombre")} removido del carrito'
            }

        except Exception as exc:
            logger.exception(f'Error removiendo item: {exc}')
            return {
                'success': False,
                'error': 'error_interno',
                'mensaje': f'Error: {str(exc)[:100]}'
            }

    @staticmethod
    def _recalcular_totales(carrito):
        """Recalcula totales y descuentos del carrito.

        Usa PackDescuentoService para detectar y calcular descuentos dinámicamente.
        """
        if not carrito.items:
            carrito.subtotal_servicios = Decimal('0')
            carrito.subtotal_productos = Decimal('0')
            carrito.descuento_combo = Decimal('0')
            carrito.packs_aplicados = []
            carrito.total = Decimal('0')
            carrito.save(update_fields=[
                'subtotal_servicios', 'subtotal_productos',
                'descuento_combo', 'packs_aplicados', 'total', 'updated_at'
            ])
            return

        # Separar servicios y productos
        servicios_items = [item for item in carrito.items if item.get('tipo') == 'servicio']
        productos_items = [item for item in carrito.items if item.get('tipo') == 'producto']

        # Calcular subtotales
        subtotal_servicios = sum(Decimal(str(item['subtotal'])) for item in servicios_items)
        subtotal_productos = sum(Decimal(str(item['subtotal'])) for item in productos_items)

        # Detectar packs aplicables (solo servicios)
        descuento_combo = Decimal('0')
        packs_aplicados = []

        if servicios_items:
            try:
                # Usar PackDescuentoService para detectar packs. construir_cart NORMALIZA los
                # ítems como los espera el motor: clave 'id' (los del carrito traen 'servicio_id')
                # y masajes divididos por persona. Sin esto, el match de servicios específicos
                # fallaba (buscaba 'id') y el descuento del pack no se aplicaba en el checkout.
                packs = PackDescuentoService.detectar_packs_aplicables(
                    PackDescuentoService.construir_cart(servicios_items))
                if packs:
                    for pack in packs:
                        descuento_combo += Decimal(str(pack.get('descuento', 0)))
                        packs_aplicados.append({
                            'pack_id': pack.get('id'),
                            'nombre': pack.get('nombre'),
                            'descuento': pack.get('descuento')
                        })
            except Exception as exc:
                logger.warning(f'Error detectando packs: {exc}')

        # Calcular total
        total = subtotal_servicios + subtotal_productos - descuento_combo

        # Guardar
        carrito.subtotal_servicios = subtotal_servicios
        carrito.subtotal_productos = subtotal_productos
        carrito.descuento_combo = descuento_combo
        carrito.packs_aplicados = packs_aplicados
        carrito.total = total
        carrito.save(update_fields=[
            'subtotal_servicios', 'subtotal_productos',
            'descuento_combo', 'packs_aplicados', 'total', 'updated_at'
        ])

    @staticmethod
    def ver_carrito(canal, external_id):
        """Obtiene el resumen del carrito para mostrar a Luna.

        Returns:
            {
                'items_count': int,
                'servicios_count': int,
                'productos_count': int,
                'subtotal_servicios': float,
                'subtotal_productos': float,
                'descuento_combo': float,
                'packs_aplicados': [...],
                'total': float,
                'items': [...]
            }
        """
        try:
            carrito = CarritoReserva.obtener_o_crear(canal, external_id)
            return {
                'items_count': carrito.contar_items(),
                'servicios_count': carrito.contar_servicios(),
                'productos_count': carrito.contar_productos(),
                'subtotal_servicios': float(carrito.subtotal_servicios),
                'subtotal_productos': float(carrito.subtotal_productos),
                'descuento_combo': float(carrito.descuento_combo),
                'packs_aplicados': carrito.packs_aplicados,
                'total': float(carrito.total),
                'items': carrito.items,
            }
        except Exception as exc:
            logger.exception(f'Error obteniendo carrito: {exc}')
            return {'error': f'Error: {str(exc)[:100]}'}

    @staticmethod
    def vaciar_carrito(canal, external_id):
        """Vacía el carrito (elimina todos los items)."""
        try:
            carrito = CarritoReserva.obtener_o_crear(canal, external_id)
            carrito.items = []
            CarritoService._recalcular_totales(carrito)
            logger.info(f'[Carrito] Vaciado {canal}:{external_id}')
            return {'success': True, 'carrito': carrito}
        except Exception as exc:
            logger.exception(f'Error vaciando carrito: {exc}')
            return {'success': False, 'error': str(exc)[:100]}

    @staticmethod
    def checkout_carrito(canal, external_id):
        """Inicia el checkout del carrito (H-029 FASE 2).

        Marca el carrito como 'checkout' para que Luna sepa que debe:
        1. Verificar datos del cliente (FASE 1)
        2. Pedir lo que falta (nombre/email/RUT/región)
        3. Mostrar resumen final
        4. Confirmar
        5. Llamar preparar_reserva con TODOS los items del carrito

        Returns:
            {
                'success': bool,
                'resumen': {
                    'items_count': int,
                    'servicios': [...],
                    'productos': [...],
                    'subtotal_servicios': float,
                    'subtotal_productos': float,
                    'descuentos': float,
                    'total': float,
                    'packs_aplicados': [...]
                }
            }
        """
        try:
            carrito = CarritoReserva.obtener_o_crear(canal, external_id)

            if not carrito.items:
                return {
                    'success': False,
                    'error': 'carrito_vacio',
                    'mensaje': 'El carrito está vacío. Agrega servicios o productos primero.'
                }

            # Marcar como checkout
            carrito.marcar_como_checkout()

            # Preparar resumen para Luna
            servicios = [item for item in carrito.items if item.get('tipo') == 'servicio']
            productos = [item for item in carrito.items if item.get('tipo') == 'producto']

            resumen = {
                'items_count': carrito.contar_items(),
                'servicios': servicios,
                'productos': productos,
                'subtotal_servicios': float(carrito.subtotal_servicios),
                'subtotal_productos': float(carrito.subtotal_productos),
                'descuentos': float(carrito.descuento_combo),
                'total': float(carrito.total),
                'packs_aplicados': carrito.packs_aplicados,
            }

            logger.info(f'[Carrito] Checkout iniciado {canal}:{external_id} (${carrito.total})')

            return {
                'success': True,
                'resumen': resumen
            }

        except Exception as exc:
            logger.exception(f'Error en checkout: {exc}')
            return {
                'success': False,
                'error': 'error_interno',
                'mensaje': f'Error: {str(exc)[:100]}'
            }

    @staticmethod
    def construir_payload_reserva_desde_carrito(carrito, cliente_data):
        """Construye el payload para `preparar_reserva` con TODOS los items del carrito.

        Usado cuando el cliente completa FASE 1 (recolección de datos) en checkout.

        Args:
            carrito: CarritoReserva
            cliente_data: {nombre, email, documento_identidad, region_id, ...}

        Returns:
            {
                'cliente': {...},
                'servicios': [{servicio_id, fecha, hora, cantidad_personas}, ...],
                'productos': [opcional, para futuras fases],
                'metodo_pago': 'pendiente'
            }
        """
        servicios = []
        productos = []
        for item in carrito.items:
            if item.get('tipo') == 'servicio':
                servicios.append({
                    'servicio_id': item.get('servicio_id'),
                    'fecha': item.get('fecha'),
                    'hora': item.get('hora'),
                    'cantidad_personas': item.get('cantidad_personas', 1),
                })
            elif item.get('tipo') == 'producto':
                productos.append({
                    'producto_id': item.get('producto_id'),
                    'cantidad': item.get('cantidad', 1),
                })

        payload = {
            'cliente': cliente_data,
            'servicios': servicios,
            'productos': productos,   # tablas, jugos, etc. (se descontaba inventario al crear)
            'metodo_pago': 'pendiente',
        }

        return payload
