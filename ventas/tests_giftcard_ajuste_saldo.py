"""«Ajustar saldo» de una GiftCard — SOLO el dueño (Jorge, 2026-08-04).

Nace de una necesidad concreta: Jorge regala una GiftCard emitida en $50.000 y
quiere que valga $100.000. El admin no servía — `monto_disponible` es readonly, y
cambiar `monto_inicial` a mano NO lo arrastra (el modelo solo copia uno al otro
al crear). Habría quedado una tarjeta que dice $100.000 y al canjear alcanza
para $50.000: ese reclamo llega en el mesón.

Su condición fue explícita: "solo yo como usuario pueda hacerlo, nadie más".

El candado va en DOS capas y estos tests protegen la segunda, que es la que
importa: esconder la acción del desplegable NO es bloquearla — un POST armado a
mano la ejecuta igual. Los tests de acceso valen justamente porque prueban el
camino que un atajo de UI no cubre.

Ejecutar:
    python manage.py test ventas.tests_giftcard_ajuste_saldo
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import GiftCard

URL_ADMIN = '/admin/ventas/giftcard/'


class _Base(TestCase):

    def setUp(self):
        self.gc = GiftCard.objects.create(
            monto_inicial=Decimal('50000'), monto_disponible=Decimal('50000'),
            fecha_vencimiento=timezone.localdate() + timedelta(days=365))
        User = get_user_model()
        self.dueno = User.objects.create_superuser(
            'jorge_test', 'j@test.cl', 'x')
        self.empleada = User.objects.create_user(
            'deborah_test', 'd@test.cl', 'x', is_staff=True)
        # Sin esto el staff no ve ni el listado y el test de acceso mentiría:
        # daría "bloqueado" por no tener permiso de ver, no por el candado.
        from django.contrib.auth.models import Permission
        self.empleada.user_permissions.add(
            *Permission.objects.filter(content_type__app_label='ventas',
                                       content_type__model='giftcard'))

    def tearDown(self):
        from ventas import middleware
        middleware._thread_locals.user = None
        super().tearDown()

    def _ajustar(self, monto=100000, motivo='Regalo de cortesía'):
        return self.client.post(URL_ADMIN, {
            'action': 'ajustar_saldo',
            '_selected_action': [str(self.gc.pk)],
            'aplicar': 'Ajustar el saldo',
            'nuevo_monto': str(monto),
            'motivo': motivo,
        }, follow=True)


class SoloElDuenoTest(_Base):
    """La condición de Jorge, probada por el camino que la UI no cubre."""

    def test_el_dueno_SI_puede(self):
        self.client.force_login(self.dueno)
        self._ajustar()
        self.gc.refresh_from_db()
        self.assertEqual(int(self.gc.monto_disponible), 100000)

    def test_una_empleada_NO_puede_aunque_arme_el_POST_a_mano(self):
        """Esconder la acción del desplegable no basta: el POST se falsifica.
        Este es el test que de verdad prueba el candado."""
        self.client.force_login(self.empleada)
        self._ajustar()
        self.gc.refresh_from_db()
        self.assertEqual(int(self.gc.monto_disponible), 50000)  # intacta

    def test_la_accion_NI_APARECE_para_quien_no_es_dueno(self):
        self.client.force_login(self.empleada)
        cuerpo = self.client.get(URL_ADMIN).content.decode()
        self.assertNotIn('ajustar_saldo', cuerpo)

    def test_para_el_dueno_SI_aparece(self):
        self.client.force_login(self.dueno)
        cuerpo = self.client.get(URL_ADMIN).content.decode()
        self.assertIn('ajustar_saldo', cuerpo)


class ReemisionVsRecargaTest(_Base):
    """`monto_inicial` es el registro de por cuánto se emitió: no siempre se toca."""

    def test_sin_usar_es_REEMISION_y_cambian_los_dos(self):
        self.client.force_login(self.dueno)
        self._ajustar(monto=100000)
        self.gc.refresh_from_db()
        self.assertEqual(int(self.gc.monto_disponible), 100000)
        self.assertEqual(int(self.gc.monto_inicial), 100000)

    def test_ya_usada_es_RECARGA_y_el_inicial_NO_se_toca(self):
        """Si se emitió en $50.000 y se gastaron $20.000, cambiar el inicial
        borraría por cuánto se vendió de verdad."""
        self.gc.monto_disponible = Decimal('30000')
        self.gc.save()
        self.client.force_login(self.dueno)
        self._ajustar(monto=100000)
        self.gc.refresh_from_db()
        self.assertEqual(int(self.gc.monto_disponible), 100000)
        self.assertEqual(int(self.gc.monto_inicial), 50000)   # el registro sobrevive

    def test_una_cobrada_con_saldo_nuevo_vuelve_a_estar_vigente(self):
        self.gc.monto_disponible = Decimal('0')
        self.gc.estado = 'cobrado'
        self.gc.save()
        self.client.force_login(self.dueno)
        self._ajustar(monto=100000)
        self.gc.refresh_from_db()
        self.assertEqual(self.gc.estado, 'por_cobrar')


class RastroTest(_Base):

    def test_queda_registrado_QUIEN_y_POR_QUE(self):
        self.client.force_login(self.dueno)
        self._ajustar(monto=100000, motivo='Regalo a proveedor')
        entrada = LogEntry.objects.filter(object_id=str(self.gc.pk)).latest('action_time')
        self.assertEqual(entrada.user_id, self.dueno.pk)
        self.assertIn('Regalo a proveedor', entrada.change_message)
        self.assertIn('50.000', entrada.change_message)    # de cuánto venía
        self.assertIn('100.000', entrada.change_message)   # a cuánto quedó

    def test_sin_MOTIVO_no_se_aplica(self):
        """El motivo es lo único que explica el ajuste dentro de seis meses."""
        self.client.force_login(self.dueno)
        self._ajustar(monto=100000, motivo='   ')
        self.gc.refresh_from_db()
        self.assertEqual(int(self.gc.monto_disponible), 50000)

    def test_un_monto_basura_no_se_aplica(self):
        self.client.force_login(self.dueno)
        self._ajustar(monto='abc')
        self.gc.refresh_from_db()
        self.assertEqual(int(self.gc.monto_disponible), 50000)


class ElCasoDeJorgeTest(_Base):
    """La GiftCard real que originó todo esto."""

    def test_de_50_a_100_mil_deja_la_tarjeta_coherente(self):
        self.client.force_login(self.dueno)
        self._ajustar(monto=100000, motivo='Regalo')
        self.gc.refresh_from_db()
        # Lo que se quería evitar: que digan cosas distintas.
        self.assertEqual(self.gc.monto_disponible, self.gc.monto_inicial)
        self.assertEqual(int(self.gc.monto_disponible), 100000)
