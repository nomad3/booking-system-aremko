"""
Diagnóstico de la app facturacion (P-16). Seguro para producción.

- Sin flags: SOLO LECTURA (tablas, config, medios de pago, boletas).
- --smoke: prueba la emisión end-to-end (cliente+reserva+pago+boleta) dentro de
  una transacción que SIEMPRE se revierte — no persiste nada, ni en prod.

Uso: python manage.py diagnostico_facturacion [--smoke]
"""
from django.core.management.base import BaseCommand
from django.db import connection, transaction

from facturacion.models import (BoletaElectronica, ConfiguracionFacturacion,
                                MedioPago)


class Command(BaseCommand):
    help = 'Diagnóstico de facturación (solo lectura; --smoke prueba emisión con rollback).'

    def add_arguments(self, parser):
        parser.add_argument('--smoke', action='store_true',
                            help='Prueba de emisión simulada con rollback (no persiste).')

    def handle(self, *args, **options):
        tablas = sorted(t for t in connection.introspection.table_names()
                        if t.startswith('facturacion_'))
        self.stdout.write(f"Tablas: {', '.join(tablas) or 'NINGUNA (falta migrar)'}")

        if not tablas:
            return

        config = ConfiguracionFacturacion.get()
        self.stdout.write(f"Ambiente: {config.ambiente} | emisión automática: "
                          f"{'ON' if config.emision_automatica else 'OFF'}")

        # Credenciales del entorno (solo presencia/tamaño, jamás valores)
        import os
        from facturacion.services.simpleapi_client import obtener_certificado
        cert, pwd = obtener_certificado()
        self.stdout.write(
            f"Credenciales: API_KEY={'SÍ' if os.environ.get('SIMPLEAPI_API_KEY') else 'NO'} | "
            f"CERT={'SÍ (' + str(len(cert)) + ' bytes)' if cert else 'NO'} | "
            f"CLAVE={'SÍ' if pwd else 'NO'}")
        on = MedioPago.objects.filter(genera_boleta=True).count()
        off = MedioPago.objects.filter(genera_boleta=False).count()
        self.stdout.write(f"Medios de pago: {on} boletean / {off} no boletean "
                          f"(total {on + off})")
        self.stdout.write(f"Boletas registradas: {BoletaElectronica.objects.count()}")

        if not options['smoke']:
            return

        self.stdout.write("--- SMOKE con rollback (usa un pago EXISTENTE, no crea datos de ventas) ---")
        from facturacion.services.emisor import (emitir_boleta_para_pago,
                                                 medio_genera_boleta)
        from ventas.models import Pago

        pago = (Pago.objects
                .filter(metodo_pago='transferencia', monto__gt=0,
                        boleta_electronica__isnull=True)
                .order_by('-id').first())
        if pago is None:
            self.stdout.write(self.style.WARNING(
                "No hay pagos por transferencia sin boleta para el smoke — se omite."))
            return

        with transaction.atomic():
            boleta, msg1 = emitir_boleta_para_pago(pago)
            assert boleta is not None, f"debió emitir: {msg1}"
            self.stdout.write(f"1) emisión sobre pago #{pago.pk}: {msg1} | "
                              f"estado={boleta.estado} neto={boleta.monto_neto} "
                              f"iva={boleta.monto_iva} total={boleta.monto_total}")
            assert (int(boleta.monto_neto) + int(boleta.monto_iva)
                    == int(boleta.monto_total)), "montos no cuadran"

            b2, msg2 = emitir_boleta_para_pago(pago)
            assert b2.pk == boleta.pk, "idempotencia rota: creó una segunda boleta"
            self.stdout.write(f"2) idempotencia: {msg2}")

            assert not medio_genera_boleta('mercadopago_link'), \
                "mercadopago_link no debía boletear"
            self.stdout.write("3) medio no boleteable: mercadopago_link → NO boletea (correcto)")

            transaction.set_rollback(True)

        self.stdout.write(self.style.SUCCESS(
            "SMOKE OK — todo revertido, la base quedó intacta."))
