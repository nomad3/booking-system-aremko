# -*- coding: utf-8 -*-
"""Publicación del .ics por cabaña (H-106 Fase 1).

La URL lleva un token secreto porque queda PEGADA en el extranet de Booking y
de Airbnb, que la leen sin ninguna sesión. No expone datos del huésped: solo
fechas ocupadas y el número de reserva, que es lo mínimo para que la OTA sepa
que no puede vender.
"""
import logging

from django.http import Http404, HttpResponse

from ventas.ical import construir_ics, tramos_ocupados
from ventas.models import CalendarioCabana

logger = logging.getLogger(__name__)


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

    tramos = tramos_ocupados(cal.servicio_id)
    cuerpo = construir_ics(cal.servicio.nombre, tramos)
    logger.info('[ical] %s servido con %s tramos', cal.servicio.nombre, len(tramos))

    resp = HttpResponse(cuerpo, content_type='text/calendar; charset=utf-8')
    resp['Content-Disposition'] = f'inline; filename="{slug or "aremko"}.ics"'
    # Sin caché: si Booking cachea, la ventana de doble venta se agranda.
    resp['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return resp
