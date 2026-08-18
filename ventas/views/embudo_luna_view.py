# -*- coding: utf-8 -*-
"""Tablero del embudo de conversaciones de Luna (P-30, Fase 1).

GET /ventas/analytics/embudo-luna/?dias=60
"""
from datetime import timedelta

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.utils import timezone

from whatsapp_agent.embudo import INICIO_DATOS_REALES, embudo

DIAS_POR_DEFECTO = 60
DIAS_VALIDOS = (30, 60, 90, 180)


@staff_member_required
def embudo_luna(request):
    try:
        dias = int(request.GET.get('dias', DIAS_POR_DEFECTO))
    except (TypeError, ValueError):
        dias = DIAS_POR_DEFECTO
    if dias not in DIAS_VALIDOS:
        dias = DIAS_POR_DEFECTO

    ahora = timezone.now()
    hasta = timezone.localdate()
    desde = hasta - timedelta(days=dias)
    datos = embudo(desde, hasta, ahora)
    return render(request, 'ventas/embudo_luna.html', {
        'd': datos,
        'dias': dias,
        'dias_validos': DIAS_VALIDOS,
        # Para que quede a la vista por qué la ventana puede ser más corta de
        # lo pedido: antes de esta fecha no hay datos reales de WhatsApp.
        'recortado': desde < INICIO_DATOS_REALES,
        'inicio_datos': INICIO_DATOS_REALES,
    })
