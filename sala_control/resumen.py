# -*- coding: utf-8 -*-
"""Arma el resumen ejecutivo del día.

Junta lo que trae `fuentes` y lo pasa por las reglas de `alertas`. Devuelve
una estructura plana lista para renderizar — sin HTML, para poder probarla.
"""
import os
from datetime import date

from . import alertas, fuentes

# El bloque de presencia web sale los MARTES, no los lunes: las fotos de
# Analytics y Search Console se toman el lunes, después de que este correo
# ya salió. Mostrarlas el lunes a las 8:00 sería enseñar la foto de la
# semana pasada con cara de recién tomada.
DIA_PRESENCIA_WEB = 1  # 0=lunes, 1=martes


def _umbral_caja():
    crudo = os.environ.get('UMBRAL_CAJA_MINIMA', '').strip()
    try:
        return int(crudo)
    except (TypeError, ValueError):
        return alertas.UMBRAL_CAJA_DEFAULT


def variacion(actual, anterior):
    """Cambio porcentual, o None cuando no hay con qué comparar.

    Devolver 0% cuando el mes anterior fue cero sería mentir: no es «igual»,
    es que no hay base.
    """
    if actual is None or anterior is None or anterior == 0:
        return None
    return (actual - anterior) / anterior * 100


def construir(hoy=None):
    """El resumen completo del día. No lanza: cada bloque puede venir vacío."""
    hoy = hoy or date.today()
    lunes = fuentes.lunes_de(hoy)
    dias_mes = fuentes.dias_transcurridos_del_mes(hoy)

    caja = fuentes.caja(hoy)
    gasto = fuentes.gasto_diario(hasta=hoy)
    comparativa = fuentes.comparativa_ventas()
    ads = fuentes.publicidad(dias_mes)
    telar = fuentes.plan_del_dia(fecha=hoy)

    caja_total = caja['total'] if caja else None
    promedio = gasto['promedio_diario'] if gasto else None
    colchon = None
    if caja_total is not None and promedio:
        from finanzas.services import colchon_dias
        colchon = colchon_dias(caja_total, promedio)

    publicaciones = (telar or {}).get('publicaciones') or []

    gasto_ads = None
    if ads['meta'] is not None or ads['google'] is not None:
        gasto_ads = (ads['meta'] or 0) + (ads['google'] or 0)

    lista_alertas = alertas.construir_alertas(
        caja_total=caja_total,
        umbral_caja=_umbral_caja(),
        cuentas=(caja or {}).get('cuentas') or [],
        publicaciones=publicaciones,
        comparativa=comparativa,
        dia_del_mes=hoy.day,
        campanas=ads['campanas'],
    )

    # Una sola consulta: se necesita la lista completa para saber si
    # están todas listas o si no se fijó ninguna — son mensajes distintos.
    todas = fuentes.prioridades(lunes)
    pendientes = [p for p in todas if not p.hecha]

    return {
        'fecha': hoy,
        'semana_inicio': lunes,
        'prioridades': pendientes,
        'sin_prioridades': not todas,
        'caja': caja,
        'caja_total': caja_total,
        'umbral_caja': _umbral_caja(),
        'gasto_diario': gasto,
        'colchon_dias': colchon,
        'comparativa': comparativa,
        'ads': ads,
        'gasto_ads': gasto_ads,
        'telar': telar,
        'publicaciones': publicaciones,
        'alertas': lista_alertas,
        'presencia_web': (fuentes.presencia_web()
                          if hoy.weekday() == DIA_PRESENCIA_WEB else None),
        'notas': fuentes.notas_negocios(),
    }
