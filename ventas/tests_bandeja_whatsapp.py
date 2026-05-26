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
        # Default dias=100 para que todos los tests pasen el filtro previo
        # de OVC_DIAS_MINIMO_DESDE_ULTIMA_VISITA (Campeón=45, Leal=60, etc.).
        # Cada test que necesite verificar bordes de inactividad/visita
        # reciente lo sobreescribe explícitamente.
        kw = {
            **self.BASE_KWARGS,
            'eje_valor': 'Regular',
            'dias_desde_ultima_visita': 100,
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
        # avg=30d, no viene hace 50d → pasa filtro (>=30) pero P4 requiere >60
        # → None por cadencia, no por filtro previo
        self.assertIsNone(
            self._call(
                eje_valor='Regular',
                dias_desde_ultima_visita=50,
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
        # GG Ocasional min=45, dias=100 pasa filtro pero ninguna regla P aplica.
        self.assertIsNone(self._call(eje_valor='Gran Gastador Ocasional'))

    # ---- Filtro previo: días mínimos desde última visita ----
    # Bug fix 2026-05-25: Campeones/Leales con visita reciente entraban a
    # bandeja P0 porque su ultimo_contacto_outbound era NULL (nunca habíamos
    # corrido el sistema). Resultado: cliente Ema (Campeón, visita hace 4d)
    # iba a recibir "te echamos de menos". El filtro previo bloquea ese caso.
    def test_filtro_campeon_visita_reciente_bloqueado(self):
        # Campeón con visita hace 30d (< 45 mínimo) → None aunque P0 calzaría.
        self.assertIsNone(
            self._call(
                eje_valor='Campeón',
                dias_desde_ultima_visita=30,
                ultimo_contacto_outbound=None,
            )
        )

    def test_filtro_campeon_visita_60d_califica_p0(self):
        # Campeón con visita hace 60d (>= 45 mínimo) → P0 normal.
        self.assertEqual(
            self._call(
                eje_valor='Campeón',
                dias_desde_ultima_visita=60,
                ultimo_contacto_outbound=None,
            ),
            0
        )

    def test_filtro_leal_visita_50d_bloqueado(self):
        # Leal con visita hace 50d (< 60 mínimo) → None.
        self.assertIsNone(
            self._call(
                eje_valor='Leal',
                dias_desde_ultima_visita=50,
                ultimo_contacto_outbound=None,
            )
        )

    def test_filtro_leal_visita_90d_califica_p0(self):
        # Leal con visita hace 90d (>= 60 mínimo) → P0 normal.
        self.assertEqual(
            self._call(
                eje_valor='Leal',
                dias_desde_ultima_visita=90,
                ultimo_contacto_outbound=None,
            ),
            0
        )

    def test_filtro_dormido_365d_califica_p6(self):
        # Dormido tiene min=0 (heurística P3/P6 ya cubre inactividad).
        # 365 días → fuera de ventana [195-210] → cae a P6.
        self.assertEqual(
            self._call(
                eje_valor='Dormido',
                dias_desde_ultima_visita=365,
            ),
            6
        )


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

    # ========================================================================
    # Feature 2026-05-26: Acumulación de pendientes entre días
    # ========================================================================

    def _crear_pendiente_historico(self, cliente, dias_atras, estado='pendiente'):
        """Helper: crea un ContactoWhatsApp con fecha_sugerido en el pasado."""
        return ContactoWhatsApp.objects.create(
            cliente=cliente,
            script=self.script_dormido,
            eje_valor_snapshot='Dormido',
            eje_estilo_snapshot='Amante de las Tinas',
            eje_contexto_snapshot='Visitante Pareja',
            dias_sin_venir_snapshot=200,
            salva=1,
            mensaje_renderizado=f'mensaje histórico de hace {dias_atras}d',
            prioridad=3,
            fecha_sugerido=date.today() - timedelta(days=dias_atras),
            estado=estado,
        )

    def test_arrastra_pendiente_del_dia_anterior(self):
        """Test 1 del brief: pendiente de ayer aparece en bandeja de hoy."""
        # Crear cliente extra (diferente al cli_dormido del setUp) con
        # pendiente histórico de ayer. Lo hacemos opt_out=True para que el
        # cron NO lo seleccione como candidato nuevo — así aislamos la
        # validación del arrastre puro.
        otro_cli = self._make_cliente_taxonomia(
            nombre='Arrastrado Uno',
            telefono='+56911111001',
            eje_valor='Dormido',
            dias_desde_ultima_visita=200,
            opt_out_whatsapp=True,
        )
        pendiente_ayer = self._crear_pendiente_historico(otro_cli, dias_atras=1)

        self._run()

        pendiente_ayer.refresh_from_db()
        self.assertEqual(
            pendiente_ayer.fecha_sugerido, date.today(),
            "El pendiente de ayer debe haberse arrastrado a hoy"
        )
        self.assertEqual(pendiente_ayer.estado, 'pendiente')

    def test_no_arrastra_enviado_ni_omitido(self):
        """Test 2 del brief: contactos enviados/omitidos NO se arrastran."""
        cli_enviado = self._make_cliente_taxonomia(
            nombre='Ya Enviado',
            telefono='+56911111002',
            eje_valor='Dormido',
            dias_desde_ultima_visita=200,
            opt_out_whatsapp=True,
        )
        cli_omitido = self._make_cliente_taxonomia(
            nombre='Ya Omitido',
            telefono='+56911111003',
            eje_valor='Dormido',
            dias_desde_ultima_visita=200,
            opt_out_whatsapp=True,
        )
        ayer = date.today() - timedelta(days=1)
        enviado = self._crear_pendiente_historico(
            cli_enviado, dias_atras=1, estado='enviado'
        )
        omitido = self._crear_pendiente_historico(
            cli_omitido, dias_atras=1, estado='omitido'
        )

        self._run()

        enviado.refresh_from_db()
        omitido.refresh_from_db()
        self.assertEqual(
            enviado.fecha_sugerido, ayer,
            "Enviado NO debe arrastrarse — su fecha queda intacta"
        )
        self.assertEqual(enviado.estado, 'enviado')
        self.assertEqual(
            omitido.fecha_sugerido, ayer,
            "Omitido NO debe arrastrarse — su fecha queda intacta"
        )
        self.assertEqual(omitido.estado, 'omitido')

    def test_expira_pendiente_muy_viejo(self):
        """Test 3 del brief: pendiente de hace 10 días → expirado_acumulacion."""
        cli_viejo = self._make_cliente_taxonomia(
            nombre='Pendiente Viejo',
            telefono='+56911111004',
            eje_valor='Dormido',
            dias_desde_ultima_visita=200,
            opt_out_whatsapp=True,
        )
        viejo = self._crear_pendiente_historico(cli_viejo, dias_atras=10)

        # OVC_DIAS_MAX_ACUMULACION default = 7, así que 10 > 7 → debe expirar
        self._run()

        viejo.refresh_from_db()
        self.assertEqual(
            viejo.estado, 'expirado_acumulacion',
            "Pendiente con >7 días debe marcarse como expirado"
        )
        # La fecha original se preserva (auditoría)
        self.assertEqual(
            viejo.fecha_sugerido, date.today() - timedelta(days=10),
            "fecha_sugerido del expirado NO debe moverse"
        )

    def test_dedupe_cliente_arrastrado_y_candidato_nuevo(self):
        """Test 4 del brief: cliente con pendiente de ayer + califica hoy
        → solo aparece una vez (el arrastrado), NO se duplica."""
        # cli_dormido del setUp es candidato P3. Le creamos un pendiente de
        # ayer para que sea arrastrado. Luego el cron NO debe crearle un
        # nuevo (violaría unique_pendiente_por_cliente_dia).
        pendiente_ayer = self._crear_pendiente_historico(
            self.cli_dormido, dias_atras=1
        )

        self._run()

        # Solo debe existir 1 ContactoWhatsApp pendiente para este cliente
        # con fecha_sugerido=hoy (el arrastrado)
        pendientes_hoy = ContactoWhatsApp.objects.filter(
            cliente=self.cli_dormido,
            fecha_sugerido=date.today(),
            estado='pendiente',
        )
        self.assertEqual(
            pendientes_hoy.count(), 1,
            "Cliente arrastrado NO debe duplicarse al generar nuevos"
        )
        # Y debe ser EL MISMO objeto del arrastre (mismo id)
        self.assertEqual(pendientes_hoy.first().id, pendiente_ayer.id)


# ============================================================================
# Etapa 5.5.1 — Exclusión por nombre (clientes staff/proxy)
# ============================================================================

from django.test import override_settings


@override_settings(
    OVC_CLIENTES_EXCLUIDOS_ICONTAINS=['aremko'],
    OVC_CLIENTES_EXCLUIDOS_IEXACT=['Jorge Aguilera', 'Deborah'],
)
class ExclusionPorNombreTests(TestCase):
    """Valida el filtro de Etapa 5.5.1: clientes proxy/staff no entran a bandeja."""

    def setUp(self):
        ScriptWhatsApp.objects.all().delete()
        # Script genérico Dormido para que cualquier cliente Dormido tenga match
        self.script = ScriptWhatsApp.objects.create(
            script_id='B.1.TEST', nombre='Dormido genérico',
            estado_valor_target='Dormido',
            cohorte_estilo='', cohorte_contexto='', salva=1,
            plantilla_texto='Hola {nombre}',
        )

    def _make_cliente_dormido(self, nombre, telefono):
        cli = Cliente.objects.create(nombre=nombre, telefono=telefono)
        ClienteTaxonomia.objects.create(
            cliente=cli, eje_valor='Dormido',
            eje_estilo='Amante de las Tinas', eje_contexto='Visitante Pareja',
            dias_desde_ultima_visita=200, gasto_total=100000,
            ultima_visita=date.today() - timedelta(days=200),
        )
        return cli

    def _run(self, **kwargs):
        out = StringIO()
        call_command('generar_bandeja_whatsapp_diaria', stdout=out, **kwargs)
        return out.getvalue()

    # ---- icontains ----
    def test_aremko_hotel_spa_se_excluye_por_icontains(self):
        self._make_cliente_dormido('Aremko Hotel Spa', '+56912340001')
        self._make_cliente_dormido('Cliente Real', '+56912340002')
        self._run()
        contactos = list(ContactoWhatsApp.objects.values_list('cliente__nombre', flat=True))
        self.assertIn('Cliente Real', contactos)
        self.assertNotIn('Aremko Hotel Spa', contactos)

    def test_icontains_es_case_insensitive(self):
        self._make_cliente_dormido('AREMKO PRUEBAS', '+56912340003')
        self._make_cliente_dormido('aremko test', '+56912340004')
        self._run()
        contactos = list(ContactoWhatsApp.objects.values_list('cliente__nombre', flat=True))
        self.assertNotIn('AREMKO PRUEBAS', contactos)
        self.assertNotIn('aremko test', contactos)

    # ---- iexact ----
    def test_jorge_aguilera_exacto_se_excluye(self):
        self._make_cliente_dormido('Jorge Aguilera', '+56912340005')
        self._run()
        contactos = list(ContactoWhatsApp.objects.values_list('cliente__nombre', flat=True))
        self.assertNotIn('Jorge Aguilera', contactos)

    def test_jorge_mendoza_NO_se_excluye(self):
        """Patrón iexact NO debe disparar contra homónimos legítimos."""
        self._make_cliente_dormido('Jorge Mendoza', '+56912340006')
        self._make_cliente_dormido('Jorge Pérez Aguilera', '+56912340007')
        self._run()
        contactos = list(ContactoWhatsApp.objects.values_list('cliente__nombre', flat=True))
        self.assertIn('Jorge Mendoza', contactos)
        self.assertIn('Jorge Pérez Aguilera', contactos)  # NO match exacto

    def test_iexact_es_case_insensitive(self):
        self._make_cliente_dormido('JORGE AGUILERA', '+56912340008')
        self._make_cliente_dormido('jorge aguilera', '+56912340009')
        self._run()
        contactos = list(ContactoWhatsApp.objects.values_list('cliente__nombre', flat=True))
        self.assertNotIn('JORGE AGUILERA', contactos)
        self.assertNotIn('jorge aguilera', contactos)

    # ---- Combinación ----
    def test_multiples_patrones_se_aplican_todos(self):
        self._make_cliente_dormido('Aremko Hotel Spa', '+56912340010')
        self._make_cliente_dormido('Jorge Aguilera', '+56912340011')
        self._make_cliente_dormido('Deborah', '+56912340012')
        self._make_cliente_dormido('Cliente Normal', '+56912340013')
        self._run()
        contactos = list(ContactoWhatsApp.objects.values_list('cliente__nombre', flat=True))
        self.assertEqual(contactos, ['Cliente Normal'])

    # ---- Edge case: nombre vacío ----
    def test_cliente_sin_nombre_no_crashea(self):
        """El cron NO debe explotar si un cliente tiene nombre vacío."""
        Cliente.objects.create(nombre='', telefono='+56912340014')
        # No le agrego ClienteTaxonomia (no entrará a la bandeja igual),
        # pero confirmamos que el query base con icontains de '' no crashea
        # cuando hay nombres vacíos en otras filas.
        self._make_cliente_dormido('Cliente Real', '+56912340015')
        self._run()
        # No assertion fuerte: solo que no crasheó.

    @override_settings(
        OVC_CLIENTES_EXCLUIDOS_ICONTAINS=[],
        OVC_CLIENTES_EXCLUIDOS_IEXACT=[],
    )
    def test_sin_settings_no_excluye_nada(self):
        """Con listas vacías, todos los candidatos pasan (backward compat)."""
        self._make_cliente_dormido('Aremko Hotel Spa', '+56912340016')
        self._make_cliente_dormido('Jorge Aguilera', '+56912340017')
        self._run()
        contactos = list(ContactoWhatsApp.objects.values_list('cliente__nombre', flat=True))
        self.assertIn('Aremko Hotel Spa', contactos)
        self.assertIn('Jorge Aguilera', contactos)

    # ---- Logging ----
    def test_log_reporta_cuantos_excluyo(self):
        self._make_cliente_dormido('Aremko Hotel Spa', '+56912340018')
        self._make_cliente_dormido('Jorge Aguilera', '+56912340019')
        self._make_cliente_dormido('Cliente Real', '+56912340020')
        out = self._run()
        # Mensaje exacto del log
        self.assertIn('Excluidos por OVC_CLIENTES_EXCLUIDOS_*', out)
        self.assertIn('2', out)  # 2 excluidos (Aremko + Jorge)


# ============================================================================
# Etapa Geo.3 — Cascada + filtro extranjero + plantillas geo
# ============================================================================

class CascadaGeoTests(TestCase):
    """Tests de la cascada extendida con región (Geo.3.b)."""

    def setUp(self):
        ScriptWhatsApp.objects.all().delete()
        # Plantilla universal (region='') - fallback para sur
        self.s_universal = ScriptWhatsApp.objects.create(
            script_id='UNI.1', nombre='Universal',
            estado_valor_target='Dormido',
            cohorte_estilo='', cohorte_contexto='', salva=1,
            region_geografica_target='',
            plantilla_texto='universal',
        )
        # Plantilla específica nacional
        self.s_nacional = ScriptWhatsApp.objects.create(
            script_id='NAC.1', nombre='Nacional',
            estado_valor_target='Dormido',
            cohorte_estilo='', cohorte_contexto='', salva=1,
            region_geografica_target='nacional',
            plantilla_texto='pack alojamiento',
        )

    def test_cliente_sur_usa_universal_fallback(self):
        s = buscar_script_cascada(
            ScriptWhatsApp.objects.all(),
            estado_valor='Dormido', estilo='', contexto='', salva=1,
            region='sur',
        )
        # No hay plantilla específica sur → cae al fallback universal
        self.assertEqual(s.script_id, 'UNI.1')

    def test_cliente_nacional_usa_plantilla_nacional(self):
        s = buscar_script_cascada(
            ScriptWhatsApp.objects.all(),
            estado_valor='Dormido', estilo='', contexto='', salva=1,
            region='nacional',
        )
        self.assertEqual(s.script_id, 'NAC.1')

    def test_cliente_nacional_sin_plantilla_NO_cae_a_universal(self):
        # En Riesgo no tiene plantilla nacional ni universal
        s = buscar_script_cascada(
            ScriptWhatsApp.objects.all(),
            estado_valor='En Riesgo', estilo='', contexto='', salva=1,
            region='nacional',
        )
        # Debe retornar None — mejor no enviar que enviar mensaje desubicado
        self.assertIsNone(s)

    def test_cliente_sin_clasificar_sin_plantilla_NO_cae_a_universal(self):
        s = buscar_script_cascada(
            ScriptWhatsApp.objects.all(),
            estado_valor='En Riesgo', estilo='', contexto='', salva=1,
            region='sin_clasificar',
        )
        self.assertIsNone(s)

    def test_caller_sin_region_comportamiento_original(self):
        """Backward-compat: caller que no pasa region usa cascada original."""
        s = buscar_script_cascada(
            ScriptWhatsApp.objects.all(),
            estado_valor='Dormido', estilo='', contexto='', salva=1,
            # NO pasamos region
        )
        # Cae a la plantilla universal directamente
        self.assertEqual(s.script_id, 'UNI.1')

    def test_plantilla_region_mas_especifica_gana_sobre_universal(self):
        """Si hay plantilla nacional Y universal, nacional gana para region=nacional."""
        s = buscar_script_cascada(
            ScriptWhatsApp.objects.all(),
            estado_valor='Dormido', estilo='', contexto='', salva=1,
            region='nacional',
        )
        self.assertEqual(s.script_id, 'NAC.1')  # NO 'UNI.1'

    def test_plantilla_sur_explicita_no_existe_pero_universal_si(self):
        """region='sur' sin plantilla sur específica → fallback universal."""
        # No hay plantilla con region='sur' explícita, solo universal y nacional
        s = buscar_script_cascada(
            ScriptWhatsApp.objects.all(),
            estado_valor='Dormido', estilo='', contexto='', salva=1,
            region='sur',
        )
        self.assertEqual(s.script_id, 'UNI.1')


class FiltroExtranjeroTests(TestCase):
    """Tests del filtro automático de extranjeros en el cron (Geo.3.a)."""

    def setUp(self):
        ScriptWhatsApp.objects.all().delete()
        ScriptWhatsApp.objects.create(
            script_id='B.1.GEO', nombre='Dormido genérico',
            estado_valor_target='Dormido',
            cohorte_estilo='', cohorte_contexto='', salva=1,
            region_geografica_target='',
            plantilla_texto='Hola {nombre}',
        )

    def _make_cliente(self, telefono, region):
        cli = Cliente.objects.create(
            nombre=f'Test {region}', telefono=telefono,
            region_geografica=region,
        )
        ClienteTaxonomia.objects.create(
            cliente=cli, eje_valor='Dormido',
            eje_estilo='Amante de las Tinas', eje_contexto='Visitante Pareja',
            dias_desde_ultima_visita=200, gasto_total=100000,
            ultima_visita=date.today() - timedelta(days=200),
        )
        return cli

    def _run(self, **kwargs):
        out = StringIO()
        call_command('generar_bandeja_whatsapp_diaria', stdout=out, **kwargs)
        return out.getvalue()

    def test_extranjero_se_excluye_de_bandeja(self):
        cli_sur = self._make_cliente('+56912349001', 'sur')
        cli_ext = self._make_cliente('+56912349002', 'extranjero')

        self._run()

        contactos_clientes = list(
            ContactoWhatsApp.objects.values_list('cliente__nombre', flat=True)
        )
        self.assertIn('Test sur', contactos_clientes)
        self.assertNotIn('Test extranjero', contactos_clientes)

    def test_log_reporta_excluidos_por_region(self):
        self._make_cliente('+56912349003', 'extranjero')
        self._make_cliente('+56912349004', 'extranjero')
        self._make_cliente('+56912349005', 'sur')

        out = self._run()
        self.assertIn("Excluidos por region='extranjero'", out)
        self.assertIn('2', out)  # 2 extranjeros excluidos


class PlantillasGeoCascadaIntegracionTests(TestCase):
    """Test end-to-end: cliente nacional matchea plantilla nacional."""

    def setUp(self):
        ScriptWhatsApp.objects.all().delete()
        # Plantilla nacional específica
        self.s_nacional = ScriptWhatsApp.objects.create(
            script_id='B.1-N.TEST', nombre='Pack alojamiento',
            estado_valor_target='Dormido',
            cohorte_estilo='', cohorte_contexto='', salva=1,
            region_geografica_target='nacional',
            plantilla_texto='Hola {nombre}, pack 2 noches.',
        )
        # Plantilla sin_clasificar específica
        self.s_sc = ScriptWhatsApp.objects.create(
            script_id='B.1-SC.TEST', nombre='Neutra',
            estado_valor_target='Dormido',
            cohorte_estilo='', cohorte_contexto='', salva=1,
            region_geografica_target='sin_clasificar',
            plantilla_texto='Hola {nombre}, cuéntame desde dónde vienes.',
        )
        # Plantilla universal (sirve solo para sur)
        self.s_universal = ScriptWhatsApp.objects.create(
            script_id='B.1.UNI.TEST', nombre='Universal',
            estado_valor_target='Dormido',
            cohorte_estilo='', cohorte_contexto='', salva=1,
            region_geografica_target='',
            plantilla_texto='Hola {nombre}, ven esta semana.',
        )

    def _make_cliente(self, telefono, region):
        cli = Cliente.objects.create(
            nombre=f'Cliente {region}', telefono=telefono,
            region_geografica=region,
        )
        ClienteTaxonomia.objects.create(
            cliente=cli, eje_valor='Dormido',
            eje_estilo='Amante de las Tinas', eje_contexto='Visitante Pareja',
            dias_desde_ultima_visita=200, gasto_total=100000,
            ultima_visita=date.today() - timedelta(days=200),
        )
        return cli

    def _run(self):
        out = StringIO()
        call_command('generar_bandeja_whatsapp_diaria', stdout=out)
        return out.getvalue()

    def test_cliente_sur_recibe_universal(self):
        self._make_cliente('+56912350001', 'sur')
        self._run()
        c = ContactoWhatsApp.objects.get()
        self.assertEqual(c.script.script_id, 'B.1.UNI.TEST')
        self.assertIn('ven esta semana', c.mensaje_renderizado)

    def test_cliente_nacional_recibe_pack_alojamiento(self):
        self._make_cliente('+56912350002', 'nacional')
        self._run()
        c = ContactoWhatsApp.objects.get()
        self.assertEqual(c.script.script_id, 'B.1-N.TEST')
        self.assertIn('pack 2 noches', c.mensaje_renderizado)

    def test_cliente_sin_clasificar_recibe_neutra(self):
        self._make_cliente('+56912350003', 'sin_clasificar')
        self._run()
        c = ContactoWhatsApp.objects.get()
        self.assertEqual(c.script.script_id, 'B.1-SC.TEST')
        self.assertIn('cuéntame', c.mensaje_renderizado)

    def test_cliente_nacional_sin_plantilla_nacional_no_recibe_universal(self):
        # Borrar la plantilla nacional → no debe caer al universal
        self.s_nacional.delete()
        self._make_cliente('+56912350004', 'nacional')
        self._run()
        # Cero contactos creados
        self.assertEqual(ContactoWhatsApp.objects.count(), 0)


# ============================================================================
# Migración 0107 — saludo Deborah (cosmético cross-cutting)
# ============================================================================

class Migracion0107SaludoDeborahTests(TestCase):
    """Valida el reemplazo de las 4 variantes de saludo viejas por la firma
    canónica nueva 'Te saluda Deborah desde Aremko Spa Boutique'.

    Importa la función `actualizar_saludo` de la migración 0107 y la corre
    sobre scripts de test (NO confía en los seeds, así el test queda
    autocontenido y robusto incluso si los seeds cambian en el futuro).
    """

    def setUp(self):
        ScriptWhatsApp.objects.all().delete()

    def _crear(self, script_id, texto):
        return ScriptWhatsApp.objects.create(
            script_id=script_id,
            nombre=f'Test {script_id}',
            estado_valor_target='Dormido',
            cohorte_estilo='', cohorte_contexto='', salva=1,
            plantilla_texto=texto,
        )

    def _aplicar_migracion(self):
        # Importar la función de la migración para reutilizar su lógica real
        import importlib
        mod = importlib.import_module(
            'ventas.migrations.0107_saludo_deborah'
        )
        # apps falso: usamos el get_model real de Django
        from django.apps import apps as django_apps

        class _AppsShim:
            def get_model(self, app_label, model_name):
                return django_apps.get_model(app_label, model_name)

        mod.actualizar_saludo(_AppsShim(), schema_editor=None)

    def test_reemplaza_te_escribe_aremko_de_puerto_varas(self):
        s = self._crear('A.X', 'Hola María, te escribe Aremko de Puerto Varas.\n\nResto del mensaje.')
        self._aplicar_migracion()
        s.refresh_from_db()
        self.assertIn('te saluda Deborah desde Aremko Spa Boutique', s.plantilla_texto)
        self.assertNotIn('te escribe Aremko', s.plantilla_texto)

    def test_reemplaza_te_escribo_de_aremko_mesa_chica(self):
        # Mesa chica empieza con mayúscula tras signo de interrogación
        s = self._crear('E.X', 'Hola María, ¿cómo has estado? Te escribo de Aremko.\n\nResto.')
        self._aplicar_migracion()
        s.refresh_from_db()
        self.assertIn('Te saluda Deborah desde Aremko Spa Boutique', s.plantilla_texto)
        self.assertNotIn('Te escribo de Aremko', s.plantilla_texto)

    def test_reemplaza_te_escribe_aremko_simple(self):
        s = self._crear('A.Y', 'Hola María, te escribe Aremko.\n\nResto.')
        self._aplicar_migracion()
        s.refresh_from_db()
        self.assertIn('te saluda Deborah desde Aremko Spa Boutique', s.plantilla_texto)
        # Ya no debe quedar el saludo viejo aislado
        self.assertNotIn('te escribe Aremko.', s.plantilla_texto)

    def test_reemplaza_soy_de_aremko(self):
        s = self._crear('C.X', 'Hola María, soy de Aremko.\n\nResto.')
        self._aplicar_migracion()
        s.refresh_from_db()
        self.assertIn('te saluda Deborah desde Aremko Spa Boutique', s.plantilla_texto)
        self.assertNotIn('soy de Aremko', s.plantilla_texto)

    def test_orden_largo_primero_no_rompe(self):
        # Si la migración procesara los patrones en orden inverso (corto primero),
        # 'te escribe Aremko' se reemplazaría primero y dejaría dangling
        # ' de Puerto Varas' colgando. Validamos que NO ocurre.
        s = self._crear('A.Z', 'Hola, te escribe Aremko de Puerto Varas, escapada.')
        self._aplicar_migracion()
        s.refresh_from_db()
        self.assertEqual(
            s.plantilla_texto,
            'Hola, te saluda Deborah desde Aremko Spa Boutique, escapada.',
            "El reemplazo debe procesar la variante larga primero"
        )

    def test_idempotente_segunda_corrida_no_rompe(self):
        # Si la migración corre 2 veces (raro pero posible con --fake o errores),
        # la segunda no debe corromper el texto. Como la firma nueva ya no
        # contiene ninguno de los 4 patrones viejos, no hay reemplazos.
        s = self._crear('A.W', 'Hola, te escribe Aremko.')
        self._aplicar_migracion()
        s.refresh_from_db()
        texto_post_1 = s.plantilla_texto
        self._aplicar_migracion()
        s.refresh_from_db()
        self.assertEqual(s.plantilla_texto, texto_post_1)

    def test_script_sin_saludo_viejo_no_se_toca(self):
        # D.1 / D.2 originales no tienen saludo Aremko, solo "Hola {nombre},"
        texto_original = 'Hola María,\n\nMensaje sin saludo de marca.'
        s = self._crear('D.X', texto_original)
        self._aplicar_migracion()
        s.refresh_from_db()
        self.assertEqual(s.plantilla_texto, texto_original)


# ============================================================================
# Migración 0108 — quitar "almuerzo" de plantillas (bug contenido Jorge)
# ============================================================================

class Migracion0108QuitarAlmuerzoTests(TestCase):
    """Valida que la migración elimina las menciones a 'almuerzo' que
    prometían algo que Aremko no ofrece. NO toca 'desayunos' que sí existe
    como servicio."""

    def setUp(self):
        ScriptWhatsApp.objects.all().delete()

    def _crear(self, script_id, texto):
        return ScriptWhatsApp.objects.create(
            script_id=script_id,
            nombre=f'Test {script_id}',
            estado_valor_target='En Riesgo',
            cohorte_estilo='', cohorte_contexto='', salva=1,
            plantilla_texto=texto,
        )

    def _aplicar_migracion(self):
        import importlib
        mod = importlib.import_module('ventas.migrations.0108_quitar_almuerzo_plantillas')
        from django.apps import apps as django_apps

        class _AppsShim:
            def get_model(self, app_label, model_name):
                return django_apps.get_model(app_label, model_name)

        mod.quitar_almuerzo(_AppsShim(), schema_editor=None)

    def test_reemplaza_a3_dia_spa_5_horas_almuerzo(self):
        original = (
            "Hola María, te saluda Deborah desde Aremko Spa Boutique.\n\n"
            "Como te gusta el día completo (tina + masaje + descanso), te aviso que "
            "abrimos una nueva opción: día spa de 5 horas con almuerzo incluido entre semana.\n\n"
            "¿Te lo cuento por aquí?"
        )
        s = self._crear('A.3', original)
        self._aplicar_migracion()
        s.refresh_from_db()
        self.assertIn('día de spa entre semana', s.plantilla_texto)
        self.assertNotIn('almuerzo', s.plantilla_texto.lower())
        self.assertNotIn('5 horas', s.plantilla_texto)

    def test_reemplaza_a3n_pack_2_noches_almuerzo(self):
        original = (
            "Hola María, te saluda Deborah desde Aremko Spa Boutique.\n\n"
            "Como les gustó el día completo, te aviso que abrimos un "
            "pack 2 noches + spa + almuerzo para que vuelvan sin estrés de organizar nada. "
            "Hasta 30 de mayo con tarifa especial.\n\n"
            "¿Les armo opciones?"
        )
        s = self._crear('A.3-N', original)
        self._aplicar_migracion()
        s.refresh_from_db()
        self.assertIn('pack 2 noches + spa, ideal para desconectarse', s.plantilla_texto)
        self.assertIn('tabla de quesos, jamones o mixta para compartir', s.plantilla_texto)
        self.assertNotIn('almuerzo', s.plantilla_texto.lower())

    def test_no_toca_desayunos_que_si_existe(self):
        """Aremko SÍ tiene servicio de desayuno (pack alojamiento+desayuno).
        La migración NO debe tocar plantillas que solo mencionan desayunos."""
        original = (
            "Hola María, te saluda Deborah desde Aremko Spa Boutique.\n\n"
            "Como les gustaron las tinas la última vez, te aviso que tenemos "
            "un pack romántico: 2 noches en cabaña con tina caliente privada + desayunos."
        )
        s = self._crear('A.1-N', original)
        self._aplicar_migracion()
        s.refresh_from_db()
        self.assertEqual(s.plantilla_texto, original)
        self.assertIn('desayunos', s.plantilla_texto)

    def test_idempotente_segunda_corrida(self):
        original = (
            "abrimos una nueva opción: día spa de 5 horas con almuerzo incluido entre semana."
        )
        s = self._crear('A.3', original)
        self._aplicar_migracion()
        s.refresh_from_db()
        texto_post_1 = s.plantilla_texto
        self._aplicar_migracion()
        s.refresh_from_db()
        self.assertEqual(s.plantilla_texto, texto_post_1)
        self.assertNotIn('almuerzo', s.plantilla_texto.lower())

    def test_script_sin_almuerzo_no_se_toca(self):
        original = "Hola María, te saluda Deborah desde Aremko Spa Boutique. Te acordamos tu última visita."
        s = self._crear('Z.1', original)
        self._aplicar_migracion()
        s.refresh_from_db()
        self.assertEqual(s.plantilla_texto, original)
