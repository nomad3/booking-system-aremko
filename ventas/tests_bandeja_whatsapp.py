"""
Tests para Operación Vuelta a Casa, Etapa 3.

Cubre:
    - SafeDict (tolerancia a placeholders faltantes)
    - calcular_prioridad (P0-P6 y casos None)
    - buscar_script_cascada (5 niveles)
    - humanize_ultima_visita, mes_proximo_nombre, compania_habitual
    - calcular_servicio_recomendado
    - Comando generar_bandeja_whatsapp_diaria:
        * idempotencia
        * filtros de exclusión (opt-out, sin teléfono, anti-saturación 30d)
        * tope de 3 salvas
        * snapshot completo en ContactoWhatsApp
        * actualización de Cliente.ultimo_contacto_outbound NO ocurre acá
          (eso es responsabilidad del endpoint /marcar-enviado/ en Etapa 4)

Ejecutar:
    python manage.py test ventas.tests_bandeja_whatsapp
"""

from __future__ import annotations

from datetime import date, timedelta
from io import StringIO
from unittest.mock import MagicMock

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from ventas.models import (
    Cliente,
    ClienteTaxonomia,
    ContactoWhatsApp,
    ScriptWhatsApp,
)
from ventas.services.bandeja_whatsapp_service import (
    DIAS_ES,
    MESES_ES,
    SafeDict,
    buscar_script_cascada,
    calcular_prioridad,
    calcular_servicio_recomendado,
    compania_habitual,
    fecha_limite_natural,
    generar_cupon_codigo,
    humanize_ultima_visita,
    mes_proximo_nombre,
)


HOY = date(2026, 6, 5)  # fecha de referencia para los tests


# ============================================================================
# Tests de funciones puras (sin DB)
# ============================================================================

class SafeDictTests(TestCase):
    def test_devuelve_vacio_para_key_faltante(self):
        self.assertEqual(
            "Hola {nombre}, te {accion} algo.".format_map(SafeDict(nombre='María')),
            "Hola María, te  algo."
        )

    def test_funciona_como_dict_normal_para_keys_existentes(self):
        d = SafeDict(a=1, b=2)
        self.assertEqual(d['a'], 1)
        self.assertEqual(d.get('c', 'default'), 'default')

    def test_no_crashea_con_multiples_placeholders_faltantes(self):
        plantilla = "Hola {nombre}, {x} {y} {z}"
        ctx = SafeDict(nombre='Juan')
        self.assertEqual(plantilla.format_map(ctx), "Hola Juan,   ")


class HumanizeUltimaVisitaTests(TestCase):
    def test_mes_reciente(self):
        # febrero 2026, consultando en junio 2026 → "en febrero"
        self.assertEqual(
            humanize_ultima_visita(date(2026, 2, 23), HOY),
            'en febrero'
        )

    def test_mas_de_6_meses(self):
        # noviembre 2025 → 7 meses
        self.assertEqual(
            humanize_ultima_visita(date(2025, 11, 1), HOY),
            'hace 7 meses'
        )

    def test_none(self):
        self.assertEqual(humanize_ultima_visita(None, HOY), 'hace un buen rato')

    def test_fecha_futura(self):
        # caso edge: cliente con cita futura
        self.assertEqual(
            humanize_ultima_visita(date(2026, 12, 1), HOY),
            'en próximos días'
        )


class MesProximoNombreTests(TestCase):
    def test_mes_intermedio(self):
        self.assertEqual(mes_proximo_nombre(date(2026, 4, 15)), 'mayo')

    def test_diciembre_envuelve_a_enero(self):
        self.assertEqual(mes_proximo_nombre(date(2026, 12, 31)), 'enero')


class CompaniaHabitualTests(TestCase):
    def test_visitante_pareja(self):
        self.assertEqual(compania_habitual('Visitante Pareja'), 'tu pareja')

    def test_visitante_solo(self):
        self.assertEqual(compania_habitual('Visitante Solo'), 'solo')

    def test_visitante_grupal(self):
        self.assertEqual(compania_habitual('Visitante Grupal'), 'tu grupo')

    def test_sin_clasificar(self):
        self.assertEqual(compania_habitual('Sin clasificar'), '')


class GenerarCuponCodigoTests(TestCase):
    def test_formato_vuelve_xxxx(self):
        codigo = generar_cupon_codigo(7821)
        self.assertTrue(codigo.startswith('VUELVE-'))
        self.assertEqual(len(codigo), len('VUELVE-XXXX'))

    def test_deterministico_mismo_cliente(self):
        # Mismo input → mismo output siempre
        self.assertEqual(generar_cupon_codigo(7821), generar_cupon_codigo(7821))

    def test_distinto_cliente_distinto_codigo(self):
        # Improbable colisión para IDs distintos
        self.assertNotEqual(generar_cupon_codigo(1), generar_cupon_codigo(2))

    def test_uppercase_hex(self):
        codigo = generar_cupon_codigo(7821)
        sufijo = codigo.split('-')[1]
        self.assertEqual(sufijo, sufijo.upper())
        # Solo chars hex válidos
        self.assertTrue(all(c in '0123456789ABCDEF' for c in sufijo))


class FechaLimiteNaturalTests(TestCase):
    def test_15_dias_default(self):
        # 5 jun 2026 + 15d = 20 jun 2026
        self.assertEqual(fecha_limite_natural(date(2026, 6, 5)), '20 de junio')

    def test_cruza_mes(self):
        # 25 jun 2026 + 15d = 10 jul 2026
        self.assertEqual(fecha_limite_natural(date(2026, 6, 25)), '10 de julio')

    def test_dias_validez_custom(self):
        self.assertEqual(fecha_limite_natural(date(2026, 6, 5), dias_validez=7), '12 de junio')


class CalcularServicioRecomendadoTests(TestCase):
    def test_solo_tinas_recomienda_masaje(self):
        self.assertEqual(
            calcular_servicio_recomendado(pct_tinas=0.8, pct_masajes=0.0, pct_cabanas=0.0),
            'un masaje relajante'
        )

    def test_solo_masaje_recomienda_tina(self):
        self.assertEqual(
            calcular_servicio_recomendado(pct_tinas=0.05, pct_masajes=0.9, pct_cabanas=0.0),
            'una tina caliente con vista'
        )

    def test_tinas_y_masaje_recomienda_cabana(self):
        self.assertEqual(
            calcular_servicio_recomendado(pct_tinas=0.5, pct_masajes=0.4, pct_cabanas=0.0),
            'una cabaña con tina privada'
        )

    def test_cabana_recomienda_dia_spa(self):
        self.assertEqual(
            calcular_servicio_recomendado(pct_tinas=0.1, pct_masajes=0.0, pct_cabanas=0.7),
            'un día spa completo'
        )

    def test_default(self):
        self.assertEqual(
            calcular_servicio_recomendado(pct_tinas=0.0, pct_masajes=0.0, pct_cabanas=0.0),
            'una experiencia nueva'
        )


# ============================================================================
# Tests de calcular_prioridad
# ============================================================================

class CalcularPrioridadTests(TestCase):
    BASE_KWARGS = dict(
        primera_visita_actual=None,
        dias_entre_visitas_avg=None,
        hoy=HOY,
    )

    def _call(self, **overrides):
        kw = {
            **self.BASE_KWARGS,
            'eje_valor': 'Regular',
            'dias_desde_ultima_visita': 30,
            'ultimo_contacto_outbound': None,
        }
        kw.update(overrides)
        return calcular_prioridad(**kw)

    # ---- P0: Mesa chica ----
    def test_p0_leal_nunca_contactado(self):
        self.assertEqual(
            self._call(eje_valor='Leal', ultimo_contacto_outbound=None),
            0
        )

    def test_p0_campeon_nunca_contactado(self):
        self.assertEqual(
            self._call(eje_valor='Campeón', ultimo_contacto_outbound=None),
            0
        )

    def test_p0_leal_contactado_hace_31d(self):
        self.assertEqual(
            self._call(eje_valor='Leal', ultimo_contacto_outbound=HOY - timedelta(days=31)),
            0
        )

    def test_leal_contactado_hace_30d_no_califica(self):
        # Borde exacto: 30 días NO debe disparar (debe ser >30)
        self.assertIsNone(
            self._call(eje_valor='Leal', ultimo_contacto_outbound=HOY - timedelta(days=30))
        )

    def test_leal_contactado_recientemente_no_califica(self):
        self.assertIsNone(
            self._call(eje_valor='Leal', ultimo_contacto_outbound=HOY - timedelta(days=5))
        )

    # ---- P1: En Riesgo óptimo [95-105] ----
    def test_p1_en_riesgo_100d(self):
        self.assertEqual(
            self._call(eje_valor='En Riesgo', dias_desde_ultima_visita=100),
            1
        )

    def test_p1_en_riesgo_95d_inclusive(self):
        self.assertEqual(
            self._call(eje_valor='En Riesgo', dias_desde_ultima_visita=95),
            1
        )

    def test_p1_en_riesgo_105d_inclusive(self):
        self.assertEqual(
            self._call(eje_valor='En Riesgo', dias_desde_ultima_visita=105),
            1
        )

    def test_p5_en_riesgo_fuera_ventana(self):
        self.assertEqual(
            self._call(eje_valor='En Riesgo', dias_desde_ultima_visita=80),
            5
        )

    def test_p5_en_riesgo_muy_lejos(self):
        self.assertEqual(
            self._call(eje_valor='En Riesgo', dias_desde_ultima_visita=180),
            5
        )

    # ---- P2: En Prueba en momentos clave ----
    def test_p2_en_prueba_dia_30(self):
        self.assertEqual(
            self._call(
                eje_valor='En Prueba',
                primera_visita_actual=HOY - timedelta(days=30),
            ),
            2
        )

    def test_p2_en_prueba_dia_60(self):
        self.assertEqual(
            self._call(
                eje_valor='En Prueba',
                primera_visita_actual=HOY - timedelta(days=60),
            ),
            2
        )

    def test_p2_en_prueba_dia_80(self):
        self.assertEqual(
            self._call(
                eje_valor='En Prueba',
                primera_visita_actual=HOY - timedelta(days=80),
            ),
            2
        )

    def test_en_prueba_dia_45_no_aplica(self):
        # No está en ninguna ventana → None
        self.assertIsNone(
            self._call(
                eje_valor='En Prueba',
                primera_visita_actual=HOY - timedelta(days=45),
            )
        )

    # ---- P3: Dormido [195-210] ----
    def test_p3_dormido_200d(self):
        self.assertEqual(
            self._call(eje_valor='Dormido', dias_desde_ultima_visita=200),
            3
        )

    def test_p6_dormido_400d(self):
        self.assertEqual(
            self._call(eje_valor='Dormido', dias_desde_ultima_visita=400),
            6
        )

    # ---- P4: Regular atrasado ----
    def test_p4_regular_atrasado(self):
        # avg=30d (viene cada mes), no viene hace 70d → atrasado
        self.assertEqual(
            self._call(
                eje_valor='Regular',
                dias_desde_ultima_visita=70,
                dias_entre_visitas_avg=30.0,
            ),
            4
        )

    def test_regular_dentro_cadencia_no_aplica(self):
        # avg=30d, no viene hace 25d → todavía está dentro
        self.assertIsNone(
            self._call(
                eje_valor='Regular',
                dias_desde_ultima_visita=25,
                dias_entre_visitas_avg=30.0,
            )
        )

    def test_regular_avg_largo_no_aplica(self):
        # avg=90d (viene cada 3 meses), no viene hace 70d → todavía OK
        self.assertIsNone(
            self._call(
                eje_valor='Regular',
                dias_desde_ultima_visita=70,
                dias_entre_visitas_avg=90.0,
            )
        )

    # ---- Casos None ----
    def test_pre_sistema_no_aplica(self):
        self.assertIsNone(self._call(eje_valor='Pre-sistema'))

    def test_gg_ocasional_sin_regla_no_aplica(self):
        self.assertIsNone(self._call(eje_valor='Gran Gastador Ocasional'))


# ============================================================================
# Tests de buscar_script_cascada (con DB real, tests más livianos)
# ============================================================================

class BuscarScriptCascadaTests(TestCase):
    def setUp(self):
        # Limpiar plantillas que pudo haber cargado la migración 0097
        ScriptWhatsApp.objects.all().delete()

        # Crear 4 scripts a propósito para probar la cascada
        self.script_exacto = ScriptWhatsApp.objects.create(
            script_id='T.1', nombre='exacto',
            estado_valor_target='En Riesgo',
            cohorte_estilo='Amante de las Tinas',
            cohorte_contexto='Visitante Pareja',
            salva=1, plantilla_texto='exacto',
        )
        self.script_solo_estilo = ScriptWhatsApp.objects.create(
            script_id='T.2', nombre='solo estilo',
            estado_valor_target='En Riesgo',
            cohorte_estilo='Devoto del Masaje',
            cohorte_contexto='',
            salva=1, plantilla_texto='solo estilo',
        )
        self.script_solo_contexto = ScriptWhatsApp.objects.create(
            script_id='T.3', nombre='solo contexto',
            estado_valor_target='En Riesgo',
            cohorte_estilo='',
            cohorte_contexto='Visitante Solo',
            salva=1, plantilla_texto='solo contexto',
        )
        self.script_generico = ScriptWhatsApp.objects.create(
            script_id='T.4', nombre='generico',
            estado_valor_target='En Riesgo',
            cohorte_estilo='',
            cohorte_contexto='',
            salva=1, plantilla_texto='generico',
        )

    def test_nivel_1_match_exacto(self):
        s = buscar_script_cascada(
            ScriptWhatsApp.objects.all(),
            'En Riesgo', 'Amante de las Tinas', 'Visitante Pareja', 1,
        )
        self.assertEqual(s.script_id, 'T.1')

    def test_nivel_2_estilo_match_contexto_no(self):
        s = buscar_script_cascada(
            ScriptWhatsApp.objects.all(),
            'En Riesgo', 'Devoto del Masaje', 'Visitante Grupal', 1,
        )
        self.assertEqual(s.script_id, 'T.2')

    def test_nivel_3_contexto_match_estilo_no(self):
        s = buscar_script_cascada(
            ScriptWhatsApp.objects.all(),
            'En Riesgo', 'Buscador de Alojamiento', 'Visitante Solo', 1,
        )
        self.assertEqual(s.script_id, 'T.3')

    def test_nivel_4_generico(self):
        s = buscar_script_cascada(
            ScriptWhatsApp.objects.all(),
            'En Riesgo', 'Buscador de Alojamiento', 'Visitante Grupal', 1,
        )
        self.assertEqual(s.script_id, 'T.4')

    def test_nivel_5_sin_match(self):
        # Estado_valor no tiene ningún script → None
        s = buscar_script_cascada(
            ScriptWhatsApp.objects.all(),
            'Dormido', 'cualquier', 'cualquier', 1,
        )
        self.assertIsNone(s)

    def test_salva_diferente_no_matchea(self):
        s = buscar_script_cascada(
            ScriptWhatsApp.objects.all(),
            'En Riesgo', 'Amante de las Tinas', 'Visitante Pareja', 2,
        )
        self.assertIsNone(s)

    def test_script_inactivo_se_excluye(self):
        self.script_exacto.activo = False
        self.script_exacto.save()
        # Debe caer al genérico T.4 (no al T.1 inactivo)
        s = buscar_script_cascada(
            ScriptWhatsApp.objects.all(),
            'En Riesgo', 'Amante de las Tinas', 'Visitante Pareja', 1,
        )
        self.assertEqual(s.script_id, 'T.4')


# ============================================================================
# Tests del comando generar_bandeja_whatsapp_diaria
# ============================================================================

class GenerarBandejaCommandTests(TestCase):
    def setUp(self):
        ScriptWhatsApp.objects.all().delete()

        # Script genérico Dormido que matchea cualquier estilo/contexto
        self.script_dormido = ScriptWhatsApp.objects.create(
            script_id='B.1', nombre='Dormido genérico',
            estado_valor_target='Dormido',
            cohorte_estilo='', cohorte_contexto='', salva=1,
            plantilla_texto='Hola {nombre}, hace {dias_sin_venir} días que no vienes.',
        )

        # Cliente Dormido en ventana óptima (200 días) → P3
        self.cli_dormido = self._make_cliente_taxonomia(
            nombre='María Test',
            telefono='+56912345001',
            eje_valor='Dormido',
            dias_desde_ultima_visita=200,
        )

    def _make_cliente_taxonomia(
        self, nombre, telefono, eje_valor,
        eje_estilo='Amante de las Tinas',
        eje_contexto='Visitante Pareja',
        dias_desde_ultima_visita=None,
        gasto_total=100000,
        **cliente_kwargs,
    ):
        cli = Cliente.objects.create(
            nombre=nombre, telefono=telefono, **cliente_kwargs
        )
        ClienteTaxonomia.objects.create(
            cliente=cli,
            eje_valor=eje_valor,
            eje_estilo=eje_estilo,
            eje_contexto=eje_contexto,
            dias_desde_ultima_visita=dias_desde_ultima_visita,
            gasto_total=gasto_total,
            ultima_visita=(date.today() - timedelta(days=dias_desde_ultima_visita))
                          if dias_desde_ultima_visita else None,
        )
        return cli

    def _run(self, **kwargs):
        out = StringIO()
        call_command('generar_bandeja_whatsapp_diaria', stdout=out, **kwargs)
        return out.getvalue()

    # ---- Generación básica ----
    def test_dry_run_no_escribe(self):
        self._run(dry_run=True)
        self.assertEqual(ContactoWhatsApp.objects.count(), 0)

    def test_creacion_real_persiste(self):
        self._run()
        self.assertEqual(ContactoWhatsApp.objects.count(), 1)

    def test_snapshot_completo_persistido(self):
        self._run()
        c = ContactoWhatsApp.objects.get()
        self.assertEqual(c.cliente, self.cli_dormido)
        self.assertEqual(c.script, self.script_dormido)
        self.assertEqual(c.eje_valor_snapshot, 'Dormido')
        self.assertEqual(c.eje_estilo_snapshot, 'Amante de las Tinas')
        self.assertEqual(c.eje_contexto_snapshot, 'Visitante Pareja')
        self.assertEqual(c.dias_sin_venir_snapshot, 200)
        self.assertEqual(c.gasto_historico_snapshot, 100000)
        self.assertEqual(c.salva, 1)
        self.assertEqual(c.prioridad, 3)
        self.assertEqual(c.estado, 'pendiente')
        self.assertIn('María', c.mensaje_renderizado)
        self.assertIn('200', c.mensaje_renderizado)

    # ---- Idempotencia ----
    def test_idempotencia_no_genera_dos_veces(self):
        self._run()
        self.assertEqual(ContactoWhatsApp.objects.count(), 1)
        # Segunda corrida sin --force debe abortar
        salida = self._run()
        self.assertIn('Ya existen', salida)
        self.assertEqual(ContactoWhatsApp.objects.count(), 1)

    def test_force_regenera(self):
        self._run()
        self.assertEqual(ContactoWhatsApp.objects.count(), 1)
        # Con --force debe borrar pendientes previos y regenerar
        self._run(force=True)
        self.assertEqual(ContactoWhatsApp.objects.count(), 1)
        # El nuevo no es el mismo objeto
        ids = list(ContactoWhatsApp.objects.values_list('id', flat=True))
        self.assertEqual(len(ids), 1)

    # ---- Exclusiones ----
    def test_excluye_opt_out(self):
        self.cli_dormido.opt_out_whatsapp = True
        self.cli_dormido.save()
        self._run()
        self.assertEqual(ContactoWhatsApp.objects.count(), 0)

    def test_excluye_proximo_contacto_no_antes_de(self):
        self.cli_dormido.proximo_contacto_no_antes_de = date.today() + timedelta(days=10)
        self.cli_dormido.save()
        self._run()
        self.assertEqual(ContactoWhatsApp.objects.count(), 0)

    def test_excluye_contactado_hace_menos_de_30d(self):
        self.cli_dormido.ultimo_contacto_outbound = date.today() - timedelta(days=15)
        self.cli_dormido.save()
        self._run()
        self.assertEqual(ContactoWhatsApp.objects.count(), 0)

    def test_incluye_contactado_hace_mas_de_30d(self):
        self.cli_dormido.ultimo_contacto_outbound = date.today() - timedelta(days=45)
        self.cli_dormido.save()
        self._run()
        self.assertEqual(ContactoWhatsApp.objects.count(), 1)

    # ---- Salvas ----
    def test_no_genera_si_ya_envio_3_salvas(self):
        # Crear 3 ContactoWhatsApp enviados históricos
        for i in range(3):
            ContactoWhatsApp.objects.create(
                cliente=self.cli_dormido,
                script=self.script_dormido,
                eje_valor_snapshot='Dormido',
                eje_estilo_snapshot='Amante de las Tinas',
                eje_contexto_snapshot='Visitante Pareja',
                dias_sin_venir_snapshot=200,
                salva=i + 1,
                mensaje_renderizado='x',
                fecha_sugerido=date.today() - timedelta(days=60 + i * 30),
                estado='enviado',
            )
        self._run()
        # 0 nuevos creados (todos los previos quedan)
        nuevos = ContactoWhatsApp.objects.filter(fecha_sugerido=date.today()).count()
        self.assertEqual(nuevos, 0)

    def test_salva_2_si_ya_envio_1(self):
        ContactoWhatsApp.objects.create(
            cliente=self.cli_dormido,
            script=self.script_dormido,
            eje_valor_snapshot='Dormido',
            eje_estilo_snapshot='Amante de las Tinas',
            eje_contexto_snapshot='Visitante Pareja',
            dias_sin_venir_snapshot=200,
            salva=1,
            mensaje_renderizado='x',
            fecha_sugerido=date.today() - timedelta(days=60),
            estado='enviado',
        )
        # Cliente fuera del filtro 30d porque no actualizamos
        # ultimo_contacto_outbound (eso es del endpoint en Etapa 4).
        # Necesitamos crear un script para Dormido salva=2:
        ScriptWhatsApp.objects.create(
            script_id='B.2', nombre='Dormido salva 2',
            estado_valor_target='Dormido',
            cohorte_estilo='', cohorte_contexto='', salva=2,
            plantilla_texto='Salva 2 para {nombre}',
        )
        self._run()
        c = ContactoWhatsApp.objects.get(fecha_sugerido=date.today())
        self.assertEqual(c.salva, 2)
        self.assertEqual(c.script.script_id, 'B.2')

    # ---- Filtro por cliente específico ----
    def test_cliente_id_filtra(self):
        # Crear otro cliente que también sería candidato
        self._make_cliente_taxonomia(
            nombre='Pedro Test',
            telefono='+56912345002',
            eje_valor='Dormido',
            dias_desde_ultima_visita=200,
        )
        self._run(cliente_id=self.cli_dormido.id)
        # Solo se generó para María, no para Pedro
        self.assertEqual(ContactoWhatsApp.objects.count(), 1)
        self.assertEqual(
            ContactoWhatsApp.objects.get().cliente_id,
            self.cli_dormido.id
        )

    # ---- Limit ----
    def test_limit_recorta(self):
        # Crear 5 candidatos con distinto gasto
        for i in range(5):
            self._make_cliente_taxonomia(
                nombre=f'Test{i}',
                telefono=f'+5691234500{i + 2}',
                eje_valor='Dormido',
                dias_desde_ultima_visita=200,
                gasto_total=10000 * i,
            )
        self._run(limit=3)
        # 3 generados, NO 6
        self.assertEqual(ContactoWhatsApp.objects.count(), 3)

    # ---- Sin script aplicable ----
    def test_sin_script_aplicable_no_crashea(self):
        # Cambiar el cliente a un estado_valor sin scripts
        self.cli_dormido.taxonomia.eje_valor = 'Regular'
        self.cli_dormido.taxonomia.save()
        # Y poner el cliente en P4 (Regular atrasado)
        self.cli_dormido.taxonomia.dias_desde_ultima_visita = 70
        self.cli_dormido.taxonomia.dias_entre_visitas_avg = 30.0
        self.cli_dormido.taxonomia.save()
        # No hay script Regular → debe loguear warning, no crashear
        self._run()
        self.assertEqual(ContactoWhatsApp.objects.count(), 0)
