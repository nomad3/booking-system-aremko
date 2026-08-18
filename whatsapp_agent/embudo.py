# -*- coding: utf-8 -*-
"""Embudo de las conversaciones de Luna por WhatsApp (P-30, Fase 1).

Contesta con datos que YA existen: de cada 100 personas que escriben, cuántas
llegan a cotización y cuántas terminan reservando — y cuánta plata se cae en
cada escalón.

Tres decisiones que vale la pena tener escritas, las tres salidas de medir
producción el 2026-08-17 y no de suponer:

1. **Solo WhatsApp.** Instagram y Messenger juntaron 473 conversaciones y
   produjeron 2 cotizaciones (0,4%); WhatsApp, 265 de 267. Mezclarlos diluiría
   el embudo con tráfico que no cotiza. Cuando se entienda qué pasa en esos dos
   canales tendrán su propia vista.

2. **El estado se calcula al vuelo, no se cree el guardado.** Una propuesta
   `pendiente` cuyo `expires_at` ya pasó ES una expirada, corriera o no el
   comando `expirar_propuestas_vencidas`. Medido: 55 de 56 «pendientes» estaban
   vencidas, la más vieja de dos meses atrás. Un tablero que depende de que un
   cron haya corrido miente el día que el cron falla, y encima en silencio.

3. **Descartada ≠ expirada.** Son causas de muerte distintas: la descartada es
   un «no» del cliente (problema de oferta o precio); la expirada se apagó sin
   decisión en 24 horas (problema de seguimiento). Sumarlas en «no vendidas»
   esconde justo lo que hay que arreglar.
"""
from datetime import date, timedelta

from django.db.models import Count, Sum
from django.db.models.functions import TruncWeek

# La tabla arranca con UN mensaje de 2017 del teléfono +1 631 555 1181 — el
# webhook de PRUEBA de Meta (el prefijo 555 es el falso de manual). Una fila
# entre 37.361, pero deforma cualquier serie por semana si se cuela.
INICIO_DATOS_REALES = date(2026, 6, 1)

ESTADOS_MUERTOS = ('descartada', 'expirada')


def estado_efectivo(estado, expires_at, ahora):
    """El estado REAL, sin depender de que el cron de expiración haya corrido."""
    if estado == 'pendiente' and expires_at and expires_at < ahora:
        return 'expirada'
    return estado


def _lunes(d):
    """El lunes de la semana de `d` — la etiqueta de cada bucket."""
    return d - timedelta(days=d.weekday())


def _pct(parte, total):
    return round(100 * parte / total, 1) if total else 0.0


def conversaciones_por_semana(desde, hasta):
    """{lunes: nº de teléfonos distintos que escribieron esa semana}.

    Cuenta ENTRANTES: una conversación existe cuando alguien nos habla. Los
    salientes solos son campañas, no demanda. Un teléfono activo dos semanas
    cuenta en las dos — es «conversaciones activas por semana», no altas.
    """
    from ventas.models import WhatsAppMessage

    filas = (WhatsAppMessage.objects
             .filter(direction='in', timestamp__date__gte=desde,
                     timestamp__date__lte=hasta)
             .annotate(sem=TruncWeek('timestamp'))
             .values('sem')
             .annotate(n=Count('phone', distinct=True)))
    return {_lunes(f['sem'].date()): f['n'] for f in filas if f['sem']}


def conversaciones_totales(desde, hasta):
    from ventas.models import WhatsAppMessage

    return (WhatsAppMessage.objects
            .filter(direction='in', timestamp__date__gte=desde,
                    timestamp__date__lte=hasta)
            .values('phone').distinct().count())


def _propuestas(desde, hasta):
    from whatsapp_agent.models import PropuestaReserva

    return (PropuestaReserva.objects
            .filter(canal='whatsapp', created_at__date__gte=desde,
                    created_at__date__lte=hasta)
            .only('estado', 'expires_at', 'created_at', 'total', 'servicios',
                  'payload'))


def servicios_que_mueren(propuestas, ahora, tope=10):
    """En cuántas cotizaciones CAÍDAS aparece cada servicio.

    Cuenta apariciones, no plata: una cotización con tres servicios no permite
    decir cuál de los tres la mató, y repartir el monto entre los tres sería
    inventar una precisión que no tenemos.
    """
    from ventas.models import Servicio

    conteo = {}
    for p in propuestas:
        if estado_efectivo(p.estado, p.expires_at, ahora) not in ESTADOS_MUERTOS:
            continue
        ids = [s.get('servicio_id') for s in (p.servicios or [])
               if isinstance(s, dict) and s.get('servicio_id')]
        if ids:
            for sid in set(ids):
                conteo[sid] = conteo.get(sid, 0) + 1
        elif (p.payload or {}).get('giftcards'):
            # Las gift cards no llevan servicio_id: van a su propia fila.
            conteo['giftcard'] = conteo.get('giftcard', 0) + 1

    nombres = dict(Servicio.objects
                   .filter(id__in=[k for k in conteo if k != 'giftcard'])
                   .values_list('id', 'nombre'))
    filas = [{'nombre': 'Gift Card' if k == 'giftcard'
                        else nombres.get(k, f'Servicio {k} (borrado)'), 'n': v}
             for k, v in conteo.items()]
    filas.sort(key=lambda f: (-f['n'], f['nombre']))
    return filas[:tope]


def embudo(desde, hasta, ahora):
    """El cuadro completo para el tablero. `ahora` entra por parámetro para
    que los tests puedan fijar el reloj."""
    desde = max(desde, INICIO_DATOS_REALES)
    props = list(_propuestas(desde, hasta))

    por_estado, plata_estado = {}, {}
    for p in props:
        e = estado_efectivo(p.estado, p.expires_at, ahora)
        por_estado[e] = por_estado.get(e, 0) + 1
        plata_estado[e] = plata_estado.get(e, 0) + int(p.total or 0)

    convs = conversaciones_totales(desde, hasta)
    cotiz = len(props)
    reservas = por_estado.get('creada', 0)

    # Serie semanal: un bucket por lunes, aunque alguna fuente no tenga datos.
    conv_sem = conversaciones_por_semana(desde, hasta)
    cot_sem, res_sem = {}, {}
    for p in props:
        lun = _lunes(p.created_at.date())
        cot_sem[lun] = cot_sem.get(lun, 0) + 1
        if estado_efectivo(p.estado, p.expires_at, ahora) == 'creada':
            res_sem[lun] = res_sem.get(lun, 0) + 1

    semanas = []
    for lun in sorted(set(conv_sem) | set(cot_sem) | set(res_sem)):
        c, q, r = conv_sem.get(lun, 0), cot_sem.get(lun, 0), res_sem.get(lun, 0)
        semanas.append({
            'semana': lun, 'conversaciones': c, 'cotizaciones': q, 'reservas': r,
            'pct_cotiza': _pct(q, c), 'pct_cierra': _pct(r, q),
        })

    plata_perdida = sum(plata_estado.get(e, 0) for e in ESTADOS_MUERTOS)
    return {
        'desde': desde, 'hasta': hasta,
        'conversaciones': convs, 'cotizaciones': cotiz, 'reservas': reservas,
        'pct_conv_a_cotiza': _pct(cotiz, convs),
        'pct_cotiza_a_reserva': _pct(reservas, cotiz),
        'pct_conv_a_reserva': _pct(reservas, convs),
        'por_estado': [
            {'estado': e, 'n': n, 'plata': plata_estado.get(e, 0)}
            for e, n in sorted(por_estado.items(), key=lambda kv: -kv[1])],
        'plata_cotizada': sum(plata_estado.values()),
        'plata_cerrada': plata_estado.get('creada', 0),
        'plata_perdida': plata_perdida,
        'plata_sin_decision': plata_estado.get('expirada', 0),
        'plata_rechazada': plata_estado.get('descartada', 0),
        'semanas': semanas,
        'servicios_que_mueren': servicios_que_mueren(props, ahora),
    }
