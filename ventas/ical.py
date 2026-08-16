# -*- coding: utf-8 -*-
"""Calendario .ics por cabaña para Booking y Airbnb (H-106, Fase 1).

Lo que resuelve: hoy una cabaña se puede vender dos veces —una por Booking y
otra directo— porque los calendarios no se hablan. Publicando un .ics por
cabaña, las OTAs bloquean solas las fechas que Aremko ya vendió.

DOS TRAMPAS DEL MODELO, las dos verificadas contra producción el 2026-08-14 y
ninguna evidente leyendo el código:

1. Una estadía de N noches son N filas de `ReservaServicio`, una por noche, con
   el MISMO `servicio_id` y fechas consecutivas. No hay fecha de salida en la
   base: se deriva como «última noche + 1 día». Confirmado con las reservas
   6561 (Torre, 21 y 22 de agosto) y 6330 (Acantilado, 23 y 24 de julio).

2. Una reserva PUEDE cambiar de cabaña a mitad de la estadía. Existen casos
   reales —la 1170 usa TRES cabañas distintas—, así que los tramos se agrupan
   por (reserva, cabaña) y no por reserva. Un UID por reserva, como parecía
   natural, habría hecho que los eventos de dos cabañas se pisaran entre sí.

Y una tercera, que vive en `agenda_operativa_view.filtro_alojamiento()`:
`tipo_servicio='cabana'` incluye «Persona Adicional» y «Hora Adicional», que no
son lugares donde dormir. El filtro es compartido a propósito: la agenda y este
calendario tienen que contar exactamente las mismas noches.

Límite honesto, para que quede escrito donde se lea: iCal tiene latencia. Las
OTAs releen el calendario cada varios minutos u horas y ese reloj no lo
controlamos. La ventana de doble venta se achica mucho, pero no es cero. Sin
latencia solo se llega con un channel manager certificado, que es otra liga.
"""
from datetime import timedelta

from ventas.models import ReservaServicio, ServicioBloqueo
from ventas.views.agenda_operativa_view import filtro_alojamiento

# RFC 5545: las líneas se pliegan a 75 octetos. Los nombres de cabaña de Aremko
# no llegan ni cerca, pero el plegado igual se hace para no depender de eso.
_MAX_OCTETOS = 75


def _escapar(texto):
    """Coma, punto y coma y barra son separadores en iCal: van escapados."""
    return (str(texto or '')
            .replace('\\', '\\\\').replace(';', r'\;')
            .replace(',', r'\,').replace('\n', r'\n'))


def _plegar(linea):
    """Corta a 75 octetos con una continuación que empieza en espacio."""
    crudo = linea.encode('utf-8')
    if len(crudo) <= _MAX_OCTETOS:
        return linea
    partes, resto = [], crudo
    partes.append(resto[:_MAX_OCTETOS])
    resto = resto[_MAX_OCTETOS:]
    while resto:
        partes.append(resto[:_MAX_OCTETOS - 1])
        resto = resto[_MAX_OCTETOS - 1:]
    return '\r\n '.join(p.decode('utf-8', 'ignore') for p in partes)


def tramos_ocupados(servicio_id, desde=None):
    """Rangos ocupados de UNA cabaña: [(inicio, fin_exclusivo, uid, titulo)].

    `fin` es EXCLUSIVO, como manda iCal para eventos de día completo: una noche
    del 21 se publica como 21 → 22, que es la fecha de check-out real.

    Las noches sueltas de una misma reserva se parten en tramos distintos: si
    alguien reserva el 5 y el 20 en la misma cabaña, son dos estadías, no una
    de quince días con la cabaña bloqueada al medio.
    """
    filas = (ReservaServicio.objects
             # El filtro de alojamiento acá es redundante con `servicio_id`,
             # pero blinda contra que alguien pida el calendario de «Persona
             # Adicional»: devolvería fechas ocupadas que no son de una cabaña.
             .filter(servicio_id=servicio_id, venta_reserva__isnull=False,
                     **filtro_alojamiento())
             .exclude(venta_reserva__estado_reserva='cancelada')
             .select_related('venta_reserva'))
    if desde:
        filas = filas.filter(fecha_agendamiento__gte=desde)

    # Agrupar por (reserva, cabaña) — la clave del hallazgo 2.
    por_estadia = {}
    for f in filas:
        por_estadia.setdefault((f.venta_reserva_id, f.servicio_id), []).append(
            f.fecha_agendamiento)

    tramos = []
    for (venta_id, serv_id), noches in por_estadia.items():
        for inicio, ultima in _bloques_consecutivos(sorted(set(noches))):
            tramos.append((
                inicio, ultima + timedelta(days=1),
                f'reserva-{venta_id}-{serv_id}-{inicio.isoformat()}@aremko.cl',
                f'Reservado (RES-{venta_id})'))

    # `activo=True` no es un detalle: un bloqueo desactivado es una fecha que
    # Jorge volvió a abrir. Publicarlo igual dejaría la cabaña cerrada en
    # Booking para siempre, perdiendo ventas en silencio — el error opuesto a
    # la doble reserva, y más difícil de notar porque nadie reclama.
    bloqueos = ServicioBloqueo.objects.filter(servicio_id=servicio_id,
                                              activo=True)
    if desde:
        bloqueos = bloqueos.filter(fecha_fin__gte=desde)
    for b in bloqueos:
        # `fecha_fin` es INCLUSIVA (lo dice su help_text), así que se le suma uno
        # para el `fin` exclusivo de iCal. En producción los 93 bloqueos son de
        # UN día —`fecha_inicio == fecha_fin`, con `hora_slot='N/A'`—, o sea la
        # noche completa de esa cabaña; verificado el 2026-08-14.
        tramos.append((b.fecha_inicio, b.fecha_fin + timedelta(days=1),
                       f'bloqueo-{b.id}@aremko.cl', 'No disponible'))

    tramos.sort(key=lambda t: (t[0], t[2]))
    return tramos


def _bloques_consecutivos(fechas):
    """[(primera, ultima)] por cada corrida de días seguidos."""
    if not fechas:
        return []
    bloques, inicio, previa = [], fechas[0], fechas[0]
    for f in fechas[1:]:
        if (f - previa).days == 1:
            previa = f
            continue
        bloques.append((inicio, previa))
        inicio = previa = f
    bloques.append((inicio, previa))
    return bloques


def construir_ics(nombre_cabana, tramos, ahora=None):
    """VCALENDAR completo, con CRLF como exige el RFC."""
    from django.utils import timezone

    sello = (ahora or timezone.now()).strftime('%Y%m%dT%H%M%SZ')
    lineas = [
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        'PRODID:-//Aremko Spa//Calendario de cabanas//ES',
        'CALSCALE:GREGORIAN',
        'METHOD:PUBLISH',
        f'X-WR-CALNAME:{_escapar(nombre_cabana)} · Aremko',
    ]
    for inicio, fin, uid, titulo in tramos:
        lineas += [
            'BEGIN:VEVENT',
            f'UID:{uid}',
            f'DTSTAMP:{sello}',
            f'DTSTART;VALUE=DATE:{inicio.strftime("%Y%m%d")}',
            f'DTEND;VALUE=DATE:{fin.strftime("%Y%m%d")}',
            f'SUMMARY:{_escapar(titulo)}',
            'TRANSP:OPAQUE',
            'END:VEVENT',
        ]
    lineas.append('END:VCALENDAR')
    return '\r\n'.join(_plegar(l) for l in lineas) + '\r\n'
