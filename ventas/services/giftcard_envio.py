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
