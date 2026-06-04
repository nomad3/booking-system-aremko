"""Tests del módulo Conexión-Masajes (F8).

Cubre el flujo end-to-end:
- generación de participantes (1 persona → comprador; 2 → comprador + acompañante)
- idempotencia
- completar la ficha pública (crea Cliente + BienestarMasajeFicha + estado)
- token único / token inválido
- F6: gating de seguimientos comerciales por consentimiento_marketing
- F7: el resumen del terapeuta programa el email 'resumen_bienestar' (idempotente)
"""

from decimal import Decimal
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from ventas.models import (
    Cliente, CategoriaServicio, Servicio, VentaReserva, ReservaServicio,
    ParticipanteMasajeReserva, BienestarMasajeFicha, SeguimientoBienestarMasaje,
)


class MasajeConexionTestBase(TestCase):
    def setUp(self):
        self.cat = CategoriaServicio.objects.create(nombre='Masajes')
        self.serv_masaje = Servicio.objects.create(
            nombre='Masaje Relajante', categoria=self.cat,
            tipo_servicio='masaje', precio_base=Decimal('35000'), duracion=60,
        )
        self._tel_seq = 0

    def _cliente(self, nombre='Cliente Uno', email='cli@test.com'):
        self._tel_seq += 1
        return Cliente.objects.create(
            nombre=nombre, telefono=f'9{self._tel_seq:08d}', email=email,
        )

    def _reserva_con_masaje(self, cliente, cantidad):
        vr = VentaReserva.objects.create(
            cliente=cliente, total=Decimal('35000'), estado_pago='pagado',
        )
        ReservaServicio.objects.create(
            venta_reserva=vr, servicio=self.serv_masaje,
            fecha_agendamiento=timezone.now().date() + timedelta(days=3),
            hora_inicio='15:00', cantidad_personas=cantidad,
            precio_unitario_venta=Decimal('35000'),
        )
        return vr


class GeneracionParticipantesTests(MasajeConexionTestBase):
    def test_masaje_individual_genera_un_comprador(self):
        cli = self._cliente(nombre='Ana Solo')
        vr = self._reserva_con_masaje(cli, cantidad=1)
        parts = ParticipanteMasajeReserva.objects.filter(reserva=vr)
        self.assertEqual(parts.count(), 1)
        p = parts.first()
        self.assertEqual(p.tipo_participante, 'comprador')
        self.assertEqual(p.cliente_id, cli.id)
        self.assertTrue(p.token_formulario)  # token generado

    def test_masaje_pareja_genera_comprador_y_acompanante(self):
        cli = self._cliente(nombre='Beto Pareja')
        vr = self._reserva_con_masaje(cli, cantidad=2)
        parts = list(ParticipanteMasajeReserva.objects.filter(reserva=vr))
        self.assertEqual(len(parts), 2)
        tipos = sorted(p.tipo_participante for p in parts)
        self.assertEqual(tipos, ['acompanante', 'comprador'])
        # tokens únicos
        tokens = {p.token_formulario for p in parts}
        self.assertEqual(len(tokens), 2)
        # el acompañante nace vacío
        acomp = next(p for p in parts if p.tipo_participante == 'acompanante')
        self.assertEqual(acomp.nombre, '')

    def test_idempotente_no_duplica(self):
        cli = self._cliente()
        vr = self._reserva_con_masaje(cli, cantidad=2)
        # re-guardar el masaje no debe crear más participantes
        rs = vr.reservaservicios.first()
        rs.save()
        from ventas.services.masaje_participantes_service import generar_participantes_masaje
        generar_participantes_masaje(vr)
        self.assertEqual(ParticipanteMasajeReserva.objects.filter(reserva=vr).count(), 2)


class FichaPublicaTests(MasajeConexionTestBase):
    def _completar_ficha(self, participante, marketing=False, extra=None):
        url = reverse('masaje_ficha', kwargs={'token': participante.token_formulario})
        data = {
            'nombre_completo': 'Ana Pérez',
            'telefono': '912340000',
            'email': 'ana@test.com',
            'consentimiento_datos': 'on',
            'objetivo_principal': 'relajacion',
            'intensidad_preferida': 'media',
            'zonas_tension': 'cuello',
        }
        if marketing:
            data['consentimiento_marketing'] = 'on'
        if extra:
            data.update(extra)
        return self.client.post(url, data)

    def test_completar_ficha_crea_cliente_y_ficha(self):
        cli = self._cliente()
        vr = self._reserva_con_masaje(cli, cantidad=1)
        p = ParticipanteMasajeReserva.objects.get(reserva=vr)
        resp = self._completar_ficha(p)
        self.assertEqual(resp.status_code, 200)
        p.refresh_from_db()
        self.assertEqual(p.estado_contacto, 'ficha_completada')
        self.assertIsNotNone(p.ficha_bienestar_id)
        ficha = BienestarMasajeFicha.objects.get(id=p.ficha_bienestar_id)
        self.assertEqual(ficha.estado_ficha, 'completada')
        self.assertTrue(ficha.consentimiento_datos)
        self.assertIsNotNone(ficha.cliente_id)

    def test_token_invalido_404(self):
        url = reverse('masaje_ficha', kwargs={'token': 'token-que-no-existe-xyz'})
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_ficha_no_se_completa_dos_veces(self):
        cli = self._cliente()
        vr = self._reserva_con_masaje(cli, cantidad=1)
        p = ParticipanteMasajeReserva.objects.get(reserva=vr)
        self._completar_ficha(p)
        # segundo intento no debe crear otra ficha
        self._completar_ficha(p)
        self.assertEqual(BienestarMasajeFicha.objects.filter(reserva=vr).count(), 1)


class SeguimientosGatingTests(MasajeConexionTestBase):
    def _completar(self, p, marketing):
        url = reverse('masaje_ficha', kwargs={'token': p.token_formulario})
        data = {
            'nombre_completo': 'Ceci Test', 'telefono': '913330000',
            'email': 'ceci@test.com', 'consentimiento_datos': 'on',
            'objetivo_principal': 'relajacion', 'intensidad_preferida': 'media',
        }
        if marketing:
            data['consentimiento_marketing'] = 'on'
        return self.client.post(url, data)

    def test_sin_consentimiento_solo_transaccional(self):
        cli = self._cliente()
        vr = self._reserva_con_masaje(cli, cantidad=1)
        p = ParticipanteMasajeReserva.objects.get(reserva=vr)
        self._completar(p, marketing=False)
        tipos = set(SeguimientoBienestarMasaje.objects
                    .filter(participante=p).values_list('tipo_email', flat=True))
        self.assertEqual(tipos, {'gracias_visita'})

    def test_con_consentimiento_programa_comerciales(self):
        cli = self._cliente()
        vr = self._reserva_con_masaje(cli, cantidad=1)
        p = ParticipanteMasajeReserva.objects.get(reserva=vr)
        self._completar(p, marketing=True)
        tipos = set(SeguimientoBienestarMasaje.objects
                    .filter(participante=p).values_list('tipo_email', flat=True))
        self.assertEqual(
            tipos,
            {'gracias_visita', 'seguimiento_7d', 'recomendacion_30d',
             'reactivacion_60d', 'reactivacion_90d'},
        )


class ResumenTerapeutaTests(MasajeConexionTestBase):
    def _ficha_completada(self):
        cli = self._cliente()
        vr = self._reserva_con_masaje(cli, cantidad=1)
        p = ParticipanteMasajeReserva.objects.get(reserva=vr)
        url = reverse('masaje_ficha', kwargs={'token': p.token_formulario})
        self.client.post(url, {
            'nombre_completo': 'Dani Test', 'telefono': '914440000',
            'email': 'dani@test.com', 'consentimiento_datos': 'on',
        })
        p.refresh_from_db()
        return BienestarMasajeFicha.objects.get(id=p.ficha_bienestar_id), p

    def test_resumen_terapeuta_programa_email_idempotente(self):
        ficha, p = self._ficha_completada()
        # antes de cargar resumen, no hay 'resumen_bienestar'
        self.assertFalse(SeguimientoBienestarMasaje.objects
                         .filter(participante=p, tipo_email='resumen_bienestar').exists())
        # la masajista completa su resumen → se programa
        ficha.zonas_trabajadas = 'espalda y cuello'
        ficha.sugerencia_frecuencia = 'cada 3-4 semanas'
        ficha.save()
        qs = SeguimientoBienestarMasaje.objects.filter(
            participante=p, tipo_email='resumen_bienestar')
        self.assertEqual(qs.count(), 1)
        # re-guardar no duplica
        ficha.obs_terapeuta = 'sesión tranquila'
        ficha.save()
        self.assertEqual(qs.count(), 1)
