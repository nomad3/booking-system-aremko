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


def ventanas_de_7_dias(desde, hasta):
    """[(inicio, fin)] de 7 días COMPLETOS, ancladas a `hasta` y hacia atrás.

    Pedido de Jorge (2026-08-18): «sería mejor que las semanas fueran todas
    completas, es decir la última, la vigente, los últimos 7 días y así hacia
    atrás».

    Con semanas de calendario (lunes a domingo) siempre quedaban dos ventanas a
    medias —la primera de la ventana y la que está corriendo— y sus porcentajes
    se leían como caídas: en la lectura real dieron 5,6% y 7,8% contra un ~12%
    estable. Con ventanas móviles todas duran lo mismo y se pueden comparar de
    frente. El costo es que sobran hasta 6 días al principio, que se descartan:
    es preferible perder unos días viejos antes que mostrar un número que
    invita a una conclusión falsa.
    """
    ventanas, fin = [], hasta
    while fin - timedelta(days=6) >= desde:
        ventanas.append((fin - timedelta(days=6), fin))
        fin -= timedelta(days=7)
    ventanas.reverse()
    return ventanas


def _pct(parte, total):
    return round(100 * parte / total, 1) if total else 0.0


def conversaciones_totales(desde, hasta):
    from ventas.models import WhatsAppMessage

    return (WhatsAppMessage.objects
            .filter(direction='in', timestamp__date__gte=desde,
                    timestamp__date__lte=hasta)
            .values('phone').distinct().count())


# El mínimo de mensajes entrantes para que una conversación sin cotizar valga
# la pena clasificar (P-31). Los de 1 mensaje suelen ser número equivocado o
# spam y cuestan lo mismo clasificar que los que importan.
MIN_MENSAJES_TEMA = 4


def candidatos_sin_cotizar(desde, hasta, min_mensajes=MIN_MENSAJES_TEMA):
    """[(telefono, n_mensajes, ultimo_mensaje)] — escribieron en la ventana,
    tuvieron conversación de verdad y NUNCA recibieron una cotización.

    Fuente única para el comando `clasificar_conversaciones` y para el panel
    de temas del embudo: si esta definición cambia, cambia en los dos lugares
    a la vez y no hay riesgo de que uno cuente distinto que el otro.

    «Nunca cotizó» va SIN ventana de fecha a propósito: alguien puede escribir
    hoy y haber recibido una cotización real hace un mes — eso no es una venta
    perdida, es una que ya se resolvió antes.
    """
    from ventas.models import WhatsAppMessage
    from whatsapp_agent.models import PropuestaReserva

    cotizaron = set(PropuestaReserva.objects
                    .filter(canal='whatsapp')
                    .values_list('external_id', flat=True))
    entrantes = {}
    for tel, ts in (WhatsAppMessage.objects
                    .filter(direction='in', timestamp__date__gte=desde,
                            timestamp__date__lte=hasta)
                    .values_list('phone', 'timestamp')):
        n, ultimo = entrantes.get(tel, (0, None))
        entrantes[tel] = (n + 1, max(ultimo, ts) if ultimo else ts)
    return [(t, n, u) for t, (n, u) in entrantes.items()
            if t not in cotizaron and n >= min_mensajes]


def temas_de_las_caidas(desde, hasta, tope=10):
    """Reparto de temas entre las conversaciones sin cotizar YA clasificadas.

    Declara su cobertura a propósito, mismo principio que el panel financiero
    de Jorge («un panel declara su cobertura»): si la ventana pedida es más
    ancha que la última corrida de `clasificar_conversaciones`, va a faltar
    clasificar una parte, y mostrar el reparto como si fuera completo
    escondería justo esa brecha.

    Sin plata: estas conversaciones nunca generaron una `PropuestaReserva`, así
    que no hay monto que sumarles — el número que importa acá es CUÁNTAS, no
    CUÁNTO.
    """
    from whatsapp_agent.models import TemaConversacion
    from whatsapp_agent.temas import VERSION_TAXONOMIA

    candidatos = candidatos_sin_cotizar(desde, hasta)
    telefonos = [t for t, _, _ in candidatos]
    clasificadas = list(TemaConversacion.objects
                        .filter(telefono__in=telefonos,
                                version_taxonomia=VERSION_TAXONOMIA))

    conteo = {}
    for c in clasificadas:
        conteo[c.tema] = conteo.get(c.tema, 0) + 1
    etiquetas = dict(TemaConversacion.TEMA_CHOICES)
    total = len(clasificadas)
    filas = [{'tema': k, 'nombre': etiquetas.get(k, k), 'n': v,
              'pct': _pct(v, total)}
             for k, v in conteo.items()]
    filas.sort(key=lambda f: -f['n'])

    total_candidatos = len(candidatos)
    return {
        'temas': filas[:tope],
        'total_sin_cotizar': total_candidatos,
        'total_clasificadas': total,
        'faltan_clasificar': max(total_candidatos - total, 0),
        'cobertura_pct': _pct(total, total_candidatos),
    }


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

    # Serie por ventanas móviles de 7 días: todas completas, comparables entre sí.
    ventanas = ventanas_de_7_dias(desde, hasta)
    semanas = []
    for ini, fin in ventanas:
        c = conversaciones_totales(ini, fin)
        q = r = 0
        for p in props:
            if ini <= p.created_at.date() <= fin:
                q += 1
                if estado_efectivo(p.estado, p.expires_at, ahora) == 'creada':
                    r += 1
        semanas.append({
            'desde': ini, 'hasta': fin, 'conversaciones': c,
            'cotizaciones': q, 'reservas': r,
            'pct_cotiza': _pct(q, c), 'pct_cierra': _pct(r, q),
        })

    plata_perdida = sum(plata_estado.get(e, 0) for e in ESTADOS_MUERTOS)
    d_temas = temas_de_las_caidas(desde, hasta)
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
        # Días viejos que no alcanzaron para una ventana entera.
        'dias_descartados': (ventanas[0][0] - desde).days if ventanas else 0,
        'servicios_que_mueren': servicios_que_mueren(props, ahora),
        'temas_que_no_cotizan': d_temas['temas'],
        'temas_total_sin_cotizar': d_temas['total_sin_cotizar'],
        'temas_total_clasificadas': d_temas['total_clasificadas'],
        'temas_faltan': d_temas['faltan_clasificar'],
        'temas_cobertura_pct': d_temas['cobertura_pct'],
    }
