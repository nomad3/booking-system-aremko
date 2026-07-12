"""
Siembra idempotente de MedioPago desde los choices reales de Pago.metodo_pago.

Criterio confirmado por Jorge (2026-07-11):
- GENERAN boleta: efectivo y toda transferencia a cuentas propias (bancos,
  Mach, Copec, y la Cuenta Vista de Mercado Pago).
- NO generan: tarjeta (SumUp), Webpay, Flow, links de Mercado Pago (el
  recaudador informa al SII: voucher = boleta), descuento y giftcard (el CANJE
  nunca boletea; la VENTA de una giftcard es un producto más — boletea o no
  según el medio con que se pagó, como una tabla de quesos), y booking (lo
  gestiona el contador aparte).

Idempotente: NO pisa el switch genera_boleta de medios ya existentes (los
ajustes hechos en el admin se respetan). Solo crea los que falten.
"""
from django.core.management.base import BaseCommand

from facturacion.models import MedioPago
from ventas.models import Pago

GENERAN_BOLETA = {
    'efectivo',
    'transferencia',
    'scotiabank',
    'bancoestado',
    'cuentarut',
    'machjorge',
    'machalda',
    'bicegoalda',
    'bcialda',
    'andesalda',
    'scotiabankalda',
    'copecjorge',
    'copecalda',
    'mercadopagoaremko',  # transferencia directa a la Cuenta Vista MP → SÍ boletea
}

NOTAS = {
    'mercadopago_link': 'Link de pago MP: lo informa MP al SII (voucher = boleta).',
    'mercadopago': 'Revisar caso a caso: si es transferencia a la Cuenta Vista, boletea.',
    'flow': 'Flow informa al SII (checkout web).',
    'webpay': 'El operador informa al SII.',
    'tarjeta': 'SumUp informa al SII.',
    'descuento': 'No es plata real.',
    'giftcard': 'Canje: nunca boletea. La VENTA de una giftcard es un producto más: '
                'boletea según el medio con que se pagó (Jorge 2026-07-11).',
    'booking': 'Lo gestiona el contador aparte.',
    'mercadopagoaremko': 'Transferencia directa a Cuenta Vista MP → boletea (Jorge 2026-07-11).',
}


# Textos de siembras anteriores: si la nota actual calza EXACTO con uno de
# estos, se refresca al texto vigente. Una nota editada a mano jamás se pisa.
NOTAS_OBSOLETAS = {
    'giftcard': ['El canje no boletea; la giftcard se boleteó al venderse.'],
}


class Command(BaseCommand):
    help = 'Crea los MedioPago que falten a partir de Pago.METODOS_PAGO (no pisa ajustes del admin).'

    def handle(self, *args, **options):
        creados, existentes = 0, 0
        for codigo, nombre in Pago.METODOS_PAGO:
            obj, created = MedioPago.objects.get_or_create(
                codigo=codigo,
                defaults={
                    'nombre': nombre,
                    'genera_boleta': codigo in GENERAN_BOLETA,
                    'nota': NOTAS.get(codigo, ''),
                },
            )
            if not created and obj.nota in NOTAS_OBSOLETAS.get(codigo, []):
                obj.nota = NOTAS.get(codigo, '')
                obj.save(update_fields=['nota', 'actualizado_at'])
                self.stdout.write(f"nota refrescada: {codigo}")
            creados += int(created)
            existentes += int(not created)
        total_on = MedioPago.objects.filter(genera_boleta=True).count()
        self.stdout.write(self.style.SUCCESS(
            f"MedioPago: {creados} creados, {existentes} ya existían. "
            f"{total_on} medios generan boleta."))
