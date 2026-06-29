"""Servicio de preparación de reservas para Luna (H-028).

Flujo:
1. Luna llama preparar_reserva(payload) con cliente + servicios
2. Validamos disponibilidad + datos del cliente
3. Guardamos PropuestaReserva con estado='pendiente'
4. Devolvemos {propuesta_id, resumen, total} para mostrar a Deborah
5. aremko-cli expone en READ /api/inbox/conversation/
6. Deborah aprueba → aremko-cli llama crear_reserva(propuesta_id)
"""

import logging
import uuid
from datetime import timedelta

from django.utils import timezone
from django.db import transaction

from whatsapp_agent.models import PropuestaReserva
from ventas.models import Servicio

logger = logging.getLogger(__name__)


class _PropuestaCalcError(Exception):
    """Error de cálculo de propuesta (servicio/producto inexistente). Lleva código + mensaje
    para que el caller devuelva el mismo shape de error que antes."""
    def __init__(self, error, mensaje):
        self.error = error
        self.mensaje = mensaje
        super().__init__(mensaje)


def recalcular_propuesta(servicios_data, productos_data):
    """FUENTE ÚNICA del cálculo de una propuesta. Dado servicios + productos (estructura del
    payload), LEE los precios del catálogo (no confía en precios del input), aplica el descuento
    de pack y arma líneas + total + resumen. La usan `preparar_reserva` (al crear) y
    `editar_propuesta` (al corregir) para que el total que ve/edita Deborah sea SIEMPRE idéntico
    al de la reserva final.

    Lanza `_PropuestaCalcError` si un servicio/producto no existe.
    Devuelve: (servicios_info, productos_info, descuento_pack, total_int, resumen_texto)
    """
    from ventas.models import Producto

    servicios_info = []
    total = 0
    for srv_data in servicios_data:
        try:
            servicio = Servicio.objects.get(id=srv_data['servicio_id'])
        except Servicio.DoesNotExist:
            raise _PropuestaCalcError('service_not_found', f'Servicio {srv_data.get("servicio_id")} no existe')
        personas = int(srv_data.get('cantidad_personas', 1) or 1)
        precio = float(servicio.precio_base) * personas
        total += precio
        servicios_info.append({
            'servicio_id': servicio.id,
            'nombre': servicio.nombre,
            'fecha': srv_data.get('fecha'),
            'hora': srv_data.get('hora'),
            'cantidad_personas': personas,
            'precio_unitario': float(servicio.precio_base),
            'subtotal': precio,
        })

    productos_info = []
    for prod_data in productos_data:
        try:
            producto = Producto.objects.get(id=prod_data['producto_id'])
        except Producto.DoesNotExist:
            raise _PropuestaCalcError('product_not_found', f'Producto {prod_data.get("producto_id")} no existe')
        cant = int(prod_data.get('cantidad', 1) or 1)
        sub_prod = float(producto.precio_base) * cant
        total += sub_prod
        productos_info.append({
            'producto_id': producto.id,
            'nombre': producto.nombre,
            'cantidad': cant,
            'precio_unitario': float(producto.precio_base),
            'subtotal': sub_prod,
        })

    # Descuento de pack (fuente única: PackDescuentoService.descuento_para_servicios). Solo si
    # los servicios NO traen ya una línea "descuento" (Ritual/Refugio la traen → no doble).
    descuento_pack = 0
    if not any('descuento' in (i['nombre'] or '').lower() for i in servicios_info):
        from ventas.services.pack_descuento_service import PackDescuentoService
        try:
            descuento_pack = PackDescuentoService.descuento_para_servicios(servicios_data)
        except Exception:  # noqa: BLE001 — sin descuento si el motor falla
            logger.exception('[Luna] no se pudo calcular el descuento de pack')
            descuento_pack = 0
    total = total - descuento_pack

    lineas_resumen = []
    for info in servicios_info:
        lineas_resumen.append(
            f"{info['cantidad_personas']}x {info['nombre']} "
            f"({info['fecha']} {info['hora']}) = ${int(info['subtotal']):,}"
        )
    for info in productos_info:
        lineas_resumen.append(
            f"{info['cantidad']}x {info['nombre']} = ${int(info['subtotal']):,}"
        )
    if descuento_pack:
        lineas_resumen.append(f"Descuento pack = -${descuento_pack:,}")
    resumen_texto = '\n'.join(lineas_resumen)

    return servicios_info, productos_info, descuento_pack, int(total), resumen_texto


def preparar_reserva(canal, external_id, payload, idempotency_key=None):
    """Valida, re-verifica disponibilidad y guarda propuesta de reserva (idempotente).

    Args:
        canal: 'whatsapp'
        external_id: teléfono normalizado (+56...)
        payload: {
            'cliente': {nombre, email, documento_identidad, region_id, comuna_id},
            'servicios': [{servicio_id, fecha, hora, cantidad_personas}, ...],
            'metodo_pago': 'pendiente'  (opcional)
        }
        idempotency_key: string opcional (si Luna reenvía, evita duplicados)

    Returns:
        {
            'success': True,
            'propuesta_id': 'uuid-string',
            'resumen_texto': '2 Tina Hidromasaje (20-06-2026) + 1 Masaje Relajación...',
            'total': 180000,
            'cliente': 'Juan Pérez',
            'servicios_count': 2
        }
        o error {success: False, error: 'code', mensaje: '...'}
    """
    try:
        cliente_data = payload.get('cliente', {})
        servicios_data = payload.get('servicios', [])
        productos_data = payload.get('productos', [])  # tablas, jugos, etc. (opcional)

        # Si tiene idempotency_key, buscar propuesta existente
        if idempotency_key:
            try:
                propuesta = PropuestaReserva.objects.get(idempotency_key=idempotency_key)
                if propuesta.esta_vigente():
                    logger.info(f'[Luna] Propuesta duplicada (idempotent): {idempotency_key[:16]}')
                    return {
                        'success': True,
                        'propuesta_id': propuesta.propuesta_id,
                        'resumen_texto': propuesta.resumen_texto,
                        'total': int(propuesta.total),
                        'duplicada': True
                    }
            except PropuestaReserva.DoesNotExist:
                pass

        # 1. Validar cliente_data obligatorio
        nombre = cliente_data.get('nombre', '').strip()
        email = cliente_data.get('email', '').strip()
        rut = cliente_data.get('documento_identidad', '').strip()

        if not nombre or len(nombre) < 3:
            return {
                'success': False,
                'error': 'validation_error',
                'mensaje': 'Nombre requerido (mín 3 caracteres)'
            }
        if not email or '@' not in email:
            return {
                'success': False,
                'error': 'validation_error',
                'mensaje': 'Email válido requerido'
            }
        if not rut:
            return {
                'success': False,
                'error': 'validation_error',
                'mensaje': 'RUT requerido para cliente nuevo'
            }

        # 2. Validar servicios_data
        if not servicios_data:
            return {
                'success': False,
                'error': 'validation_error',
                'mensaje': 'Debe incluir al menos un servicio'
            }

        # 3. Calcular líneas + descuento + total + resumen (FUENTE ÚNICA recalcular_propuesta,
        # compartida con editar_propuesta para que el total de la propuesta == el de la reserva).
        with transaction.atomic():
            try:
                servicios_info, productos_info, descuento_pack, total, resumen_texto = \
                    recalcular_propuesta(servicios_data, productos_data)
            except _PropuestaCalcError as e:
                return {'success': False, 'error': e.error, 'mensaje': e.mensaje}

            # 5. Guardar PropuestaReserva
            propuesta_id = str(uuid.uuid4())
            propuesta = PropuestaReserva.objects.create(
                propuesta_id=propuesta_id,
                idempotency_key=idempotency_key or '',
                canal=canal,
                external_id=external_id,
                payload=payload,  # Guarda el payload completo para crear_reserva()
                cliente_data=cliente_data,  # H-028 FIX: llenar campo cliente_data (NOT NULL de 0009)
                servicios=servicios_data,  # H-028 FIX: llenar campo servicios (NOT NULL de 0009)
                total=int(total),
                resumen_texto=resumen_texto,
                estado='pendiente',
                # TTL de 24h: Deborah revisa y aprueba más tarde (puede pasar >1h desde
                # que Luna propone). La propuesta NO bloquea cupo (la disponibilidad cuenta
                # ReservaServicio, no propuestas) y crear_reserva RE-VALIDA disponibilidad al
                # aprobar, así que extender el TTL es seguro: no hay doble-booking.
                expires_at=timezone.now() + timedelta(hours=24)
            )

            logger.info(
                f'[Luna] Propuesta {propuesta_id[:8]} preparada para {external_id}: '
                f'{len(servicios_info)} servicios, ${int(total):,}'
            )

            return {
                'success': True,
                'propuesta_id': propuesta_id,
                'resumen_texto': resumen_texto,
                'total': int(total),
                'cliente': nombre,
                'servicios_count': len(servicios_info)
            }

    except Exception as e:
        logger.exception(f'Error en preparar_reserva: {str(e)}')
        return {
            'success': False,
            'error': 'internal_error',
            'mensaje': f'Error al preparar reserva: {str(e)[:100]}'
        }


def agregar_producto_a_propuesta(canal, external_id, producto_id, cantidad=1):
    """Si YA existe una propuesta vigente para esta conversación (Ritual/Refugio/pack ya
    cotizado), suma el producto a ESA propuesta (payload + total + resumen) en vez de abrir
    un carrito nuevo separado (H-040 #1: evita propuestas desincronizadas/pisadas).

    Devuelve dict con actualizo_propuesta=True si actualizó, o None si NO hay propuesta vigente
    (en ese caso el caller debe usar el carrito normal).
    """
    from ventas.models import Producto
    propuesta = (PropuestaReserva.objects
                 .filter(canal=canal, external_id=external_id, estado='pendiente')
                 .order_by('-created_at').first())
    if propuesta is None or not propuesta.esta_vigente():
        return None  # no hay propuesta → el caller usa el carrito normal

    try:
        producto = Producto.objects.get(id=producto_id)
    except Producto.DoesNotExist:
        return {'success': False, 'error': 'producto_no_existe',
                'mensaje': f'Producto {producto_id} no existe'}

    cant = int(cantidad or 1)
    payload = dict(propuesta.payload or {})
    productos = list(payload.get('productos') or [])
    precio = int(producto.precio_base)
    # OVERWRITE (no incrementar) si el producto ya está: evita inflar la cotización por
    # re-adds espurios del LLM (consistente con el dedup del carrito). Para más unidades,
    # el LLM debe pasar `cantidad`.
    prev = 0
    for p in productos:
        if p.get('producto_id') == producto.id:
            prev = int(p.get('cantidad') or 1)
            p['cantidad'] = cant
            break
    else:
        productos.append({'producto_id': producto.id, 'cantidad': cant})
    payload['productos'] = productos
    propuesta.payload = payload

    # Ajustar el total por el CAMBIO de cantidad (no volver a sumar lo que ya estaba).
    propuesta.total = int(propuesta.total or 0) + precio * (cant - prev)
    if not prev:  # línea de resumen solo la primera vez (no duplicar)
        linea = f"{cant}x {producto.nombre} = ${precio * cant:,}"
        propuesta.resumen_texto = ((propuesta.resumen_texto or '').rstrip() + '\n' + linea).strip()
    propuesta.save(update_fields=['payload', 'total', 'resumen_texto'])

    logger.info('[Luna] Producto %s x%s sumado a propuesta vigente %s (nuevo total $%s)',
                producto.nombre, cant, propuesta.propuesta_id[:8], propuesta.total)
    return {
        'success': True,
        'actualizo_propuesta': True,
        'propuesta_id': propuesta.propuesta_id,
        'total': int(propuesta.total),
        'mensaje': (f'¡Listo! Sumé {producto.nombre} a tu cotización. '
                    f'Nuevo total ${int(propuesta.total):,}. Te la enviamos para que la revises. 🌿'),
    }


def obtener_propuesta(propuesta_id):
    """Obtiene propuesta vigente por ID.

    Returns: PropuestaReserva o None
    """
    try:
        propuesta = PropuestaReserva.objects.get(propuesta_id=propuesta_id)
        if propuesta.esta_vigente():
            return propuesta
        # Si expiró, marcar como expirada
        if propuesta.estado == 'pendiente' and not propuesta.esta_vigente():
            propuesta.estado = 'expirada'
            propuesta.save(update_fields=['estado'])
        return None
    except PropuestaReserva.DoesNotExist:
        return None


def cancelar_propuesta(propuesta_id):
    """Descarta/cierra una propuesta pendiente (botón 'Cerrar' del cajón). 'descartada' es el
    valor válido de ESTADO_CHOICES (antes seteaba 'cancelada', que no existe en el modelo)."""
    try:
        propuesta = PropuestaReserva.objects.get(propuesta_id=propuesta_id)
        if propuesta.estado == 'pendiente':
            propuesta.estado = 'descartada'
            propuesta.save(update_fields=['estado'])
            logger.info(f'[Luna] Propuesta {propuesta_id[:8]} descartada')
            return True
        return False
    except PropuestaReserva.DoesNotExist:
        return False


def editar_propuesta(propuesta_id, servicios_data, productos_data=None):
    """Corrige una propuesta PENDIENTE antes de enviarla (Deborah ajusta cantidades / quita
    líneas en el cajón). Reemplaza COMPLETAMENTE los servicios + productos del payload con las
    listas recibidas, RE-LEE los precios del catálogo y recalcula total + resumen con la misma
    lógica que preparar_reserva (recalcular_propuesta). Solo propuestas 'pendiente' y vigentes.

    El payload es la fuente de verdad: lo lee el cajón (líneas) y crear_reserva (la VentaReserva),
    así que al editarlo, la corrección llega hasta la reserva final.

    Args:
        propuesta_id: UUID de la propuesta
        servicios_data: lista COMPLETA final [{servicio_id, fecha, hora, cantidad_personas}, ...]
        productos_data: lista COMPLETA final [{producto_id, cantidad}, ...] (opcional)

    Returns: dict {success, propuesta_id, resumen_texto, total, ...} o {success: False, error, mensaje}
    """
    productos_data = productos_data or []
    try:
        propuesta = PropuestaReserva.objects.get(propuesta_id=propuesta_id)
    except PropuestaReserva.DoesNotExist:
        return {'success': False, 'error': 'propuesta_not_found', 'mensaje': 'Propuesta no existe'}

    if propuesta.estado != 'pendiente':
        return {'success': False, 'error': 'no_editable',
                'mensaje': f'La propuesta está {propuesta.get_estado_display()}; solo se editan las pendientes'}
    if not propuesta.esta_vigente():
        propuesta.estado = 'expirada'
        propuesta.save(update_fields=['estado'])
        return {'success': False, 'error': 'expirada', 'mensaje': 'La propuesta expiró'}

    # No permitir vaciar la reserva (debe quedar al menos un servicio).
    if not servicios_data:
        return {'success': False, 'error': 'validation_error', 'mensaje': 'Debe quedar al menos un servicio'}

    try:
        with transaction.atomic():
            servicios_info, productos_info, descuento_pack, total, resumen_texto = \
                recalcular_propuesta(servicios_data, productos_data)

            # Actualizar el payload (fuente de verdad) + campos espejo/display.
            payload = dict(propuesta.payload or {})
            payload['servicios'] = servicios_data
            payload['productos'] = productos_data
            propuesta.payload = payload
            propuesta.servicios = servicios_data  # campo NOT NULL espejo de payload['servicios']
            propuesta.total = total
            propuesta.resumen_texto = resumen_texto
            propuesta.save(update_fields=['payload', 'servicios', 'total', 'resumen_texto'])
    except _PropuestaCalcError as e:
        return {'success': False, 'error': e.error, 'mensaje': e.mensaje}

    logger.info(
        f'[Luna] Propuesta {propuesta_id[:8]} EDITADA por Deborah: '
        f'{len(servicios_info)} servicios + {len(productos_info)} productos → total ${total:,}'
    )
    return {
        'success': True,
        'propuesta_id': propuesta_id,
        'resumen_texto': resumen_texto,
        'total': total,
        'servicios_count': len(servicios_info),
        'productos_count': len(productos_info),
    }
