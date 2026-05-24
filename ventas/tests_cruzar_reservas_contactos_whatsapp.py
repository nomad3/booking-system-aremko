"""
Tests para Operación Vuelta a Casa, Etapa 6.

Cobertura de los 7 escenarios críticos:
    1. Reserva con WhatsApp enviado hace 5 días → atribuye
    2. Reserva con WhatsApp enviado hace 40 días → NO atribuye (fuera de ventana)
    3. Reserva con WhatsApp ya convirtio=True → NO duplica atribución
    4. Reserva sin WhatsApp previo → NO atribuye, no crashea
    5. Cliente con múltiples WhatsApp en últimos 30d → atribuye al más reciente
    6. --dry-run no escribe pero loguea
    7. Reserva creada hoy con WhatsApp enviado mismo día → atribuye (edge case)

Más:
    - Reserva cancelada se excluye
    - --fecha YYYY-MM-DD filtra correctamente
    - --ventana-dias custom funciona
    - Idempotencia: 2 corridas no duplican
    - Reserva con whatsapp_atribuidos pre-existente cuenta como 'ya_atribuidas'

Ejecutar:
    python manage.py test ventas.tests_cruzar_reservas_contactos_whatsapp
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from ventas.models import (
    Cliente,
    ContactoWhatsApp,
    ScriptWhatsApp,
    VentaReserva,
)


class CruzarReservasTestCase(TestCase):
    """Setup común: 1 cliente, 1 script, helpers para crear reservas y contactos."""

    def setUp(self):
        self.cli = Cliente.objects.create(
            nombre='María Test', telefono='+56987650100',
        )
        self.script = ScriptWhatsApp.objects.create(
            script_id='T.X', nombre='Test',
            estado_valor_target='Dormido',
            cohorte_estilo='', cohorte_contexto='', salva=1,
            plantilla_texto='Hola {nombre}',
        )

    def _crear_reserva(self, cliente=None, fecha_creacion=None, total=80000, estado='pagado'):
        """Helper para crear VentaReserva con fecha_creacion controlable."""
        cliente = cliente or self.cli
        vr = VentaReserva.objects.create(
            cliente=cliente, total=total, estado_pago=estado,
        )
        if fecha_creacion is not None:
            # fecha_creacion es auto_now_add, así que la sobreescribimos con SQL
            VentaReserva.objects.filter(id=vr.id).update(fecha_creacion=fecha_creacion)
            vr.refresh_from_db()
        return vr

    def _crear_contacto_enviado(self, cliente=None, fecha_envio=None, convirtio=False, estado='enviado'):
        """Helper para crear ContactoWhatsApp con fecha_envio controlable."""
        cliente = cliente or self.cli
        fecha_envio = fecha_envio or timezone.now()
        return ContactoWhatsApp.objects.create(
            cliente=cliente, script=self.script,
            eje_valor_snapshot='Dormido',
            eje_estilo_snapshot='', eje_contexto_snapshot='',
            dias_sin_venir_snapshot=200, salva=1,
            mensaje_renderizado='x',
            fecha_sugerido=fecha_envio.date(),
            fecha_envio=fecha_envio,
            estado=estado,
            convirtio=convirtio,
        )

    def _run(self, **kwargs):
        out = StringIO()
        call_command('cruzar_reservas_contactos_whatsapp', stdout=out, **kwargs)
        return out.getvalue()


# ============================================================================
# Escenarios principales
# ============================================================================

class AtribucionBasicaTests(CruzarReservasTestCase):
    def test_whatsapp_5d_antes_atribuye(self):
        """Escenario 1: contacto enviado hace 5 días → atribuye."""
        ahora = timezone.now()
        self._crear_contacto_enviado(fecha_envio=ahora - timedelta(days=5))
        reserva = self._crear_reserva(fecha_creacion=ahora)

        self._run()

        contacto = ContactoWhatsApp.objects.get()
        self.assertTrue(contacto.convirtio)
        self.assertEqual(contacto.reserva_atribuida_id, reserva.id)
        self.assertIsNotNone(contacto.fecha_atribucion)

    def test_whatsapp_40d_antes_no_atribuye(self):
        """Escenario 2: fuera de ventana 30d → NO atribuye."""
        ahora = timezone.now()
        self._crear_contacto_enviado(fecha_envio=ahora - timedelta(days=40))
        self._crear_reserva(fecha_creacion=ahora)

        self._run()

        contacto = ContactoWhatsApp.objects.get()
        self.assertFalse(contacto.convirtio)
        self.assertIsNone(contacto.reserva_atribuida)

    def test_whatsapp_ya_convirtio_no_duplica(self):
        """Escenario 3: contacto con convirtio=True ya → no se toca."""
        ahora = timezone.now()
        reserva_previa = self._crear_reserva(fecha_creacion=ahora - timedelta(days=10))
        contacto = self._crear_contacto_enviado(
            fecha_envio=ahora - timedelta(days=5),
            convirtio=True,
        )
        contacto.reserva_atribuida = reserva_previa
        contacto.fecha_atribucion = ahora - timedelta(days=4)
        contacto.save()

        # Nueva reserva hoy (la actual)
        self._crear_reserva(fecha_creacion=ahora)

        self._run()

        contacto.refresh_from_db()
        # Sigue apuntando a la reserva previa, no se sobreescribió
        self.assertEqual(contacto.reserva_atribuida_id, reserva_previa.id)

    def test_sin_whatsapp_previo_no_crashea(self):
        """Escenario 4: reserva sin contacto candidato → no atribuye, no crashea."""
        ahora = timezone.now()
        self._crear_reserva(fecha_creacion=ahora)
        # NO creamos contacto

        out = self._run()  # no debe lanzar excepción
        self.assertIn('Atribuciones: 0', out)

    def test_multiples_whatsapp_atribuye_al_mas_reciente(self):
        """Escenario 5: 3 contactos en últimos 30d → atribuye al más reciente."""
        ahora = timezone.now()
        c1 = self._crear_contacto_enviado(fecha_envio=ahora - timedelta(days=20))
        c2 = self._crear_contacto_enviado(fecha_envio=ahora - timedelta(days=10))
        c3 = self._crear_contacto_enviado(fecha_envio=ahora - timedelta(days=3))  # más reciente
        reserva = self._crear_reserva(fecha_creacion=ahora)

        self._run()

        c1.refresh_from_db(); c2.refresh_from_db(); c3.refresh_from_db()
        self.assertFalse(c1.convirtio)
        self.assertFalse(c2.convirtio)
        self.assertTrue(c3.convirtio)
        self.assertEqual(c3.reserva_atribuida_id, reserva.id)

    def test_dry_run_no_escribe_pero_reporta(self):
        """Escenario 6: --dry-run no toca DB pero loguea qué haría."""
        ahora = timezone.now()
        self._crear_contacto_enviado(fecha_envio=ahora - timedelta(days=5))
        self._crear_reserva(fecha_creacion=ahora)

        out = self._run(dry_run=True)

        # Output indica que SÍ habría atribuido
        self.assertIn('Atribuciones: 1', out)
        self.assertIn('simulación', out)

        # Pero la BD no cambió
        contacto = ContactoWhatsApp.objects.get()
        self.assertFalse(contacto.convirtio)
        self.assertIsNone(contacto.reserva_atribuida)

    def test_whatsapp_mismo_dia_atribuye(self):
        """Escenario 7 (edge): WhatsApp enviado y reserva creada el mismo día."""
        ahora = timezone.now()
        contacto = self._crear_contacto_enviado(fecha_envio=ahora - timedelta(hours=2))
        reserva = self._crear_reserva(fecha_creacion=ahora)

        self._run()

        contacto.refresh_from_db()
        self.assertTrue(contacto.convirtio)
        self.assertEqual(contacto.reserva_atribuida_id, reserva.id)


# ============================================================================
# Edge cases adicionales
# ============================================================================

class EdgeCasesTests(CruzarReservasTestCase):
    def test_reserva_cancelada_no_se_procesa(self):
        """Reservas con estado_pago='cancelado' se excluyen."""
        ahora = timezone.now()
        self._crear_contacto_enviado(fecha_envio=ahora - timedelta(days=5))
        self._crear_reserva(fecha_creacion=ahora, estado='cancelado')

        self._run()

        contacto = ContactoWhatsApp.objects.get()
        self.assertFalse(contacto.convirtio)

    def test_whatsapp_despues_de_la_reserva_no_atribuye(self):
        """Contacto enviado DESPUÉS de la reserva no causó la reserva → no atribuye."""
        ahora = timezone.now()
        reserva = self._crear_reserva(fecha_creacion=ahora - timedelta(days=2))
        # Contacto enviado HOY, reserva fue hace 2 días
        self._crear_contacto_enviado(fecha_envio=ahora)

        self._run()

        contacto = ContactoWhatsApp.objects.get()
        self.assertFalse(contacto.convirtio)

    def test_contacto_no_enviado_no_atribuye(self):
        """ContactoWhatsApp en estado pendiente/omitido NO atribuye."""
        ahora = timezone.now()
        self._crear_contacto_enviado(
            fecha_envio=ahora - timedelta(days=5),
            estado='pendiente',
        )
        self._crear_reserva(fecha_creacion=ahora)

        self._run()

        contacto = ContactoWhatsApp.objects.get()
        self.assertFalse(contacto.convirtio)

    def test_idempotencia_dos_corridas(self):
        """Correr 2 veces sobre la misma data no cambia el resultado."""
        ahora = timezone.now()
        self._crear_contacto_enviado(fecha_envio=ahora - timedelta(days=5))
        reserva = self._crear_reserva(fecha_creacion=ahora)

        # 1ª corrida: atribuye
        out1 = self._run()
        self.assertIn('Atribuciones: 1', out1)

        # 2ª corrida: el contacto ya tiene convirtio=True, no hay nada que hacer
        out2 = self._run()
        self.assertIn('Atribuciones: 0', out2)
        # Y "ya_atribuidas: 1" porque la reserva tiene atribución previa
        self.assertIn('ya tenían atribución previa', out2)

        # Sigue siendo el mismo contacto atribuido
        contacto = ContactoWhatsApp.objects.get()
        self.assertEqual(contacto.reserva_atribuida_id, reserva.id)

    def test_flag_fecha_filtra_solo_ese_dia(self):
        """--fecha YYYY-MM-DD solo procesa reservas creadas ese día."""
        ahora = timezone.now()
        ayer = ahora - timedelta(days=1)

        # Crear 2 reservas: una hoy, otra ayer
        self._crear_contacto_enviado(fecha_envio=ahora - timedelta(days=3))
        r_hoy = self._crear_reserva(fecha_creacion=ahora)

        cli2 = Cliente.objects.create(nombre='Otro', telefono='+56987650200')
        self._crear_contacto_enviado(cliente=cli2, fecha_envio=ayer - timedelta(days=3))
        r_ayer = self._crear_reserva(cliente=cli2, fecha_creacion=ayer)

        # Procesar SOLO el día de hoy
        self._run(fecha=ahora.date().isoformat())

        # La de hoy se atribuyó
        c1 = ContactoWhatsApp.objects.filter(cliente=self.cli).get()
        self.assertTrue(c1.convirtio)
        # La de ayer NO se procesó
        c2 = ContactoWhatsApp.objects.filter(cliente=cli2).get()
        self.assertFalse(c2.convirtio)

    def test_flag_ventana_dias_custom(self):
        """--ventana-dias 14 excluye contactos de hace 20 días."""
        ahora = timezone.now()
        self._crear_contacto_enviado(fecha_envio=ahora - timedelta(days=20))
        self._crear_reserva(fecha_creacion=ahora)

        self._run(ventana_dias=14)

        contacto = ContactoWhatsApp.objects.get()
        self.assertFalse(contacto.convirtio)

    def test_flag_ventana_dias_invalido_falla(self):
        """--ventana-dias 0 o negativo debe fallar limpio."""
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError):
            self._run(ventana_dias=0)

    def test_otro_cliente_no_se_atribuye(self):
        """El contacto de otro cliente NO se atribuye a esta reserva."""
        ahora = timezone.now()
        cli_otro = Cliente.objects.create(nombre='Otro Cliente', telefono='+56987650300')
        self._crear_contacto_enviado(cliente=cli_otro, fecha_envio=ahora - timedelta(days=5))

        # Reserva del cliente original, sin contacto propio
        self._crear_reserva(cliente=self.cli, fecha_creacion=ahora)

        self._run()

        contacto_otro = ContactoWhatsApp.objects.get()
        self.assertFalse(contacto_otro.convirtio)
        # Y la reserva de self.cli sigue sin atribución (no se le robó el contacto de otro)
        self.assertFalse(
            ContactoWhatsApp.objects.filter(reserva_atribuida__cliente=self.cli).exists()
        )

    def test_reserva_con_atribucion_previa_cuenta_separado(self):
        """Reserva que ya tiene whatsapp_atribuidos NO se reprocesa, se cuenta como 'ya_atribuidas'."""
        ahora = timezone.now()
        reserva = self._crear_reserva(fecha_creacion=ahora)

        # Contacto previo ya atribuido a esta reserva
        contacto_viejo = self._crear_contacto_enviado(
            fecha_envio=ahora - timedelta(days=5), convirtio=True,
        )
        contacto_viejo.reserva_atribuida = reserva
        contacto_viejo.fecha_atribucion = ahora - timedelta(hours=1)
        contacto_viejo.save()

        # Contacto nuevo candidato (más reciente, pero la reserva ya está atribuida)
        contacto_nuevo = self._crear_contacto_enviado(
            fecha_envio=ahora - timedelta(days=1), convirtio=False,
        )

        out = self._run()

        # El contacto viejo sigue atribuido, el nuevo NO
        contacto_viejo.refresh_from_db()
        contacto_nuevo.refresh_from_db()
        self.assertEqual(contacto_viejo.reserva_atribuida_id, reserva.id)
        self.assertFalse(contacto_nuevo.convirtio)
        self.assertIn('ya tenían atribución previa', out)
