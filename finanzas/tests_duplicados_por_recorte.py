"""Duplicados que la glosa idéntica no ve: la misma línea recortada distinto.

El 19-08-2026 entraron cinco compras dos veces en Scotiabank ($355.295). El
detector no las vio porque compara la glosa completa y el banco las escribió
con distinto largo: «REDCOMPRA LAPIZ LOPEZ      PUE» contra «REDCOMPRA LAPIZ
LOPEZ». La referencia se calcula sobre la glosa, así que al cambiar el recorte
cambió la llave de idempotencia y la línea entró de nuevo.

Ejecutar:
    python manage.py test finanzas.tests_duplicados_por_recorte
"""
from __future__ import annotations

import datetime

from django.test import TestCase

from finanzas.management.commands.revisar_duplicados import agrupar_por_recorte
from finanzas.models import CategoriaFinanciera, CuentaFinanciera, MovimientoFinanciero

HOY = datetime.date(2026, 8, 19)


class ElMismoGastoConLaGlosaRecortadaDistinto(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cta = CuentaFinanciera.objects.create(
            nombre='Scotiabank', clave='scotiabank', tipo='banco')
        cls.otra = CuentaFinanciera.objects.create(
            nombre='Mercado Pago', clave='mercadopago', tipo='pasarela')
        cls.cat = CategoriaFinanciera.objects.create(
            nombre='Alimentos', clave='alimentos', clase='gasto', grupo='operacion')

    def _mov(self, glosa, monto=9650, cuenta=None, fecha=HOY):
        # `referencia` es ÚNICA en la base: por eso un duplicado solo entra
        # cuando la glosa cambia, que es exactamente el caso que probamos.
        self._n = getattr(self, '_n', 0) + 1
        return MovimientoFinanciero.objects.create(
            fecha=fecha, cuenta=cuenta or self.cta, clase='gasto', sentido='sale',
            monto=monto, categoria=self.cat, descripcion=glosa,
            referencia=f'ref-{self._n}')

    def test_junta_la_linea_larga_con_la_corta(self):
        a = self._mov('Cartola scotiabank: REDCOMPRA LAPIZ LOPEZ      PUE')
        b = self._mov('Cartola scotiabank: REDCOMPRA LAPIZ LOPEZ')
        grupos = agrupar_por_recorte([a, b])
        self.assertEqual(len(grupos), 1)
        self.assertEqual({m.id for m in grupos[0]}, {a.id, b.id})

    def test_dos_comisiones_de_ventas_distintas_NO_son_duplicado(self):
        # La trampa que ya costó caro: la glosa lleva el id de la venta, así
        # que dos comisiones del mismo monto son cobros distintos. Ninguna es
        # prefijo de la otra.
        a = self._mov('Comisión MP del cobro 170402030994', 4084, self.otra)
        b = self._mov('Comisión MP del cobro 173996818132', 4084, self.otra)
        self.assertEqual(agrupar_por_recorte([a, b]), [])

    def test_montos_distintos_no_se_juntan(self):
        a = self._mov('Cartola: REDCOMPRA FERIA    LLA', 18400)
        b = self._mov('Cartola: REDCOMPRA FERIA', 18401)
        self.assertEqual(agrupar_por_recorte([a, b]), [])

    def test_cuentas_distintas_no_se_juntan_aca(self):
        # Ese caso es «atribución doble» y se informa aparte, porque se
        # arregla distinto: hay que saber cuál medio de pago es el bueno.
        a = self._mov('REDCOMPRA FERIA    LLA', 18400, self.cta)
        b = self._mov('REDCOMPRA FERIA', 18400, self.otra)
        self.assertEqual(agrupar_por_recorte([a, b]), [])

    def test_dias_distintos_no_se_juntan(self):
        a = self._mov('REDCOMPRA FERIA    LLA', 18400)
        b = self._mov('REDCOMPRA FERIA', 18400,
                      fecha=HOY - datetime.timedelta(days=1))
        self.assertEqual(agrupar_por_recorte([a, b]), [])

    def test_glosas_iguales_no_entran_aca(self):
        # Eso ya lo ve el grupo de «glosa idéntica»: informarlo dos veces
        # inflaría el sobrante y haría dudar del número.
        a = self._mov('REDCOMPRA FERIA')
        b = self._mov('REDCOMPRA FERIA')
        self.assertEqual(agrupar_por_recorte([a, b]), [])
