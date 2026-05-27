"""
Tests para la feature de fallback target (Jorge 2026-05-27 PM).

Cubre los 5 escenarios del brief:
    1. Día con >target óptimos → trae target óptimos, 0 rellenos
    2. Día con N<target óptimos + muchos P5/P6 → completa hasta target
    3. Universo agotado (<target total) → trae lo que hay, no inventa
    4. Cliente P5 NO entra cuando hay >=target óptimos
    5. es_relleno=True solo para los que entraron por fallback

Ejecutar:
    python manage.py test ventas.tests_fallback_target
"""

from __future__ import annotations

from datetime import date, timedelta
from io import StringIO

from django.core.management import call_command
from django.test import TestCase, override_settings

from ventas.models import (
    Cliente,
    ClienteTaxonomia,
    ContactoWhatsApp,
    ScriptWhatsApp,
)


HOY = date.today()


class FallbackTargetTests(TestCase):
    """Crea N clientes Dormido óptimos (P3) + M clientes Dormido fuera
    de ventana (P6) y valida el comportamiento del fallback."""

    def setUp(self):
        ScriptWhatsApp.objects.all().delete()
        # Script genérico Dormido — matchea P3 y P6 (mismo estado_valor)
        self.script = ScriptWhatsApp.objects.create(
            script_id='B.1', nombre='Dormido genérico',
            estado_valor_target='Dormido',
            cohorte_estilo='', cohorte_contexto='', salva=1,
            plantilla_texto='Hola {nombre}, hace {dias_sin_venir} días',
        )

    def _make_dormido(self, telefono, dias_sin_venir, gasto=100000):
        cli = Cliente.objects.create(
            nombre=f'Cliente {telefono[-4:]}',
            telefono=telefono,
        )
        ClienteTaxonomia.objects.create(
            cliente=cli, eje_valor='Dormido',
            eje_estilo='Amante de las Tinas',
            eje_contexto='Visitante Pareja',
            dias_desde_ultima_visita=dias_sin_venir,
            gasto_total=gasto,
            ultima_visita=HOY - timedelta(days=dias_sin_venir),
        )
        return cli

    def _run_cron(self, **kwargs):
        out = StringIO()
        call_command('generar_bandeja_whatsapp_diaria', stdout=out, **kwargs)
        return out.getvalue()

    # ──────────────────────────────────────────────────────────────────
    # Test 1: día con > target óptimos
    # ──────────────────────────────────────────────────────────────────
    @override_settings(OVC_TARGET_DIARIO=5)
    def test_dia_con_mas_optimos_que_target_no_trae_rellenos(self):
        # 10 Dormidos en ventana P3 (180-230) → 10 óptimos
        for i in range(10):
            self._make_dormido(f'+5691111100{i:02d}', 200, gasto=10000 * (i + 1))

        self._run_cron()

        contactos = ContactoWhatsApp.objects.all()
        self.assertEqual(contactos.count(), 5, "Debe respetar target=5")
        self.assertEqual(
            contactos.filter(es_relleno=True).count(), 0,
            "Si hay suficientes óptimos, ningún relleno"
        )
        # Todos deben ser P3 (la prioridad óptima del segmento)
        self.assertTrue(all(c.prioridad == 3 for c in contactos))

    # ──────────────────────────────────────────────────────────────────
    # Test 2: óptimos < target → completa con rellenos
    # ──────────────────────────────────────────────────────────────────
    @override_settings(OVC_TARGET_DIARIO=8)
    def test_optimos_insuficientes_completa_con_rellenos(self):
        # 3 óptimos (P3) + 10 fuera de ventana (P6 resto)
        for i in range(3):
            self._make_dormido(f'+5691111200{i:02d}', 200, gasto=999999)  # P3
        for i in range(10):
            self._make_dormido(f'+5691111300{i:02d}', 400, gasto=10000)  # P6

        self._run_cron()

        contactos = ContactoWhatsApp.objects.all()
        self.assertEqual(contactos.count(), 8, "3 óptimos + 5 rellenos = target 8")
        self.assertEqual(contactos.filter(es_relleno=False).count(), 3, "3 óptimos P3")
        self.assertEqual(contactos.filter(es_relleno=True).count(), 5, "5 rellenos P6")
        # Los óptimos son P3, los rellenos son P6
        self.assertEqual(
            set(contactos.filter(es_relleno=False).values_list('prioridad', flat=True)),
            {3}
        )
        self.assertEqual(
            set(contactos.filter(es_relleno=True).values_list('prioridad', flat=True)),
            {6}
        )

    # ──────────────────────────────────────────────────────────────────
    # Test 3: universo agotado (no inventa)
    # ──────────────────────────────────────────────────────────────────
    @override_settings(OVC_TARGET_DIARIO=50)
    def test_universo_agotado_trae_lo_que_hay(self):
        # 2 P3 + 3 P6 = 5 total. Target 50 pero universo solo da 5.
        for i in range(2):
            self._make_dormido(f'+5691111400{i:02d}', 200)
        for i in range(3):
            self._make_dormido(f'+5691111500{i:02d}', 400)

        self._run_cron()

        contactos = ContactoWhatsApp.objects.all()
        self.assertEqual(contactos.count(), 5, "Universo agotado, no inventa")
        self.assertEqual(contactos.filter(es_relleno=False).count(), 2)
        self.assertEqual(contactos.filter(es_relleno=True).count(), 3)

    # ──────────────────────────────────────────────────────────────────
    # Test 4: cliente P5/P6 NO entra cuando hay >=target óptimos
    # ──────────────────────────────────────────────────────────────────
    @override_settings(OVC_TARGET_DIARIO=3)
    def test_p6_no_entra_cuando_hay_target_completo_de_optimos(self):
        # 5 óptimos P3 + 2 P6. Target 3. Solo 3 óptimos entran, ningún P6.
        for i in range(5):
            self._make_dormido(f'+5691111600{i:02d}', 200, gasto=999999)
        cli_p6_1 = self._make_dormido('+56911117001', 400, gasto=999999)
        cli_p6_2 = self._make_dormido('+56911117002', 400, gasto=999999)

        self._run_cron()

        self.assertEqual(ContactoWhatsApp.objects.count(), 3)
        # Los P6 NO entraron
        self.assertFalse(
            ContactoWhatsApp.objects.filter(cliente_id=cli_p6_1.id).exists(),
            "P6 NO debe entrar con target completo de óptimos"
        )
        self.assertFalse(
            ContactoWhatsApp.objects.filter(cliente_id=cli_p6_2.id).exists()
        )

    # ──────────────────────────────────────────────────────────────────
    # Test 5: es_relleno=True solo por fallback, no por prioridad natural
    # ──────────────────────────────────────────────────────────────────
    @override_settings(OVC_TARGET_DIARIO=10)
    def test_es_relleno_marca_solo_a_los_de_fallback(self):
        # 4 óptimos P3 + 3 P6.
        # Target=10. Entran los 4 P3 (óptimos, es_relleno=False) +
        # los 3 P6 (rellenos por cupo no lleno, es_relleno=True).
        for i in range(4):
            self._make_dormido(f'+5691111800{i:02d}', 200)
        cli_p6 = []
        for i in range(3):
            cli_p6.append(self._make_dormido(f'+5691111900{i:02d}', 400))

        self._run_cron()

        # Los P3 son óptimos
        for c in ContactoWhatsApp.objects.filter(prioridad=3):
            self.assertFalse(
                c.es_relleno,
                f"P3 NUNCA debe ser es_relleno (cli={c.cliente_id})"
            )
        # Los P6 son rellenos
        for cli in cli_p6:
            contacto = ContactoWhatsApp.objects.get(cliente_id=cli.id)
            self.assertTrue(
                contacto.es_relleno,
                f"P6 que entró por fallback DEBE ser es_relleno (cli={cli.id})"
            )

    # ──────────────────────────────────────────────────────────────────
    # Test bonus: target default es OVC_TARGET_DIARIO (no DEFAULT_LIMIT)
    # ──────────────────────────────────────────────────────────────────
    @override_settings(OVC_TARGET_DIARIO=2)
    def test_respeta_setting_OVC_TARGET_DIARIO(self):
        for i in range(5):
            self._make_dormido(f'+5691112000{i:02d}', 200)
        self._run_cron()
        self.assertEqual(ContactoWhatsApp.objects.count(), 2)
