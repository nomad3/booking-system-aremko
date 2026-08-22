#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Micrositios Fase 1 — análisis del histórico local de servicios (2020-2024).

Lee data/servicios_historicos.csv y genera agregados ANÓNIMOS (sin nombres,
teléfonos ni emails) en analysis/output/. No toca la base de datos.

Uso:
    python analysis/estudio_historico_csv.py
"""
import csv
import os
import re
from collections import Counter, defaultdict
from datetime import date

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(BASE_DIR, "data", "servicios_historicos.csv")
OUT_DIR = os.path.join(BASE_DIR, "analysis", "output")

MESES = ["ene", "feb", "mar", "abr", "may", "jun",
         "jul", "ago", "sep", "oct", "nov", "dic"]
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]

# Filas que no son servicios reales
EXCLUIR = re.compile(r"anulado|eliminado", re.IGNORECASE)


def parse_fecha(raw):
    """Acepta 'YYYY-MM-DD' y 'DD/MM/YYYY'. Devuelve date o None."""
    raw = (raw or "").strip()
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", raw)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    else:
        m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", raw)
        if not m:
            return None
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        f = date(y, mo, d)
    except ValueError:
        return None
    # El histórico cubre 2020-2024; algunas filas 2025 son reservas anticipadas
    if not (2019 <= f.year <= 2025):
        return None
    return f


def norm_categoria(raw):
    c = (raw or "").strip().lower()
    if c.startswith("tina"):
        return "Tinas"
    if c.startswith("masaje"):
        return "Masajes"
    if c.startswith("caba"):
        return "Cabañas"
    if c.startswith("ambient"):
        return "Ambientaciones"
    return "Otros/sin categoría"


def parse_valor(raw):
    raw = re.sub(r"[^\d]", "", raw or "")
    return int(raw) if raw else 0


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    filas_total = 0
    filas_ok = 0
    sin_fecha = 0
    excluidas = 0

    por_mes_cat = defaultdict(lambda: [0, 0])       # (YYYY-MM, cat) -> [n, revenue]
    estacionalidad = defaultdict(lambda: [0, 0])    # (mes 1-12, cat) -> [n, revenue]
    dia_semana = defaultdict(lambda: [0, 0])        # (weekday, cat) -> [n, revenue]
    top_servicios = defaultdict(lambda: [0, 0])     # (servicio, cat) -> [n, revenue]
    por_anio_cat = defaultdict(lambda: [0, 0])      # (año, cat) -> [n, revenue]

    with open(CSV_PATH, encoding="utf-8", errors="replace") as f:
        for row in csv.DictReader(f):
            filas_total += 1
            servicio = (row.get("servicio") or "").strip()
            if not servicio or EXCLUIR.search(servicio):
                excluidas += 1
                continue
            fecha = parse_fecha(row.get("checkin"))
            if fecha is None:
                sin_fecha += 1
                continue
            filas_ok += 1
            cat = norm_categoria(row.get("categoria"))
            # 'valor' ya es el monto TOTAL de la línea (verificado contra
            # precios de la época: masaje x2 = $38.000, tina 2 pers = $40.000).
            # 'cantidad' son personas/unidades y NO multiplica el valor.
            revenue = parse_valor(row.get("valor"))

            ym = f"{fecha.year}-{fecha.month:02d}"
            for key, bucket in (
                ((ym, cat), por_mes_cat),
                ((fecha.month, cat), estacionalidad),
                ((fecha.weekday(), cat), dia_semana),
                ((servicio, cat), top_servicios),
                ((fecha.year, cat), por_anio_cat),
            ):
                bucket[key][0] += 1
                bucket[key][1] += revenue

    def dump(nombre, encabezado, filas):
        path = os.path.join(OUT_DIR, nombre)
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(encabezado)
            w.writerows(filas)
        return path

    dump("historico_por_mes_categoria.csv",
         ["anio_mes", "categoria", "n_servicios", "revenue_clp"],
         [(k[0], k[1], v[0], v[1]) for k, v in sorted(por_mes_cat.items())])

    dump("historico_estacionalidad.csv",
         ["mes", "categoria", "n_servicios", "revenue_clp"],
         [(MESES[k[0] - 1], k[1], v[0], v[1])
          for k, v in sorted(estacionalidad.items())])

    dump("historico_dia_semana.csv",
         ["dia", "categoria", "n_servicios", "revenue_clp"],
         [(DIAS[k[0]], k[1], v[0], v[1]) for k, v in sorted(dia_semana.items())])

    dump("historico_top_servicios.csv",
         ["servicio", "categoria", "n_servicios", "revenue_clp", "ticket_promedio_clp"],
         [(k[0], k[1], v[0], v[1], round(v[1] / v[0]) if v[0] else 0)
          for k, v in sorted(top_servicios.items(), key=lambda x: -x[1][0])
          if v[0] >= 20])

    dump("historico_por_anio.csv",
         ["anio", "categoria", "n_servicios", "revenue_clp"],
         [(k[0], k[1], v[0], v[1]) for k, v in sorted(por_anio_cat.items())])

    # Resumen en consola
    print(f"Filas totales: {filas_total} · usadas: {filas_ok} · "
          f"sin fecha válida: {sin_fecha} · excluidas (anulado/eliminado/vacío): {excluidas}")
    print("\nPor categoría (todo el período):")
    tot_cat = defaultdict(lambda: [0, 0])
    for (_, cat), v in por_anio_cat.items():
        tot_cat[cat][0] += v[0]
        tot_cat[cat][1] += v[1]
    for cat, v in sorted(tot_cat.items(), key=lambda x: -x[1][0]):
        print(f"  {cat:22s} n={v[0]:6d}  revenue=${v[1]:,.0f}  "
              f"ticket=${v[1] / v[0]:,.0f}".replace(",", "."))
    print(f"\nSalidas en {OUT_DIR}/")


if __name__ == "__main__":
    main()
