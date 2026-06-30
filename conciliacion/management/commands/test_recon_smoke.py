"""Smoke test NO-destructivo del endpoint recon/aplicar-pago (AP-001 · PASO 2).

Valida la lógica REAL contra la BD de producción SIN dejar datos (todo dentro de
una transacción que se revierte) y SIN efectos externos (desconecta —solo en este
proceso efímero, los workers web NO se tocan— los signals de "pago" que mandan la
ficha de masaje y el evento Meta CAPI).

Existe porque el drift AR-034 impide que `manage.py test` construya una BD de test
desde migraciones (falla creando test_db). Correr en el Shell de Render:

    python manage.py test_recon_smoke
"""
import json
import uuid

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models.signals import post_save
from django.test import RequestFactory
from django.utils import timezone


class _Rollback(Exception):
    """Se lanza al final para revertir TODO lo creado por el smoke test."""


class Command(BaseCommand):
    help = 'Smoke test no-destructivo de recon/aplicar-pago (rollback + sin envíos externos).'

    def handle(self, *args, **options):
        from ventas.models import Cliente, Servicio, VentaReserva, ReservaServicio, Pago
        from conciliacion.models import ReconciliacionLog
        from ventas.views.recon_api_views import recon_aplicar_pago
        import ventas.signals.main_signals as main_signals
        from ventas.signals.masaje_signals import enviar_ficha_al_confirmar_pago

        key = getattr(settings, 'AUTOMATION_API_KEY', None)
        if not key:
            self.stderr.write(self.style.ERROR('AUTOMATION_API_KEY no configurada; abortando.'))
            return

        # Desconectar SOLO en este proceso los signals de pago que hacen envíos
        # externos NO transaccionales (ficha de masaje + Meta CAPI). Los workers
        # web son procesos aparte → no se ven afectados.
        post_save.disconnect(sender=VentaReserva, dispatch_uid='masaje_enviar_ficha_al_pagar')
        post_save.disconnect(main_signals.disparar_meta_capi_purchase_on_pago, sender=VentaReserva)

        rf = RequestFactory()
        checks = []

        def post(body, with_key=True):
            extra = {'HTTP_X_API_KEY': key} if with_key else {}
            req = rf.post('/ventas/api/aremko-cli/recon/aplicar-pago/',
                          data=json.dumps(body), content_type='application/json', **extra)
            resp = recon_aplicar_pago(req)
            try:
                payload = json.loads(resp.content)
            except Exception:
                payload = {}
            return resp.status_code, payload

        def check(name, ok):
            checks.append(bool(ok))
            self.stdout.write(('  OK   ' if ok else '  FAIL ') + name)

        try:
            with transaction.atomic():
                suf = uuid.uuid4().hex[:8]
                cli = Cliente.objects.create(
                    nombre='SMOKE recon (rollback)',
                    telefono='+5699' + f'{uuid.uuid4().int % 10**7:07d}',
                )
                srv = Servicio.objects.create(
                    nombre='SMOKE tina', precio_base=50000, duracion=60, tipo_servicio='tina',
                )
                res = VentaReserva.objects.create(cliente=cli)
                ReservaServicio.objects.create(
                    venta_reserva=res, servicio=srv,
                    fecha_agendamiento=timezone.now().date(), hora_inicio='16:00',
                    cantidad_personas=1, precio_unitario_venta=50000,
                )
                res.calcular_total()
                res.refresh_from_db()
                check('baseline total=50000 / pendiente',
                      int(res.total) == 50000 and res.estado_pago == 'pendiente')

                ref = 'smoke-' + suf
                sc, d = post({'reserva_id': res.id, 'monto': 50000, 'referencia': ref})
                check('aplica -> 200', sc == 200)
                check('estado_pago = pagado', d.get('estado_pago') == 'pagado')
                check('saldo_pendiente = 0', d.get('saldo_pendiente') == 0)
                check('ya_aplicado = False', d.get('ya_aplicado') is False)
                check('1 Pago creado', Pago.objects.filter(venta_reserva=res).count() == 1)
                check('1 ReconciliacionLog', ReconciliacionLog.objects.filter(referencia=ref).count() == 1)

                sc2, d2 = post({'reserva_id': res.id, 'monto': 50000, 'referencia': ref})
                check('idempotente -> 200', sc2 == 200)
                check('idempotente ya_aplicado = True', d2.get('ya_aplicado') is True)
                check('idempotente NO duplica Pago', Pago.objects.filter(venta_reserva=res).count() == 1)

                res2 = VentaReserva.objects.create(cliente=cli)
                ReservaServicio.objects.create(
                    venta_reserva=res2, servicio=srv,
                    fecha_agendamiento=timezone.now().date(), hora_inicio='17:00',
                    cantidad_personas=1, precio_unitario_venta=50000,
                )
                res2.calcular_total()
                sc3, d3 = post({'reserva_id': res2.id, 'monto': 20000, 'referencia': 'smoke2-' + suf})
                check('parcial estado = parcial', d3.get('estado_pago') == 'parcial')
                check('parcial saldo = 30000', d3.get('saldo_pendiente') == 30000)

                sc4, _ = post({'reserva_id': res.id, 'monto': 1000, 'referencia': 'z' + suf}, with_key=False)
                check('sin key -> 401', sc4 == 401)

                sc5, _ = post({'reserva_id': res.id, 'monto': 1000, 'referencia': 'm' + suf, 'metodo_pago': 'bitcoin'})
                check('metodo invalido -> 400', sc5 == 400)

                sc6, _ = post({'reserva_id': 99999999, 'monto': 1000, 'referencia': 'n' + suf})
                check('reserva inexistente -> 404', sc6 == 404)

                raise _Rollback()
        except _Rollback:
            self.stdout.write(self.style.WARNING('Rollback OK: nada quedo en la BD de produccion.'))
        finally:
            # Reconectar (cosmetico: el proceso ya termina; los workers web nunca se tocaron).
            post_save.connect(enviar_ficha_al_confirmar_pago, sender=VentaReserva,
                              dispatch_uid='masaje_enviar_ficha_al_pagar')
            post_save.connect(main_signals.disparar_meta_capi_purchase_on_pago, sender=VentaReserva)

        passed = sum(checks)
        total = len(checks)
        style = self.style.SUCCESS if passed == total else self.style.ERROR
        self.stdout.write(style(f'\n{passed}/{total} checks OK'))
