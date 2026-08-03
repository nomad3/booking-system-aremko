"""Llegada del huésped: el escaneo del QR de El Pase, y su plan B.

Idea de Jorge (2026-08-03): el QR no controla el ingreso — **es el pretexto para
que el cliente mire El Pase**. Deborah dice "acá está su pase, con el QR para
entrar", el cliente abre la pantalla, y con la pantalla abierta aparece todo lo
demás: las claves de wifi, cómo llegar, la comanda para pedir desde la tina.
Esa conversación es capacitación y venta a la vez.

Pero un QR que no hace nada se abandona en dos semanas. Por eso el escaneo
registra de verdad la llegada, y esa llegada sirve:
  · la agenda muestra quién está adentro y quién no,
  · el saldo aparece en pantalla justo cuando corresponde cobrarlo,
  · y El Pase del cliente se reordena y pone la comanda adelante.

**Nunca es la única puerta.** Sin batería, sin señal o sin celular, recepción
sigue como siempre: el cliente dice su nombre, se busca en la agenda del día y
se marca la llegada a mano. El QR es el atajo, no el torniquete.

Sin migraciones: la llegada vive en `MovimientoCliente` con un tipo propio,
igual que la apertura de la ficha (F-01). El campo `tipo_movimiento` es texto
libre, así que no hay riesgo de tocar el drift AR-033/AR-034.
"""
import logging

from django.utils import timezone

logger = logging.getLogger(__name__)

TIPO_LLEGADA = 'llegada'

# Cómo se marcó, para poder responder después "¿el ritual del QR está vivo?".
VIA_QR = 'qr'
VIA_MANUAL = 'manual'


def llegadas_de(venta_ids):
    """{venta_id: datetime de llegada} para las reservas pedidas.

    Una sola consulta: la agenda la usa para pintar decenas de tarjetas.
    """
    from .models import MovimientoCliente
    ids = [int(i) for i in venta_ids if i]
    if not ids:
        return {}
    filas = (MovimientoCliente.objects
             .filter(tipo_movimiento=TIPO_LLEGADA, venta_reserva_id__in=ids)
             .order_by('fecha_movimiento')
             .values_list('venta_reserva_id', 'fecha_movimiento'))
    # La primera gana: si alguien marca dos veces, vale la hora en que llegó.
    llegadas = {}
    for venta_id, cuando in filas:
        llegadas.setdefault(venta_id, cuando)
    return llegadas


def ya_llego(venta_id):
    """¿Esta reserva ya registró llegada? (datetime o None)"""
    return llegadas_de([venta_id]).get(int(venta_id or 0))


def registrar_llegada(venta, usuario=None, via=VIA_QR):
    """Marca la llegada. IDEMPOTENTE: escanear dos veces no duplica ni pisa la hora.

    Devuelve (cuando, recien_marcada).
    """
    from .models import MovimientoCliente

    if not venta or not getattr(venta, 'pk', None):
        return None, False

    previa = ya_llego(venta.pk)
    if previa:
        # Escanear de nuevo NO es un error: pasa cuando el cliente muestra el
        # QR dos veces o vuelve a recepción. Se responde igual de bien.
        return previa, False

    if not getattr(venta, 'cliente_id', None):
        logger.warning('[llegada] reserva %s sin cliente — no se registra', venta.pk)
        return None, False

    try:
        mov = MovimientoCliente.objects.create(
            cliente_id=venta.cliente_id,
            venta_reserva=venta,
            tipo_movimiento=TIPO_LLEGADA,
            usuario=usuario if getattr(usuario, 'is_authenticated', False) else None,
            comentarios=f'Llegada registrada ({via}).',
        )
    except Exception:  # noqa: BLE001 — marcar llegada no puede tumbar recepción
        logger.exception('[llegada] no se pudo registrar (reserva %s)', venta.pk)
        return None, False

    logger.info('[llegada] reserva=%s via=%s usuario=%s saldo=%s',
                venta.pk, via, getattr(usuario, 'username', '-'),
                getattr(venta, 'saldo_pendiente', '?'))
    return mov.fecha_movimiento, True


def hora_local(cuando):
    """15:04 en hora de Chile, o '' si no hay dato."""
    if not cuando:
        return ''
    return timezone.localtime(cuando).strftime('%H:%M')
