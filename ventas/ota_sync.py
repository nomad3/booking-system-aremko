# -*- coding: utf-8 -*-
"""Importación de calendarios de las OTAs (H-106 Fase 2, P-27).

La otra mitad del espejo: `ventas/ical.py` PUBLICA lo ocupado en Aremko; este
módulo LEE lo que Booking/Airbnb publican y lo convierte en `ServicioBloqueo`,
para que una venta en Booking cierre la cabaña acá. Como los dos motores de
disponibilidad (calendario matriz —que reusa Luna— y el candado del checkout)
ya filtran bloqueos por rango `fecha_inicio ≤ día ≤ fecha_fin`, espejar sobre
esa tabla cierra la venta en TODOS los canales sin tocar el motor.

Tres reglas de diseño, cada una con su motivo:

1. **Espejar, no acumular.** Cada corrida borra los bloqueos `[OTA]` de la
   cabaña y los recrea desde el feed. Si la reserva desaparece del calendario
   de la OTA (cancelación), el bloqueo desaparece acá solo. Un importador que
   solo agrega va cerrando la cabaña para siempre y nadie lo nota: no hay
   reclamo por una venta que simplemente no ocurrió.

2. **Una lectura fallida no toca nada.** Si el feed no responde o no parsea,
   esa cabaña queda COMO ESTÁ y se sigue con las demás. Reconstruir con un
   feed a medias liberaría noches vendidas — una caída de Booking no puede
   abrir el calendario. `ultima_lectura_ok` solo avanza con lectura completa.

3. **El export excluye lo importado.** `tramos_ocupados` salta los bloqueos
   `[OTA]`; sin eso, la reserva de Booking volvería a Booking como evento
   externo (eco). Los bloqueos manuales de Jorge no llevan el prefijo: esos sí
   se exportan, y este módulo JAMÁS los toca.

Un choque entre lo importado y una reserva Aremko existente es un OVERBOOKING
real: el bloqueo se crea igual (espejo fiel) y se grita en el log con los IDs.
"""
import logging
from datetime import date, timedelta

from django.db import transaction
from django.utils import timezone

from ventas.models import (CalendarioCabana, ReservaServicio, ServicioBloqueo)

logger = logging.getLogger(__name__)

# Marca los bloqueos que este módulo administra. `motivo` es CharField(255):
# sobra espacio (la trampa varchar(16) de P-26 no aplica acá).
MOTIVO_PREFIJO_OTA = '[OTA]'


# ---------------------------------------------------------------------------
# Parser iCal (solo lo que las OTAs publican: eventos de día completo)
# ---------------------------------------------------------------------------

def _desplegar(texto):
    """Deshace el plegado RFC 5545: la línea que empieza con espacio o tab
    continúa la anterior."""
    lineas, actual = [], ''
    for cruda in (texto or '').replace('\r\n', '\n').replace('\r', '\n').split('\n'):
        if cruda[:1] in (' ', '\t'):
            actual += cruda[1:]
        else:
            if actual:
                lineas.append(actual)
            actual = cruda
    if actual:
        lineas.append(actual)
    return lineas


def _fecha(valor):
    """'20260821' o '20260821T140000Z' → date(2026, 8, 21)."""
    v = valor.strip()
    return date(int(v[0:4]), int(v[4:6]), int(v[6:8]))


def parsear_ics(texto):
    """[(inicio, fin_exclusivo, uid, resumen)] de un VCALENDAR.

    `fin_exclusivo` conserva la semántica iCal (el día de salida). Un VEVENT
    sin DTEND es de un día, como manda el RFC para eventos VALUE=DATE. Si la
    respuesta no es un calendario (HTML de error, página de login), ValueError:
    el que llama NO debe reconstruir nada con esto.
    """
    lineas = _desplegar(texto)
    if not any(l.strip().upper() == 'BEGIN:VCALENDAR' for l in lineas):
        raise ValueError('la respuesta no es un calendario iCal')

    eventos, dentro, actual = [], False, {}
    for linea in lineas:
        linea = linea.strip()
        if linea.upper() == 'BEGIN:VEVENT':
            dentro, actual = True, {}
            continue
        if linea.upper() == 'END:VEVENT':
            dentro = False
            inicio = actual.get('DTSTART')
            if inicio is None:
                continue
            fin = actual.get('DTEND')
            if fin is None or fin <= inicio:
                fin = inicio + timedelta(days=1)
            eventos.append((inicio, fin,
                            actual.get('UID', ''), actual.get('SUMMARY', '')))
            continue
        if not dentro or ':' not in linea:
            continue
        clave, valor = linea.split(':', 1)
        nombre = clave.split(';', 1)[0].upper()
        if nombre in ('DTSTART', 'DTEND'):
            try:
                actual[nombre] = _fecha(valor)
            except (ValueError, IndexError):
                # Una fecha ilegible invalida el feed entero: parchar un evento
                # y reconstruir con los demás sería espejar una foto incompleta.
                raise ValueError(f'{nombre} ilegible: {valor[:40]!r}')
        elif nombre in ('UID', 'SUMMARY'):
            actual[nombre] = valor.strip()
    return eventos


# ---------------------------------------------------------------------------
# Espejo sobre ServicioBloqueo
# ---------------------------------------------------------------------------

def espejar_cabana(cal, eventos, hoy=None):
    """Reescribe los bloqueos [OTA] de la cabaña según lo que publica la OTA.

    `eventos` = [(fuente, inicio, fin_exclusivo, uid, resumen)] ya parseados de
    TODOS los feeds de la cabaña. Devuelve
    {'creados', 'borrados', 'overbookings': [(venta_id, inicio, fin_exc, fuente)]}.
    """
    hoy = hoy or timezone.localdate()
    # El pasado no se espeja: un bloqueo de una noche ya vivida no protege nada.
    vigentes = [e for e in eventos if e[2] > hoy]

    overbookings = []
    for fuente, inicio, fin_exc, _uid, _resumen in vigentes:
        chocan = (ReservaServicio.objects
                  .filter(servicio_id=cal.servicio_id,
                          venta_reserva__isnull=False,
                          fecha_agendamiento__gte=inicio,
                          fecha_agendamiento__lt=fin_exc)
                  .exclude(venta_reserva__estado_reserva='cancelada')
                  .values_list('venta_reserva_id', flat=True).distinct())
        for venta_id in chocan:
            overbookings.append((venta_id, inicio, fin_exc, fuente))

    with transaction.atomic():
        borrados, _detalle = (ServicioBloqueo.objects
                              .filter(servicio_id=cal.servicio_id,
                                      motivo__startswith=MOTIVO_PREFIJO_OTA)
                              .delete())
        nuevos = [
            ServicioBloqueo(
                servicio_id=cal.servicio_id,
                fecha_inicio=inicio,
                # ServicioBloqueo es INCLUSIVO en ambos extremos; iCal trae el
                # fin EXCLUSIVO (día de salida). La noche de salida queda libre.
                fecha_fin=fin_exc - timedelta(days=1),
                activo=True,
                motivo=(f'{MOTIVO_PREFIJO_OTA} {fuente} — reserva externa '
                        f'(se regenera sola, no editar)'),
                notas=f'{fuente} · uid {uid or "sin uid"} · {resumen or "sin resumen"}',
                # `fecha` y `hora_slot` NO son de este modelo: son del bloqueo
                # por slot, fusionados en ServicioBloqueo porque a la clase
                # siguiente le falta la línea `class` (P-28). Son NOT NULL
                # también en producción; 'N/A' es la forma de los 93 reales.
                fecha=inicio,
                hora_slot='N/A',
            )
            for fuente, inicio, fin_exc, uid, resumen in vigentes
        ]
        ServicioBloqueo.objects.bulk_create(nuevos)
        cal.ultima_lectura_ok = timezone.now()
        cal.save(update_fields=['ultima_lectura_ok', 'modificado'])

    for venta_id, inicio, fin_exc, fuente in overbookings:
        logger.warning('[ota_sync] ⚠️ OVERBOOKING %s: RES-%s choca con %s %s→%s',
                       cal.servicio.nombre, venta_id, fuente, inicio, fin_exc)
    return {'creados': len(nuevos), 'borrados': borrados,
            'overbookings': overbookings}


def leer_url(url):
    import requests

    resp = requests.get(url, timeout=20,
                        headers={'User-Agent': 'Aremko-Sync/1.0 (+https://www.aremko.cl)'})
    resp.raise_for_status()
    return resp.text


def sincronizar_todo(dry_run=False, leer=None, hoy=None):
    """Corre el espejo para cada calendario activo con URL. Devuelve informes
    (una línea por cabaña, con ⚠️ si detectó overbooking)."""
    leer = leer or leer_url
    informes = []
    for cal in (CalendarioCabana.objects.select_related('servicio')
                .filter(activo=True).order_by('servicio__nombre')):
        fuentes = [(f, u) for f, u in (('Booking', cal.url_booking),
                                       ('Airbnb', cal.url_airbnb)) if u]
        if not fuentes:
            continue

        eventos, fallas = [], []
        for fuente, url in fuentes:
            try:
                for inicio, fin_exc, uid, resumen in parsear_ics(leer(url)):
                    eventos.append((fuente, inicio, fin_exc, uid, resumen))
            except Exception as e:  # noqa: BLE001 — la falla se informa, no tumba el cron
                fallas.append(f'{fuente}: {e}')

        nombre = cal.servicio.nombre
        if fallas:
            # Regla 2: con lectura incompleta NO se reconstruye. Reconstruir
            # solo con lo que sí se leyó borraría los bloqueos del feed caído.
            informes.append(f'{nombre}: SIN CAMBIOS — falló la lectura '
                            f'({"; ".join(fallas)})')
            logger.error('[ota_sync] %s sin cambios: %s', nombre, '; '.join(fallas))
            continue
        if dry_run:
            detalle = ', '.join(f'{f} {i.strftime("%d/%m")}→{fx.strftime("%d/%m")}'
                                for f, i, fx, _u, _r in eventos[:10]) or 'sin eventos'
            informes.append(f'{nombre}: leería {len(eventos)} eventos '
                            f'({detalle}) — dry-run, sin escribir')
            continue

        r = espejar_cabana(cal, eventos, hoy=hoy)
        linea = (f'{nombre}: {r["creados"]} bloqueos OTA vigentes '
                 f'(reemplazaron {r["borrados"]})')
        for venta_id, inicio, fin_exc, fuente in r['overbookings']:
            linea += (f'\n  ⚠️ OVERBOOKING: RES-{venta_id} choca con {fuente} '
                      f'{inicio.strftime("%d/%m")}→{fin_exc.strftime("%d/%m")}')
        informes.append(linea)
    return informes
