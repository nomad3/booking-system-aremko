# -*- coding: utf-8 -*-
"""Enviarle la boleta al cliente por WhatsApp.

Decisión de Jorge (04-09-2026): **todos** los clientes reciben su boleta. Su
razón no es de servicio sino de riesgo: «alguno puede pensar que estamos
evadiendo impuestos y denunciarnos, lo cual daría lugar a una fiscalización».

Dos caminos, según la ventana de servicio de 24 horas de WhatsApp:

· **Ventana abierta** (el cliente escribió hace menos de 24h): se le manda el
  PDF adjunto, al toque y gratis. Es lo que hace este módulo.
· **Ventana cerrada**: hay que pagar una plantilla, y ahí conviene juntar
  todas las boletas de la visita en un mensaje — eso es la fase 3, un proceso
  diario aparte.

Nada de esto puede voltear una emisión: la boleta ya existe ante el SII antes
de que intentemos avisar. Por eso todo acá devuelve (enviado, motivo) y jamás
lanza hacia arriba.
"""
import datetime
import logging
import os

logger = logging.getLogger(__name__)

# El backend Go es quien habla con la Cloud API de WhatsApp: sube el archivo a
# Meta, lo manda y registra el saliente en la bandeja. Django no tiene el token.
BASE_URL_DEFAULT = 'https://aremko-cli-backend.onrender.com'
VENTANA_HORAS = 24


def _base_url():
    return os.getenv('AREMKO_CLI_BASE_URL', BASE_URL_DEFAULT).rstrip('/')


def ventana_abierta(telefono, ahora=None):
    """¿El cliente escribió en las últimas 24 horas?

    Se mide desde el último mensaje ENTRANTE, que es lo que abre la ventana de
    servicio: los salientes no la reabren. Ante cualquier problema devuelve
    False — dar por abierta una ventana cerrada hace que el envío falle con
    código 131047 y el cliente no reciba nada, mientras el sistema cree que sí.
    """
    if not telefono:
        return False
    try:
        from django.utils import timezone

        from ventas.models import WhatsAppMessage

        ahora = ahora or timezone.now()
        ultimo = (WhatsAppMessage.objects
                  .filter(phone=telefono, direction='in')
                  .order_by('-timestamp').values_list('timestamp', flat=True).first())
        if not ultimo:
            return False
        return (ahora - ultimo) < datetime.timedelta(hours=VENTANA_HORAS)
    except Exception as exc:  # noqa: BLE001
        logger.warning('facturacion: no se pudo evaluar la ventana de %s: %s',
                       telefono, exc)
        return False


def _telefono_de(boleta):
    venta = getattr(boleta, 'venta_reserva', None)
    cliente = getattr(venta, 'cliente', None)
    return (getattr(cliente, 'telefono', '') or '').strip()


def _nombre_de(boleta):
    venta = getattr(boleta, 'venta_reserva', None)
    cliente = getattr(venta, 'cliente', None)
    nombre = (getattr(cliente, 'nombre', '') or '').strip()
    return nombre.split(' ')[0] if nombre else ''


def enviar_pdf_al_cliente(boleta, forzar=False):
    """Manda el PDF de la boleta por WhatsApp. Devuelve (enviado, motivo).

    `forzar=True` salta la comprobación de ventana — solo para reintentos
    manuales desde el admin, nunca automático: fuera de la ventana el envío
    falla igual y encima Meta lo cuenta como intento.
    """
    if boleta is None or not boleta.folio:
        return False, 'la boleta no está timbrada'
    if boleta.ambiente != 'produccion':
        return False, 'boleta que no es de producción: no se le manda al cliente'
    if getattr(boleta, 'enviada_cliente_at', None):
        return False, 'ya se le había enviado'

    telefono = _telefono_de(boleta)
    if not telefono:
        return False, 'el cliente no tiene teléfono'
    if not forzar and not ventana_abierta(telefono):
        return False, 'fuera de la ventana de 24h (va por plantilla)'

    try:
        from django.utils import timezone

        from facturacion.views import _pdf_boleta_impresa

        pdf, error = _pdf_boleta_impresa(boleta)
        if pdf is None:
            return False, f'no se pudo generar el PDF: {error}'

        import requests

        nombre = _nombre_de(boleta)
        saludo = f'Hola {nombre}, ' if nombre else 'Hola, '
        resp = requests.post(
            f'{_base_url()}/api/v1/whatsapp/send-media',
            data={'to': telefono,
                  'caption': (f'{saludo}acá está tu boleta electrónica '
                              f'N° {boleta.folio} de Aremko. ¡Gracias por tu visita!')},
            files={'file': (f'boleta-{boleta.folio}.pdf', pdf, 'application/pdf')},
            timeout=60)
        if resp.status_code != 200:
            return False, f'el backend respondió {resp.status_code}: {resp.text[:200]}'

        boleta.enviada_cliente_at = timezone.now()
        boleta.save(update_fields=['enviada_cliente_at', 'actualizada_at'])
        return True, 'boleta enviada por WhatsApp'
    except Exception as exc:  # noqa: BLE001 — avisar jamás puede tumbar el cobro
        logger.warning('facturacion: falló el envío de la boleta %s: %s',
                       getattr(boleta, 'folio', None), exc)
        return False, f'error al enviar: {exc}'
