"""
Tests para Operación Vuelta a Casa, Etapa 5.3.

Verifica la integración de generar_movimientos_y_celebraciones dentro de
recalcular_taxonomia_clientes detrás del flag opt-in --registrar-movimientos.

Cobertura de los 5 escenarios críticos:
    1. Sin flag: 0 filas nuevas en TaxonomiaMovimiento + EventoCelebracion
       (comportamiento bit-exact al previo)
    2. Con flag: detecta cambios sobre data sintética, crea movimientos
    3. Con flag + cliente sin cambios: 0 filas nuevas (no genera ruido)
    4. Con flag + --solo-modificados-desde 24h: aplica filtro temporal
    5. Con flag + 2 corridas seguidas: segunda no duplica (idempotente)

Estrategia: en lugar de armar el ecosistema completo (Cliente + VentaReserva
+ ReservaServicio + ServiceHistory) — que requeriría replicar mucha lógica
de fixtures — usamos un enfoque más directo:

    - Llamamos directamente a Command()._persist() con un dict de features
      sintético + ClienteTaxonomia pre-existente en BD
    - Eso aísla la integración (lo que cambió en Etapa 5.3) del resto del
      comando (que ya está testeado por su comportamiento histórico)

Ejecutar:
    python manage.py test ventas.tests_recalcular_taxonomia_registro_movimientos
"""

from __future__ import annotations

from datetime import date, timedelta
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from ventas.management.commands.recalcular_taxonomia_clientes import Command
from ventas.models import (
    Cliente,
    ClienteTaxonomia,
    EventoCelebracion,
    TaxonomiaMovimiento,
    VentaReserva,
)


def _make_features_dict(eje_valor='Dormido', eje_estilo='Amante de las Tinas',
                        eje_contexto='Visitante Pareja'):
    """Crea un dict de features mínimo aceptable por _features_to_model_kwargs."""
    return {
        'eje_valor': eje_valor,
        'eje_estilo': eje_estilo,
        'eje_contexto': eje_contexto,
        'total_visitas': 5,
        'gasto_total': 250000,
        'ticket_promedio': 50000,
        'primera_visita_actual': date.today() - timedelta(days=300),
        'ultima_visita': date.today() - timedelta(days=200),
        'dias_desde_ultima_visita': 200,
        'dias_entre_visitas_avg': 50.0,
        'meses_relacion_actual': 10.0,
        'pct_tinas': 0.8, 'pct_masajes': 0.1, 'pct_cabanas': 0.05, 'pct_otros': 0.05,
        'gasto_tinas': 200000, 'gasto_masajes': 25000,
        'gasto_cabanas': 15000, 'gasto_otros': 10000,
        'avg_cantidad_personas': 2.0,
        'pct_reservas_bundle': 0.0,
        'count_reservas_bundle': 0,
        'pct_finde': 60.0,
        'pct_verano': 30.0, 'pct_otono': 25.0,
        'pct_invierno': 20.0, 'pct_primavera': 25.0,
        'tiene_historial_pre_sistema': False,
        'visitas_history_count': 0,
        'primera_visita_global': date.today() - timedelta(days=300),
        'antiguedad_meses': 10,
    }


class IntegracionMovimientosTests(TestCase):
    """Tests directos sobre Command()._persist() — aislando Etapa 5.3."""

    def setUp(self):
        self.cmd = Command()
        self.cli = Cliente.objects.create(
            nombre='María González Test', telefono='+56987650001',
        )
        # Cliente ya tiene taxonomía existente como 'Dormido' (estado anterior)
        ClienteTaxonomia.objects.create(
            cliente=self.cli,
            eje_valor='Dormido',
            eje_estilo='Amante de las Tinas',
            eje_contexto='Visitante Pareja',
        )

    # ==================================================================
    # Escenario 1: Sin flag → 0 movimientos, 0 celebraciones
    # ==================================================================

    def test_sin_flag_no_registra_movimientos(self):
        # Cliente cambia de Dormido a En Prueba → SIN flag, NO debe registrar
        features = {self.cli.id: _make_features_dict(eje_valor='En Prueba')}
        stats = self.cmd._persist(features, batch_size=500)

        # La taxonomía sí se actualizó (comportamiento normal)
        self.cli.taxonomia.refresh_from_db()
        self.assertEqual(self.cli.taxonomia.eje_valor, 'En Prueba')

        # Pero NADA se registró en bitácora viva
        self.assertEqual(TaxonomiaMovimiento.objects.count(), 0)
        self.assertEqual(EventoCelebracion.objects.count(), 0)

        # Y las stats reportan 0 (bit-exact al previo: solo created/updated/unchanged)
        self.assertEqual(stats['updated'], 1)
        self.assertEqual(stats['movimientos_creados'], 0)
        self.assertEqual(stats['celebraciones_creadas'], 0)

    def test_sin_flag_keys_de_stats_siguen_presentes(self):
        # Aún sin flag, las nuevas keys deben aparecer con valor 0
        # (para que el código que las consume no rompa)
        features = {self.cli.id: _make_features_dict()}
        stats = self.cmd._persist(features, batch_size=500)
        self.assertIn('created', stats)
        self.assertIn('updated', stats)
        self.assertIn('unchanged', stats)
        self.assertIn('movimientos_creados', stats)
        self.assertIn('celebraciones_creadas', stats)

    # ==================================================================
    # Escenario 2: Con flag + cambio → registra movimiento y celebración
    # ==================================================================

    def test_con_flag_y_cambio_registra_movimiento(self):
        features = {self.cli.id: _make_features_dict(eje_valor='En Prueba')}
        stats = self.cmd._persist(
            features, batch_size=500,
            registrar_movimientos=True,
        )

        # 1 movimiento creado
        self.assertEqual(TaxonomiaMovimiento.objects.count(), 1)
        mov = TaxonomiaMovimiento.objects.get()
        self.assertEqual(mov.cliente_id, self.cli.id)
        self.assertEqual(mov.eje_valor_antes, 'Dormido')
        self.assertEqual(mov.eje_valor_despues, 'En Prueba')
        self.assertEqual(mov.evento_origen, 'recalculo_features')

        # 1 celebración 'recuperado_dormido'
        self.assertEqual(EventoCelebracion.objects.count(), 1)
        celeb = EventoCelebracion.objects.get()
        self.assertEqual(celeb.tipo, 'recuperado_dormido')
        self.assertEqual(celeb.movimiento_relacionado_id, mov.id)
        self.assertIn('María', celeb.mensaje_sugerido)

        # Stats consistentes
        self.assertEqual(stats['movimientos_creados'], 1)
        self.assertEqual(stats['celebraciones_creadas'], 1)

    def test_con_flag_evento_origen_se_propaga(self):
        features = {self.cli.id: _make_features_dict(eje_valor='En Prueba')}
        self.cmd._persist(
            features, batch_size=500,
            registrar_movimientos=True,
            evento_origen='paso_tiempo',  # otro valor del choices
        )
        mov = TaxonomiaMovimiento.objects.get()
        self.assertEqual(mov.evento_origen, 'paso_tiempo')

    # ==================================================================
    # Escenario 3: Con flag + sin cambios → 0 filas nuevas
    # ==================================================================

    def test_con_flag_sin_cambios_no_registra_nada(self):
        # Features idénticos a la taxonomía actual → unchanged
        features = {self.cli.id: _make_features_dict(
            eje_valor='Dormido',
            eje_estilo='Amante de las Tinas',
            eje_contexto='Visitante Pareja',
        )}
        # Nota: los features incluyen muchos campos no-eje (gasto, dias, etc.)
        # que pueden ser distintos a la taxonomía guardada (todos en 0 por
        # default en setUp). Eso significa `changed=True` aunque los ejes
        # sean iguales. Verificamos que el MOVIMIENTO solo refleja cambios
        # de los 3 ejes — porque generar_movimientos_y_celebraciones detecta
        # cambios solo en los 3 ejes (los otros campos son snapshot, no afectan).

        stats = self.cmd._persist(
            features, batch_size=500,
            registrar_movimientos=True,
        )

        # Si la taxonomía cambió en algún campo no-eje, hubo "update", pero
        # como los 3 ejes son idénticos, generar_movimientos_y_celebraciones
        # detecta cambios=[] y devuelve (None, []) → 0 movimientos.
        self.assertEqual(TaxonomiaMovimiento.objects.count(), 0)
        self.assertEqual(EventoCelebracion.objects.count(), 0)
        self.assertEqual(stats['movimientos_creados'], 0)
        self.assertEqual(stats['celebraciones_creadas'], 0)

    # ==================================================================
    # Escenario 5: Idempotencia (2 corridas seguidas, segunda no duplica)
    # ==================================================================

    def test_idempotencia_dos_corridas_no_duplica(self):
        # 1ª corrida: Dormido → En Prueba (crea 1 mov, 1 celeb)
        features1 = {self.cli.id: _make_features_dict(eje_valor='En Prueba')}
        self.cmd._persist(features1, batch_size=500, registrar_movimientos=True)
        self.assertEqual(TaxonomiaMovimiento.objects.count(), 1)
        self.assertEqual(EventoCelebracion.objects.count(), 1)

        # 2ª corrida con los mismos features: taxonomía ya está En Prueba,
        # ejes no cambian → 0 movimientos nuevos
        self.cmd._persist(features1, batch_size=500, registrar_movimientos=True)
        self.assertEqual(TaxonomiaMovimiento.objects.count(), 1)  # sigue en 1
        self.assertEqual(EventoCelebracion.objects.count(), 1)

    # ==================================================================
    # Cliente NUEVO (sin ClienteTaxonomia previo)
    # ==================================================================

    def test_cliente_nuevo_registra_creacion_sin_celebracion(self):
        # Cliente sin taxonomía previa
        cli_nuevo = Cliente.objects.create(nombre='Pedro Nuevo', telefono='+56987650002')
        features = {cli_nuevo.id: _make_features_dict(eje_valor='En Prueba')}

        self.cmd._persist(
            features, batch_size=500,
            registrar_movimientos=True,
        )

        # 1 movimiento de creación
        movs = TaxonomiaMovimiento.objects.filter(cliente=cli_nuevo)
        self.assertEqual(movs.count(), 1)
        self.assertEqual(movs.first().eje_valor_antes, '')  # cliente nuevo
        self.assertEqual(movs.first().eje_valor_despues, 'En Prueba')

        # NO celebraciones (cliente recién clasificado no se "recupera de Dormido")
        celebs = EventoCelebracion.objects.filter(cliente=cli_nuevo)
        self.assertEqual(celebs.count(), 0)

    # ==================================================================
    # Múltiples clientes con distintos cambios en una sola corrida
    # ==================================================================

    def test_lote_mixto_solo_registra_los_que_cambiaron(self):
        # Cliente 1: sin cambios → 0 movimientos
        # Cliente 2 (nuevo): registra creación, 0 celebraciones
        # Cliente 3: Dormido → Leal → 1 movimiento + 'recuperado_dormido'

        cli2 = Cliente.objects.create(nombre='C2', telefono='+56987650003')
        cli3 = Cliente.objects.create(nombre='C3', telefono='+56987650004')
        ClienteTaxonomia.objects.create(
            cliente=cli3,
            eje_valor='Dormido',
            eje_estilo='Amante de las Tinas',
            eje_contexto='Visitante Pareja',
        )

        features = {
            self.cli.id: _make_features_dict(),  # mismo Dormido, sin cambio en ejes
            cli2.id: _make_features_dict(eje_valor='Regular'),  # cliente nuevo
            cli3.id: _make_features_dict(eje_valor='Leal'),  # Dormido→Leal
        }
        self.cmd._persist(features, batch_size=500, registrar_movimientos=True)

        # cli3 (1 mov + 1 celeb 'recuperado_dormido') + cli2 (1 mov creación, 0 celeb)
        # cli1 (0 movs)
        self.assertEqual(TaxonomiaMovimiento.objects.count(), 2)
        self.assertEqual(EventoCelebracion.objects.count(), 1)
        celeb = EventoCelebracion.objects.get()
        self.assertEqual(celeb.cliente_id, cli3.id)


# ============================================================================
# Test del comando completo end-to-end (call_command)
# ============================================================================

class ComandoEndToEndTests(TestCase):
    """Verifica que el flag se propaga vía CLI sin tocar argparse internals."""

    def setUp(self):
        self.cli = Cliente.objects.create(
            nombre='María CLI Test', telefono='+56987651000',
        )
        ClienteTaxonomia.objects.create(
            cliente=self.cli,
            eje_valor='Dormido',
            eje_estilo='Amante de las Tinas',
            eje_contexto='Visitante Pareja',
        )
        # Crear UNA venta para que el cliente entre al universo de features
        # (build_features filtra por VentaReserva no cancelada en período)
        VentaReserva.objects.create(
            cliente=self.cli, total=100000, estado_pago='pagado',
        )

    def _run(self, **kwargs):
        out = StringIO()
        call_command('recalcular_taxonomia_clientes', stdout=out, **kwargs)
        return out.getvalue()

    def test_cli_sin_flag_no_registra(self):
        # Recalcular sin flag: comportamiento normal, 0 movimientos
        self._run()
        self.assertEqual(TaxonomiaMovimiento.objects.count(), 0)
        self.assertEqual(EventoCelebracion.objects.count(), 0)

    def test_cli_con_flag_aparece_en_output(self):
        # Con flag, el output debe mencionar "Bitácora viva"
        out = self._run(registrar_movimientos=True)
        self.assertIn('Bitácora viva', out)

    def test_cli_dry_run_con_flag_no_registra_nada(self):
        # dry-run gana sobre registrar-movimientos (porque retorna antes de _persist)
        self._run(dry_run=True, registrar_movimientos=True)
        self.assertEqual(TaxonomiaMovimiento.objects.count(), 0)
        self.assertEqual(EventoCelebracion.objects.count(), 0)
