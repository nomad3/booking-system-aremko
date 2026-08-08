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
from .services import (parsear_transferencia_mp, registrar_compras_mp,
                       registrar_transferencia_mp)


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

        # Regresión (visto en prod 2026-08-08): un mes SIN gastos cargados
        # muestra «—» y no "$0 + resultado" — la trampa era que sum(gastos[m])
        # sobre un defaultdict creaba la llave antes del chequeo `m in gastos`.
        por_mes = {f['mes']: f for f in r.context['resumen']}
        junio = date(2026, 6, 1)
        self.assertIn(junio, por_mes)
        self.assertEqual(por_mes[junio]['gastos'], '—')
        self.assertEqual(por_mes[junio]['resultado'], '—')
        # Julio sí tiene gastos cargados → números de verdad.
        julio = date(2026, 7, 1)
        self.assertNotEqual(por_mes[julio]['gastos'], '—')
        self.assertNotEqual(por_mes[julio]['resultado'], '—')


class ComprasMPTest(TestCase):
    """Compras vía MP (Aremko pagador) → gasto automático (P-22 F2-B)."""

    def test_registra_con_cuenta_corte_e_idempotencia(self):
        call_command('sembrar_finanzas')
        pagos = [
            # Con saldo MP → cuenta mercado_pago.
            dict(id=111, transaction_amount=25990, payment_type_id='account_money',
                 date_approved='2026-08-05T10:00:00.000-04:00',
                 description='Mercado Libre - cable HDMI'),
            # Con la Visa a través de MP → el gasto es de la Visa.
            dict(id=222, transaction_amount=49990, payment_type_id='credit_card',
                 date_approved='2026-07-15T09:00:00.000-04:00',
                 description='Retail'),
            # Antes del corte de julio → fuera.
            dict(id=333, transaction_amount=10000, payment_type_id='account_money',
                 date_approved='2026-06-20T09:00:00.000-04:00'),
            # Monto cero y sin fecha → fuera, sin explotar.
            dict(id=444, transaction_amount=0,
                 date_approved='2026-08-05T10:00:00.000-04:00'),
            dict(id=555, transaction_amount=5000, payment_type_id='account_money'),
        ]
        self.assertEqual(registrar_compras_mp(pagos), 2)

        m1 = MovimientoFinanciero.objects.get(referencia='mp:111')
        self.assertEqual((m1.cuenta.clave, m1.clase, m1.sentido, m1.fuente),
                         ('mercado_pago', 'gasto', 'sale', 'api'))
        self.assertEqual(m1.categoria.clave, 'por_clasificar')
        self.assertEqual(m1.fecha, date(2026, 8, 5))
        self.assertIn('Mercado Libre', m1.descripcion)

        m2 = MovimientoFinanciero.objects.get(referencia='mp:222')
        self.assertEqual(m2.cuenta.clave, 'visa_2936')

        # Segunda corrida: nada nuevo.
        self.assertEqual(registrar_compras_mp(pagos), 0)
        self.assertEqual(MovimientoFinanciero.objects.count(), 2)

    def test_sin_sembrar_no_explota(self):
        self.assertEqual(registrar_compras_mp([dict(
            id=1, transaction_amount=1000, payment_type_id='account_money',
            date_approved='2026-08-05T10:00:00.000-04:00')]), 0)


# Estructura real del correo «Tu transferencia fue enviada» (2026-08-08),
# anonimizada: mismos rótulos, mismo anidado de tags alrededor del monto.
HTML_TRANSFERENCIA = (
    '<html><body><span>Ya enviamos tu transferencia de '
    '<span style="white-space: nowrap;">$ {monto}</span></span>'
    '<h1> Nombre y apellido: <strong>{nombre}</strong><p></p> '
    'Entidad: <strong>Banco Estado</strong><p></p> '
    'N&uacute;mero de cuenta: <strong>12345678</strong></h1></body></html>'
)


class CorreosMPTest(TestCase):
    """F3: transferencias salientes de MP desde el correo."""

    def _html(self, monto='250.000', nombre='Maria Prueba'):
        return HTML_TRANSFERENCIA.format(monto=monto, nombre=nombre)

    def test_parser_extrae_los_tres_campos(self):
        d = parsear_transferencia_mp(self._html())
        self.assertEqual(d, {'monto': 250000, 'beneficiario': 'Maria Prueba',
                             'entidad': 'Banco Estado'})
        # Correo que no calza → None, no un registro inventado.
        self.assertIsNone(parsear_transferencia_mp('<html>Recibiste un pago</html>'))

    def test_registro_clasifica_e_idempotente(self):
        call_command('sembrar_finanzas')
        f = date(2026, 8, 7)

        d = parsear_transferencia_mp(self._html())
        self.assertEqual(registrar_transferencia_mp(d, f, 'correo:mp:t1'), ('creado', 1))
        m = MovimientoFinanciero.objects.get(referencia='correo:mp:t1')
        self.assertEqual((m.clase, m.fuente, m.cuenta.clave, m.categoria.clave),
                         ('gasto', 'correo', 'mercado_pago', 'remuneraciones'))
        # Mismo correo de nuevo → no duplica.
        self.assertEqual(registrar_transferencia_mp(d, f, 'correo:mp:t1'), ('ya_existe', 0))

        # Insumos Sur → insumos.
        d2 = parsear_transferencia_mp(self._html(monto='89.990', nombre='Insumos Sur'))
        registrar_transferencia_mp(d2, f, 'correo:mp:t2')
        self.assertEqual(MovimientoFinanciero.objects.get(
            referencia='correo:mp:t2').categoria.clave, 'insumos')

        # Barrido a cuenta propia → traspaso con dos piernas enlazadas.
        d3 = parsear_transferencia_mp(self._html(monto='1.500.000',
                                                 nombre='Aremko Spa Scotiabank'))
        self.assertEqual(registrar_transferencia_mp(d3, f, 'correo:mp:t3'), ('creado', 2))
        sale = MovimientoFinanciero.objects.get(referencia='correo:mp:t3:sale')
        self.assertEqual(sale.clase, 'traspaso')
        self.assertEqual(sale.traspaso_par.cuenta.clave, 'scotiabank')
        self.assertEqual(sale.traspaso_par.traspaso_par_id, sale.id)

    def test_no_duplica_lo_que_cargo_el_historico(self):
        call_command('sembrar_finanzas')
        f = date(2026, 8, 2)
        MovimientoFinanciero.objects.create(
            fecha=f, cuenta=CuentaFinanciera.objects.get(clave='mercado_pago'),
            clase='gasto', sentido='sale', monto=40000,
            categoria=CategoriaFinanciera.objects.get(clave='remuneraciones'),
            fuente='correo', referencia='hist:mp:77')
        d = parsear_transferencia_mp(self._html(monto='40.000', nombre='Javiera Perez'))
        self.assertEqual(registrar_transferencia_mp(d, f, 'correo:mp:t9'),
                         ('en_historico', 0))


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
