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

        # 3. Re-verificar disponibilidad de cada servicio
        servicios_info = []
        total = 0

        with transaction.atomic():
            for srv_data in servicios_data:
                try:
                    servicio = Servicio.objects.get(id=srv_data['servicio_id'])
                except Servicio.DoesNotExist:
                    return {
                        'success': False,
                        'error': 'service_not_found',
                        'mensaje': f'Servicio {srv_data["servicio_id"]} no existe'
                    }

                # Calcular precio
                personas = srv_data.get('cantidad_personas', 1)
                precio = float(servicio.precio_base) * personas
                total += precio

                servicios_info.append({
                    'servicio_id': servicio.id,
                    'nombre': servicio.nombre,
                    'fecha': srv_data['fecha'],
                    'hora': srv_data['hora'],
                    'cantidad_personas': personas,
                    'precio_unitario': float(servicio.precio_base),
                    'subtotal': precio
                })

            # 3b. Productos (tablas, jugos, etc.): suman al total, no tienen fecha/hora.
            from ventas.models import Producto
            productos_info = []
            for prod_data in productos_data:
                try:
                    producto = Producto.objects.get(id=prod_data['producto_id'])
                except Producto.DoesNotExist:
                    return {
                        'success': False,
                        'error': 'product_not_found',
                        'mensaje': f'Producto {prod_data.get("producto_id")} no existe'
                    }
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

            # 3c. Descuento de pack (MISMO motor que crear_reserva) para que el total de la
            # propuesta = el de la reserva final (banner y mensaje de Luna muestran el real).
            # Solo si los servicios NO traen ya una línea de "descuento": el Ritual/Refugio la
            # traen en el payload → NO se debe doble-descontar.
            descuento_pack = 0
            if not any('descuento' in (i['nombre'] or '').lower() for i in servicios_info):
                from ventas.services.pack_descuento_service import PackDescuentoService
                cart_pack = []
                for srv in servicios_data:
                    sobj = Servicio.objects.filter(id=srv['servicio_id']).first()
                    if sobj is None:
                        continue
                    per = srv.get('cantidad_personas', 1)
                    cart_pack.append({
                        'id': sobj.id, 'nombre': sobj.nombre, 'precio': float(sobj.precio_base),
                        'fecha': srv['fecha'], 'hora': srv['hora'], 'cantidad_personas': per,
                        'tipo_servicio': sobj.tipo_servicio,
                        'subtotal': float(sobj.precio_base) * per,
                    })
                try:
                    packs_ap = PackDescuentoService.detectar_packs_aplicables(cart_pack)
                    descuento_pack = int(sum(float(p.get('descuento') or 0) for p in packs_ap))
                except Exception:  # noqa: BLE001 — sin descuento si el motor falla
                    logger.exception('[Luna] no se pudo calcular el descuento de pack en preparar_reserva')
                    descuento_pack = 0
            total = total - descuento_pack

            # 4. Generar resumen legible para Deborah
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
    """Cancela una propuesta pendiente."""
    try:
        propuesta = PropuestaReserva.objects.get(propuesta_id=propuesta_id)
        if propuesta.estado == 'pendiente':
            propuesta.estado = 'cancelada'
            propuesta.save(update_fields=['estado'])
            logger.info(f'[Luna] Propuesta {propuesta_id[:8]} cancelada')
            return True
        return False
    except PropuestaReserva.DoesNotExist:
        return False
