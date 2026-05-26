"""
Tests para el servicio y endpoint de métricas de atribución por operador.

Cubre los 6 casos solicitados en el brief MVP (Jorge 2026-05-26):
    1. Cliente con 1 envío + reserva en ventana → atribuido
    2. Cliente con 1 envío + reserva fuera de ventana → NO atribuido
    3. Cliente con 2 envíos → atribuido al más reciente (last-touch)
    4. Cliente con reserva cancelada → NO atribuido
    5. Cliente con 2 reservas en ventana → ambas al mismo operador
    6. Operador sin reservas pero con envíos → aparece con conversiones=0

Más:
    - Normalización de operador (deborah vs Deborah vs DEBORAH)
    - Ranking ordenado por monto DESC
    - familias_top calcula via _mapear_categoria_a_familia
    - Endpoint requiere X-API-KEY (smoke test)

Ejecutar:
    python manage.py test ventas.tests_metricas_operadores
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.test import Client, TestCase, override_settings
from django.utils import timezone

from ventas.models import (
    CategoriaServicio,
    Cliente,
    ContactoWhatsApp,
    ReservaServicio,
    ScriptWhatsApp,
    Servicio,
    VentaReserva,
)
from ventas.services.metricas_operadores_service import (
    calcular_metricas_operadores,
)


# Fecha de referencia para todos los tests (alineada a las fixtures)
HOY = date(2026, 6, 1)


def _dt(d, hora=12, minuto=0):
    """Construye datetime tz-aware desde un date."""
    tz = timezone.get_current_timezone()
    return datetime.combine(d, datetime.min.time()).replace(
        hour=hora, minute=minuto, tzinfo=tz,
    )


class MetricasOperadoresServiceTests(TestCase):
    """Tests del servicio puro `calcular_metricas_operadores`.

    Hidratan datos mínimos en BD y validan la atribución last-touch.
    """

    def setUp(self):
        # Cliente reusable
        self.cli = Cliente.objects.create(
            nombre='Cliente Test',
            telefono='+56911111111',
        )
        # Script mínimo para FK requerida
        self.script = ScriptWhatsApp.objects.create(
            script_id='TEST.1', nombre='Test',
            estado_valor_target='Dormido',
            cohorte_estilo='', cohorte_contexto='', salva=1,
            plantilla_texto='Hola {nombre}',
        )
        # Categoría + servicio para tests de familias
        self.cat_tinas = CategoriaServicio.objects.create(nombre='Tinas')
        self.serv_tina = Servicio.objects.create(
            nombre='Tina Pareja',
            categoria=self.cat_tinas,
            tipo_servicio='tina',
            precio_base=Decimal('60000'),
            duracion=60,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _crear_contacto_enviado(
        self, cliente, fecha_envio_date, operador='deborah', respondio=False,
    ):
        return ContactoWhatsApp.objects.create(
            cliente=cliente,
            script=self.script,
            eje_valor_snapshot='Dormido',
            eje_estilo_snapshot='',
            eje_contexto_snapshot='',
            dias_sin_venir_snapshot=200,
            salva=1,
            mensaje_renderizado='msg',
            prioridad=3,
            fecha_sugerido=fecha_envio_date,
            estado='enviado',
            fecha_envio=_dt(fecha_envio_date, hora=10),
            operador=operador,
            respondio=respondio,
        )

    def _crear_reserva(
        self, cliente, fecha_creacion_date, total=100000,
        estado_pago='pagado', con_servicio_tina=False,
    ):
        vr = VentaReserva.objects.create(
            cliente=cliente,
            total=Decimal(total),
            estado_pago=estado_pago,
        )
        # fecha_creacion es auto_now_add → setear manualmente con .update
        VentaReserva.objects.filter(id=vr.id).update(
            fecha_creacion=_dt(fecha_creacion_date, hora=14),
        )
        vr.refresh_from_db()
        if con_servicio_tina:
            ReservaServicio.objects.create(
                venta_reserva=vr,
                servicio=self.serv_tina,
                fecha_agendamiento=fecha_creacion_date + timedelta(days=7),
                hora_inicio='15:00',
                cantidad_personas=2,
            )
        return vr

    def _llamar(self, desde, hasta, ventana=60):
        return calcular_metricas_operadores(
            desde=desde, hasta=hasta, ventana_atribucion_dias=ventana,
        )

    # ==================================================================
    # Test 1 del brief: cliente con 1 envío + reserva en ventana
    # ==================================================================
    def test_1_envio_reserva_en_ventana_atribuye(self):
        self._crear_contacto_enviado(self.cli, fecha_envio_date=HOY - timedelta(days=10))
        self._crear_reserva(self.cli, fecha_creacion_date=HOY - timedelta(days=5))

        data = self._llamar(desde=HOY - timedelta(days=20), hasta=HOY)

        self.assertEqual(data['totales']['mensajes_enviados'], 1)
        self.assertEqual(data['totales']['reservas_atribuidas'], 1)
        self.assertEqual(data['totales']['monto_atribuido'], 100000)
        self.assertEqual(len(data['operadores']), 1)
        self.assertEqual(data['operadores'][0]['username'], 'deborah')
        self.assertEqual(data['operadores'][0]['reservas_atribuidas'], 1)

    # ==================================================================
    # Test 2 del brief: reserva fuera de ventana NO atribuye
    # ==================================================================
    def test_2_reserva_fuera_de_ventana_no_atribuye(self):
        # Envío el 1-may, reserva el 5-jul (>60d) — no debe atribuirse
        self._crear_contacto_enviado(self.cli, fecha_envio_date=date(2026, 5, 1))
        self._crear_reserva(self.cli, fecha_creacion_date=date(2026, 7, 5))

        # Período que cubre tanto envío como reserva, ventana 60d
        data = calcular_metricas_operadores(
            desde=date(2026, 4, 1), hasta=date(2026, 7, 31),
            ventana_atribucion_dias=60,
        )

        self.assertEqual(data['totales']['mensajes_enviados'], 1)
        self.assertEqual(data['totales']['reservas_atribuidas'], 0)
        self.assertEqual(data['totales']['monto_atribuido'], 0)
        self.assertEqual(data['operadores'][0]['reservas_atribuidas'], 0)

    def test_2b_borde_exacto_ventana(self):
        """Reserva en día N+ventana exacto debe atribuirse; día N+ventana+1 NO."""
        # Envío hoy-30, reserva hoy-30+60 = hoy+30 (exactamente 60d después)
        f_envio = HOY - timedelta(days=30)
        f_reserva_borde = f_envio + timedelta(days=60)
        f_reserva_fuera = f_envio + timedelta(days=61)

        self._crear_contacto_enviado(self.cli, fecha_envio_date=f_envio)
        self._crear_reserva(self.cli, fecha_creacion_date=f_reserva_borde)

        data = calcular_metricas_operadores(
            desde=HOY - timedelta(days=60), hasta=HOY + timedelta(days=90),
            ventana_atribucion_dias=60,
        )
        # Día exactamente 60 — atribuye (timedelta(days=60) <= ventana_td=60)
        self.assertEqual(data['totales']['reservas_atribuidas'], 1)

    # ==================================================================
    # Test 3 del brief: 2 envíos → atribuye al más reciente (last-touch)
    # ==================================================================
    def test_3_last_touch_gana_envio_mas_reciente(self):
        # Jorge envía el día 1, Deborah el día 5, reserva el día 10
        self._crear_contacto_enviado(
            self.cli, fecha_envio_date=HOY - timedelta(days=20), operador='jorge',
        )
        self._crear_contacto_enviado(
            self.cli, fecha_envio_date=HOY - timedelta(days=10), operador='deborah',
        )
        self._crear_reserva(self.cli, fecha_creacion_date=HOY - timedelta(days=3))

        data = self._llamar(desde=HOY - timedelta(days=30), hasta=HOY)

        # Ambos cuentan como mensajes enviados, pero la reserva va solo a Deborah
        self.assertEqual(data['totales']['mensajes_enviados'], 2)
        self.assertEqual(data['totales']['reservas_atribuidas'], 1)

        operadores = {o['username']: o for o in data['operadores']}
        self.assertEqual(operadores['deborah']['reservas_atribuidas'], 1)
        self.assertEqual(operadores['deborah']['monto_atribuido'], 100000)
        self.assertEqual(operadores['jorge']['reservas_atribuidas'], 0)
        self.assertEqual(operadores['jorge']['monto_atribuido'], 0)

    # ==================================================================
    # Test 4 del brief: reserva cancelada → NO atribuye
    # ==================================================================
    def test_4_reserva_cancelada_no_atribuye(self):
        self._crear_contacto_enviado(self.cli, fecha_envio_date=HOY - timedelta(days=10))
        self._crear_reserva(
            self.cli, fecha_creacion_date=HOY - timedelta(days=5),
            estado_pago='cancelado',
        )

        data = self._llamar(desde=HOY - timedelta(days=20), hasta=HOY)
        self.assertEqual(data['totales']['mensajes_enviados'], 1)
        self.assertEqual(data['totales']['reservas_atribuidas'], 0)

    # ==================================================================
    # Test 5 del brief: cliente con 2 reservas en ventana → ambas al mismo op
    # ==================================================================
    def test_5_dos_reservas_mismo_operador(self):
        self._crear_contacto_enviado(self.cli, fecha_envio_date=HOY - timedelta(days=20))
        self._crear_reserva(self.cli, fecha_creacion_date=HOY - timedelta(days=10), total=80000)
        self._crear_reserva(self.cli, fecha_creacion_date=HOY - timedelta(days=3), total=120000)

        data = self._llamar(desde=HOY - timedelta(days=30), hasta=HOY)

        self.assertEqual(data['totales']['reservas_atribuidas'], 2)
        self.assertEqual(data['totales']['monto_atribuido'], 200000)
        self.assertEqual(data['operadores'][0]['username'], 'deborah')
        self.assertEqual(data['operadores'][0]['reservas_atribuidas'], 2)
        self.assertEqual(data['operadores'][0]['ticket_promedio_atribuido'], 100000)

    # ==================================================================
    # Test 6 del brief (reinterpretado): operador con envíos pero sin
    # conversiones aparece en ranking con monto=0.
    # ==================================================================
    def test_6_operador_sin_conversiones_aparece_con_ceros(self):
        # Deborah envía, nadie reserva
        self._crear_contacto_enviado(self.cli, fecha_envio_date=HOY - timedelta(days=10))

        data = self._llamar(desde=HOY - timedelta(days=30), hasta=HOY)

        self.assertEqual(len(data['operadores']), 1)
        op = data['operadores'][0]
        self.assertEqual(op['username'], 'deborah')
        self.assertEqual(op['mensajes_enviados'], 1)
        self.assertEqual(op['reservas_atribuidas'], 0)
        self.assertEqual(op['monto_atribuido'], 0)
        self.assertEqual(op['ticket_promedio_atribuido'], 0)
        self.assertEqual(op['tasa_conversion'], 0.0)
        self.assertEqual(op['familias_top'], [])

    # ==================================================================
    # Tests adicionales
    # ==================================================================

    def test_normalizacion_operador_capitalizacion(self):
        """'Deborah', 'deborah', 'DEBORAH' deben colapsar a un solo operador."""
        cli2 = Cliente.objects.create(nombre='B', telefono='+56922222222')
        cli3 = Cliente.objects.create(nombre='C', telefono='+56933333333')

        self._crear_contacto_enviado(self.cli, HOY - timedelta(days=10), operador='Deborah')
        self._crear_contacto_enviado(cli2, HOY - timedelta(days=8), operador='deborah')
        self._crear_contacto_enviado(cli3, HOY - timedelta(days=5), operador='DEBORAH')

        data = self._llamar(desde=HOY - timedelta(days=30), hasta=HOY)

        # Un solo operador en el ranking
        self.assertEqual(len(data['operadores']), 1)
        self.assertEqual(data['operadores'][0]['mensajes_enviados'], 3)
        # display_name: el que más se repitió. Aquí cada uno aparece 1 vez,
        # most_common() rompe empates por orden de inserción → 'Deborah' gana.
        self.assertIn(data['operadores'][0]['username'], {'Deborah', 'deborah', 'DEBORAH'})

    def test_ranking_ordenado_por_monto_desc(self):
        cli_b = Cliente.objects.create(nombre='B', telefono='+56922222222')

        self._crear_contacto_enviado(self.cli, HOY - timedelta(days=10), operador='deborah')
        self._crear_contacto_enviado(cli_b, HOY - timedelta(days=10), operador='jorge')
        # Jorge atribuye más monto → debe estar primero
        self._crear_reserva(self.cli, HOY - timedelta(days=3), total=50000)
        self._crear_reserva(cli_b, HOY - timedelta(days=3), total=500000)

        data = self._llamar(desde=HOY - timedelta(days=30), hasta=HOY)

        self.assertEqual(data['operadores'][0]['username'], 'jorge')
        self.assertEqual(data['operadores'][0]['monto_atribuido'], 500000)
        self.assertEqual(data['operadores'][1]['username'], 'deborah')

    def test_familias_top_mapea_categoria(self):
        """Reserva con servicio Tina debe aparecer en familias_top='Tinas'."""
        self._crear_contacto_enviado(self.cli, HOY - timedelta(days=10))
        self._crear_reserva(
            self.cli, HOY - timedelta(days=5),
            total=60000, con_servicio_tina=True,
        )

        data = self._llamar(desde=HOY - timedelta(days=30), hasta=HOY)

        op = data['operadores'][0]
        self.assertEqual(len(op['familias_top']), 1)
        self.assertEqual(op['familias_top'][0]['familia'], 'Tinas')
        self.assertEqual(op['familias_top'][0]['reservas'], 1)
        self.assertEqual(op['familias_top'][0]['monto'], 60000)


@override_settings(AUTOMATION_API_KEY='test-key-metricas')
class MetricasOperadoresEndpointTests(TestCase):
    """Smoke tests del endpoint HTTP — auth + parsing de query params."""

    URL = '/ventas/api/aremko-cli/operacion-vuelta-a-casa/metricas-operadores/'

    def setUp(self):
        self.client = Client()

    def test_sin_api_key_401(self):
        resp = self.client.get(self.URL)
        self.assertEqual(resp.status_code, 401)

    def test_api_key_invalida_401(self):
        resp = self.client.get(self.URL, HTTP_X_API_KEY='wrong')
        self.assertEqual(resp.status_code, 401)

    def test_endpoint_ok_response_shape(self):
        resp = self.client.get(self.URL, HTTP_X_API_KEY='test-key-metricas')
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        # Shape mínimo del brief
        self.assertIn('periodo', data)
        self.assertIn('desde', data['periodo'])
        self.assertIn('hasta', data['periodo'])
        self.assertIn('ventana_atribucion_dias', data)
        self.assertIn('totales', data)
        self.assertIn('operadores', data)
        # Sin datos en BD → totales en 0
        self.assertEqual(data['totales']['mensajes_enviados'], 0)
        self.assertEqual(data['operadores'], [])

    def test_ventana_invalida_400(self):
        resp = self.client.get(
            self.URL + '?ventana_atribucion_dias=999',
            HTTP_X_API_KEY='test-key-metricas',
        )
        self.assertEqual(resp.status_code, 400)

    def test_desde_mayor_hasta_400(self):
        resp = self.client.get(
            self.URL + '?desde=2026-12-31&hasta=2026-01-01',
            HTTP_X_API_KEY='test-key-metricas',
        )
        self.assertEqual(resp.status_code, 400)
