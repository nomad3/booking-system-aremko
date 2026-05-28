"""
Tests para la integración del programa Refugio Aremko en la bandeja
WhatsApp (Jorge 2026-05-27 PM).

Cubre los 9 escenarios del brief:
    1. Cliente nacional En Riesgo (salva 1)            → recibe B.refugio-N
    2. Cliente sin_clasificar Dormido (salva 1)        → recibe B.refugio-DOR-SC
    3. Cliente sur (cualquier estado)                   → NUNCA Refugio
    4. Cliente nacional Campeón                         → NUNCA Refugio
    5. Cliente nacional En Riesgo salva 2               → NO Refugio (salva > 1)
    6. Cliente con Refugio hace 30 días                 → NO Refugio (saturación)
    7. Cliente con Refugio hace 70 días                 → SÍ Refugio
    8. Render de {dias_sin_venir} en variantes DOR      → reemplazo correcto
    9. URL aremko.cl/refugio aparece literal en mensaje

Ejecutar:
    python manage.py test ventas.tests_refugio_bandeja
"""

from __future__ import annotations

from datetime import date, timedelta
from io import StringIO

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from ventas.models import (
    Cliente,
    ClienteTaxonomia,
    ContactoWhatsApp,
    ScriptWhatsApp,
)
from ventas.services.bandeja_whatsapp_service import (
    califica_refugio,
    buscar_script_refugio,
)


HOY = date.today()


def _seed_plantillas_refugio():
    """Crea las 4 plantillas Refugio (igual que la migración 0115).

    Necesario porque los tests corren sobre BD fresca sin data migrations
    ejecutadas (Django solo aplica schema en TestCase).
    """
    plantillas = [
        ('B.refugio-N',      'En Riesgo', 'nacional',       False),
        ('B.refugio-SC',     'En Riesgo', 'sin_clasificar', False),
        ('B.refugio-DOR-N',  'Dormido',   'nacional',       True),
        ('B.refugio-DOR-SC', 'Dormido',   'sin_clasificar', True),
    ]
    for script_id, estado, region, con_dias in plantillas:
        texto = (
            "¡Hola {nombre}! Te saluda Deborah desde Aremko Spa Boutique. "
            + ("Han pasado {dias_sin_venir} días. " if con_dias else "")
            + "Refugio Aremko: dos noches, segunda noche cortesía. "
            "Detalles: aremko.cl/refugio"
        )
        ScriptWhatsApp.objects.update_or_create(
            script_id=script_id,
            defaults={
                'nombre': f'Test Refugio {script_id}',
                'estado_valor_target': estado,
                'cohorte_estilo': '',
                'cohorte_contexto': '',
                'salva': 1,
                'region_geografica_target': region,
                'plantilla_texto': texto,
                'activo': True,
            },
        )


def _seed_plantilla_normal(estado_valor, region='', script_id=None):
    """Crea una plantilla 'normal' para fallback de la cascada."""
    return ScriptWhatsApp.objects.create(
        script_id=script_id or f'A.test-{estado_valor[:3]}-{region or "U"}',
        nombre=f'Normal {estado_valor} {region}',
        estado_valor_target=estado_valor,
        cohorte_estilo='', cohorte_contexto='', salva=1,
        region_geografica_target=region,
        plantilla_texto=(
            f"Hola {{nombre}}, mensaje normal {estado_valor} {{dias_sin_venir}} días"
        ),
        activo=True,
    )


def _make_cliente(telefono, region, eje_valor, dias_sin_venir, gasto=100000):
    cli = Cliente.objects.create(
        nombre=f'Cliente {telefono[-4:]}',
        telefono=telefono,
        region_geografica=region,
    )
    ClienteTaxonomia.objects.create(
        cliente=cli,
        eje_valor=eje_valor,
        eje_estilo='Amante de las Tinas',
        eje_contexto='Visitante Pareja',
        dias_desde_ultima_visita=dias_sin_venir,
        gasto_total=gasto,
        ultima_visita=HOY - timedelta(days=dias_sin_venir),
    )
    return cli


# ════════════════════════════════════════════════════════════════════
#  Tests sobre califica_refugio() y buscar_script_refugio() — unit
# ════════════════════════════════════════════════════════════════════

class CalificaRefugioTests(TestCase):
    """Tests unitarios de la función califica_refugio sin pasar por cron."""

    def setUp(self):
        _seed_plantillas_refugio()

    # Test 1: nacional + En Riesgo + salva 1 → CALIFICA
    def test_nacional_en_riesgo_salva1_califica(self):
        cli = _make_cliente('+56911100001', 'nacional', 'En Riesgo', 120)
        self.assertTrue(califica_refugio(cli, 'En Riesgo', salva=1))
        script = buscar_script_refugio(cli, 'En Riesgo')
        self.assertEqual(script.script_id, 'B.refugio-N')

    # Test 2: sin_clasificar + Dormido + salva 1 → CALIFICA → DOR-SC
    def test_sc_dormido_salva1_califica_dor_sc(self):
        cli = _make_cliente('+56911100002', 'sin_clasificar', 'Dormido', 200)
        self.assertTrue(califica_refugio(cli, 'Dormido', salva=1))
        script = buscar_script_refugio(cli, 'Dormido')
        self.assertEqual(script.script_id, 'B.refugio-DOR-SC')

    # Test 3: sur → NUNCA califica
    def test_sur_nunca_califica(self):
        cli = _make_cliente('+56911100003', 'sur', 'En Riesgo', 120)
        self.assertFalse(califica_refugio(cli, 'En Riesgo', salva=1))
        # También Dormido del sur
        cli2 = _make_cliente('+56911100004', 'sur', 'Dormido', 200)
        self.assertFalse(califica_refugio(cli2, 'Dormido', salva=1))

    # Test 4: Campeón (incluso nacional) → NUNCA califica
    def test_campeon_nunca_califica(self):
        cli = _make_cliente('+56911100005', 'nacional', 'Campeón', 30)
        self.assertFalse(califica_refugio(cli, 'Campeón', salva=1))
        # Otros estados no elegibles
        for estado in ('Leal', 'Regular', 'Gran Gastador Ocasional', 'En Prueba'):
            cli_x = _make_cliente(f'+5691110000{ord(estado[0])}', 'nacional', estado, 40)
            self.assertFalse(califica_refugio(cli_x, estado, salva=1))

    # Test 5: salva 2 → NO califica (aunque cumpla otros criterios)
    def test_salva_2_no_califica(self):
        cli = _make_cliente('+56911100006', 'nacional', 'En Riesgo', 120)
        self.assertFalse(califica_refugio(cli, 'En Riesgo', salva=2))
        self.assertFalse(califica_refugio(cli, 'En Riesgo', salva=3))

    # Test 6: anti-saturación 30 días → NO califica
    def test_anti_saturacion_30d_no_califica(self):
        cli = _make_cliente('+56911100007', 'nacional', 'En Riesgo', 120)
        # Simular envío Refugio hace 30 días
        script_ref = ScriptWhatsApp.objects.get(script_id='B.refugio-N')
        ContactoWhatsApp.objects.create(
            cliente=cli,
            script=script_ref,
            salva=1,
            mensaje_renderizado='msg de hace 30d',
            fecha_sugerido=HOY - timedelta(days=30),
            estado='enviado',
            fecha_envio=timezone.now() - timedelta(days=30),
        )
        self.assertFalse(califica_refugio(cli, 'En Riesgo', salva=1, hoy=HOY))

    # Test 7: 70 días → SÍ califica de nuevo
    def test_anti_saturacion_70d_si_califica(self):
        cli = _make_cliente('+56911100008', 'nacional', 'En Riesgo', 120)
        script_ref = ScriptWhatsApp.objects.get(script_id='B.refugio-N')
        ContactoWhatsApp.objects.create(
            cliente=cli,
            script=script_ref,
            salva=1,
            mensaje_renderizado='msg viejo',
            fecha_sugerido=HOY - timedelta(days=70),
            estado='enviado',
            fecha_envio=timezone.now() - timedelta(days=70),
        )
        self.assertTrue(califica_refugio(cli, 'En Riesgo', salva=1, hoy=HOY))


# ════════════════════════════════════════════════════════════════════
#  Tests sobre render + URL literal en mensaje persistido
# ════════════════════════════════════════════════════════════════════

class RefugioRenderEIntegracionTests(TestCase):
    """Tests del flujo completo: cron crea ContactoWhatsApp con el
    mensaje correcto renderizado."""

    def setUp(self):
        ScriptWhatsApp.objects.all().delete()
        _seed_plantillas_refugio()
        # Plantilla normal de fallback para casos NO Refugio
        _seed_plantilla_normal('En Riesgo', region='sur', script_id='A.test-ER-sur')
        _seed_plantilla_normal('Dormido',   region='sur', script_id='A.test-DOR-sur')

    def _run_cron(self):
        out = StringIO()
        call_command('generar_bandeja_whatsapp_diaria', stdout=out)
        return out.getvalue()

    # Test 8: render correcto de {dias_sin_venir} en variantes DOR
    @override_settings(OVC_TARGET_DIARIO=10, OVC_USAR_VARIACIONES_IA=False)
    def test_render_dias_sin_venir_en_variantes_dor(self):
        _make_cliente('+56911200001', 'nacional', 'Dormido', 250)
        self._run_cron()
        c = ContactoWhatsApp.objects.get(cliente__telefono='+56911200001')
        self.assertIn('250 días', c.mensaje_renderizado)
        self.assertEqual(c.script.script_id, 'B.refugio-DOR-N')

    # Test 9: URL aremko.cl/refugio aparece literal en el mensaje persistido
    @override_settings(OVC_TARGET_DIARIO=10, OVC_USAR_VARIACIONES_IA=False)
    def test_url_aremko_refugio_literal_en_mensaje(self):
        _make_cliente('+56911200002', 'nacional', 'En Riesgo', 130)
        self._run_cron()
        c = ContactoWhatsApp.objects.get(cliente__telefono='+56911200002')
        self.assertIn('aremko.cl/refugio', c.mensaje_renderizado)

    # Test 10 (bonus): cliente del sur NO recibe Refugio aunque la plantilla exista
    @override_settings(OVC_TARGET_DIARIO=10, OVC_USAR_VARIACIONES_IA=False)
    def test_sur_recibe_plantilla_normal_no_refugio(self):
        _make_cliente('+56911200003', 'sur', 'En Riesgo', 130)
        self._run_cron()
        c = ContactoWhatsApp.objects.get(cliente__telefono='+56911200003')
        # Recibe la plantilla A.test-ER-sur, NO B.refugio-N
        self.assertFalse(c.script.script_id.startswith('B.refugio'))
        self.assertEqual(c.script.script_id, 'A.test-ER-sur')
