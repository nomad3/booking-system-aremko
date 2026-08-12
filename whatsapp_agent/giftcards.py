# -*- coding: utf-8 -*-
"""Venta de gift cards por Luna (pedido de Jorge 2026-08-12).

El caso que se caía: «quiero regalar dos masajes para mis papás» — Luna no
tenía camino y la venta moría ahí. Este módulo le da los dos pasos:

1. catalogo_giftcards(): las experiencias regalables, LEÍDAS DE LA BD en cada
   conversación. Jorge agrega «Masaje para dos» en el admin y Luna la ofrece
   en el mensaje siguiente, sin deploy.
2. preparar_giftcard(): arma la PropuestaReserva con payload['giftcards'] —
   el MISMO cajón que las reservas: Deborah aprueba, se crea la venta con sus
   GiftCards y sale el Pase con los datos de transferencia. Al registrarse el
   pago, la señal existente envía las cartas por email sola.

Lo que a propósito NO hay acá: disponibilidad. Una gift card no ocupa slot ni
tiene fecha — vale 365 días y el destinatario agenda después. Ese es además el
argumento de venta que Luna debe decir.
"""
import logging
import uuid
from datetime import timedelta

from django.utils import timezone

from whatsapp_agent.models import PropuestaReserva

logger = logging.getLogger(__name__)

# Tope defensivo por venta: Luna es un LLM y un «regalo para los 40 invitados»
# merece pasar por un humano, no crearse solo.
MAX_GIFTCARDS_POR_VENTA = 10
MONTO_MINIMO_VALOR = 20000       # tarjeta de valor libre: piso razonable
MONTO_MAXIMO_VALOR = 1000000


def catalogo_giftcards():
    """Experiencias regalables activas, compacto para el LLM.

    Devuelve {'success': True, 'experiencias': [...], 'nota': str}.
    """
    from ventas.models import GiftCardExperiencia

    experiencias = []
    for e in (GiftCardExperiencia.objects.filter(activo=True)
              .order_by('categoria', 'orden', 'nombre')):
        experiencias.append({
            'id': e.id_experiencia,
            'nombre': e.nombre,
            'categoria': e.get_categoria_display(),
            'precio': int(e.monto_fijo) if e.monto_fijo else None,
            'montos_sugeridos': [int(m) for m in (e.montos_sugeridos or [])],
            'descripcion': (e.descripcion or '')[:120],
        })
    return {
        'success': True,
        'experiencias': experiencias,
        'nota': ('Una gift card no lleva fecha: vale 1 año y quien la recibe '
                 'agenda cuando quiera. Ofrecé UNA opción a la vez.'),
    }


def preparar_giftcard(canal, external_id, cliente_data, giftcards_data,
                      idempotency_key=None):
    """Crea la propuesta de venta de gift cards (mismo cajón que las reservas).

    giftcards_data: [{experiencia_id, monto (solo si la experiencia es de
    valor libre), cantidad, destinatario_nombre, mensaje}]

    Cada UNIDAD es una GiftCard propia (dos masajes = dos cartas, cada una
    canjeable por separado). El precio SIEMPRE se lee del catálogo — el LLM
    no fija precios (defense in depth: lo mismo que recalcular_propuesta).
    """
    from ventas.models import GiftCardExperiencia

    try:
        nombre = (cliente_data.get('nombre') or '').strip()
        email = (cliente_data.get('email') or '').strip()
        if not nombre or len(nombre) < 3:
            return {'success': False, 'error': 'validation_error',
                    'mensaje': 'Nombre del comprador requerido (mín 3 caracteres)'}
        # Sin email no hay carta que entregar: acá es obligatorio de verdad.
        if not email or '@' not in email:
            return {'success': False, 'error': 'validation_error',
                    'mensaje': 'Email válido requerido: la gift card se envía por email'}
        if not giftcards_data:
            return {'success': False, 'error': 'validation_error',
                    'mensaje': 'Debe incluir al menos una gift card'}

        if idempotency_key:
            previa = PropuestaReserva.objects.filter(
                idempotency_key=idempotency_key).first()
            if previa and previa.esta_vigente():
                logger.info('[Luna] Propuesta giftcard duplicada (idempotente): %s',
                            idempotency_key[:24])
                return {'success': True, 'propuesta_id': previa.propuesta_id,
                        'resumen_texto': previa.resumen_texto,
                        'total': int(previa.total), 'duplicada': True}

        lineas, items, total, n_cartas = [], [], 0, 0
        for gc in giftcards_data:
            exp_id = (gc.get('experiencia_id') or '').strip()
            exp = GiftCardExperiencia.objects.filter(
                id_experiencia=exp_id, activo=True).first()
            if exp is None:
                return {'success': False, 'error': 'experiencia_no_existe',
                        'mensaje': f'No hay una gift card «{exp_id}» activa. '
                                   'Consultá el catálogo de nuevo.'}
            cantidad = max(1, int(gc.get('cantidad') or 1))

            if exp.tiene_monto_fijo():
                monto = int(exp.monto_fijo)
            else:
                # Tarjeta de valor: el monto lo elige el cliente, con pisos y
                # techos para que un typo del LLM no venda una carta de $2.
                try:
                    monto = int(gc.get('monto') or 0)
                except (TypeError, ValueError):
                    monto = 0
                if not (MONTO_MINIMO_VALOR <= monto <= MONTO_MAXIMO_VALOR):
                    return {'success': False, 'error': 'monto_invalido',
                            'mensaje': (f'Para «{exp.nombre}» falta el monto: entre '
                                        f'${MONTO_MINIMO_VALOR:,} y ${MONTO_MAXIMO_VALOR:,}')}

            n_cartas += cantidad
            total += monto * cantidad
            destinatario = (gc.get('destinatario_nombre') or '').strip()
            items.append({
                'experiencia_id': exp.id_experiencia,
                'experiencia_nombre': exp.nombre,
                'precio': monto,
                'cantidad': cantidad,
                'destinatario_nombre': destinatario,
                'mensaje': (gc.get('mensaje') or '').strip()[:500],
            })
            para = f' para {destinatario}' if destinatario else ''
            lineas.append(f'{cantidad}x Gift Card {exp.nombre}{para} = ${monto * cantidad:,}')

        if n_cartas > MAX_GIFTCARDS_POR_VENTA:
            return {'success': False, 'error': 'demasiadas_giftcards',
                    'mensaje': (f'Son {n_cartas} gift cards: para pedidos así de '
                                'grandes lo ve el equipo directamente.')}

        resumen = '🎁 ' + '\n🎁 '.join(lineas)
        propuesta = PropuestaReserva.objects.create(
            propuesta_id=str(uuid.uuid4()),
            idempotency_key=idempotency_key or '',
            canal=canal,
            external_id=external_id,
            payload={'cliente': cliente_data, 'servicios': [],
                     'giftcards': items},
            cliente_data=cliente_data,
            servicios=[],
            total=total,
            resumen_texto=resumen,
            estado='pendiente',
            # Mismo TTL que las reservas. Acá ni siquiera hay cupo en juego:
            # una propuesta vencida solo obliga a cotizar de nuevo.
            expires_at=timezone.now() + timedelta(hours=24),
        )
        logger.info('[Luna] Propuesta GIFTCARD %s para %s: %s cartas, $%s',
                    propuesta.propuesta_id[:8], external_id, n_cartas, f'{total:,}')
        return {'success': True, 'propuesta_id': propuesta.propuesta_id,
                'resumen_texto': resumen, 'total': total,
                'giftcards_count': n_cartas}
    except Exception as e:  # noqa: BLE001
        logger.exception('Error en preparar_giftcard: %s', e)
        return {'success': False, 'error': 'internal_error',
                'mensaje': f'No se pudo preparar la gift card: {str(e)[:100]}'}


def materializar_giftcards(venta, payload, cliente_comprador):
    """Crea las filas GiftCard de una propuesta aprobada sobre SU venta.

    Espejo de reservation_service.finalize (el camino de la web): por_cobrar,
    vencimiento 365 días, datos de comprador y destinatario. Cada unidad es
    una carta. La señal de Pago las envía por email al confirmarse el pago.
    Devuelve (cantidad creada, monto total): el caller debe sumar ese monto a
    su total ANTES de fijarlo — la señal de GiftCard recalcula desde las
    líneas y pisaría un total puesto a mano (la trampa documentada en el
    paso 4 de crear_reserva).
    """
    from ventas.models import GiftCard

    creadas, monto_total = 0, 0
    hoy = timezone.now().date()
    cliente_data = payload.get('cliente') or {}
    for item in payload.get('giftcards') or []:
        for _ in range(max(1, int(item.get('cantidad') or 1))):
            GiftCard.objects.create(
                monto_inicial=item['precio'],
                monto_disponible=item['precio'],
                fecha_emision=hoy,
                fecha_vencimiento=hoy + timedelta(days=365),
                estado='por_cobrar',
                cliente_comprador=cliente_comprador,
                venta_reserva=venta,
                comprador_nombre=cliente_data.get('nombre', ''),
                comprador_email=cliente_data.get('email', ''),
                comprador_telefono=cliente_data.get('telefono', ''),
                destinatario_nombre=item.get('destinatario_nombre', ''),
                mensaje_personalizado=item.get('mensaje', ''),
                servicio_asociado=item.get('experiencia_id', ''),
            )
            creadas += 1
            monto_total += int(item['precio'])
    if creadas:
        logger.info('[Luna] %s GiftCard(s) creadas para venta %s ($%s)',
                    creadas, venta.id, f'{monto_total:,}')
    return creadas, monto_total
