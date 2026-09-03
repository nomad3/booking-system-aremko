"""
Reconcilia el estado real en el SII de los envíos ya transmitidos — punto 7
de la Declaración de Cumplimiento («Cuadratura de envíos aceptados,
rechazados y aceptados con reparos por el SII»).

Por cada trackId con boletas en 'enviada', consulta al SII (vía SimpleAPI) y
clasifica el resultado real, folio por folio:
· Aceptada limpia     -> 'aceptada'
· Aceptada con reparo -> 'aceptada' (el SII SÍ la aceptó) + el detalle del
  reparo queda en error_mensaje, para que no se pierda de vista.
· Rechazada           -> 'rechazada' — esto SÍ necesita que alguien lo mire.
· El sobre ENTERO rechazado (caso raro) -> las boletas vuelven a 'generada'
  con el MISMO folio y XML, para que enviar_boletas_sii las reintente solas.
· Todavía procesando (estado REC) -> no se toca nada, se reintenta mañana.

Formato de respuesta verificado contra un envío real (trackId 32124491,
03-09-2026), no inventado:
  {'estado': 'EPR',
   'estadistica': [{'tipo':39,'informados':15,'aceptados':5,'rechazados':0,'reparos':10}],
   'detalles': [{'folio':6,'estado':'RLV','descripcion':'DTE Aceptado con Reparos Leves', ...}, ...]}
`detalles` solo lista los folios CON problema (reparo o rechazo); los
folios aceptados limpio no aparecen ahí — se infieren por ausencia. La
clasificación usa el texto de `descripcion` (no el código), porque solo
hemos visto 'RLV' en producción real y no vale la pena adivinar el resto
del catálogo de códigos.

Uso:
  python manage.py cuadrar_envios_sii
  python manage.py cuadrar_envios_sii --ambiente certificacion
"""
from django.core.management.base import BaseCommand, CommandError

from facturacion.models import BoletaElectronica, ConfiguracionFacturacion
from facturacion.services import simpleapi_client

AMBIENTE_NUM = {'certificacion': 0, 'produccion': 1}
TERMINALES_OK = {'EPR', 'ACEPTADO'}
TERMINAL_RECHAZO = {'RECHAZADO'}


class Command(BaseCommand):
    help = 'Consulta al SII el resultado real de los envíos y clasifica cada boleta.'

    def add_arguments(self, parser):
        parser.add_argument('--ambiente', choices=['certificacion', 'produccion'],
                            default=None)

    def handle(self, *args, **options):
        config = ConfiguracionFacturacion.get()
        ambiente = options['ambiente'] or config.ambiente
        if ambiente not in AMBIENTE_NUM:
            self.stdout.write(f"Ambiente '{ambiente}' no tiene envíos que cuadrar.")
            return

        # .order_by() VACÍO antes de .distinct() es obligatorio acá: el
        # modelo trae Meta.ordering = ['-creada_at'], y en Postgres el
        # ORDER BY implícito se cuela dentro del SELECT DISTINCT -- termina
        # deduplicando por (track_id, creada_at) en vez de por track_id
        # solo. Se veía perfecto en sqlite (los tests locales) y llamaba a
        # consultar_estado_envio una vez por CADA boleta del mismo sobre en
        # producción real -- lo agarré viendo el mismo trackId repetido 5
        # veces en un envío que solo tenía un track.
        track_ids = list(
            BoletaElectronica.objects.filter(ambiente=ambiente, estado='enviada')
            .exclude(track_id='').order_by().values_list('track_id', flat=True)
            .distinct())
        if not track_ids:
            self.stdout.write(f"Sin envíos pendientes de cuadrar en {ambiente}.")
            return

        if not simpleapi_client.credenciales_listas():
            raise CommandError('Faltan credenciales.')
        cert_bytes, cert_password = simpleapi_client.obtener_certificado()

        for track_id in track_ids:
            # Un trackId con problemas NO debe frenar la cuadratura de los
            # demás -- se procesan de forma independiente.
            try:
                self._cuadrar_uno(track_id, ambiente, config, cert_bytes, cert_password)
            except Exception as exc:  # noqa: BLE001
                self.stdout.write(self.style.WARNING(
                    f"trackId={track_id}: no se pudo cuadrar ({exc}). Se reintenta después."))

    def _cuadrar_uno(self, track_id, ambiente, config, cert_bytes, cert_password):
        boletas = list(BoletaElectronica.objects.filter(
            ambiente=ambiente, estado='enviada', track_id=track_id))
        if not boletas:
            return

        resp = simpleapi_client.consultar_estado_envio(
            track_id, cert_bytes, cert_password, config,
            AMBIENTE_NUM[ambiente], servidor_boleta=True)
        estado = resp.get('estado', '')

        if estado in TERMINAL_RECHAZO:
            for b in boletas:
                b.estado = 'generada'
                b.track_id = ''
                b.save(update_fields=['estado', 'track_id', 'actualizada_at'])
            self.stdout.write(self.style.WARNING(
                f"trackId={track_id}: el SII rechazó el SOBRE completo. "
                f"{len(boletas)} boleta(s) vuelven a 'generada' para reintentar."))
            return

        if estado not in TERMINALES_OK:
            # 'REC' (aún procesando) o cualquier valor no documentado: no se
            # toca nada -- se prefiere reintentar mañana a adivinar hoy.
            self.stdout.write(f"trackId={track_id}: estado '{estado}' — aún no definitivo.")
            return

        detalles_por_folio = {d.get('folio'): d for d in resp.get('detalles', [])}
        aceptadas = rechazadas = sin_clasificar = 0
        for b in boletas:
            detalle = detalles_por_folio.get(b.folio)
            if detalle is None:
                b.estado = 'aceptada'
                aceptadas += 1
            else:
                descripcion = detalle.get('descripcion') or ''
                baja = descripcion.lower()
                if 'rechaz' in baja:
                    b.estado = 'rechazada'
                    b.error_mensaje = f"SII: {descripcion}"
                    rechazadas += 1
                elif 'aceptad' in baja:
                    b.estado = 'aceptada'
                    b.error_mensaje = f"Aceptada con reparo — SII: {descripcion}"
                    aceptadas += 1
                else:
                    # Ni "rechaz" ni "aceptad" en el texto: no se adivina.
                    # Queda 'enviada', visible para revisión manual.
                    b.error_mensaje = f"SII (sin clasificar): {descripcion}"
                    sin_clasificar += 1
            b.save(update_fields=['estado', 'error_mensaje', 'actualizada_at'])

        self.stdout.write(self.style.SUCCESS(
            f"trackId={track_id}: {aceptadas} aceptada(s), {rechazadas} rechazada(s), "
            f"{sin_clasificar} sin clasificar (de {len(boletas)})."))
