#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Micrositios Fase 1 — export de Google Ads y Meta Ads (SOLO LECTURA).

Usa los clientes API ya existentes en el repo (google_ads_reporter y
meta_reporter) con las credenciales configuradas en Render. Imprime un
informe markdown a stdout: campañas, keywords y TÉRMINOS DE BÚSQUEDA reales
de Google, más rendimiento por campaña de Meta. No contiene datos personales
(los términos de búsqueda son texto de queries, no identifican personas).

Uso (shell de Render):
    python analysis/export_ads.py > /tmp/export_ads.md
    cat /tmp/export_ads.md

Si faltan credenciales, cada sección lo indica y el script continúa.
"""
import os
import sys
from datetime import date

import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "aremko_project.settings")
django.setup()

from ventas.services import google_ads_reporter as gads  # noqa: E402
from ventas.services import meta_reporter as meta  # noqa: E402

DIAS_VENTANA = 365  # 12 meses


def linea(*cols):
    print("| " + " | ".join(str(c) for c in cols) + " |")


def encabezado(*cols):
    linea(*cols)
    print("|" + "---|" * len(cols))


def _detectar_version_google():
    """Google retira versiones de la API ~cada año (síntoma: 404 HTML).

    Prueba de la más nueva a la más vieja hasta que una responda, ajustando
    el módulo del reporter en memoria (no toca configuración persistente).
    """
    for v in ("v27", "v26", "v25", "v24", "v23", "v22", "v21"):
        gads.GOOGLE_ADS_API_BASE = f"https://googleads.googleapis.com/{v}"
        if gads.get_account_summary() is not None:
            return v
    return None


def seccion_google():
    print(f"# Google Ads — últimos {DIAS_VENTANA} días — {date.today().isoformat()}\n")
    version = _detectar_version_google()
    if version is None:
        print("⚠️ Sin acceso a Google Ads API (credenciales ausentes/ inválidas "
              "o ninguna versión v21-v27 respondió). Sección omitida.\n")
        return
    print(f"_Versión de API detectada: {version}_\n")
    campañas = gads.get_campaigns_summary(days=DIAS_VENTANA)
    if campañas is None:
        print("⚠️ Campañas no disponibles pese a versión detectada. Sección omitida.\n")
        return

    print("## Campañas\n")
    encabezado("campaña", "estado", "impresiones", "clics", "CTR %",
               "gasto CLP", "conv.", "CPL CLP")
    for c in campañas:
        linea(c["name"], c["status"], c["impressions"], c["clicks"], c["ctr"],
              f"{c['spend_clp']:,.0f}", c["conversions"], f"{c['cpl_clp']:,.0f}")
    print()

    for c in campañas:
        if not c.get("impressions"):
            continue
        cid = c["id"]
        print(f"## Campaña: {c['name']} (id {cid})\n")

        kws = gads.get_keywords_performance(cid, days=DIAS_VENTANA, limit=100)
        if kws:
            print("### Keywords\n")
            encabezado("keyword", "match", "QS", "impresiones", "clics",
                       "CTR %", "gasto CLP", "conv.")
            for k in kws:
                linea(k["text"], k["match_type"], k.get("quality_score") or "—",
                      k["impressions"], k["clicks"], k["ctr"],
                      f"{k['spend_clp']:,.0f}", k["conversions"])
            print()

        terms = gads.get_search_terms_report(cid, days=DIAS_VENTANA, limit=300)
        if terms:
            print("### Términos de búsqueda reales\n")
            encabezado("término", "impresiones", "clics", "CTR %",
                       "gasto CLP", "conv.", "candidato negativa")
            for t in terms:
                linea(t["term"], t["impressions"], t["clicks"], t["ctr"],
                      f"{t['spend_clp']:,.0f}", t["conversions"],
                      "sí" if t["candidate_negative"] else "")
            print()


def seccion_meta():
    """Insights lifetime por campaña (date_preset=maximum).

    El listado de get_campaigns_summary trae `insights{}` sin rango de fechas
    y sale en cero cuando no hubo gasto en la ventana por defecto; por eso
    aquí se consulta el endpoint de insights de la cuenta con
    date_preset=maximum, que agrega TODO el historial de cada campaña.
    """
    print(f"\n# Meta Ads (lifetime por campaña) — {date.today().isoformat()}\n")
    for cuenta, etiqueta in (
        (meta.AD_ACCOUNT_PRINCIPAL, "cuenta principal (CLP)"),
        (meta.AD_ACCOUNT_BOOSTED_IG, "cuenta boosts IG (CLP)"),
    ):
        print(f"## {etiqueta} — {cuenta}\n")
        try:
            filas = []
            params = {
                "level": "campaign",
                "fields": "campaign_name,spend,impressions,clicks,ctr,actions",
                "date_preset": "maximum",
                "limit": 100,
            }
            data = meta._get(f"/{cuenta}/insights", params)
            filas.extend(data.get("data", []))
            # una página extra por si hay más de 100 campañas con gasto
            siguiente = (data.get("paging") or {}).get("next")
            if siguiente:
                import requests as _rq
                data2 = _rq.get(siguiente, timeout=30).json()
                filas.extend(data2.get("data", []))
        except Exception as exc:  # credenciales o permisos
            print(f"⚠️ Sin acceso: {exc}\n")
            continue
        if not filas:
            print("(sin campañas con gasto)\n")
            continue
        filas.sort(key=lambda r: float(r.get("spend") or 0), reverse=True)
        encabezado("campaña", "gasto", "impresiones", "clics", "CTR",
                   "leads", "mensajes", "link clicks")
        for r in filas[:40]:
            acciones = meta._extract_action_metrics(r.get("actions") or [])
            mensajes = next((int(a.get("value") or 0)
                             for a in (r.get("actions") or [])
                             if a.get("action_type") ==
                             "onsite_conversion.messaging_conversation_started_7d"), 0)
            linea(r.get("campaign_name"), f"{float(r.get('spend') or 0):,.0f}",
                  r.get("impressions"), r.get("clicks"), r.get("ctr"),
                  acciones["leads"], mensajes, acciones["link_clicks"])
        print()


if __name__ == "__main__":
    seccion_google()
    seccion_meta()
    print("\n_Fin del export. Solo métricas agregadas; sin datos personales._")
