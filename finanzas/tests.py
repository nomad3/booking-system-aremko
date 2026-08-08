# -*- coding: utf-8 -*-
"""Tests de finanzas (P-22 F1).

Sin fixtures de ventas: la app es aislada y el tablero funciona con Pago vacío.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db.models import Sum
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from conciliacion.models import MOTIVO_NO_ES_COBRO, MovimientoMP

from .models import CategoriaFinanciera, CuentaFinanciera, MovimientoFinanciero


class SiembraTest(TestCase):
    def test_sembrar_es_idempotente(self):
        call_command('sembrar_finanzas')
        cuentas, cats = CuentaFinanciera.objects.count(), CategoriaFinanciera.objects.count()
        self.assertGreaterEqual(cuentas, 6)
        self.assertGreaterEqual(cats, 13)
        call_command('sembrar_finanzas')
        self.assertEqual(CuentaFinanciera.objects.count(), cuentas)
        self.assertEqual(CategoriaFinanciera.objects.count(), cats)


class CargaHistoricaTest(TestCase):
    def test_carga_idempotente_y_traspasos_cuadran(self):
        call_command('sembrar_finanzas')
        # Modo lectura no escribe nada.
        call_command('cargar_historico_finanzas')
        self.assertEqual(MovimientoFinanciero.objects.count(), 0)

        call_command('cargar_historico_finanzas', '--aplicar')
        total = MovimientoFinanciero.objects.count()
        self.assertGreater(total, 100)

        # Decisión 2026-08-08: se parte de julio, el primer mes completo y que
        # se recuerda. Nada anterior debe entrar con el default.
        self.assertEqual(
            MovimientoFinanciero.objects.filter(fecha__lt=date(2026, 7, 1)).count(), 0)

        # Idempotencia: segunda corrida no duplica.
        call_command('cargar_historico_finanzas', '--aplicar')
        self.assertEqual(MovimientoFinanciero.objects.count(), total)

        # El control central del diseño: los traspasos suman cero.
        agg = {r['sentido']: int(r['t'] or 0)
               for r in MovimientoFinanciero.objects.filter(clase='traspaso')
               .values('sentido').annotate(t=Sum('monto'))}
        self.assertEqual(agg.get('entra', 0), agg.get('sale', 0))
        self.assertGreater(agg.get('entra', 0), 0)

        # Las dos piernas quedan enlazadas y en cuentas distintas.
        una = MovimientoFinanciero.objects.filter(clase='traspaso', sentido='sale').first()
        self.assertIsNotNone(una.traspaso_par)
        self.assertNotEqual(una.cuenta_id, una.traspaso_par.cuenta_id)
        self.assertEqual(una.monto, una.traspaso_par.monto)

        # El SII quedó con fecha real y categoría impuestos.
        sii = MovimientoFinanciero.objects.get(monto=Decimal('1956770'))
        self.assertEqual(sii.categoria.clave, 'impuestos')
        self.assertEqual(sii.fecha, date(2026, 7, 20))
        self.assertFalse(sii.fecha_estimada)


class CoherenciaTest(TestCase):
    def test_un_gasto_que_entra_no_pasa(self):
        call_command('sembrar_finanzas')
        m = MovimientoFinanciero(
            fecha=date(2026, 8, 1),
            cuenta=CuentaFinanciera.objects.get(clave='efectivo'),
            clase='gasto', sentido='entra', monto=1000,
            categoria=CategoriaFinanciera.objects.get(clave='insumos'))
        with self.assertRaises(ValidationError):
            m.full_clean()

    def test_traspaso_con_categoria_no_pasa(self):
        call_command('sembrar_finanzas')
        m = MovimientoFinanciero(
            fecha=date(2026, 8, 1),
            cuenta=CuentaFinanciera.objects.get(clave='efectivo'),
            clase='traspaso', sentido='sale', monto=1000,
            categoria=CategoriaFinanciera.objects.get(clave='insumos'))
        with self.assertRaises(ValidationError):
            m.full_clean()


class TableroTest(TestCase):
    def test_solo_superusuario(self):
        url = reverse('finanzas:tablero')
        # Anónimo → redirect a login.
        self.assertEqual(self.client.get(url).status_code, 302)
        # Staff no superusuario → tampoco entra.
        User.objects.create_user('staff', password='x', is_staff=True)
        self.client.login(username='staff', password='x')
        self.assertEqual(self.client.get(url).status_code, 302)

    def test_superusuario_ve_el_tablero(self):
        call_command('sembrar_finanzas')
        call_command('cargar_historico_finanzas', '--aplicar')
        User.objects.create_superuser('duenio', 'x@x.cl', 'x')
        self.client.login(username='duenio', password='x')
        r = self.client.get(reverse('finanzas:tablero'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Resumen mensual')
        self.assertContains(r, 'Los traspasos cuadran')


class VerificacionMPTest(TestCase):
    """La sección sistema-vs-API del tablero (P-22 F2-A)."""

    def test_lado_mp_cuenta_lo_correcto(self):
        # La tabla agrega POR DÍA: cada caso va en su propio día para poder
        # afirmar su monto, y el ajeno comparte día con v1 — si se colara,
        # el día de v1 mostraría la suma y no $987.654.
        ahora = timezone.now()
        # Cobro normal → cuenta.
        MovimientoMP.objects.create(mp_payment_id='v1', fecha=ahora, monto=987654)
        # Ignorado POR DEBORAH (irrelevante para su tarea, pero plata que entró) → cuenta.
        MovimientoMP.objects.create(mp_payment_id='v2', monto=345678,
                                    fecha=ahora - timedelta(days=1),
                                    estado='ignorado')
        # Ajeno confirmado por la API (Aremko pagador) → NO cuenta.
        MovimientoMP.objects.create(mp_payment_id='v3', fecha=ahora, monto=111222,
                                    estado='ignorado',
                                    sugerencia_motivo=MOTIVO_NO_ES_COBRO)

        User.objects.create_superuser('duenio', 'x@x.cl', 'x')
        self.client.login(username='duenio', password='x')
        r = self.client.get(reverse('finanzas:tablero'))
        self.assertContains(r, 'Verificación Mercado Pago')
        self.assertContains(r, '$987.654')
        self.assertContains(r, '$345.678')
        self.assertNotContains(r, '$111.222')
        # Sin pagos en Django, la diferencia de la ventana es todo el lado MP.
        self.assertContains(r, '+$1.333.332')
