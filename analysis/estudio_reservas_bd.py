#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Micrositios Fase 1 — agregados de reservas desde la BD (SOLO LECTURA).

Imprime a stdout un informe markdown 100% agregado y anónimo: sin nombres,
teléfonos, emails ni IDs de cliente. No escribe nada en la base de datos.

Uso (shell de Render):
    python analysis/estudio_reservas_bd.py > /tmp/estudio_reservas.md
    cat /tmp/estudio_reservas.md
"""
import os
import statistics
import sys
from collections import Counter, defaultdict
from datetime import date, timedelta

import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "aremko_project.settings")
django.setup()

from ventas.models import (  # noqa: E402
    EncuestaSatisfaccion,
    GiftCard,
    Pago,
    RefugioLead,
    ReservaServicio,
    VentaReserva,
)

MESES = ["ene", "feb", "mar", "abr", "may", "jun",
         "jul", "ago", "sep", "oct", "nov", "dic"]
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
DESDE = date.today() - timedelta(days=730)  # 24 meses


def linea(*cols):
    print("| " + " | ".join(str(c) for c in cols) + " |")


def encabezado(*cols):
    linea(*cols)
    print("|" + "---|" * len(cols))


def pct(parte, todo):
    return f"{100.0 * parte / todo:.1f}%" if todo else "—"


def main():
    print(f"# Estudio de reservas (BD, solo lectura) — {date.today().isoformat()}\n")
    print(f"Ventana principal: últimos 24 meses (desde {DESDE.isoformat()}).\n")

    # ------------------------------------------------------------------
    # Base: ReservaServicio con tipo, fechas y precio congelado
    # ------------------------------------------------------------------
    filas = list(
        ReservaServicio.objects
        .filter(fecha_agendamiento__gte=DESDE)
        .exclude(fecha_agendamiento=None)
        .values_list(
            "servicio__tipo_servicio",
            "servicio__nombre",
            "fecha_agendamiento",
            "hora_inicio",
            "cantidad_personas",
            "precio_unitario_venta",
            "servicio__precio_base",
            "venta_reserva__fecha_creacion",
        )
    )
    print(f"Servicios reservados en la ventana: **{len(filas)}**\n")

    # ------------------------------------------------------------------
    # 1. Volumen y revenue por tipo de servicio y mes
    # ------------------------------------------------------------------
    print("## 1. Reservas por tipo de servicio y mes\n")
    por_mes = defaultdict(lambda: [0, 0, 0.0])  # (YYYY-MM, tipo) -> [n, personas, rev]
    for tipo, _n, fecha, _h, personas, precio, precio_base, _fc in filas:
        precio_unit = precio if precio is not None else (precio_base or 0)
        key = (f"{fecha.year}-{fecha.month:02d}", tipo or "otro")
        por_mes[key][0] += 1
        por_mes[key][1] += personas or 0
        por_mes[key][2] += float(precio_unit) * (personas or 1)
    encabezado("año-mes", "tipo", "reservas", "personas", "revenue CLP (estimado)")
    for (ym, tipo), (n, p, rev) in sorted(por_mes.items()):
        linea(ym, tipo, n, p, f"{rev:,.0f}")
    print()

    # ------------------------------------------------------------------
    # 2. Anticipación de reserva (creación de la venta vs fecha del servicio)
    # ------------------------------------------------------------------
    print("## 2. Anticipación de reserva por tipo (días entre compra y servicio)\n")
    anticipacion = defaultdict(list)
    for tipo, _n, fecha, _h, _p, _pr, _pb, fecha_creacion in filas:
        if fecha_creacion is None:
            continue
        dias = (fecha - fecha_creacion.date()).days
        if -1 <= dias <= 365:  # descarta datos corruptos
            anticipacion[tipo or "otro"].append(dias)
    encabezado("tipo", "n", "mismo día", "≤1 día", "≤7 días", "≤30 días",
               "mediana", "p75", "p90")
    for tipo, valores in sorted(anticipacion.items()):
        valores.sort()
        n = len(valores)
        if not n:
            continue
        linea(
            tipo, n,
            pct(sum(1 for v in valores if v <= 0), n),
            pct(sum(1 for v in valores if v <= 1), n),
            pct(sum(1 for v in valores if v <= 7), n),
            pct(sum(1 for v in valores if v <= 30), n),
            f"{statistics.median(valores):.0f}d",
            f"{valores[int(n * 0.75)]}d",
            f"{valores[int(n * 0.90)]}d",
        )
    print()

    # ------------------------------------------------------------------
    # 3. Día de semana y hora de inicio
    # ------------------------------------------------------------------
    print("## 3. Día de semana por tipo\n")
    dow = defaultdict(Counter)
    horas = defaultdict(Counter)
    for tipo, _n, fecha, hora, _p, _pr, _pb, _fc in filas:
        dow[tipo or "otro"][fecha.weekday()] += 1
        if hora:
            horas[tipo or "otro"][hora[:2]] += 1
    encabezado("tipo", *DIAS)
    for tipo, c in sorted(dow.items()):
        total = sum(c.values())
        linea(tipo, *[pct(c.get(d, 0), total) for d in range(7)])
    print("\n### Hora de inicio (top 5 por tipo)\n")
    encabezado("tipo", "horas más reservadas")
    for tipo, c in sorted(horas.items()):
        top = ", ".join(f"{h}h ({n})" for h, n in c.most_common(5))
        linea(tipo, top)
    print()

    # ------------------------------------------------------------------
    # 4. Top servicios últimos 12 meses
    # ------------------------------------------------------------------
    print("## 4. Top servicios (últimos 12 meses)\n")
    hace_12m = date.today() - timedelta(days=365)
    top = Counter()
    for tipo, nombre, fecha, _h, _p, _pr, _pb, _fc in filas:
        if fecha >= hace_12m:
            top[(nombre, tipo or "otro")] += 1
    encabezado("servicio", "tipo", "reservas 12m")
    for (nombre, tipo), n in top.most_common(25):
        linea(nombre, tipo, n)
    print()

    # ------------------------------------------------------------------
    # 5. Proxy de canal: métodos de pago por mes
    # ------------------------------------------------------------------
    print("## 5. Proxy de canal (métodos de pago, últimos 24 meses)\n")
    print("`flow/webpay/mercadopago*` ⇒ checkout web · `booking` ⇒ OTA · "
          "resto ⇒ admin/recepción/transferencia.\n")
    pagos = (
        Pago.objects.filter(fecha_pago__date__gte=DESDE)
        .values_list("fecha_pago", "metodo_pago", "monto", "usuario_id")
    )
    canal_mes = defaultdict(lambda: Counter())
    web_admin = Counter()
    for fp, metodo, monto, usuario_id in pagos:
        ym = f"{fp.year}-{fp.month:02d}"
        if metodo in ("flow", "webpay", "mercadopago", "mercadopago_link"):
            canal = "web"
        elif metodo == "booking":
            canal = "OTA"
        elif metodo == "giftcard":
            canal = "giftcard"
        else:
            canal = "manual/otros"
        canal_mes[ym][canal] += 1
        web_admin["registrado_por_staff" if usuario_id else "sin_usuario"] += 1
    encabezado("año-mes", "web", "OTA", "giftcard", "manual/otros")
    for ym, c in sorted(canal_mes.items()):
        linea(ym, c.get("web", 0), c.get("OTA", 0), c.get("giftcard", 0),
              c.get("manual/otros", 0))
    total_pagos = sum(web_admin.values())
    print(f"\nPagos registrados por staff (proxy admin): "
          f"{pct(web_admin['registrado_por_staff'], total_pagos)} de {total_pagos}.\n")

    # Ventas nacidas del checkout web (PendingReservation)
    ventas_24m = VentaReserva.objects.filter(fecha_creacion__date__gte=DESDE)
    con_pending = ventas_24m.filter(pending_origin__isnull=False).count()
    total_ventas = ventas_24m.count()
    print(f"Ventas con origen checkout web comprobado (PendingReservation): "
          f"**{con_pending} de {total_ventas}** ({pct(con_pending, total_ventas)}).\n")

    # ------------------------------------------------------------------
    # 6. Atribución declarada (EncuestaSatisfaccion.como_se_entero)
    # ------------------------------------------------------------------
    print("## 6. ¿Cómo se enteró? (encuesta post-visita)\n")
    encuesta = Counter(
        EncuestaSatisfaccion.objects.exclude(como_se_entero="")
        .exclude(como_se_entero=None)
        .values_list("como_se_entero", flat=True)
    )
    total_enc = sum(encuesta.values())
    encabezado("canal declarado", "n", "%")
    for canal, n in encuesta.most_common():
        linea(canal, n, pct(n, total_enc))
    print()

    # ------------------------------------------------------------------
    # 7. Leads Refugio por UTM (sin datos personales)
    # ------------------------------------------------------------------
    print("## 7. RefugioLead por UTM\n")
    leads = RefugioLead.objects.values_list("utm_source", "utm_campaign", "status")
    src = Counter()
    camp = Counter()
    status = Counter()
    for s, c, st in leads:
        src[s or "(sin utm)"] += 1
        camp[c or "(sin utm)"] += 1
        status[st] += 1
    encabezado("utm_source", "n")
    for k, n in src.most_common():
        linea(k, n)
    print()
    encabezado("utm_campaign", "n")
    for k, n in camp.most_common():
        linea(k, n)
    print()
    encabezado("status", "n")
    for k, n in status.most_common():
        linea(k, n)
    print()

    # ------------------------------------------------------------------
    # 8. Gift cards emitidas por mes (motivo regalo)
    # ------------------------------------------------------------------
    print("## 8. Gift cards emitidas por mes\n")
    gc = GiftCard.objects.filter(fecha_emision__gte=DESDE).values_list(
        "fecha_emision", "monto_inicial")
    gc_mes = defaultdict(lambda: [0, 0.0])
    for fe, monto in gc:
        ym = f"{fe.year}-{fe.month:02d}"
        gc_mes[ym][0] += 1
        gc_mes[ym][1] += float(monto or 0)
    encabezado("año-mes", "emitidas", "monto total CLP")
    for ym, (n, monto) in sorted(gc_mes.items()):
        linea(ym, n, f"{monto:,.0f}")
    print("\n_Fin del informe. Ningún dato personal fue exportado._")


if __name__ == "__main__":
    main()
