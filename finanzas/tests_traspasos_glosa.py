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
                       clasificar_compra_tarjeta, destino_puente,
                       marcar_traspaso_puente)


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


class TraspasoHuerfanoTest(TestCase):
    """22/08/2026 — el bug que dejó $809.331 en piernas sin par.

    La vista previa de cartolas marcaba `f['clase'] = 'traspaso'` para mostrar
    que un cargo hacia una cuenta puente no es retiro, pero ese mismo dict
    viaja firmado al confirmar: `registrar_filas_cartola` decide si arma el
    traspaso de dos piernas preguntando `if f['clase'] == 'gasto'`, y ya nunca
    se cumplía. Quedaba una pierna «sale» huérfana y los traspasos dejaban de
    cuadrar.
    """

    def setUp(self):
        call_command('sembrar_finanzas')
        call_command('aplicar_plan_cuentas', '--aplicar')

    def _fila(self, clase='gasto'):
        return {
            'fecha': '2026-08-06', 'descripcion': 'TEF A TOLOZA POBLETE ALDA ANGELICA',
            'cargo': 500000, 'abono': 0, 'saldo': 0,
            'clase': clase, 'sentido': 'sale', 'categoria': 'por_clasificar',
            'referencia': 'be:huerfano-test',
        }

    def test_la_carga_arma_las_DOS_piernas_y_cuadran(self):
        from .services import registrar_filas_cartola
        registrar_filas_cartola([self._fila()], cuenta_clave='bancoestado')
        piernas = MovimientoFinanciero.objects.filter(clase='traspaso')
        self.assertEqual(piernas.count(), 2, 'deben ser dos piernas')
        sale = piernas.get(sentido='sale')
        entra = piernas.get(sentido='entra')
        self.assertEqual(sale.traspaso_par_id, entra.id)
        self.assertEqual(entra.traspaso_par_id, sale.id)
        self.assertEqual(entra.cuenta.clave, 'scotiabank_alda')
        # Un traspaso no lleva categoría: no es ingreso ni gasto.
        self.assertIsNone(sale.categoria)
        # Y el control global cuadra: lo que sale es igual a lo que entra.
        self.assertEqual(sum(int(m.monto) for m in piernas.filter(sentido='sale')),
                         sum(int(m.monto) for m in piernas.filter(sentido='entra')))

    def test_no_queda_ninguna_pierna_sin_par(self):
        from .services import registrar_filas_cartola
        registrar_filas_cartola([self._fila()], cuenta_clave='bancoestado')
        self.assertFalse(
            MovimientoFinanciero.objects.filter(
                clase='traspaso', traspaso_par__isnull=True).exists())


class CalzarHuerfanoTest(TestCase):
    """Los huérfanos que ya están en la base tienen que poder repararse."""

    def setUp(self):
        call_command('sembrar_finanzas')
        call_command('aplicar_plan_cuentas', '--aplicar')
        self.be = CuentaFinanciera.objects.get(clave='bancoestado')
        self.alda = CuentaFinanciera.objects.get(clave='scotiabank_alda')
        self.por_calzar, _ = CategoriaFinanciera.objects.get_or_create(
            clave=CLAVE_POR_CALZAR,
            defaults={'nombre': 'Abono desde Aremko por calzar',
                      'clase': 'ingreso', 'grupo': 'otros'})

    def _huerfano(self, monto=500000, fecha=date(2026, 8, 6)):
        return MovimientoFinanciero.objects.create(
            fecha=fecha, cuenta=self.be, clase='traspaso', sentido='sale',
            monto=Decimal(monto),
            categoria=CategoriaFinanciera.objects.get(clave='por_clasificar'),
            fuente='captura', referencia=f'h:{monto}:{fecha}',
            descripcion='Cartola bancoestado: TEF A TOLOZA POBLETE ALDA ANG')

    def _abono(self, monto=500000, fecha=date(2026, 8, 5)):
        return MovimientoFinanciero.objects.create(
            fecha=fecha, cuenta=self.alda, clase='ingreso', sentido='entra',
            monto=Decimal(monto), categoria=self.por_calzar, fuente='captura',
            referencia=f'a:{monto}:{fecha}',
            descripcion='Cartola scotiabank alda: TEF 76485192-7 AREMKO')

    def test_el_huerfano_aparece_como_candidato(self):
        h = self._huerfano()
        self.assertIn(h.id, [c.id for c in candidatos_de_calce(self._abono())])

    def test_una_pierna_YA_emparejada_no_se_ofrece(self):
        # Solo las huérfanas: una pareja armada no se toca.
        h = self._huerfano()
        otra = self._huerfano(monto=500000, fecha=date(2026, 8, 7))
        h.traspaso_par = otra
        h.save(update_fields=['traspaso_par'])
        self.assertNotIn(h.id, [c.id for c in candidatos_de_calce(self._abono())])

    def test_calzarlo_deja_las_piernas_cuadradas(self):
        from .services import calzar_abono_con_retiro
        h, a = self._huerfano(), self._abono()
        comun, resto_a, resto_r = calzar_abono_con_retiro(a, h)
        self.assertEqual((comun, resto_a, resto_r), (500000, 0, 0))
        h.refresh_from_db(); a.refresh_from_db()
        self.assertEqual(h.traspaso_par_id, a.id)
        self.assertEqual(a.clase, 'traspaso')
        self.assertIsNone(a.categoria)

    def test_calce_parcial_deja_el_resto_con_categoria(self):
        # Un gasto sin categoría es un dato corrupto: el resto cae en
        # «por clasificar», que es donde se ve.
        from .services import calzar_abono_con_retiro
        h = self._huerfano(monto=500000)
        h.categoria = None
        h.save(update_fields=['categoria'])
        comun, resto_a, resto_r = calzar_abono_con_retiro(self._abono(monto=430000), h)
        self.assertEqual((comun, resto_a, resto_r), (430000, 0, 70000))
        resto = MovimientoFinanciero.objects.get(referencia__endswith=':resto')
        self.assertEqual(resto.clase, 'gasto')
        self.assertIsNotNone(resto.categoria)
        self.assertEqual(resto.categoria.clave, 'por_clasificar')


class MarcarTraspasoPuenteTest(TestCase):
    """EL test que faltaba: la vista previa no puede tocar `clase`.

    Es el invariante que se rompió el 22/08/2026 — el dict de la propuesta
    viaja firmado hasta la escritura, y allá se decide por `clase == 'gasto'`
    si se arman las dos piernas del traspaso. Marcar para la pantalla está
    bien; mutar el dato, no.
    """

    def _fila(self):
        return {'fecha': '2026-08-06', 'clase': 'gasto', 'sentido': 'sale',
                'categoria': 'por_clasificar', 'cargo': 500000, 'abono': 0,
                'descripcion': 'TEF A TOLOZA POBLETE ALDA ANGELICA'}

    def test_marca_para_mostrar_pero_NO_toca_clase_ni_categoria(self):
        f = marcar_traspaso_puente(self._fila(), 'bancoestado',
                                   {'scotiabank_alda': 'Scotiabank Alda'})
        self.assertTrue(f['es_traspaso_puente'])
        self.assertEqual(f['destino_puente'], 'Scotiabank Alda')
        # Lo que importa: la escritura sigue viendo un gasto y arma las dos piernas.
        self.assertEqual(f['clase'], 'gasto')
        self.assertEqual(f['categoria'], 'por_clasificar')

    def test_una_glosa_que_no_es_puente_no_se_marca(self):
        f = self._fila()
        f['descripcion'] = 'COMPRA JUMBO PUERTO VARAS'
        f = marcar_traspaso_puente(f, 'bancoestado', {})
        self.assertNotIn('es_traspaso_puente', f)
        self.assertEqual(f['clase'], 'gasto')

    def test_un_abono_no_se_marca_aunque_diga_el_nombre(self):
        f = self._fila()
        f['clase'], f['sentido'] = 'ingreso', 'entra'
        self.assertNotIn('es_traspaso_puente',
                         marcar_traspaso_puente(f, 'bancoestado', {}))


class DeshacerCalceTest(TestCase):
    """El botón Deshacer (22/08/2026).

    Nace de un error real: se calzó un pago a Previred contra un abono de Alda
    —$567.500 los dos, a nueve días de distancia— y deshacerlo exigió un
    comando escrito a mano. La herramienta sabía crear el par pero no romperlo.
    """

    def setUp(self):
        call_command('sembrar_finanzas')
        call_command('aplicar_plan_cuentas', '--aplicar')
        self.scotia = CuentaFinanciera.objects.get(clave='scotiabank')
        self.alda = CuentaFinanciera.objects.get(clave='scotiabank_alda')
        self.imposiciones = CategoriaFinanciera.objects.get(clave='imposiciones')
        self.por_calzar, _ = CategoriaFinanciera.objects.get_or_create(
            clave=CLAVE_POR_CALZAR,
            defaults={'nombre': 'Abono desde Aremko por calzar',
                      'clase': 'ingreso', 'grupo': 'otros'})

    def _par(self, monto=567500):
        """El caso real: un gasto de imposiciones y un abono, calzados."""
        from .services import calzar_abono_con_retiro
        gasto = MovimientoFinanciero.objects.create(
            fecha=date(2026, 7, 1), cuenta=self.scotia, clase='gasto',
            sentido='sale', monto=Decimal(monto), categoria=self.imposiciones,
            fuente='captura', referencia='d:gasto',
            descripcion='Cartola scotiabank: TEF PATRICIO RUBIO')
        abono = MovimientoFinanciero.objects.create(
            fecha=date(2026, 7, 10), cuenta=self.alda, clase='ingreso',
            sentido='entra', monto=Decimal(monto), categoria=self.por_calzar,
            fuente='captura', referencia='d:abono',
            descripcion='Cartola scotiabank alda: TEF 76485192-7 AREMKO')
        calzar_abono_con_retiro(abono, gasto)
        gasto.refresh_from_db(); abono.refresh_from_db()
        return gasto, abono

    def test_al_calzar_se_guarda_la_categoria_para_poder_volver(self):
        gasto, abono = self._par()
        self.assertEqual(gasto.clase, 'traspaso')
        self.assertIsNone(gasto.categoria)
        self.assertEqual(gasto.categoria_previa.clave, 'imposiciones')

    def test_deshacer_devuelve_las_dos_piernas_a_como_estaban(self):
        from .services import descalzar_par
        gasto, abono = self._par()
        descalzar_par(gasto)
        gasto.refresh_from_db(); abono.refresh_from_db()
        # El gasto vuelve a ser gasto, con SU categoría — no una genérica.
        self.assertEqual(gasto.clase, 'gasto')
        self.assertEqual(gasto.categoria.clave, 'imposiciones')
        self.assertIsNone(gasto.traspaso_par)
        self.assertIsNone(gasto.categoria_previa)
        # Y el abono vuelve a la cola de por calzar.
        self.assertEqual(abono.clase, 'ingreso')
        self.assertEqual(abono.categoria.clave, CLAVE_POR_CALZAR)
        self.assertIsNone(abono.traspaso_par)

    def test_deshacer_desde_cualquiera_de_las_dos_piernas(self):
        from .services import descalzar_par
        gasto, abono = self._par()
        descalzar_par(abono)          # se tira del otro lado
        gasto.refresh_from_db()
        self.assertEqual(gasto.categoria.clave, 'imposiciones')

    def test_una_pierna_vieja_sin_categoria_previa_cae_en_el_default_honesto(self):
        # Filas anteriores al campo: no se inventa una categoría, se usa el
        # default de cada lado y Jorge la asigna.
        from .services import descalzar_par
        gasto, abono = self._par()
        MovimientoFinanciero.objects.filter(
            pk__in=(gasto.pk, abono.pk)).update(categoria_previa=None)
        gasto.refresh_from_db()
        descalzar_par(gasto)
        gasto.refresh_from_db(); abono.refresh_from_db()
        self.assertEqual(gasto.categoria.clave, 'por_clasificar')
        self.assertEqual(abono.categoria.clave, CLAVE_POR_CALZAR)

    def test_deshacer_algo_que_no_es_traspaso_no_hace_nada(self):
        from .services import descalzar_par
        suelto = MovimientoFinanciero.objects.create(
            fecha=date(2026, 7, 1), cuenta=self.scotia, clase='gasto',
            sentido='sale', monto=Decimal('1000'), categoria=self.imposiciones,
            fuente='manual', referencia='d:suelto')
        self.assertEqual(descalzar_par(suelto), [])
        self.assertEqual(descalzar_par(None), [])
        suelto.refresh_from_db()
        self.assertEqual(suelto.clase, 'gasto')

    def test_calzar_y_deshacer_deja_las_piernas_cuadradas(self):
        # El invariante de siempre: entra == sale.
        from django.db.models import Sum
        from .services import descalzar_par
        gasto, _ = self._par()
        descalzar_par(gasto)
        agg = {r['sentido']: int(r['t']) for r in
               MovimientoFinanciero.objects.filter(clase='traspaso')
               .values('sentido').annotate(t=Sum('monto'))}
        self.assertEqual(agg.get('entra', 0), agg.get('sale', 0))

    def test_el_par_aparece_en_la_lista_de_calzados(self):
        from .services import pares_calzados
        gasto, _ = self._par()
        self.assertIn(gasto.id, [m.id for m in pares_calzados(dias=3650)])


class GuardasDeCandidatosTest(TestCase):
    """22/08/2026 — el caso que corrompió datos.

    Un abono de $567.500 que Aremko le mandó a Alda se consumió en SEIS calces
    parciales seguidos contra cosas que no podían ser su origen: un consumo de
    restorán de la tarjeta de ella, un retiro a Martín desde la CuentaRUT de
    Jorge, compras con tarjeta. El filtro solo miraba monto y fecha.
    """

    def setUp(self):
        call_command('sembrar_finanzas')
        call_command('aplicar_plan_cuentas', '--aplicar')
        self.por_calzar, _ = CategoriaFinanciera.objects.get_or_create(
            clave=CLAVE_POR_CALZAR,
            defaults={'nombre': 'Abono desde Aremko por calzar',
                      'clase': 'ingreso', 'grupo': 'otros'})
        self.abono_alda = MovimientoFinanciero.objects.create(
            fecha=date(2026, 7, 10),
            cuenta=CuentaFinanciera.objects.get(clave='scotiabank_alda'),
            clase='ingreso', sentido='entra', monto=Decimal('567500'),
            categoria=self.por_calzar, fuente='captura', referencia='g:abono',
            descripcion='Cartola scotiabank alda: TEF 76485192-7 AREMKO HOTEL SP')

    def _salida(self, cuenta_clave, monto, glosa, cat='por_clasificar'):
        return MovimientoFinanciero.objects.create(
            fecha=date(2026, 7, 10),
            cuenta=CuentaFinanciera.objects.get(clave=cuenta_clave),
            clase='gasto', sentido='sale', monto=Decimal(monto),
            categoria=CategoriaFinanciera.objects.get(clave=cat),
            fuente='captura', referencia=f'g:{cuenta_clave}:{monto}',
            descripcion=glosa)

    def _ids(self):
        return [m.id for m in candidatos_de_calce(self.abono_alda)]

    def test_una_compra_de_la_tarjeta_de_alda_no_puede_ser_el_origen(self):
        # $109.560 en LA FORJA PARRILLA: es un consumo de ella, no plata de Aremko.
        m = self._salida('tarjeta_alda_1', 109560,
                         'Tarjeta: LA FORJA PARRILLA PUERTO VARAS')
        self.assertNotIn(m.id, self._ids())

    def test_una_salida_de_la_cuentarut_de_jorge_tampoco(self):
        m = self._salida('cuentarut_jorge', 20000,
                         'Cartola cuentarut jorge: Tef A Martin Aguilera Toloza')
        self.assertNotIn(m.id, self._ids())

    def test_plata_que_iba_a_JORGE_no_calza_con_el_abono_de_ALDA(self):
        # Sale de una cuenta de Aremko (pasa la guarda 1) pero la glosa dice
        # a quién iba, y no es la dueña de esta cuenta.
        m = self._salida('bancoestado', 200000,
                         'Cartola bancoestado: TEF BANCOESTADO A AGUILERA GONZALEZ')
        self.assertNotIn(m.id, self._ids())

    def test_plata_de_aremko_que_SI_iba_a_alda_se_ofrece(self):
        m = self._salida('bancoestado', 248000,
                         'Cartola bancoestado: TEF A TOLOZA POBLETE ALDA ANGELICA')
        self.assertIn(m.id, self._ids())

    def test_una_glosa_que_no_dice_a_quien_sigue_ofreciendose(self):
        # Sin destino identificable no se descarta: ahí decide Jorge.
        m = self._salida('mercado_pago', 234000, 'Transferencia MP a Alda Bci')
        self.assertIn(m.id, self._ids())


class ParesCalzadosSoloRetirosTest(TestCase):
    """La lista de «Calces hechos» no puede ofrecer Deshacer sobre traspasos
    automáticos: romper un barrido MP → Scotiabank inventa un gasto y un
    ingreso de $1.000.000 que nunca existieron."""

    def setUp(self):
        call_command('sembrar_finanzas')
        call_command('aplicar_plan_cuentas', '--aplicar')

    def _par(self, origen, destino, monto, glosa):
        from .services import pares_calzados  # noqa: F401 (import de contexto)
        sale = MovimientoFinanciero.objects.create(
            fecha=date(2026, 8, 6),
            cuenta=CuentaFinanciera.objects.get(clave=origen),
            clase='traspaso', sentido='sale', monto=Decimal(monto),
            fuente='captura', referencia=f'p:{origen}:{monto}', descripcion=glosa)
        entra = MovimientoFinanciero.objects.create(
            fecha=date(2026, 8, 6),
            cuenta=CuentaFinanciera.objects.get(clave=destino),
            clase='traspaso', sentido='entra', monto=Decimal(monto),
            fuente='captura', referencia=f'p:{destino}:{monto}:e',
            traspaso_par=sale, descripcion=glosa)
        sale.traspaso_par = entra
        sale.save(update_fields=['traspaso_par'])
        return sale

    def test_el_barrido_entre_cuentas_de_aremko_no_se_lista(self):
        from .services import pares_calzados
        barrido = self._par('mercado_pago', 'scotiabank', 1000000,
                            'Barrido MP → Scotiabank')
        self.assertNotIn(barrido.id, [m.id for m in pares_calzados(dias=3650)])

    def test_el_pago_de_tarjeta_de_alda_tampoco(self):
        from .services import pares_calzados
        pago = self._par('scotiabank_alda', 'tarjeta_alda_1', 718000,
                         'Cartola alda: PAGO TARJ.CRED.')
        self.assertNotIn(pago.id, [m.id for m in pares_calzados(dias=3650)])

    def test_el_calce_de_retiro_SI_se_lista(self):
        from .services import pares_calzados
        calce = self._par('bancoestado', 'cuentarut_jorge', 300000,
                          'Cartola bancoestado: TEF BANCOESTADO A AGUILERA GONZALEZ')
        self.assertIn(calce.id, [m.id for m in pares_calzados(dias=3650)])
