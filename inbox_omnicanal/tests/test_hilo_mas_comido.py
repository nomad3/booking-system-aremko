"""El hilo del inbox y el «+» comido del teléfono (2026-08-31).

Bug real, cazado por Jorge desde su celular: la LISTA de conversaciones
funcionaba, pero al abrir un hilo de WhatsApp quedaba el spinner eterno. La
causa: un cliente (el build de Vercel) manda `external_id=+56…` sin codificar;
el «+» viaja como ESPACIO, el strip lo borra, y el hilo buscaba `56959098816`
contra un guardado `+56959098816` → cero mensajes, sin error. Instagram nunca
falló porque sus IDs no llevan «+».

La tolerancia vive en el SERVIDOR (si el id de whatsapp es puro dígito, se le
antepone el «+») porque arregla a todos los builds de frontend de una vez.

Ejecutar:
    python manage.py test inbox_omnicanal
"""
from __future__ import annotations

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone


@override_settings(LUNA_API_KEY='llave-de-prueba')
class ElHiloToleraElMasComido(TestCase):
    maxDiff = None

    @classmethod
    def setUpTestData(cls):
        from ventas.models import WhatsAppMessage

        for i, (d, body) in enumerate((('in', 'Hola buenas tardes'),
                                       ('in', 'Me daría sus precios porfabor'))):
            WhatsAppMessage.objects.create(
                phone='+56959098816', direction=d, body=body,
                wa_message_id=f'wamid-test-{i}', msg_type='text',
                timestamp=timezone.now())

    def _get(self, **params):
        return self.client.get(reverse('inbox_conversation'), params,
                               HTTP_X_API_KEY='llave-de-prueba')

    def test_con_el_mas_correcto_encuentra_el_hilo(self):
        r = self._get(canal='whatsapp', external_id='+56959098816')
        self.assertEqual(r.json()['count'], 2)

    def test_SIN_el_mas_tambien_lo_encuentra(self):
        """El caso del celular de Jorge: el + llegó como espacio y el strip lo
        borró. El servidor lo repone y el hilo aparece igual."""
        r = self._get(canal='whatsapp', external_id='56959098816')
        d = r.json()
        self.assertEqual(d['count'], 2, 'el hilo volvió a quedar vacío sin el +')
        self.assertEqual(d['messages'][0]['body'], 'Hola buenas tardes')

    def test_instagram_con_id_numerico_NO_gana_un_mas(self):
        """La contraparte: los IGSID son puros dígitos y NO llevan +. La
        tolerancia es solo del canal whatsapp."""
        from inbox_omnicanal.models import ChannelMessage

        ChannelMessage.objects.create(
            canal='instagram', external_id='1334763291834043', direction='in',
            body='Sería para 2 personas', msg_type='text',
            external_message_id='ig-test-1', timestamp=timezone.now())
        r = self._get(canal='instagram', external_id='1334763291834043')
        self.assertEqual(r.json()['count'], 1)

    def test_sin_llave_sigue_cerrado(self):
        r = self.client.get(reverse('inbox_conversation'),
                            {'canal': 'whatsapp', 'external_id': '56959098816'})
        self.assertEqual(r.status_code, 401)
