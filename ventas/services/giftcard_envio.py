"""Mandarle al comprador su gift card desde la tarjeta móvil (P-52, paso 2).

Jorge, 24-09-2026: en la tarjeta de una venta de gift card, «ver gift cards»,
copiar el código y enviar el PDF por WhatsApp al comprador. En 60 días se
vendieron 40 gift cards y unos 6 compradores escribieron que no les llegó
(spam, «me llegó solo el respaldo del pago»); Deborah ya había mandado 10 PDF a
mano, descargándolos del admin y subiéndolos a la bandeja.

El PDF es el mismo del email (GiftCardPDFService, fuente única de la carta) y
sale por el mismo canal que la boleta. Si está pagada, si hay ventana de 24 h
y a qué número va lo decide quien llama (la tarjeta), no este módulo.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def nombre_experiencia(gc):
    """Nombre de la experiencia de la gift card, para mostrar y para el mensaje."""
    from ventas.models import GiftCardExperiencia
    clave = (gc.servicio_asociado or '').strip()
    if not clave:
        return 'Gift card de monto libre'
    nombre = (GiftCardExperiencia.objects.filter(id_experiencia=clave)
              .values_list('nombre', flat=True).first())
    if nombre:
        return nombre
    legible = clave.replace('_', ' ')
    return legible[:1].upper() + legible[1:]


def contacto_comprador(gc, venta):
    """(teléfono, email, nombre) de quien COMPRÓ la gift card."""
    comprador = gc.cliente_comprador if gc.cliente_comprador_id else venta.cliente
    telefono = ((getattr(comprador, 'telefono', '') or '') or (venta.cliente.telefono or '')
                or (gc.comprador_telefono or '')).strip()
    email = ((getattr(comprador, 'email', '') or '') or (venta.cliente.email or '')
             or (gc.comprador_email or '')).strip()
    nombre = ((getattr(comprador, 'nombre', '') or '') or (gc.comprador_nombre or '')).strip()
    return telefono, email, nombre


def _primer_nombre(texto):
    partes = (texto or '').strip().split()
    return partes[0] if partes else ''


def pdf_de(giftcard):
    from .giftcard_pdf_service import GiftCardPDFService
    return GiftCardPDFService.generar_pdf_giftcard(
        GiftCardPDFService.datos_carta(giftcard), formato='mobile')


def enviar_por_whatsapp(giftcard, telefono, nombre_comprador, experiencia):
    """Manda el PDF al teléfono dado. Devuelve (enviado, motivo)."""
    from facturacion.services.envio_whatsapp import enviar_documento

    pdf = pdf_de(giftcard)
    if not pdf:
        return False, 'no se pudo generar el PDF'
    nombre = _primer_nombre(nombre_comprador)
    saludo = f'Hola {nombre}, ' if nombre else 'Hola, '
    para = (giftcard.destinatario_nombre or '').strip()
    vence = giftcard.fecha_vencimiento
    saldo, inicial = int(giftcard.monto_disponible or 0), int(giftcard.monto_inicial or 0)
    # Usada en parte: el PDF muestra la carta original, así que el mensaje dice
    # cuánto queda de verdad.
    queda = (f' Le quedan ${saldo:,} por usar.'.replace(',', '.')
             if 0 < saldo < inicial else '')
    caption = (f'{saludo}acá está tu gift card de Aremko: {experiencia}'
               + (f' para {para}' if para else '') + ' 🎁'
               + queda
               + (f' Vale hasta el {vence:%d-%m-%Y}.' if vence else ''))
    enviado, motivo = enviar_documento(
        telefono, pdf, f'giftcard-{giftcard.codigo}.pdf', caption)
    if enviado:
        type(giftcard).objects.filter(pk=giftcard.pk).update(enviado_whatsapp=True)
    return enviado, motivo


def reenviar_por_email(giftcard, email, nombre_comprador):
    """Vuelve a mandar el email de la gift card (el mismo que sale al pagarse)."""
    from .giftcard_pdf_service import GiftCardPDFService

    ok = GiftCardPDFService.enviar_giftcard_por_email(
        comprador_email=email, comprador_nombre=nombre_comprador or '',
        giftcards_data=[GiftCardPDFService.datos_carta(giftcard)])
    if ok:
        type(giftcard).objects.filter(pk=giftcard.pk).update(enviado_email=True)
    return bool(ok)


def enviar_al_pagarse(venta_id, giftcard_ids):
    """El PDF sale solo por WhatsApp al registrarse el pago (2b; Jorge, 24-09-2026).

    Igual que la boleta: si el comprador conversó en las últimas 24 horas, se le
    manda el PDF sin que nadie apriete nada. Es justo cuando más sirve: el caso
    de Claudia (22-09) fue un «Me llegó la confirmación pero no gift» minutos
    después de pagar, con la gift card en spam.

    Solo con la venta pagada ENTERA —la regla que Jorge fijó para el código en
    la tarjeta—, aunque el email automático salga también con un pago parcial.
    Fuera de la ventana no se hace nada: queda el email y el botón de la
    tarjeta. Se llama después de confirmado el pago y NUNCA puede voltearlo:
    todo va envuelto y solo deja registro. Devuelve cuántas envió.
    """
    enviadas = 0
    try:
        from django.utils import timezone

        from facturacion.services.envio_whatsapp import ventana_abierta
        from ventas.models import GiftCard, VentaReserva

        venta = VentaReserva.objects.select_related('cliente').get(pk=venta_id)
        if int(venta.saldo_pendiente or 0) > 0:
            logger.info('[giftcard] venta %s con saldo pendiente: el PDF no sale solo por '
                        'WhatsApp todavía', venta_id)
            return 0
        hoy = timezone.localdate()
        cartas = (GiftCard.objects.select_related('cliente_comprador')
                  .filter(pk__in=list(giftcard_ids), venta_reserva_id=venta_id).order_by('id'))
        for gc in cartas:
            if gc.enviado_whatsapp or int(gc.monto_disponible or 0) <= 0 or (
                    gc.fecha_vencimiento and gc.fecha_vencimiento < hoy):
                continue
            telefono, _, nombre = contacto_comprador(gc, venta)
            if not telefono or not ventana_abierta(telefono):
                logger.info('[giftcard] %s: el comprador no conversó en 24 h, queda el email',
                            gc.codigo)
                continue
            try:
                ok, motivo = enviar_por_whatsapp(gc, telefono, nombre, nombre_experiencia(gc))
            except Exception as exc:  # noqa: BLE001
                ok, motivo = False, str(exc)
            if ok:
                enviadas += 1
                logger.info('[giftcard] %s enviada sola por WhatsApp a %s al pagarse la venta %s',
                            gc.codigo, telefono, venta_id)
            else:
                logger.warning('[giftcard] %s no salió sola por WhatsApp: %s', gc.codigo, motivo)
    except Exception:  # noqa: BLE001 — avisar jamás puede tumbar un cobro
        logger.exception('[giftcard] falló el envío automático de la venta %s', venta_id)
    return enviadas
