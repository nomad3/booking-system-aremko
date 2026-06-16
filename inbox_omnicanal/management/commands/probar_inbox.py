"""Valida la persistencia + reads de la bandeja omnicanal (H-016) sin enviar nada.

Por defecto solo MUESTRA el estado actual (read-only). Con --simular inserta un DM
entrante + un eco de prueba en una transacción que se DESHACE (rollback), así verifica
el modelo y las consultas contra el esquema real sin dejar basura en la BD.

  python manage.py probar_inbox
  python manage.py probar_inbox --simular
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone


class _Rollback(Exception):
    pass


class Command(BaseCommand):
    help = 'Muestra/valida la bandeja omnicanal (Instagram). --simular hace un dry-run con rollback.'

    def add_arguments(self, parser):
        parser.add_argument('--simular', action='store_true',
                            help='Inserta un DM entrante + un eco de prueba y los muestra (rollback al final).')

    def handle(self, *args, **opts):
        from inbox_omnicanal.models import ChannelMessage
        from inbox_omnicanal import views as v

        self.stdout.write(self.style.MIGRATE_HEADING('— Estado actual (Instagram) —'))
        self.stdout.write(f'  mensajes IG en BD: {ChannelMessage.objects.filter(canal="instagram").count()}')

        if not opts.get('simular'):
            self._mostrar_conversaciones(v)
            return

        igsid = 'TEST_IGSID_9999'
        try:
            with transaction.atomic():
                ahora = timezone.now()
                ChannelMessage.objects.create(
                    canal='instagram', external_id=igsid,
                    external_message_id='TEST_MID_in_1', direction='in',
                    body='hola, ¿tienen tinas el sábado?', timestamp=ahora,
                    contact_name='@cliente_prueba', requiere_atencion=True,
                )
                ChannelMessage.objects.create(
                    canal='instagram', external_id=igsid,
                    external_message_id='TEST_MID_echo_1', direction='out',
                    body='¡Hola! Sí, te paso disponibilidad 🌿', timestamp=ahora,
                    contact_name='@cliente_prueba', requiere_atencion=False,
                )

                self.stdout.write(self.style.MIGRATE_HEADING('\n— Simulación (rollback al final) —'))
                self.stdout.write('  Insertados 2 mensajes IG de prueba (1 entrante pendiente + 1 eco).')

                agg = v._agg_instagram()
                fila = next((a for a in agg if a['external_id'] == igsid), None)
                self.stdout.write(self.style.SUCCESS(f'  Agregado: {fila}  (req=1 → entrante pendiente)'))

                # Simula el efecto del eco (responder): debe sacar la conversación de pendientes.
                limpiados = v._limpiar_pendientes_channel('instagram', igsid)
                fila2 = next((a for a in v._agg_instagram() if a['external_id'] == igsid), None)
                self.stdout.write(self.style.SUCCESS(
                    f'  Tras responder (eco): pendientes_limpiados={limpiados} → req ahora '
                    f'{fila2["req"] if fila2 else "?"}  (debe ser 0)'))

                det = v._detalle_instagram([igsid]).get(igsid, {})
                self.stdout.write(self.style.SUCCESS(f'  Detalle conversación: {det}'))

                hilo = list(ChannelMessage.objects.filter(canal='instagram', external_id=igsid)
                            .order_by('timestamp'))
                self.stdout.write('  Hilo:')
                for m in hilo:
                    self.stdout.write(f'    [{m.direction}] {m.body!r} · pendiente={m.requiere_atencion}')

                raise _Rollback()
        except _Rollback:
            self.stdout.write(self.style.WARNING('\n  ✓ Rollback hecho: la BD quedó intacta (0 mensajes de prueba persistidos).'))

        self._mostrar_conversaciones(v)

    def _mostrar_conversaciones(self, v):
        agg = v._agg_instagram()
        self.stdout.write(self.style.MIGRATE_HEADING('\n— Conversaciones IG (agregado) —'))
        if not agg:
            self.stdout.write('  (sin conversaciones de Instagram todavía)')
            return
        for a in sorted(agg, key=lambda x: x['ultimo_ts'] or timezone.now(), reverse=True)[:20]:
            self.stdout.write(f"  {a['external_id']} · últimos {a['total']} · pendientes {a['req']}")
