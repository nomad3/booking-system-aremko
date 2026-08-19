# -*- coding: utf-8 -*-
"""Recordatorios de Luna (H-109): recuperar la plata que muere en silencio.

Medido en el embudo el 2026-08-19 (30 días): $3,4M expiraron sin que el
cliente dijera ni que sí ni que no, y hay reservas aprobadas que nadie pagó.
Tres toques, todos con texto DETERMINISTA (lo arma este módulo, no el LLM):

1. `cotizacion_lista` — la cotización lleva ≥6h enviada y el cliente lleva
   ≥4h sin escribir. Un solo empujón suave con el link.
2. `cotizacion_por_vencer` — quedan ≤3h para que expire y el silencio sigue.
   Último aviso con la hora de vencimiento.
3. `pago_pendiente` — el cliente APROBÓ (la reserva existe) pero no ha pagado
   tras ≥6h. Se le manda el link del Pase.

La condición de "no molestar" es SILENCIO ACTUAL (horas desde el último
entrante), no "nunca escribió después de la cotización": un «gracias, lo veo»
a los 10 minutos no puede vetar el recordatorio para siempre — ese cliente
que agradece y desaparece es EXACTAMENTE el caso que más plata pierde
(52% de las conversaciones muere así, medido en P-31).

Restricción dura de Meta: un mensaje LIBRE de sesión solo puede salir si el
último entrante del cliente tiene <24h. Se usa margen de 23h acá al generar,
y el pull del Go lo revalida (`pending_luna_nudges`) por si el envío esperó.

Anti-spam: máximo un recordatorio por tipo por propuesta/reserva (la bitácora
`RecordatorioLuna` es la memoria), máximo UNO por teléfono por corrida, nunca
en medio de una conversación viva (silencio mínimo por tipo), y tope global
por corrida.
"""
import logging
from datetime import timedelta

from django.utils import timezone

logger = logging.getLogger(__name__)

# Horas desde que se creó la cotización para el primer empujón.
HORAS_AVISO_COTIZACION = 6
# Horas antes de expirar para el último aviso.
HORAS_ANTES_DE_VENCER = 3
# La reserva aprobada sin pago se recuerda entre estas horas desde su creación
# (el mínimo evita apurar a quien acaba de aprobar; el máximo evita revivir
# casos viejos que Deborah ya está manejando por otro lado).
HORAS_MIN_PAGO = 6
HORAS_MAX_PAGO = 72
# Silencio mínimo del cliente para cada tipo: no meterse en conversación viva.
SILENCIO_MIN_HORAS = {
    'cotizacion_lista': 4,
    'cotizacion_por_vencer': 2,   # urgente: justifica un umbral más corto
    'pago_pendiente': 4,
}
# Ventana de sesión de Meta (24h) con margen de seguridad.
VENTANA_META_HORAS = 23
# Tope de recordatorios NUEVOS por corrida del cron (paracaídas anti-ráfaga).
TOPE_POR_CORRIDA = 20


def _ultimo_entrante(phone):
    from ventas.models import WhatsAppMessage

    return (WhatsAppMessage.objects
            .filter(phone=phone[:20], direction='in')
            .order_by('-timestamp')
            .values_list('timestamp', flat=True)
            .first())


def silencio_ok(phone, ahora, tipo):
    """True si el cliente lleva el silencio mínimo del tipo Y la ventana de
    Meta sigue abierta. False también cuando nunca escribió (sin entrante no
    hay sesión que aprovechar)."""
    ultimo = _ultimo_entrante(phone)
    if ultimo is None:
        return False
    silencio = ahora - ultimo
    if silencio < timedelta(hours=SILENCIO_MIN_HORAS[tipo]):
        return False
    return silencio < timedelta(hours=VENTANA_META_HORAS)


def dentro_de_ventana(phone, ahora):
    """True si Meta todavía acepta un mensaje libre de sesión para este phone.
    La usa el pull del Go para revalidar antes de entregar."""
    ultimo = _ultimo_entrante(phone)
    if ultimo is None:
        return False
    return ahora - ultimo < timedelta(hours=VENTANA_META_HORAS)


def _texto_cotizacion_lista(propuesta):
    from ventas.views.ficha_reserva_view import url_cotizacion

    link = url_cotizacion(propuesta.propuesta_id)
    return ('¡Hola! Te escribo de Aremko 🌿 Tu cotización sigue disponible — '
            f'puedes revisarla y confirmarla aquí: {link}\n'
            'Si prefieres otra fecha u otra combinación, dime y la armamos.')


def _texto_cotizacion_por_vencer(propuesta):
    from ventas.views.ficha_reserva_view import url_cotizacion

    hora = timezone.localtime(propuesta.expires_at).strftime('%H:%M')
    link = url_cotizacion(propuesta.propuesta_id)
    return (f'¡Hola! Tu cotización de Aremko vence a las {hora}. '
            f'Si quieres tomarla, confírmala aquí: {link}\n'
            'Y si te acomoda más otra fecha, dime y te preparo una nueva.')


def _texto_pago_pendiente(reserva_id):
    from ventas.views.ficha_reserva_view import url_ficha_reserva

    link = url_ficha_reserva(reserva_id)
    return ('¡Tu reserva en Aremko quedó lista! Para dejarla confirmada solo '
            f'falta el pago. El detalle está en tu Pase: {link}\n'
            'Cualquier duda, me dices.')


def _ya_enviado(tipo, propuesta=None, reserva_id=None):
    from whatsapp_agent.models import RecordatorioLuna

    qs = RecordatorioLuna.objects.filter(tipo=tipo)
    if propuesta is not None:
        qs = qs.filter(propuesta=propuesta)
    if reserva_id is not None:
        qs = qs.filter(reserva_id=reserva_id)
    return qs.exists()


def candidatos(ahora):
    """[{tipo, phone, propuesta, reserva_id, texto}] — lo que corresponde
    recordar AHORA. Puro cálculo: no escribe nada (el comando persiste).

    Orden: primero lo urgente (por vencer), después el aviso suave, al final
    los pagos — si el tope corta, corta lo menos urgente. Máximo un item por
    teléfono por corrida: si a alguien le calzan dos, recibe solo el primero
    (el más urgente) y el otro sale en una corrida siguiente.
    """
    from whatsapp_agent.models import PropuestaReserva

    resultado = []
    telefonos_usados = set()

    def _agregar(item):
        if item['phone'] in telefonos_usados:
            return
        telefonos_usados.add(item['phone'])
        resultado.append(item)

    # 1) Cotizaciones a punto de expirar (lo más urgente).
    por_vencer = (PropuestaReserva.objects
                  .filter(canal='whatsapp', estado='pendiente',
                          expires_at__gt=ahora,
                          expires_at__lte=ahora + timedelta(hours=HORAS_ANTES_DE_VENCER)))
    for p in por_vencer:
        if not p.external_id:
            continue
        if _ya_enviado('cotizacion_por_vencer', propuesta=p):
            continue
        if not silencio_ok(p.external_id, ahora, 'cotizacion_por_vencer'):
            continue
        _agregar({'tipo': 'cotizacion_por_vencer', 'phone': p.external_id,
                  'propuesta': p, 'reserva_id': None,
                  'texto': _texto_cotizacion_por_vencer(p)})

    # 2) Cotizaciones con ≥6h enviadas (y que NO estén ya en la zona de
    #    "por vencer": para esas manda el aviso urgente de arriba, no dos).
    listas = (PropuestaReserva.objects
              .filter(canal='whatsapp', estado='pendiente',
                      created_at__lte=ahora - timedelta(hours=HORAS_AVISO_COTIZACION),
                      expires_at__gt=ahora + timedelta(hours=HORAS_ANTES_DE_VENCER)))
    for p in listas:
        if not p.external_id:
            continue
        if _ya_enviado('cotizacion_lista', propuesta=p):
            continue
        if not silencio_ok(p.external_id, ahora, 'cotizacion_lista'):
            continue
        _agregar({'tipo': 'cotizacion_lista', 'phone': p.external_id,
                  'propuesta': p, 'reserva_id': None,
                  'texto': _texto_cotizacion_lista(p)})

    # 3) Reservas aprobadas sin pago.
    from ventas.models import VentaReserva

    aprobadas = (PropuestaReserva.objects
                 .filter(canal='whatsapp', estado='creada',
                         reserva_id__isnull=False)
                 .order_by('created_at'))
    ventas = {v.id: v for v in VentaReserva.objects.filter(
        id__in=[p.reserva_id for p in aprobadas],
        estado_pago='pendiente',
        fecha_creacion__gte=ahora - timedelta(hours=HORAS_MAX_PAGO),
        fecha_creacion__lte=ahora - timedelta(hours=HORAS_MIN_PAGO),
    ).exclude(estado_reserva='cancelada')}
    reservas_usadas = set()
    for p in aprobadas:
        v = ventas.get(p.reserva_id)
        if v is None or not p.external_id:
            continue
        if v.id in reservas_usadas:
            continue  # dos propuestas (H-060) pueden apuntar a la misma venta
        if _ya_enviado('pago_pendiente', reserva_id=v.id):
            continue
        if not silencio_ok(p.external_id, ahora, 'pago_pendiente'):
            continue
        reservas_usadas.add(v.id)
        _agregar({'tipo': 'pago_pendiente', 'phone': p.external_id,
                  'propuesta': p, 'reserva_id': v.id,
                  'texto': _texto_pago_pendiente(v.id)})

    return resultado


def persistir(items, tope=TOPE_POR_CORRIDA):
    """Crea las filas RecordatorioLuna (estado pendiente_envio). Devuelve las
    creadas. Los candidatos que el tope deja fuera NO se pierden: al no quedar
    en bitácora, la próxima corrida los vuelve a encontrar."""
    from whatsapp_agent.models import RecordatorioLuna

    creados = []
    for item in items[:tope]:
        creados.append(RecordatorioLuna.objects.create(
            tipo=item['tipo'], phone=item['phone'][:20],
            propuesta=item['propuesta'], reserva_id=item['reserva_id'],
            texto=item['texto']))
    if len(items) > tope:
        logger.warning('Recordatorios: %s candidatos superan el tope %s — '
                       'los restantes saldrán en la próxima corrida',
                       len(items), tope)
    return creados
