# -*- coding: utf-8 -*-
"""De dónde sale cada número del resumen.

Regla de esta capa: NINGUNA función revienta. Si una fuente falla, devuelve
None y el resumen muestra «no disponible» en ese bloque. Un correo diario que
no llega porque la API de Meta tuvo un mal día es peor que un correo con un
bloque vacío — el hábito de leerlo se pierde a la primera ausencia.

Regla dos: cada bloque declara su cobertura. Un número sin fecha de corte se
lee como si fuera de hoy aunque sea de la semana pasada.
"""
import logging
import os
from datetime import date, timedelta

logger = logging.getLogger(__name__)

# Las cuentas publicitarias que se escanean. Se pueden sobreescribir por env
# (mismo nombre que usa el backend Go, para no tener dos verdades).
CUENTAS_META_DEFAULT = (
    'act_214650980544393',   # operativa: acá viven Ritual y Pausa
    'act_455070225054110',
    'act_323860814935576',
)


def _safe(nombre, fn, *args, **kwargs):
    """Corre fn y devuelve None si falla, dejando rastro en el log."""
    try:
        return fn(*args, **kwargs)
    except Exception as exc:
        logger.warning('sala_control: fuente «%s» falló: %s: %s',
                       nombre, type(exc).__name__, exc)
        return None


# ── Plata ────────────────────────────────────────────────────────────────

def caja(hasta=None):
    from finanzas.services import saldos_actuales
    return _safe('caja', saldos_actuales, hasta)


def gasto_diario(dias=28, hasta=None):
    from finanzas.services import gasto_diario_promedio
    return _safe('gasto diario', gasto_diario_promedio, dias, hasta)


# ── Ventas ───────────────────────────────────────────────────────────────

def comparativa_ventas():
    """Ventas del mes vs el mismo tramo del mes anterior (1 al día de hoy)."""
    def _leer():
        from ventas.models import ReservaServicio, VentaReserva
        from ventas.services.marketing_brief_generator import (
            _comparativa_mensual_misma_fecha)
        return _comparativa_mensual_misma_fecha(VentaReserva, ReservaServicio)
    return _safe('comparativa de ventas', _leer)


# ── Publicidad ───────────────────────────────────────────────────────────

def _cuentas_meta():
    crudo = os.environ.get('META_AD_ACCOUNT_IDS', '')
    ids = [c.strip() for c in crudo.split(',') if c.strip()]
    return ids or list(CUENTAS_META_DEFAULT)


def publicidad(dias):
    """Gasto y resultados de Meta y Google en la ventana pedida.

    Devuelve siempre un dict (nunca None): cada plataforma trae su gasto o
    None si no se pudo leer, y la lista de campañas para las alertas.

    Detalle importante en Google: sus `conversions` vienen en cero porque el
    lead de WhatsApp no está importado como conversión en la plataforma. NO es
    que la campaña no funcione. Por eso sus campañas viajan con
    `resultados=None` — «no medible» — y quedan fuera de las alertas. Poner un
    cero ahí llevaría a apagar campañas que están vendiendo.
    """
    salida = {'dias': dias, 'meta': None, 'google': None, 'campanas': []}

    def _meta():
        from ventas.services.meta_reporter import get_campaign_results
        total, campanas = 0.0, []
        leyo_alguna = False
        for cuenta in _cuentas_meta():
            filas = _safe(f'meta {cuenta}', get_campaign_results, cuenta, dias)
            if filas is None:
                continue
            leyo_alguna = True
            for f in filas:
                total += f.get('gasto') or 0
                if (f.get('gasto') or 0) > 0:
                    campanas.append({
                        'plataforma': 'Meta',
                        'nombre': f.get('nombre'),
                        'gasto': f.get('gasto') or 0,
                        'resultados': f.get('resultados'),
                        'unidad': f.get('unidad') or 'resultados',
                        'dias': dias,
                    })
        return (total if leyo_alguna else None), campanas

    def _google():
        from ventas.services.google_ads_reporter import get_campaigns_summary
        filas = get_campaigns_summary(days=dias)
        if filas is None:
            return None, []
        total, campanas = 0.0, []
        for f in filas:
            gasto = f.get('spend_clp') or 0
            total += gasto
            if gasto > 0:
                campanas.append({
                    'plataforma': 'Google',
                    'nombre': f.get('name'),
                    'gasto': gasto,
                    # Ver docstring: la conversión no está importada en Google.
                    'resultados': None,
                    'unidad': 'conversiones',
                    'dias': dias,
                })
        return total, campanas

    r_meta = _safe('meta ads', _meta)
    if r_meta:
        salida['meta'], campanas_meta = r_meta
        salida['campanas'].extend(campanas_meta)

    r_google = _safe('google ads', _google)
    if r_google:
        salida['google'], campanas_google = r_google
        salida['campanas'].extend(campanas_google)

    return salida


# ── El Telar (Datamatic Hospitality) ─────────────────────────────────────

def plan_del_dia(tenant='aremko', fecha=None):
    """Las publicaciones de hoy, leídas del Telar.

    Vive en otro servicio, así que acá se le pone un timeout corto: el resumen
    tiene que salir aunque el Telar esté durmiendo.
    """
    url = os.environ.get('DH_PLAN_DIA_URL', '').strip()
    token = os.environ.get('DH_CRON_TOKEN', '').strip()
    if not url or not token:
        logger.info('sala_control: sin DH_PLAN_DIA_URL/DH_CRON_TOKEN, '
                    'el bloque de publicaciones queda fuera')
        return None

    def _leer():
        import requests
        params = {'token': token, 'tenant': tenant}
        if fecha:
            params['fecha'] = fecha.isoformat()
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        return r.json()

    return _safe('plan del día', _leer)


# ── Presencia web (solo los lunes) ───────────────────────────────────────

def presencia_web():
    """Último snapshot de GA4 y Search Console.

    Se persisten una vez por semana, así que no tiene sentido mirarlos a
    diario: el resumen los muestra los lunes.
    """
    def _leer():
        from ventas.models import GA4Snapshot, SearchConsoleSnapshot
        ga4 = GA4Snapshot.objects.order_by('-fecha_snapshot', '-id').first()
        gsc = (SearchConsoleSnapshot.objects
               .order_by('-fecha_snapshot', '-id').first())
        if not ga4 and not gsc:
            return None
        return {'ga4': ga4, 'gsc': gsc}
    return _safe('presencia web', _leer)


# ── Lo que el dueño escribió ─────────────────────────────────────────────

def prioridades(semana_inicio):
    def _leer():
        from .models import PrioridadSemana
        return list(PrioridadSemana.objects.filter(semana_inicio=semana_inicio))
    return _safe('prioridades', _leer) or []


def notas_negocios():
    def _leer():
        from .models import NotaNegocio
        return {n.negocio: n for n in NotaNegocio.objects.all()}
    return _safe('notas de negocios', _leer) or {}


def lunes_de(fecha):
    return fecha - timedelta(days=fecha.weekday())


def dias_transcurridos_del_mes(hoy=None):
    """Cuántos días lleva el mes, mínimo 1 (para las ventanas de publicidad)."""
    hoy = hoy or date.today()
    return max(1, hoy.day - 1)
