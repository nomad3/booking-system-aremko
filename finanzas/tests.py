# -*- coding: utf-8 -*-
"""Tests de finanzas (P-22 F1).

Sin fixtures de ventas: la app es aislada y el tablero funciona con Pago vacío.
"""
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db.models import Sum
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from conciliacion.models import MOTIVO_NO_ES_COBRO, MovimientoMP

from .models import (CategoriaFinanciera, CuentaFinanciera,
                     MovimientoFinanciero, SaldoMensual)
from .services import (parsear_cartola_bancoestado, parsear_transferencia_mp,
                       registrar_compras_mp, registrar_comisiones_mp,
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


class ComisionesMPTest(TestCase):
    """F4 paso 2: la comisión que MP descuenta de cada cobro, como gasto."""

    def test_registra_con_corte_e_idempotencia(self):
        call_command('sembrar_finanzas')
        cobros = [
            # Cobro con comisión del lado de Aremko → gasto comisiones.
            dict(id=901, date_approved='2026-08-06T12:00:00.000-04:00',
                 description='Reserva Ana',
                 fee_details=[{'type': 'mercadopago_fee', 'amount': 1990.0,
                               'fee_payer': 'collector'}]),
            # Comisión que paga el CLIENTE → no es gasto de Aremko.
            dict(id=902, date_approved='2026-08-06T12:00:00.000-04:00',
                 fee_details=[{'amount': 500.0, 'fee_payer': 'payer'}]),
            # Transferencia simple sin comisión → nada.
            dict(id=903, date_approved='2026-08-06T12:00:00.000-04:00',
                 fee_details=[]),
            # Antes del corte de julio → fuera.
            dict(id=904, date_approved='2026-06-06T12:00:00.000-04:00',
                 fee_details=[{'amount': 1000.0, 'fee_payer': 'collector'}]),
        ]
        self.assertEqual(registrar_comisiones_mp(cobros), 1)
        m = MovimientoFinanciero.objects.get(referencia='mp:fee:901')
        self.assertEqual((m.clase, m.cuenta.clave, m.categoria.clave, int(m.monto)),
                         ('gasto', 'mercado_pago', 'comisiones', 1990))
        self.assertIn('Reserva Ana', m.descripcion)
        # Segunda corrida: no duplica.
        self.assertEqual(registrar_comisiones_mp(cobros), 0)
        self.assertEqual(MovimientoFinanciero.objects.filter(
            referencia__startswith='mp:fee:').count(), 1)


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

        # Nombre desconocido → por clasificar (plan de cuentas 2026-08-08:
        # ya no se asume que toda transferencia a persona es remuneración).
        d = parsear_transferencia_mp(self._html())
        self.assertEqual(registrar_transferencia_mp(d, f, 'correo:mp:t1'), ('creado', 1))
        m = MovimientoFinanciero.objects.get(referencia='correo:mp:t1')
        self.assertEqual((m.clase, m.fuente, m.cuenta.clave, m.categoria.clave),
                         ('gasto', 'correo', 'mercado_pago', 'por_clasificar'))

        # Masajista conocida por regla → honorarios.
        dm = parsear_transferencia_mp(self._html(monto='120.000', nombre='Sofia Plaza Cue'))
        registrar_transferencia_mp(dm, f, 'correo:mp:tm')
        self.assertEqual(MovimientoFinanciero.objects.get(
            referencia='correo:mp:tm').categoria.clave, 'honorarios_masajistas')
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


def _xlsx_cartola():
    """Un export de BancoEstado en memoria con la estructura real: Resumen con
    rótulos en col A y valores en col E; Movimientos con fechas DD/MM (sin
    año), cargos como enteros crudos y abonos/saldos como strings '$1.234'.
    Incluye dos transferencias GEMELAS el mismo día (el saldo encadenado las
    distingue) y el cruce julio→agosto (cierre de julio derivable)."""
    import io

    import openpyxl

    wb = openpyxl.Workbook()
    res = wb.active
    res.title = 'Resumen'
    for i, (k, v) in enumerate([
            ('Fecha Inicio', '14/07/2026'), ('Fecha Final', '04/08/2026'),
            ('Saldo Inicial', '$100.000'), ('Saldo Final', '$100.000'),
            ('N° Cuenta', '82370351925')], 1):
        res.cell(row=i, column=1, value=k)
        res.cell(row=i, column=5, value=v)
    mov = wb.create_sheet('Movimientos')
    mov.append(['Fecha', 'Sucursal', 'N° Cuenta', 'Alias', 'N° Cartola',
                'N° Operación', 'Descripción', 'Cheques / Cargos',
                'Depósitos / Abonos', 'Saldo'])
    mov.append(['15/07', 'STGO', '82370351925', 'CHEQ', 9, '0001077',
                'TEF DE SUMUP CHILE PAYMENTS S A', 0, '$50.000', '$150.000'])
    mov.append(['20/07', 'STGO', '82370351925', 'CHEQ', 9, '7023294',
                'TEF A PEREZ SOTO MARIA', 30000, '$0', '$120.000'])
    mov.append(['20/07', 'STGO', '82370351925', 'CHEQ', 9, '7023295',
                'TEF A PEREZ SOTO MARIA', 30000, '$0', '$90.000'])
    mov.append(['02/08', 'STGO', '82370351925', 'CHEQ', 9, '0001077',
                'TEF DE FLOW S A', 0, '$10.000', '$100.000'])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


class CartolaBancoEstadoTest(TestCase):
    """F4 paso 3: parser del export XLSX y página de carga con confirmación."""

    def test_parser_cuadra_clasifica_y_deriva_cierre_julio(self):
        r = parsear_cartola_bancoestado(_xlsx_cartola())
        self.assertTrue(r['cuadra'])
        self.assertEqual(len(r['filas']), 4)
        self.assertEqual(r['cierres_mes'], {'2026-07': 90000})
        # El año se asigna bien cruzando julio→agosto.
        self.assertEqual(r['filas'][-1]['fecha'], '2026-08-02')
        # Las gemelas (mismo día, mismo monto) tienen referencias distintas.
        refs = [f['referencia'] for f in r['filas']]
        self.assertEqual(len(refs), len(set(refs)))
        # Clasificación por descripción.
        self.assertEqual(r['filas'][0]['categoria'], 'liquidacion_sumup')
        self.assertEqual(r['filas'][1]['categoria'], 'por_clasificar')
        self.assertEqual(r['filas'][3]['categoria'], 'liquidacion_flow')

    def test_pagina_propone_confirma_y_no_duplica(self):
        call_command('sembrar_finanzas')
        User.objects.create_superuser('duenio', 'x@x.cl', 'x')
        self.client.login(username='duenio', password='x')
        url = reverse('finanzas:cargar_cartola')

        self.assertContains(self.client.get(url), 'Subir el export')

        # Propuesta: nada se escribe todavía.
        r = self.client.post(url, {'archivo': _xlsx_cartola()})
        self.assertContains(r, 'Confirmar y escribir 4')
        self.assertEqual(MovimientoFinanciero.objects.count(), 0)

        # Confirmar: se escriben los 4 + el cierre de julio.
        r2 = self.client.post(url, {'confirmar': '1',
                                    'payload': r.context['payload']})
        self.assertContains(r2, 'movimientos nuevos escritos')
        en_be = MovimientoFinanciero.objects.filter(cuenta__clave='bancoestado')
        self.assertEqual(en_be.count(), 4)
        self.assertEqual(en_be.filter(clase='ingreso').count(), 2)
        self.assertEqual(en_be.filter(fuente='captura').count(), 4)
        cierre = SaldoMensual.objects.get(cuenta__clave='bancoestado',
                                          periodo=date(2026, 7, 1))
        self.assertEqual((int(cierre.saldo_cierre), cierre.fuente),
                         (90000, 'cartola'))
        # Las categorías de ingreso se crearon solas.
        self.assertTrue(CategoriaFinanciera.objects.filter(
            clave='liquidacion_sumup', clase='ingreso').exists())

        # Re-subir el mismo archivo: todo «ya está», nada que confirmar.
        r3 = self.client.post(url, {'archivo': _xlsx_cartola()})
        self.assertContains(r3, 'Nada nuevo que escribir')
        # Y re-confirmar el payload viejo tampoco duplica.
        self.client.post(url, {'confirmar': '1', 'payload': r.context['payload']})
        self.assertEqual(en_be.count(), 4)

    def test_solo_superusuario(self):
        self.assertEqual(self.client.get(
            reverse('finanzas:cargar_cartola')).status_code, 302)


class CartolaScotiabankTest(TestCase):
    """F4 paso 3b: núcleo puro del parser Scotiabank + estados anti-doble-conteo."""

    # Estructura real de typeDesc.xls: metadatos rótulo/valor, encabezado, y
    # filas DESCENDENTES con cargos NEGATIVOS. Cruza julio→agosto.
    FILAS = [
        ['Nombre Empresa', 'AREMKO HOTEL SPA', '', '', '', '', ''],
        ['Saldo Disponible', 700000.0, '', '', '', '', ''],
        ['Fecha', 'Descripción', 'Sucursal', 'N° Doc.', 'Cargos', 'Abonos', 'Saldo'],
        ['02-08-2026', 'PAC SEGUROS GENERALES  51927', 'PM', 1.0, -100000.0, '', 700000.0],
        ['02-08-2026', 'REDCOMPRA COVEPA SPA', 'PM', 2.0, -50000.0, '', 800000.0],
        ['20-07-2026', 'TEF 76485192-7 AREMKO HOTEL SP', 'NM', 3.0, '', 500000.0, 850000.0],
        ['20-07-2026', 'TEF 12343982-1 Nancy Mansilla', 'PM', 4.0, -150000.0, '', 350000.0],
    ]

    def _parsear(self):
        from finanzas.services import parsear_filas_scotiabank
        return parsear_filas_scotiabank([list(f) for f in self.FILAS])

    def test_nucleo_invierte_encadena_y_clasifica(self):
        r = self._parsear()
        self.assertTrue(r['cuadra'])
        self.assertEqual(r['cadena_rota'], 0)
        # Invertido: la más vieja primero; saldo inicial derivado de ella.
        self.assertEqual(r['filas'][0]['fecha'], '2026-07-20')
        self.assertEqual(r['saldo_inicial'], 500000)   # 350.000 + 150.000
        self.assertEqual(r['saldo_final_calculado'], 700000)
        # Cierre de julio derivado (el archivo sigue en agosto).
        self.assertEqual(r['cierres_mes'], {'2026-07': 850000})
        # Clasificación: barrido propio → traspaso; TEF persona → gasto;
        # PAC SEGUROS → seguros; REDCOMPRA → por clasificar.
        por_desc = {f['descripcion']: f for f in r['filas']}
        self.assertEqual(por_desc['TEF 76485192-7 AREMKO HOTEL SP']['clase'], 'traspaso')
        self.assertTrue(por_desc['TEF 76485192-7 AREMKO HOTEL SP']['propio'])
        self.assertEqual(por_desc['TEF 12343982-1 Nancy Mansilla']['categoria'],
                         'por_clasificar')
        self.assertEqual(por_desc['PAC SEGUROS GENERALES  51927']['categoria'], 'seguros')

    def test_estados_evitan_dobles_conteos(self):
        from finanzas.services import estado_fila_cartola, registrar_filas_cartola
        call_command('sembrar_finanzas')
        r = self._parsear()
        por_desc = {f['descripcion']: f for f in r['filas']}

        # Barrido propio SIN traspaso registrado → revisar (no se crea suelto).
        barrido = por_desc['TEF 76485192-7 AREMKO HOTEL SP']
        self.assertEqual(estado_fila_cartola('scotiabank', barrido), 'revisar')

        # Con el traspaso registrado (fecha ±2 días) → ya_existe.
        mp = CuentaFinanciera.objects.get(clave='mercado_pago')
        sc = CuentaFinanciera.objects.get(clave='scotiabank')
        sale = MovimientoFinanciero.objects.create(
            fecha=date(2026, 7, 19), cuenta=mp, clase='traspaso', sentido='sale',
            monto=500000, fuente='correo', referencia='t:s')
        MovimientoFinanciero.objects.create(
            fecha=date(2026, 7, 19), cuenta=sc, clase='traspaso', sentido='entra',
            monto=500000, fuente='correo', referencia='t:e', traspaso_par=sale)
        self.assertEqual(estado_fila_cartola('scotiabank', barrido), 'ya_existe')

        # Gasto que el histórico mes-nivel ya cubre (mismo MES + monto) → en_historico.
        MovimientoFinanciero.objects.create(
            fecha=date(2026, 7, 1), cuenta=sc, clase='gasto', sentido='sale',
            monto=150000, fecha_estimada=True, fuente='correo',
            categoria=CategoriaFinanciera.objects.get(clave='por_clasificar'),
            referencia='hist:scotia:99')
        nancy = por_desc['TEF 12343982-1 Nancy Mansilla']
        self.assertEqual(estado_fila_cartola('scotiabank', nancy), 'en_historico')

        # El registro respeta los estados: solo entran los 2 gastos de agosto.
        creados, saltados = registrar_filas_cartola(
            r['filas'], r['cierres_mes'], cuenta_clave='scotiabank')
        self.assertEqual((creados, saltados), (2, 2))
        self.assertEqual(MovimientoFinanciero.objects.filter(
            fuente='captura', cuenta=sc).count(), 2)
        self.assertEqual(int(SaldoMensual.objects.get(
            cuenta=sc, periodo=date(2026, 7, 1)).saldo_cierre), 850000)


class FlujoCajaTest(TestCase):
    """F4 paso 4: saldo = ancla de julio + movimientos, día a día."""

    def test_ancla_mas_movimientos_da_el_saldo(self):
        call_command('sembrar_finanzas')
        be = CuentaFinanciera.objects.get(clave='bancoestado')
        sc = CuentaFinanciera.objects.get(clave='scotiabank')
        SaldoMensual.objects.create(cuenta=be, periodo=date(2026, 7, 1),
                                    saldo_cierre=1000000, fuente='cartola')
        SaldoMensual.objects.create(cuenta=sc, periodo=date(2026, 7, 1),
                                    saldo_cierre=500000, fuente='cartola')
        oi = CategoriaFinanciera.objects.get(clave='otros_ingresos')
        pc = CategoriaFinanciera.objects.get(clave='por_clasificar')
        M = MovimientoFinanciero
        M.objects.create(fecha=date(2026, 8, 2), cuenta=be, clase='ingreso',
                         sentido='entra', monto=100000, categoria=oi,
                         fuente='captura', referencia='fc:1')
        M.objects.create(fecha=date(2026, 8, 3), cuenta=sc, clase='gasto',
                         sentido='sale', monto=50000, categoria=pc,
                         fuente='captura', referencia='fc:2')
        # Traspaso BE → Scotia: mueve saldos, pero NO es entrada ni salida.
        M.objects.create(fecha=date(2026, 8, 4), cuenta=be, clase='traspaso',
                         sentido='sale', monto=200000, fuente='manual',
                         referencia='fc:3')
        M.objects.create(fecha=date(2026, 8, 4), cuenta=sc, clase='traspaso',
                         sentido='entra', monto=200000, fuente='manual',
                         referencia='fc:4')
        # Cobro MP por API (cuenta sin ancla: cuenta como entrada del día,
        # pero su saldo muestra «—»).
        MovimientoMP.objects.create(
            mp_payment_id='fc1', monto=30000,
            fecha=timezone.make_aware(datetime(2026, 8, 5, 12, 0)))

        User.objects.create_superuser('duenio', 'x@x.cl', 'x')
        self.client.login(username='duenio', password='x')
        r = self.client.get(reverse('finanzas:flujo_caja'))
        self.assertEqual(r.status_code, 200)

        # La primera fila es HOY (orden descendente pedido por Jorge).
        hoy_fila = r.context['filas'][0]
        self.assertEqual(hoy_fila['dia'], date.today())
        # Orden: MP, BancoEstado, Scotiabank, Efectivo + las dos puente
        # (sin ancla todavía → «—» y fuera de los totales).
        self.assertEqual(hoy_fila['saldos'],
                         ['—', '$900.000', '$650.000', '—', '—', '—'])
        self.assertEqual(hoy_fila['total_caja'], '$1.550.000')
        self.assertEqual(hoy_fila['total_puente'], '—')
        self.assertEqual(hoy_fila['total'], '$1.550.000')

        por_dia = {f['dia']: f for f in r.context['filas']}
        self.assertEqual(por_dia[date(2026, 8, 2)]['entradas'], '$100.000')
        self.assertEqual(por_dia[date(2026, 8, 4)]['entradas'], '')
        self.assertEqual(por_dia[date(2026, 8, 4)]['salidas'], '')
        self.assertEqual(por_dia[date(2026, 8, 5)]['entradas'], '$30.000')
        self.assertIn('Mercado Pago', ' '.join(r.context['sin_ancla']))

        # Detalle por día: cada fila trae sus movimientos uno a uno.
        self.assertEqual(por_dia[date(2026, 8, 2)]['n_movs'], 1)
        self.assertEqual(por_dia[date(2026, 8, 2)]['movs'][0]['sentido'], 'entra')
        # El día del traspaso muestra sus dos piernas.
        self.assertEqual(por_dia[date(2026, 8, 4)]['n_movs'], 2)
        self.assertEqual(por_dia[date(2026, 8, 4)]['movs'][0]['extra'], 'traspaso')
        # El cobro MP aparece con su glosa/etiqueta y cuenta.
        mp_mov = por_dia[date(2026, 8, 5)]['movs'][0]
        self.assertIn('Cobro MP', mp_mov['desc'])
        self.assertEqual(mp_mov['cuenta'], 'Mercado Pago')

    def test_traspaso_a_cuenta_puente_no_hace_desaparecer_la_plata(self):
        """El caso que pilló Jorge (2026-08-09): sacar plata del negocio a la
        CuentaRUT baja Caja Aremko pero NO el total disponible — la plata
        sigue existiendo, solo cambió de bolsillo."""
        call_command('sembrar_finanzas')
        sc = CuentaFinanciera.objects.get(clave='scotiabank')
        rut = CuentaFinanciera.objects.get(clave='cuentarut_jorge')
        SaldoMensual.objects.create(cuenta=sc, periodo=date(2026, 7, 1),
                                    saldo_cierre=3000000, fuente='cartola')
        SaldoMensual.objects.create(cuenta=rut, periodo=date(2026, 7, 1),
                                    saldo_cierre=344977, fuente='cartola')
        M = MovimientoFinanciero
        sale = M.objects.create(fecha=date(2026, 8, 2), cuenta=sc,
                                clase='traspaso', sentido='sale',
                                monto=1000000, fuente='manual',
                                referencia='fp:1')
        M.objects.create(fecha=date(2026, 8, 2), cuenta=rut, clase='traspaso',
                         sentido='entra', monto=1000000, fuente='manual',
                         referencia='fp:2', traspaso_par=sale)

        User.objects.create_superuser('duenio', 'x@x.cl', 'x')
        self.client.login(username='duenio', password='x')
        r = self.client.get(reverse('finanzas:flujo_caja'))
        hoy_fila = r.context['filas'][0]
        self.assertEqual(hoy_fila['total_caja'], '$2.000.000')
        self.assertEqual(hoy_fila['total_puente'], '$1.344.977')
        self.assertEqual(hoy_fila['total'], '$3.344.977')
        # Y el día del traspaso no muestra salida: no se gastó nada.
        por_dia = {f['dia']: f for f in r.context['filas']}
        self.assertEqual(por_dia[date(2026, 8, 2)]['salidas'], '')

    def test_gasto_desde_la_cuenta_puente_si_baja_el_total(self):
        """Contrapartida: cuando esa plata se gasta de verdad, el total baja."""
        call_command('sembrar_finanzas')
        call_command('aplicar_plan_cuentas', '--aplicar')
        rut = CuentaFinanciera.objects.get(clave='cuentarut_jorge')
        SaldoMensual.objects.create(cuenta=rut, periodo=date(2026, 7, 1),
                                    saldo_cierre=344977, fuente='cartola')
        MovimientoFinanciero.objects.create(
            fecha=date(2026, 8, 3), cuenta=rut, clase='gasto', sentido='sale',
            monto=119443, fuente='captura', referencia='fp:3',
            categoria=CategoriaFinanciera.objects.get(clave='infraestructura'))

        User.objects.create_superuser('duenio', 'x@x.cl', 'x')
        self.client.login(username='duenio', password='x')
        r = self.client.get(reverse('finanzas:flujo_caja'))
        hoy_fila = r.context['filas'][0]
        self.assertEqual(hoy_fila['total_puente'], '$225.534')
        por_dia = {f['dia']: f for f in r.context['filas']}
        self.assertEqual(por_dia[date(2026, 8, 3)]['salidas'], '$119.443')

    def test_solo_superusuario(self):
        self.assertEqual(self.client.get(
            reverse('finanzas:flujo_caja')).status_code, 302)


class CartolaScotiabankMensualTest(TestCase):
    """La segunda variante real del portal: estado de cuenta mensual —
    6 columnas, orden ASCENDENTE, Saldo Anterior/Actual en la cabecera."""

    FILAS = [
        ['Nombre Empresa', 'AREMKO HOTEL SPA', '', '', '', ''],
        ['Numero Cuenta', 973080644.0, '', '', '', ''],
        ['Fecha Desde', '01-07-2026', '', '', '', ''],
        ['Fecha Hasta', '31-07-2026', '', '', '', ''],
        ['Saldo Anterior', 882699.0, '', '', '', ''],
        ['Saldo Actual', 490434.0, '', '', '', ''],
        ['Fecha', 'Descripción', 'Numero Documento', 'Cargo', 'Abono', 'Saldo Diario'],
        ['01-07-2026', 'COMISION MANTENCION PLAN', 0.0, -40823.0, '', 841876.0],
        ['03-07-2026', 'TEF 18883207-5 PAULA ANDREA IB', 0.0, '', 155000.0, 996876.0],
        ['31-07-2026', 'REDCOMPRA COVEPA SPA', 0.0, -506442.0, '', 490434.0],
    ]

    def test_variante_mensual_cuadra_y_ancla_el_cierre(self):
        from finanzas.services import parsear_filas_scotiabank
        r = parsear_filas_scotiabank([list(f) for f in self.FILAS])
        self.assertTrue(r['cuadra'])
        self.assertEqual(r['cadena_rota'], 0)
        # NO se invierte (ya viene cronológico) y el inicio sale de la cabecera.
        self.assertEqual(r['filas'][0]['fecha'], '2026-07-01')
        self.assertEqual(r['saldo_inicial'], 882699)
        self.assertEqual(r['saldo_final_calculado'], 490434)
        # Mes cerrado (Fecha Hasta = 31-07) → ancla el cierre aunque no haya
        # filas de agosto.
        self.assertEqual(r['cierres_mes'], {'2026-07': 490434})
        self.assertEqual(r['cuenta_numero'], '973080644')
        # El abono de una clienta cuenta como ingreso (transferencia recibida).
        self.assertEqual(r['filas'][1]['categoria'], 'transferencias_recibidas')


class ComisionesSumUpTest(TestCase):
    """F5: la comisión de cada payout SumUp como gasto en la cuenta puente."""

    def test_registra_solo_payouts_exitosos_con_fee(self):
        from finanzas.services import registrar_payouts_sumup
        call_command('sembrar_finanzas')
        items = [
            # Payout real con comisión (estructura de la sonda 2026-08-08).
            {'id': 111, 'type': 'PAYOUT', 'status': 'SUCCESSFUL', 'fee': 1998.0,
             'amount': 58002.0, 'date': '2026-07-27', 'transaction_code': 'TAAA1'},
            # Sin comisión → nada.
            {'id': 222, 'type': 'PAYOUT', 'status': 'SUCCESSFUL', 'fee': 0,
             'amount': 10000.0, 'date': '2026-08-01'},
            # No es payout → fuera.
            {'id': 333, 'type': 'CHARGE_BACK', 'status': 'SUCCESSFUL',
             'fee': 500.0, 'date': '2026-08-01'},
            # Antes del corte de julio → fuera.
            {'id': 444, 'type': 'PAYOUT', 'status': 'SUCCESSFUL', 'fee': 900.0,
             'amount': 5000.0, 'date': '2026-06-15'},
        ]
        self.assertEqual(registrar_payouts_sumup(items), (1, 3))
        m = MovimientoFinanciero.objects.get(referencia='sumup:fee:111')
        self.assertEqual(
            (m.cuenta.clave, m.categoria.clave, int(m.monto), str(m.fecha)),
            ('sumup_transito', 'comisiones', 1998, '2026-07-27'))
        # La cuenta puente NO participa del flujo de caja.
        from finanzas.views import CUENTAS_FLUJO
        self.assertNotIn('sumup_transito', CUENTAS_FLUJO)
        # Idempotente.
        self.assertEqual(registrar_payouts_sumup(items), (0, 4))


class PlanCuentasTest(TestCase):
    """El plan de cuentas de Jorge (2026-08-08): grupos, reglas y reclasificación."""

    def test_reglas_puras(self):
        from finanzas.reglas import clasificar_por_reglas
        self.assertEqual(clasificar_por_reglas('TEF A VIDAL PANTOJA CAROLINA ANDREA'),
                         'honorarios_masajistas')
        self.assertEqual(clasificar_por_reglas('Cintia Brinzo'), 'personales_alda')
        self.assertEqual(clasificar_por_reglas('TEF 7604892-4 jorge aguilera'),
                         'personales_jorge')
        self.assertEqual(clasificar_por_reglas('TEF A AGUILERA GONZALEZ CRISTIAN AN'),
                         'infraestructura')
        self.assertEqual(clasificar_por_reglas('PAGO CRELL PUERTO VARAS'),
                         'energia_electrica')
        self.assertEqual(clasificar_por_reglas('Rafael Perez Quintero'),
                         'remuneraciones')
        self.assertIsNone(clasificar_por_reglas('REDCOMPRA COMERCIO CUALQUIERA'))

    def test_comando_sincroniza_y_reclasifica(self):
        call_command('sembrar_finanzas')
        call_command('cargar_historico_finanzas', '--aplicar')

        # Lectura: no crea ni cambia nada.
        call_command('aplicar_plan_cuentas')
        self.assertFalse(CategoriaFinanciera.objects.filter(
            clave='honorarios_masajistas').exists())

        call_command('aplicar_plan_cuentas', '--aplicar')
        self.assertEqual(CategoriaFinanciera.objects.get(
            clave='honorarios_masajistas').grupo, 'masajistas')
        self.assertEqual(CategoriaFinanciera.objects.get(
            clave='remuneraciones').grupo, 'personal')

        # Del histórico: Angélica/Alda → personales_alda; Martín → personales_martin.
        angelica = MovimientoFinanciero.objects.filter(
            descripcion__icontains='Angelica Toloza').first()
        self.assertEqual(angelica.categoria.clave, 'personales_alda')
        martin = MovimientoFinanciero.objects.filter(
            descripcion__icontains='Martin Aguilera').first()
        self.assertEqual(martin.categoria.clave, 'personales_martin')
        # Rafael era y sigue siendo remuneraciones (decisión de Jorge).
        rafael = MovimientoFinanciero.objects.filter(
            descripcion__icontains='Rafael Perez').first()
        self.assertEqual(rafael.categoria.clave, 'remuneraciones')

        # Idempotente: segunda corrida no cambia nada más.
        antes = list(MovimientoFinanciero.objects.values_list('id', 'categoria__clave'))
        call_command('aplicar_plan_cuentas', '--aplicar')
        self.assertEqual(antes, list(
            MovimientoFinanciero.objects.values_list('id', 'categoria__clave')))

    def test_tablero_separa_negocio_de_retiros(self):
        call_command('sembrar_finanzas')
        call_command('cargar_historico_finanzas', '--aplicar')
        call_command('aplicar_plan_cuentas', '--aplicar')
        User.objects.create_superuser('duenio', 'x@x.cl', 'x')
        self.client.login(username='duenio', password='x')
        r = self.client.get(reverse('finanzas:tablero'))
        self.assertContains(r, 'Resultado operacional')
        self.assertContains(r, 'Retiros familia')
        por_mes = {f['mes']: f for f in r.context['resumen']}
        julio = por_mes[date(2026, 7, 1)]
        # Julio tiene retiros de la familia (Alda/Jorge del histórico) > 0.
        self.assertNotEqual(julio['retiros'], '')
        self.assertNotEqual(julio['gastos'], '—')
        # La tabla agrupada trae subtotales de grupo.
        grupos = [f['nombre'] for f in r.context['tabla_gastos'] if f['es_grupo']]
        self.assertIn('Personales Alda', grupos)
        self.assertIn('Sueldos de personal', grupos)


class DevolucionesTest(TestCase):
    """Devoluciones = contra-ingreso: restan de ingresos, no suman a gastos."""

    def test_resumen_resta_de_ingresos(self):
        call_command('sembrar_finanzas')
        call_command('aplicar_plan_cuentas', '--aplicar')
        dev = CategoriaFinanciera.objects.get(clave='devoluciones')
        self.assertEqual(dev.grupo, 'devoluciones')
        MovimientoFinanciero.objects.create(
            fecha=date(2026, 8, 6),
            cuenta=CuentaFinanciera.objects.get(clave='bancoestado'),
            clase='gasto', sentido='sale', monto=50000, categoria=dev,
            fuente='manual', referencia='dev:test:1',
            descripcion='Devolución reserva anulada')

        User.objects.create_superuser('duenio', 'x@x.cl', 'x')
        self.client.login(username='duenio', password='x')
        r = self.client.get(reverse('finanzas:tablero'))
        por_mes = {f['mes']: f for f in r.context['resumen']}
        agosto = por_mes[date(2026, 8, 1)]
        # La devolución aparece en su columna, NO en gastos del negocio,
        # y los ingresos netos la restan (sin Pago en el test: 0 − 50.000).
        self.assertEqual(agosto['devoluciones'], '$50.000')
        self.assertEqual(agosto['gastos'], '$0')
        self.assertEqual(agosto['ingresos'], '$-50.000')
        self.assertEqual(agosto['resultado'], '$-50.000')
        # En el flujo de caja SÍ es plata que sale (día con salida real).
        rf = self.client.get(reverse('finanzas:flujo_caja'))
        por_dia = {f['dia']: f for f in rf.context['filas']}
        self.assertEqual(por_dia[date(2026, 8, 6)]['salidas'], '$50.000')


class AccesoColaboradorTest(TestCase):
    """El grupo «Finanzas colaborador» (Alda): ve las 3 páginas y solo edita
    la categoría de movimientos; el staff común sigue sin ver nada."""

    def setUp(self):
        call_command('sembrar_finanzas')
        from django.contrib.auth.models import Group
        self.grupo = Group.objects.create(name='Finanzas colaborador')
        self.alda = User.objects.create_user('alda', password='x', is_staff=True,
                                             first_name='Alda')
        self.alda.groups.add(self.grupo)

    def test_colaboradora_ve_las_tres_paginas(self):
        self.client.login(username='alda', password='x')
        for nombre in ('finanzas:tablero', 'finanzas:flujo_caja',
                       'finanzas:cargar_cartola'):
            self.assertEqual(self.client.get(reverse(nombre)).status_code, 200,
                             nombre)

    def test_staff_comun_sigue_afuera(self):
        User.objects.create_user('deborah', password='x', is_staff=True)
        self.client.login(username='deborah', password='x')
        for nombre in ('finanzas:tablero', 'finanzas:flujo_caja',
                       'finanzas:cargar_cartola'):
            self.assertEqual(self.client.get(reverse(nombre)).status_code, 302,
                             nombre)

    def test_admin_movimientos_solo_categoria_editable(self):
        from django.contrib import admin as dj_admin

        from .admin import MovimientoFinancieroAdmin
        from .models import MovimientoFinanciero

        ma = MovimientoFinancieroAdmin(MovimientoFinanciero, dj_admin.site)

        class Req:
            pass
        r = Req()
        r.user = self.alda
        self.assertTrue(ma.has_view_permission(r))
        self.assertTrue(ma.has_change_permission(r))
        self.assertFalse(ma.has_add_permission(r))
        self.assertFalse(ma.has_delete_permission(r))
        readonly = ma.get_readonly_fields(r)
        self.assertIn('monto', readonly)
        self.assertIn('cuenta', readonly)
        self.assertNotIn('categoria', readonly)

    def test_comando_configura_al_usuario_existente(self):
        from django.contrib.auth.models import Group
        Group.objects.filter(name='Finanzas colaborador').delete()
        self.alda.groups.clear()
        call_command('configurar_acceso_alda')
        self.alda.refresh_from_db()
        self.assertTrue(self.alda.groups.filter(
            name='Finanzas colaborador').exists())
        # La contraseña sigue funcionando (no se tocó).
        self.assertTrue(self.client.login(username='alda', password='x'))


class ReportesGastosTest(TestCase):
    """Reportes de Jorge 2026-08-09: plan de cuentas x cuenta financiera
    (mes elegido) y plan de cuentas x meses del año."""

    def setUp(self):
        call_command('sembrar_finanzas')
        from django.contrib.auth.models import Group
        grupo = Group.objects.create(name='Finanzas colaborador')
        self.alda = User.objects.create_user('alda', password='x', is_staff=True)
        self.alda.groups.add(grupo)

        from .models import (CategoriaFinanciera, CuentaFinanciera,
                             MovimientoFinanciero)
        be = CuentaFinanciera.objects.get(clave='bancoestado')
        mp = CuentaFinanciera.objects.get(clave='mercado_pago')
        luz = CategoriaFinanciera.objects.create(
            clave='test-luz', nombre='Luz Crell', clase='gasto', grupo='energia')
        sueldo = CategoriaFinanciera.objects.create(
            clave='test-sueldo', nombre='Sueldo Nancy', clase='gasto',
            grupo='personal')
        crear = MovimientoFinanciero.objects.create
        crear(fecha=date(2026, 7, 15), cuenta=be, clase='gasto', sentido='sale',
              monto=111000, descripcion='luz julio', categoria=luz,
              fuente='manual', referencia='manual:test:1')
        crear(fecha=date(2026, 8, 5), cuenta=be, clase='gasto', sentido='sale',
              monto=222000, descripcion='luz agosto', categoria=luz,
              fuente='manual', referencia='manual:test:2')
        crear(fecha=date(2026, 8, 10), cuenta=mp, clase='gasto', sentido='sale',
              monto=55000, descripcion='sueldo agosto', categoria=sueldo,
              fuente='manual', referencia='manual:test:3')
        # Un traspaso NO debe aparecer en ninguno de los dos reportes.
        crear(fecha=date(2026, 8, 12), cuenta=be, clase='traspaso',
              sentido='sale', monto=999999, descripcion='barrido',
              fuente='manual', referencia='manual:test:4')
        self.be, self.mp = be, mp

    def test_gastos_mes_cruza_plan_con_cuentas(self):
        self.client.login(username='alda', password='x')
        r = self.client.get(reverse('finanzas:gastos_mes'),
                            {'ano': 2026, 'mes': 8})
        self.assertEqual(r.status_code, 200)
        # Columnas: solo cuentas con gastos del mes, la mayor primero, con
        # nombre corto para que la tabla quepa en pantalla.
        self.assertEqual([c['largo'] for c in r.context['cuentas']],
                         [self.be.nombre, self.mp.nombre])
        self.assertEqual(r.context['cuentas'][0]['corto'],
                         'BancoEstado Chequera')
        # Grupo con una sola categoría → se muestra la fila del grupo
        # (mismo criterio del tablero).
        self.assertContains(r, 'Energía eléctrica')
        self.assertContains(r, 'Sueldos de personal')
        self.assertContains(r, '$222.000')
        self.assertContains(r, '$55.000')
        self.assertContains(r, '$277.000')          # total general del mes
        self.assertNotContains(r, '$111.000')       # julio queda fuera
        self.assertNotContains(r, '999.999')        # traspasos no son gasto

    def test_gastos_mes_selector_de_mes(self):
        self.client.login(username='alda', password='x')
        r = self.client.get(reverse('finanzas:gastos_mes'),
                            {'ano': 2026, 'mes': 7})
        self.assertContains(r, '$111.000')
        self.assertNotContains(r, '$222.000')

    def test_gastos_ano_mes_a_mes(self):
        self.client.login(username='alda', password='x')
        r = self.client.get(reverse('finanzas:gastos_ano'), {'ano': 2026})
        self.assertEqual(r.status_code, 200)
        # 2026 parte en julio (corte de datos).
        # Encabezado abreviado (cabe en pantalla), nombre completo en el title.
        self.assertEqual(r.context['columnas'][0]['nombre'], 'Jul')
        self.assertEqual(r.context['columnas'][0]['largo'], 'Julio')
        self.assertEqual(len(r.context['columnas']), 6)   # jul..dic
        self.assertContains(r, '$333.000')   # fila luz: 111 + 222
        self.assertContains(r, '$388.000')   # total general del anio
        self.assertNotContains(r, '999.999')

    def test_staff_comun_no_ve_los_reportes(self):
        User.objects.create_user('deborah', password='x', is_staff=True)
        self.client.login(username='deborah', password='x')
        for nombre in ('finanzas:gastos_mes', 'finanzas:gastos_ano'):
            self.assertEqual(self.client.get(reverse(nombre)).status_code,
                             302, nombre)

    def test_tarjeta_repo_en_el_panel(self):
        """La tarjeta REPO del panel: Alda ve los enlaces de finanzas
        adentro; el staff común la ve pero solo con Artesanías."""
        self.client.login(username='alda', password='x')
        r = self.client.get('/admin/')
        self.assertContains(r, 'REPO')
        self.assertContains(r, 'Gastos del mes')
        self.assertContains(r, 'Tablero financiero')

        User.objects.create_user('deborah', password='x', is_staff=True)
        self.client.login(username='deborah', password='x')
        r = self.client.get('/admin/')
        self.assertContains(r, 'REPO')
        self.assertNotContains(r, 'Tablero financiero')
        self.assertContains(r, 'Artesan')


BSA_ALDA = ("\r\n".join([
    ";Cartola ",
    ";Numero Cuenta : 99-00138-96",
    ";Fecha Desde : 24/06/2026",
    ";Fecha Hasta : 31/07/2026",
    ";Ejecutivo : EJECUTIVA DE PRUEBA",
    "Fecha;Descripcion;NroDoc.;Cargos;Abonos;Saldo",
    "   28062026;CARGO SEG.Fraude              ;00000000;0000000005000,00;;+0000000061836,00",
    "   02072026;TEF 76485192-7 AREMKO HOTEL SP;00000000;;0000001000000,00;+0000001061836,00",
    "   02072026;820407_PAGO TARJ.CRED. POR SWE;00000000;0000001000000,00;;+0000000061836,00",
    "   06072026;CARGO SEG.Fraude              ;00000000;0000000010618,00;;+0000000051218,00",
    "   10072026;EMISION DE VIGENTE.     298494;00000000;0000000020000,00;;+0000000031218,00",
    "   13072026;TEF 11744727-8 ALDA ANGELICA T;00000000;;0000000400000,00;+0000000431218,00",
]) + "\r\n").encode("latin-1")


class CartolaAldaTest(TestCase):
    """F7: la cuenta personal de Alda — BSA.dat de Scotia Connect."""

    def setUp(self):
        call_command('sembrar_finanzas')

    def _retiro_aremko(self):
        cat = CategoriaFinanciera.objects.create(
            clave='retiros-alda-test', nombre='Retiros Alda', clase='gasto',
            grupo='personales_alda')
        return MovimientoFinanciero.objects.create(
            fecha=date(2026, 7, 2),
            cuenta=CuentaFinanciera.objects.get(clave='mercado_pago'),
            clase='gasto', sentido='sale', monto=1000000, categoria=cat,
            descripcion='Transferencia a ALDA ANGELICA TOLOZA',
            fuente='correo', referencia='correo:mp:test-retiro')

    def test_parser_bsa(self):
        import io

        from .services import parsear_cartola_alda
        datos = parsear_cartola_alda(io.BytesIO(BSA_ALDA))
        self.assertEqual(datos['cuenta_numero'], '99-00138-96')
        self.assertEqual(len(datos['filas']), 6)
        self.assertTrue(datos['cuadra'])            # cadena de saldos sana
        self.assertEqual(datos['cierres_mes']['2026-07'], 431218)
        self.assertEqual(datos['cierres_mes']['2026-06'], 61836)

        por_desc = {f['descripcion']: f for f in datos['filas']}
        aremko = por_desc['TEF 76485192-7 AREMKO HOTEL SP']
        self.assertEqual((aremko['clase'], aremko['propio']), ('traspaso', True))
        self.assertEqual(aremko['abono'], 1000000)
        self.assertEqual(
            por_desc['TEF 11744727-8 ALDA ANGELICA T']['clase'], 'personal')
        self.assertEqual(
            por_desc['820407_PAGO TARJ.CRED. POR SWE']['categoria'],
            'tarjeta_alda')
        # Scotiabank llama «EMISION DE VIGENTE» al vale vista: no se adivina
        # su destino, queda por clasificar y visible.
        self.assertEqual(
            por_desc['EMISION DE VIGENTE.     298494']['categoria'],
            'vale_vista_alda')
        self.assertEqual(
            por_desc['EMISION DE VIGENTE.     298494']['cargo'], 20000)

    def test_reglas_de_clasificacion(self):
        from .services import clasificar_fila_alda
        casos = [
            ('TEF 11744727-8 alda Toloza BCI', 'traslado_alda'),
            ('PAGO AUTOMATICO LINEA CREDITO', 'banco_alda'),
            ('PAGO INTERES LINEA DE CREDITO', 'banco_alda'),
            ('ABONO A L.CREDITO POR SGO', 'banco_alda'),
            ('CARGO SEG.Fraude', 'banco_alda'),
            ('820407_PAGO TARJ.CRED. POR SWE', 'tarjeta_alda'),
            ('REDCOMPRA ARTESANIAS WILMA', 'personales_alda_pc'),
            ('eCOMMERCE DL TEMUCOM', 'personales_alda_pc'),
        ]
        for desc, esperada in casos:
            clase, sentido, cat, propio = clasificar_fila_alda(desc, 1000, 0)
            self.assertEqual((clase, sentido, cat, propio),
                             ('gasto', 'sale', esperada, False), desc)
        # Los abonos de su línea de crédito no son ingreso de nadie.
        self.assertEqual(
            clasificar_fila_alda('TRANSFERENCIA DE LINEA CREDITO', 0, 5000)[0],
            'personal')

    def test_registro_convierte_el_retiro_y_es_idempotente(self):
        import io

        from .services import (estado_fila_cartola, parsear_cartola_alda,
                               registrar_filas_alda)
        retiro = self._retiro_aremko()
        datos = parsear_cartola_alda(io.BytesIO(BSA_ALDA))

        # El abono desde Aremko se ofrece como NUEVO (hay retiro que calza).
        aremko = next(f for f in datos['filas']
                      if 'AREMKO' in f['descripcion'])
        self.assertEqual(estado_fila_cartola('scotiabank_alda', aremko),
                         'nuevo')

        creados, saltados, convertidos = registrar_filas_alda(
            datos['filas'], datos['cierres_mes'])
        # 3 cargos de julio + el abono personal (que también mueve su saldo);
        # solo junio queda fuera por cobertura.
        self.assertEqual((creados, convertidos, saltados), (4, 1, 1))
        # El abono que no viene de Aremko entra como ingreso personal: hace
        # que el saldo de la cuenta puente cuadre con el banco, sin tocar el
        # resultado del negocio.
        personal = MovimientoFinanciero.objects.get(monto=400000)
        self.assertEqual(personal.clase, 'ingreso')
        self.assertEqual(personal.categoria.clave, 'abonos_personales')

        retiro.refresh_from_db()
        self.assertEqual(retiro.clase, 'traspaso')
        self.assertIsNone(retiro.categoria)
        entra = retiro.traspaso_par
        self.assertEqual(entra.cuenta.clave, 'scotiabank_alda')
        self.assertEqual((entra.sentido, int(entra.monto)),
                         ('entra', 1000000))
        # La suma global de traspasos sigue en cero.
        tras = (MovimientoFinanciero.objects.filter(clase='traspaso')
                .values('sentido').annotate(t=Sum('monto')))
        por_sentido = {r['sentido']: int(r['t']) for r in tras}
        self.assertEqual(por_sentido.get('entra'), por_sentido.get('sale'))

        # El vale vista quedó como gasto de la EMPRESA (grupo impuestos).
        vale = MovimientoFinanciero.objects.get(monto=20000,
                                                cuenta__clave='scotiabank_alda')
        self.assertEqual(vale.categoria.clave, 'vale_vista_alda')
        self.assertEqual(vale.categoria.grupo, 'otros')
        # La tarjeta quedó personal.
        tarjeta = MovimientoFinanciero.objects.get(
            monto=1000000, cuenta__clave='scotiabank_alda', clase='gasto')
        self.assertEqual(tarjeta.categoria.grupo, 'personales_alda')

        # Re-registrar: nada nuevo, nada se convierte dos veces.
        creados2, saltados2, convertidos2 = registrar_filas_alda(
            datos['filas'], datos['cierres_mes'])
        self.assertEqual((creados2, convertidos2), (0, 0))

    def test_vista_detecta_bsa_y_marca_personales(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        self._retiro_aremko()
        User.objects.create_superuser('jefe', password='x')
        self.client.login(username='jefe', password='x')

        r = self.client.post(reverse('finanzas:cargar_cartola'),
                             {'archivo': SimpleUploadedFile('BSA.dat',
                                                            BSA_ALDA)})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Scotiabank Alda (personal)')
        self.assertContains(r, 'abono personal')
        self.assertContains(r, 'fuera de cobertura')     # la fila de junio

        # Un BSA de otra cuenta se rechaza con mensaje claro.
        otro = BSA_ALDA.replace(b'99-00138-96', b'11-22222-33')
        r2 = self.client.post(reverse('finanzas:cargar_cartola'),
                              {'archivo': SimpleUploadedFile('BSA.dat', otro)})
        self.assertContains(r2, '11-22222-33')


class MovimientosPegadosTest(TestCase):
    """F7b: la CuentaRUT de Jorge se carga pegando lo que muestra la app."""

    def setUp(self):
        call_command('sembrar_finanzas')
        call_command('aplicar_plan_cuentas', '--aplicar')
        User.objects.create_superuser('jefe', password='x')
        self.client.login(username='jefe', password='x')

    PEGADO = """
14-07-2026 ; Pago Google Ads Google ; -180.000
14-07-2026 ; Tef De Aremko Hotel Spa ; 200.000
06-07-2026 ; Pago Fs Dataforseo ; -56.560
06-07-2026 ; Comision Transaccion Internacional ; -1.075
06-07-2026 ; Tef A Martin Aguilera Toloza 777021 ; -20.000
18-07-2026 ; Abono Convenio Afp Plan Vital ; 162.154
20-06-2026 ; Pago viejo antes del corte ; -9.999
"""

    def test_parseo_y_clasificacion(self):
        from .services import preparar_filas_manual
        filas, errores = preparar_filas_manual(self.PEGADO, 'cuentarut_jorge')
        self.assertEqual(errores, [])
        self.assertEqual(len(filas), 7)
        por_desc = {f['descripcion']: f for f in filas}
        self.assertEqual(por_desc['Pago Google Ads Google']['categoria'],
                         'publicidad')
        self.assertEqual(por_desc['Pago Google Ads Google']['cargo'], 180000)
        self.assertEqual(por_desc['Pago Fs Dataforseo']['categoria'],
                         'infraestructura')
        self.assertEqual(por_desc['Comision Transaccion Internacional']
                         ['categoria'], 'comisiones')
        self.assertEqual(por_desc['Tef A Martin Aguilera Toloza 777021']
                         ['categoria'], 'personales_martin')
        aremko = por_desc['Tef De Aremko Hotel Spa']
        self.assertEqual((aremko['clase'], aremko['abono']), ('traspaso', 200000))
        self.assertEqual(por_desc['Abono Convenio Afp Plan Vital']['clase'],
                         'personal')

    def test_lineas_malas_se_reportan(self):
        from .services import preparar_filas_manual
        filas, errores = preparar_filas_manual(
            "14-07-2026 ; Buena ; -1.000\n"
            "sin fecha ; Mala ; -2.000\n"
            "15-07-2026 ; Sin monto ; abc\n"
            "15-07-2026 solo dos campos\n", 'cuentarut_jorge')
        self.assertEqual(len(filas), 1)
        self.assertEqual(len(errores), 3)
        self.assertEqual([n for n, _, _ in errores], [2, 3, 4])

    def test_carga_e2e_por_la_pagina_es_idempotente(self):
        url = reverse('finanzas:cargar_movimientos')
        r = self.client.post(url, {'cuenta': 'cuentarut_jorge',
                                   'texto': self.PEGADO})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'CuentaRUT Jorge')
        self.assertContains(r, 'publicidad')
        # El abono de AFP entra como personal; el de junio queda fuera.
        self.assertContains(r, 'abono personal')
        self.assertContains(r, 'fuera de cobertura')
        # Sin retiro que calce, el abono de Aremko pide revisión.
        self.assertContains(r, 'sin retiro que calce')
        payload = r.context['payload']
        self.assertEqual(r.context['n_nuevas'], 5)   # 4 cargos + abono AFP

        r2 = self.client.post(url, {'payload': payload, 'confirmar': '1'})
        self.assertEqual(r2.context['resultado']['creados'], 5)
        google = MovimientoFinanciero.objects.get(monto=180000)
        self.assertEqual(google.cuenta.clave, 'cuentarut_jorge')
        self.assertEqual(google.categoria.grupo, 'marketing')
        self.assertEqual(google.fuente, 'captura')

        # Re-pegar el mismo bloque: todo "ya está", nada se duplica.
        r3 = self.client.post(url, {'cuenta': 'cuentarut_jorge',
                                    'texto': self.PEGADO})
        self.assertEqual(r3.context['n_nuevas'], 0)
        self.assertEqual(MovimientoFinanciero.objects.filter(
            cuenta__clave='cuentarut_jorge').count(), 5)

    def test_retiro_a_jorge_se_convierte_en_traspaso(self):
        from .services import registrar_filas_puente, preparar_filas_manual
        cat = CategoriaFinanciera.objects.get(clave='personales_jorge')
        retiro = MovimientoFinanciero.objects.create(
            fecha=date(2026, 7, 14),
            cuenta=CuentaFinanciera.objects.get(clave='mercado_pago'),
            clase='gasto', sentido='sale', monto=200000, categoria=cat,
            descripcion='Transferencia a Jorge', fuente='correo',
            referencia='correo:mp:test-jorge')
        filas, _ = preparar_filas_manual(
            "14-07-2026 ; Tef De Aremko Hotel Spa ; 200.000",
            'cuentarut_jorge')
        creados, saltados, convertidos = registrar_filas_puente(
            filas, 'cuentarut_jorge')
        self.assertEqual((creados, convertidos), (0, 1))
        retiro.refresh_from_db()
        self.assertEqual(retiro.clase, 'traspaso')
        self.assertEqual(retiro.traspaso_par.cuenta.clave, 'cuentarut_jorge')

    def test_dos_movimientos_identicos_el_mismo_dia_entran_los_dos(self):
        from .services import preparar_filas_manual
        filas, _ = preparar_filas_manual(
            "20-07-2026 ; Pago Farmacias Del Doc ; -3.090\n"
            "20-07-2026 ; Pago Farmacias Del Doc ; -3.090\n",
            'cuentarut_jorge')
        self.assertEqual(len({f['referencia'] for f in filas}), 2)
