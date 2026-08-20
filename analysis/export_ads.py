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


def seccion_google():
    print(f"# Google Ads — últimos {DIAS_VENTANA} días — {date.today().isoformat()}\n")
    campañas = gads.get_campaigns_summary(days=DIAS_VENTANA)
    if campañas is None:
        print("⚠️ Sin acceso a Google Ads API (credenciales GOOGLE_ADS_* "
              "ausentes o inválidas). Sección omitida.\n")
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
    print(f"\n# Meta Ads — {date.today().isoformat()}\n")
    for cuenta, etiqueta in (
        (meta.AD_ACCOUNT_PRINCIPAL, "cuenta principal (CLP)"),
        (meta.AD_ACCOUNT_BOOSTED_IG, "cuenta boosts IG (CLP)"),
    ):
        print(f"## {etiqueta} — {cuenta}\n")
        try:
            campañas = meta.get_campaigns_summary(account_id=cuenta, limit=50)
        except Exception as exc:  # credenciales o permisos
            print(f"⚠️ Sin acceso: {exc}\n")
            continue
        if not campañas:
            print("(sin campañas)\n")
            continue
        encabezado("campaña", "estado", "objetivo", "creada", "gasto",
                   "impresiones", "clics", "CTR")
        for c in campañas:
            linea(c.get("name"), c.get("status"), c.get("objective"),
                  (c.get("created_time") or "")[:10],
                  f"{c.get('spend', 0):,.0f}", c.get("impressions", 0),
                  c.get("clicks", 0), c.get("ctr", 0))
        print()
        try:
            detalle = meta.get_active_campaigns_detail(
                account_id=cuenta, days=28, max_campaigns=10)
        except Exception as exc:
            print(f"⚠️ Detalle no disponible: {exc}\n")
            continue
        if detalle:
            print("### Campañas activas (28 días): totales\n")
            for d in detalle:
                print(f"**{d.get('name')}** (inicio hace "
                      f"{d.get('days_since_start')} días)\n")
                totals = d.get("totals") or {}
                encabezado("métrica", "valor")
                for clave, valor in totals.items():
                    if valor not in (None, "", 0):
                        linea(clave, valor)
                print()


if __name__ == "__main__":
    seccion_google()
    seccion_meta()
    print("\n_Fin del export. Solo métricas agregadas; sin datos personales._")
