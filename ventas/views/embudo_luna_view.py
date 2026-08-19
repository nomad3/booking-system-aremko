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

    # Payload chico y ya-listo para Chart.js: las series comparten las mismas
    # ventanas por construcción (todas llaman a ventanas_de_7_dias con el
    # mismo desde/hasta dentro de embudo()), así que alinean por posición sin
    # necesidad de cruzarlas por fecha.
    graficos = {
        'labels': [s['hasta'].strftime('%d/%m') for s in datos['semanas']],
        'conversaciones': [s['conversaciones'] for s in datos['semanas']],
        'cotizaciones': [s['cotizaciones'] for s in datos['semanas']],
        'reservas': [s['reservas'] for s in datos['semanas']],
        'pct_cotiza': [s['pct_cotiza'] for s in datos['semanas']],
        'pct_cierra': [s['pct_cierra'] for s in datos['semanas']],
        'pct_sin_editar': [s['pct_sin_editar'] for s in datos['serie_agente']],
        'pct_escalado': [s['pct_escalado'] for s in datos['serie_agente']],
        # v2 (2026-08-18): la mediana global salía clavada en 1 minuto — el
        # 62% de las respuestas es automática y bajo 90s, y ese cluster tapa
        # la parte que sí varía. Ahora dos señales en vez de una.
        'pct_respuesta_rapida': [s['pct_rapido'] for s in datos['serie_respuesta']],
        'mediana_respuesta_lenta_min': [s['mediana_lenta_min']
                                        for s in datos['serie_respuesta']],
        'pct_ventas_whatsapp': [s['pct_whatsapp'] for s in datos['serie_ventas']],
    }

    return render(request, 'ventas/embudo_luna.html', {
        'd': datos,
        'dias': dias,
        'dias_validos': DIAS_VALIDOS,
        'graficos': graficos,
        # Para que quede a la vista por qué la ventana puede ser más corta de
        # lo pedido: antes de esta fecha no hay datos reales de WhatsApp.
        'recortado': desde < INICIO_DATOS_REALES,
        'inicio_datos': INICIO_DATOS_REALES,
    })
