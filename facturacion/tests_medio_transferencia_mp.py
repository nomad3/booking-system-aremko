"""Existe UN medio para las transferencias recibidas en Mercado Pago, y boletea.

El 15-08-2026 se ocultó «mercadopago aremko» al cobrar, junto con las cuentas
personales. Con eso quedó sin forma de registrar una transferencia recibida en
la Cuenta Vista de Mercado Pago: había que elegir «MercadoPago», que NO boletea
porque se asume cobro con tarjeta.

Mientras decidía una persona caso a caso se notaba poco. Cuando la emisión mire
el switch, esas transferencias se quedarían sin boleta — y el SII sí las espera:
transferencia electrónica siempre exige boleta, aunque llegue a una billetera.

Ejecutar:
    python manage.py test facturacion.tests_medio_transferencia_mp
"""
from __future__ import annotations

from django.test import TestCase


class ElMedioDeTransferenciaAMercadoPago(TestCase):
    def test_el_nombre_dice_que_es_una_transferencia(self):
        # «mercadopago aremko» no le decía nada a quien cobra: se confunde con
        # el cobro por Mercado Pago, que es lo contrario.
        from ventas.models import Pago

        etiquetas = dict(Pago.METODOS_PAGO)
        self.assertEqual(etiquetas['mercadopagoaremko'], 'Transferencia a Mercado Pago')

    def test_no_queda_oculto_al_cobrar_en_la_siembra(self):
        from facturacion.management.commands.sembrar_medios_pago import (
            GENERAN_BOLETA, OCULTOS_AL_COBRAR)

        self.assertNotIn('mercadopagoaremko', OCULTOS_AL_COBRAR)
        self.assertIn('mercadopagoaremko', GENERAN_BOLETA)

    def test_los_cobros_electronicos_siguen_sin_boletear(self):
        # El voucher del operador ya es la boleta: emitir otra sería duplicar.
        from facturacion.management.commands.sembrar_medios_pago import GENERAN_BOLETA

        for codigo in ('flow', 'mercadopago', 'mercadopago_link', 'tarjeta', 'webpay'):
            self.assertNotIn(codigo, GENERAN_BOLETA, codigo)

    def test_las_transferencias_de_verdad_si_boletean(self):
        from facturacion.management.commands.sembrar_medios_pago import GENERAN_BOLETA

        for codigo in ('efectivo', 'scotiabank', 'bancoestado', 'cuentarut',
                       'mercadopagoaremko'):
            self.assertIn(codigo, GENERAN_BOLETA, codigo)

    def test_las_cuentas_personales_siguen_ocultas(self):
        # Están bien clasificadas (si un cliente transfiere ahí, boletea) pero
        # no tienen por qué estorbar en la lista de cobro.
        from facturacion.management.commands.sembrar_medios_pago import OCULTOS_AL_COBRAR

        for codigo in ('machjorge', 'machalda', 'bcialda', 'copecjorge', 'scotiabankalda'):
            self.assertIn(codigo, OCULTOS_AL_COBRAR, codigo)
