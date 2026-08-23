# -*- coding: utf-8 -*-
"""Tres arreglos del 2026-08-22 (revisión de gastos con Jorge):

· La TEF intra-BancoEstado a "AGUILERA GONZALEZ" (apellidos a secas, como la
  escribe el banco) es traspaso a la CuentaRUT de Jorge; la interbancaria
  "TRANSFERENCIA A AGUILERA GONZALEZ" sigue por clasificar (ambigua).
· El calce a mano también ofrece los retiros «por clasificar» como candidatos.
· "TRASPASO DEUDA INTERNAC" de la tarjeta no es traspaso: es el gasto
  internacional del ciclo, y va a su propia categoría.
"""
from datetime import date
from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase

from .models import CategoriaFinanciera, CuentaFinanciera, MovimientoFinanciero
from .reglas import PLAN_CUENTAS
from .services import (CLAVE_POR_CALZAR, candidatos_de_calce,
                       clasificar_compra_tarjeta, destino_puente)


class DestinoPuenteTest(TestCase):

    def test_tef_intra_bancoestado_a_apellidos_es_cuentarut_de_jorge(self):
        self.assertEqual(
            destino_puente('TEF BANCOESTADO A AGUILERA GONZALEZ', 'bancoestado'),
            'cuentarut_jorge')

    def test_la_interbancaria_sigue_ambigua(self):
        # "TRANSFERENCIA A AGUILERA GONZALEZ" puede ser Cristian o Martín: no
        # se adivina, queda por clasificar (None = retiro/gasto, no puente).
        self.assertIsNone(
            destino_puente('TRANSFERENCIA A AGUILERA GONZALEZ', 'bancoestado'))

    def test_las_reglas_anteriores_siguen_igual(self):
        self.assertEqual(destino_puente('TEF A JORGE AGUILERA', 'bancoestado'),
                         'cuentarut_jorge')
        self.assertEqual(destino_puente('TEF A TOLOZA POBLETE ALDA', 'bancoestado'),
                         'scotiabank_alda')


class TarjetaInternacionalTest(TestCase):

    def test_traspaso_deuda_va_a_su_categoria(self):
        self.assertEqual(clasificar_compra_tarjeta('TRASPASO DEUDA INTERNAC'),
                         'tarjeta_internacional')
        self.assertEqual(clasificar_compra_tarjeta('TRASPASO DEUDA INTERNACIONAL'),
                         'tarjeta_internacional')

    def test_la_categoria_existe_en_el_plan_y_es_gasto(self):
        nombre, clase, grupo = PLAN_CUENTAS['tarjeta_internacional']
        self.assertEqual(clase, 'gasto')
        self.assertEqual(grupo, 'otros')  # no se asigna sola a Aremko


class CandidatosDeCalceTest(TestCase):
    """El retiro «por clasificar» de BancoEstado debe aparecer como candidato
    del abono de la CuentaRUT (caso 20/08/2026, $300.000)."""

    def setUp(self):
        call_command('sembrar_finanzas')
        call_command('aplicar_plan_cuentas', '--aplicar')
        self.be = CuentaFinanciera.objects.get(clave='bancoestado')
        self.rut = CuentaFinanciera.objects.get(clave='cuentarut_jorge')
        self.por_clasificar = CategoriaFinanciera.objects.get(clave='por_clasificar')
        # Esta categoría no está en el plan de cuentas: la crea al vuelo el
        # registrador de cartolas puente. Acá se crea igual que allá.
        self.por_calzar, _ = CategoriaFinanciera.objects.get_or_create(
            clave=CLAVE_POR_CALZAR,
            defaults={'nombre': 'Abono desde Aremko por calzar',
                      'clase': 'ingreso', 'grupo': 'otros'})

    def test_el_retiro_por_clasificar_aparece_como_candidato(self):
        retiro = MovimientoFinanciero.objects.create(
            fecha=date(2026, 8, 20), cuenta=self.be, clase='gasto', sentido='sale',
            monto=Decimal('300000'), categoria=self.por_clasificar, fuente='captura',
            referencia='t:be1',
            descripcion='Cartola bancoestado: TEF BANCOESTADO A AGUILERA GONZALEZ')
        abono = MovimientoFinanciero.objects.create(
            fecha=date(2026, 8, 19), cuenta=self.rut, clase='ingreso', sentido='entra',
            monto=Decimal('300000'), categoria=self.por_calzar, fuente='captura',
            referencia='t:rut1', descripcion='Cartola CuentaRUT: Tef De Aremko Hotel Spa')
        ids = [c.id for c in candidatos_de_calce(abono)]
        self.assertIn(retiro.id, ids)

    def test_un_gasto_de_aremko_ya_clasificado_no_es_candidato(self):
        # Un gasto real de la empresa (insumos) no es un retiro: no se ofrece.
        insumos = CategoriaFinanciera.objects.get(clave='insumos')
        MovimientoFinanciero.objects.create(
            fecha=date(2026, 8, 20), cuenta=self.be, clase='gasto', sentido='sale',
            monto=Decimal('300000'), categoria=insumos, fuente='captura',
            referencia='t:be2', descripcion='Cartola bancoestado: JUMBO')
        abono = MovimientoFinanciero.objects.create(
            fecha=date(2026, 8, 19), cuenta=self.rut, clase='ingreso', sentido='entra',
            monto=Decimal('300000'), categoria=self.por_calzar, fuente='captura',
            referencia='t:rut2', descripcion='Cartola CuentaRUT: Tef De Aremko Hotel Spa')
        self.assertEqual(candidatos_de_calce(abono), [])


class CuentaRutJubilacionesTest(TestCase):
    """Las tres jubilaciones de Jorge (en UF: el monto cambia cada mes, la
    glosa no) entran a su CuentaRUT y salen casi íntegras al día siguiente.
    Nada de eso es plata de Aremko."""

    def _clasificar(self, glosa, cargo=0, abono=0):
        from .services import clasificar_fila_cuentarut
        return clasificar_fila_cuentarut(glosa, cargo, abono)

    def test_las_jubilaciones_que_entran_son_abono_personal(self):
        # No dicen «Aremko» → plata suya: mueve su saldo, NO es ingreso del spa.
        for glosa in ('Abono Convenio Pago Beneficios Ips',
                      'Abono Convenio Pago Ips Reforma',
                      'Abono Convenio Banco Santander-chil'):
            clase, sentido, _, propio = self._clasificar(glosa, abono=263971)
            self.assertEqual((clase, sentido, propio), ('personal', 'entra', False),
                             f'falló con: {glosa}')

    def test_el_abono_desde_aremko_sigue_siendo_traspaso(self):
        clase, sentido, _, propio = self._clasificar(
            'Tef De Aremko Hotel Spa', abono=300000)
        self.assertEqual((clase, sentido, propio), ('traspaso', 'entra', True))

    def test_traslado_a_su_otra_cuenta_no_es_gasto_de_aremko(self):
        _, _, cat, _ = self._clasificar('Tef A Jorge Antonio Aguilera Gonzal',
                                        cargo=263971)
        self.assertEqual(cat, 'traslado_cuenta_propia')

    def test_aporte_a_datamatic_no_es_gasto_de_aremko(self):
        _, _, cat, _ = self._clasificar('Tef A Datamatic Software Limitada',
                                        cargo=145868)
        self.assertEqual(cat, 'aporte_datamatic')

    def test_ambas_quedan_fuera_del_resultado_operacional(self):
        # La prueba que importa: su GRUPO es el de la familia, que el tablero
        # resta aparte y la cuenta corriente excluye.
        from .reglas import GRUPOS_FAMILIA, PLAN_CUENTAS
        for clave in ('traslado_cuenta_propia', 'aporte_datamatic'):
            _, clase, grupo = PLAN_CUENTAS[clave]
            self.assertEqual(clase, 'gasto')
            self.assertIn(grupo, GRUPOS_FAMILIA, f'falló con: {clave}')

    def test_martin_y_lo_ambiguo_no_cambiaron(self):
        _, _, cat, _ = self._clasificar('Tef A Martin Aguilera Toloza 777021',
                                        cargo=10000)
        self.assertEqual(cat, 'personales_martin')
        _, _, cat, _ = self._clasificar('Pago Almapan', cargo=30580)
        self.assertEqual(cat, 'por_clasificar')
