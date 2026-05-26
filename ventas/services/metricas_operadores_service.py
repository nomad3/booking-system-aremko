"""
metricas_operadores_service
============================

Calcula métricas de atribución por operador para Operación Vuelta a Casa
(MVP solicitado por Jorge 2026-05-26 PM).

Modelo de atribución: **last-touch**.
    Una reserva se atribuye al ÚLTIMO ContactoWhatsApp enviado al mismo
    cliente cuya fecha_envio esté en (reserva.fecha_creacion - ventana_dias,
    reserva.fecha_creacion]. Si hay varios envíos en ventana, gana el más
    reciente.

Recalculo en vivo (NO usa el campo cacheado convirtio):
    El cron `cruzar_reservas_contactos_whatsapp` usa ventana 30d fija. Como
    el endpoint permite ventana configurable (default 60d), recalcular en
    vivo da datos correctos para cualquier ventana sin tocar el cron.

    Volumen actual ~50 envíos/día × 60d = ~3000 contactos máx por request.
    Si crece, materializar a tabla agregada AtribucionContacto.

Familia de servicios:
    Reutiliza `ClienteTaxonomia._mapear_categoria_a_familia()`. 5 valores:
    Tinas, Masajes, Cabañas, Ambientaciones, Otros.

Normalización de operador:
    `ContactoWhatsApp.operador` es CharField libre. Agrupamos por
    `operador.lower().strip()` para que "Deborah" / "deborah" / "DEBORAH"
    cuenten como uno solo. El display_name expuesto al frontend es el
    valor original más frecuente en el grupo (preserva capitalización
    que el frontend prefiera mostrar).

Test coverage: ver ventas/tests_metricas_operadores.py
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional

from django.utils import timezone

from ventas.models import (
    ClienteTaxonomia,
    ContactoWhatsApp,
    ReservaServicio,
    VentaReserva,
)


# Estados de VentaReserva.estado_pago que NO cuentan como conversión
ESTADOS_PAGO_DESCARTADOS = {'cancelado'}


def calcular_metricas_operadores(
    desde: date,
    hasta: date,
    ventana_atribucion_dias: int = 60,
) -> dict:
    """Calcula totales y ranking de operadores en el período.

    Args:
        desde: fecha inicial (inclusive) — filtro sobre fecha_envio del contacto
        hasta: fecha final (inclusive) — filtro sobre fecha_envio del contacto
        ventana_atribucion_dias: ventana hacia adelante desde fecha_envio para
            considerar reservas como atribuibles. Default 60 días.

    Returns:
        dict con shape definido en el brief MVP:
        {
          "periodo": {"desde": "YYYY-MM-DD", "hasta": "YYYY-MM-DD"},
          "ventana_atribucion_dias": int,
          "totales": {
            "mensajes_enviados": int,
            "respuestas": int,
            "tasa_respuesta": float (0.0-1.0),
            "reservas_atribuidas": int,
            "tasa_conversion": float (0.0-1.0),
            "monto_atribuido": int (CLP, sin decimales),
            "ticket_promedio_atribuido": int (CLP)
          },
          "operadores": [
            {
              "username": str (display name),
              "mensajes_enviados": int,
              "respuestas": int,
              "tasa_respuesta": float,
              "reservas_atribuidas": int,
              "tasa_conversion": float,
              "monto_atribuido": int,
              "ticket_promedio_atribuido": int,
              "familias_top": [
                {"familia": str, "reservas": int, "monto": int},
                ...  # hasta 3
              ]
            },
            ...  # ordenado por monto_atribuido DESC
          ]
        }

    Notas:
      - Operadores sin envíos en período NO aparecen (no podemos enumerarlos —
        no hay tabla de operadores). El brief pide "operador sin envíos
        aparece con 0", pero como no hay catálogo definido, el caller debe
        proveer la lista de operadores esperados si quiere mostrar ceros.
        En MVP solo retornamos los que efectivamente enviaron.
    """
    # Convert dates to timezone-aware datetimes for fecha_envio comparison
    # (fecha_envio es DateTimeField). Asumimos zona Santiago via TIME_ZONE.
    tz = timezone.get_current_timezone()
    desde_dt = datetime.combine(desde, datetime.min.time()).replace(tzinfo=tz)
    hasta_dt = datetime.combine(hasta, datetime.max.time()).replace(tzinfo=tz)

    # ──── Paso 1: contactos enviados en el período ────
    contactos_enviados = list(
        ContactoWhatsApp.objects
        .filter(
            estado='enviado',
            fecha_envio__gte=desde_dt,
            fecha_envio__lte=hasta_dt,
        )
        .values('id', 'cliente_id', 'fecha_envio', 'operador', 'respondio')
    )

    # ──── Paso 2: candidatos a reserva — todas las reservas no canceladas
    #            creadas en [desde, hasta + ventana_dias].
    # Una reserva creada despues de "hasta" puede atribuirse a un envío del
    # último día del período si está dentro de la ventana de 60d.
    reservas_hasta_dt = hasta_dt + timedelta(days=ventana_atribucion_dias)
    cliente_ids_enviados = {c['cliente_id'] for c in contactos_enviados}

    if cliente_ids_enviados:
        reservas = list(
            VentaReserva.objects
            .filter(
                cliente_id__in=cliente_ids_enviados,
                fecha_creacion__gte=desde_dt,
                fecha_creacion__lte=reservas_hasta_dt,
            )
            .exclude(estado_pago__in=ESTADOS_PAGO_DESCARTADOS)
            .values('id', 'cliente_id', 'fecha_creacion', 'total')
        )
    else:
        reservas = []

    # ──── Paso 3: atribución last-touch ────
    # Para cada reserva, buscar el contacto con MAYOR fecha_envio entre los
    # candidatos del mismo cliente que cumplan:
    #   contacto.fecha_envio <= reserva.fecha_creacion
    #   contacto.fecha_envio + ventana_dias >= reserva.fecha_creacion

    # Indexar contactos por cliente_id (lista ordenada por fecha_envio DESC)
    contactos_por_cliente: dict[int, list[dict]] = defaultdict(list)
    for c in contactos_enviados:
        contactos_por_cliente[c['cliente_id']].append(c)
    for lst in contactos_por_cliente.values():
        lst.sort(key=lambda c: c['fecha_envio'], reverse=True)  # más reciente primero

    # atribuciones: {reserva_id: contacto_dict}
    atribuciones: dict[int, dict] = {}
    ventana_td = timedelta(days=ventana_atribucion_dias)

    for r in reservas:
        cli_id = r['cliente_id']
        f_reserva = r['fecha_creacion']
        candidatos = contactos_por_cliente.get(cli_id, [])

        # Iterar del más reciente al más viejo, tomar el primero válido
        for c in candidatos:
            f_envio = c['fecha_envio']
            if f_envio > f_reserva:
                continue  # contacto posterior a la reserva — no aplica
            if (f_reserva - f_envio) > ventana_td:
                # Como están ordenados DESC por fecha_envio, todos los siguientes
                # estarán aún más viejos → break
                break
            # Match: este es el last-touch
            atribuciones[r['id']] = c
            break

    # ──── Paso 4: agregación por operador ────
    # Por operador normalizado (lowercase strip), acumulamos métricas.
    agg = defaultdict(lambda: {
        'mensajes_enviados': 0,
        'respuestas': 0,
        'reservas_atribuidas': 0,
        'monto_atribuido': 0,
        'reservas_ids': set(),     # para evitar doble conteo
        'display_names': Counter(),  # para elegir el display name del grupo
    })

    for c in contactos_enviados:
        op_raw = (c['operador'] or '').strip()
        op_key = op_raw.lower()
        if not op_key:
            op_key = '(sin operador)'
            op_raw = '(sin operador)'
        agg[op_key]['mensajes_enviados'] += 1
        agg[op_key]['display_names'][op_raw] += 1
        if c['respondio']:
            agg[op_key]['respuestas'] += 1

    # Reverse index: contacto_id → (op_key, contacto_dict)
    contacto_a_opkey: dict[int, str] = {}
    for c in contactos_enviados:
        op = (c['operador'] or '').strip().lower() or '(sin operador)'
        contacto_a_opkey[c['id']] = op

    # Acumular reservas atribuidas por operador
    reservas_por_id = {r['id']: r for r in reservas}
    for reserva_id, contacto in atribuciones.items():
        op_key = contacto_a_opkey[contacto['id']]
        r = reservas_por_id[reserva_id]
        monto = int(r['total'] or 0)
        agg[op_key]['reservas_atribuidas'] += 1
        agg[op_key]['monto_atribuido'] += monto
        agg[op_key]['reservas_ids'].add(reserva_id)

    # ──── Paso 5: familias_top por operador ────
    # Cargar servicios de las reservas atribuidas para mapear familias.
    todas_reservas_atribuidas = {rid for rid, _ in atribuciones.items()}
    familias_por_operador: dict[str, dict[str, dict]] = defaultdict(
        lambda: defaultdict(lambda: {'reservas': 0, 'monto': 0})
    )

    if todas_reservas_atribuidas:
        # Para cada ReservaServicio dentro de las reservas atribuidas,
        # mapear familia + contar reserva + sumar monto.
        # Una reserva puede tener varios servicios: agrupamos por familia única
        # por reserva (no contamos 1 reserva como 3 si tiene 3 servicios de la
        # misma familia). El monto se atribuye a la familia "dominante"
        # (primera encontrada por reserva).
        reserva_servicios = (
            ReservaServicio.objects
            .filter(venta_reserva_id__in=todas_reservas_atribuidas)
            .select_related('servicio', 'servicio__categoria')
            .values(
                'venta_reserva_id',
                'servicio__tipo_servicio',
                'servicio__categoria__nombre',
            )
        )
        # Agrupar familias presentes en cada reserva
        familias_por_reserva: dict[int, set[str]] = defaultdict(set)
        for rs in reserva_servicios:
            categoria_nombre = rs['servicio__categoria__nombre'] or ''
            tipo = rs['servicio__tipo_servicio'] or ''
            familia = ClienteTaxonomia._mapear_categoria_a_familia(
                categoria_nombre, tipo
            )
            familias_por_reserva[rs['venta_reserva_id']].add(familia)

        # Para cada reserva atribuida, contar reserva en cada familia presente
        # y sumar monto / N_familias para no inflar el total.
        for reserva_id, contacto in atribuciones.items():
            op_key = contacto_a_opkey[contacto['id']]
            r = reservas_por_id[reserva_id]
            monto_total_reserva = int(r['total'] or 0)
            familias_set = familias_por_reserva.get(reserva_id) or {'Otros'}
            n_familias = len(familias_set)
            monto_por_familia = monto_total_reserva // n_familias  # entero
            for fam in familias_set:
                familias_por_operador[op_key][fam]['reservas'] += 1
                familias_por_operador[op_key][fam]['monto'] += monto_por_familia

    # ──── Paso 6: construir response ────
    operadores_out = []
    for op_key, stats in agg.items():
        display_name = stats['display_names'].most_common(1)[0][0] if stats['display_names'] else op_key
        n_enviados = stats['mensajes_enviados']
        n_respuestas = stats['respuestas']
        n_reservas = stats['reservas_atribuidas']
        monto = stats['monto_atribuido']

        # Top 3 familias por monto
        familias_dict = familias_por_operador.get(op_key, {})
        familias_top = sorted(
            [
                {'familia': fam, 'reservas': d['reservas'], 'monto': d['monto']}
                for fam, d in familias_dict.items()
            ],
            key=lambda x: (-x['monto'], -x['reservas'], x['familia']),
        )[:3]

        operadores_out.append({
            'username': display_name,
            'mensajes_enviados': n_enviados,
            'respuestas': n_respuestas,
            'tasa_respuesta': round(n_respuestas / n_enviados, 3) if n_enviados else 0.0,
            'reservas_atribuidas': n_reservas,
            'tasa_conversion': round(n_reservas / n_enviados, 3) if n_enviados else 0.0,
            'monto_atribuido': monto,
            'ticket_promedio_atribuido': round(monto / n_reservas) if n_reservas else 0,
            'familias_top': familias_top,
        })

    operadores_out.sort(key=lambda o: -o['monto_atribuido'])

    # Totales globales
    t_enviados = sum(o['mensajes_enviados'] for o in operadores_out)
    t_respuestas = sum(o['respuestas'] for o in operadores_out)
    t_reservas = sum(o['reservas_atribuidas'] for o in operadores_out)
    t_monto = sum(o['monto_atribuido'] for o in operadores_out)

    return {
        'periodo': {
            'desde': desde.isoformat(),
            'hasta': hasta.isoformat(),
        },
        'ventana_atribucion_dias': ventana_atribucion_dias,
        'totales': {
            'mensajes_enviados': t_enviados,
            'respuestas': t_respuestas,
            'tasa_respuesta': round(t_respuestas / t_enviados, 3) if t_enviados else 0.0,
            'reservas_atribuidas': t_reservas,
            'tasa_conversion': round(t_reservas / t_enviados, 3) if t_enviados else 0.0,
            'monto_atribuido': t_monto,
            'ticket_promedio_atribuido': round(t_monto / t_reservas) if t_reservas else 0,
        },
        'operadores': operadores_out,
    }
