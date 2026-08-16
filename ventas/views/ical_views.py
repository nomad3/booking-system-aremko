# -*- coding: utf-8 -*-
"""Publicación del .ics por cabaña (H-106 Fase 1).

La URL lleva un token secreto porque queda PEGADA en el extranet de Booking y
de Airbnb, que la leen sin ninguna sesión. No expone datos del huésped: solo
fechas ocupadas y el número de reserva, que es lo mínimo para que la OTA sepa
que no puede vender.
"""
import logging
from datetime import timedelta

from django.http import Http404, HttpResponse
from django.utils import timezone

from ventas.ical import construir_ics, tramos_ocupados
from ventas.models import CalendarioCabana

logger = logging.getLogger(__name__)

# Cuánto pasado se publica. Solo existe para no cortar a un huésped que llegó
# antes y todavía no se va: su tramo tiene que seguir bloqueando las noches que
# le quedan.
DIAS_DE_GRACIA_ATRAS = 7


def calendario_cabana_ics(request, token, slug=None):
    """GET /reservas/ical/<token>/<slug>.ics — fechas ocupadas de una cabaña.

    El `slug` no se valida: está en la URL para que Jorge distinga de un
    vistazo cuál pegó en cada anuncio. Lo que manda es el token.
    """
    cal = (CalendarioCabana.objects
           .filter(token=token, activo=True)
           .select_related('servicio').first())
    if cal is None:
        # 404 y no 403: a quien tenga un token viejo no se le confirma que
        # exista un calendario detrás.
        raise Http404('calendario no encontrado')

    # Solo de una semana atrás en adelante. Las OTAs ignoran el pasado, así que
    # publicar el histórico completo no sirve para nada y sí tiene costo: en la
    # primera prueba real (Torre, 2026-08-15) el archivo traía 211 eventos de
    # los cuales 208 eran viejos —40 KB en cada lectura, y Booking lee seguido—
    # y de paso le contaba a un tercero qué noches estuvo llena la cabaña desde
    # que existe. Los 7 días de margen cubren a alguien que sigue alojado.
    desde = timezone.localdate() - timedelta(days=DIAS_DE_GRACIA_ATRAS)
    tramos = tramos_ocupados(cal.servicio_id, desde=desde)
    cuerpo = construir_ics(cal.servicio.nombre, tramos)
    logger.info('[ical] %s servido con %s tramos desde %s',
                cal.servicio.nombre, len(tramos), desde)

    resp = HttpResponse(cuerpo, content_type='text/calendar; charset=utf-8')
    resp['Content-Disposition'] = f'inline; filename="{slug or "aremko"}.ics"'
    # Sin caché: si Booking cachea, la ventana de doble venta se agranda.
    resp['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return resp
