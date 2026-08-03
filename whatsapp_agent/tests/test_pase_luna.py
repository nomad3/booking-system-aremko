"""El Pase en la conversación de Luna (H-096).

Jorge armó un guion para Deborah: le manda El Pase apenas paga y lo recorre con
el cliente paso a paso, y cada paso termina cuando el cliente dice "sí, lo veo".

**Luna no puede sostener ese baile de cinco turnos** — está documentado dos veces
en este repo (H-085: no encadena dos llamadas; H-090: narró un cambio en vez de
ejecutarlo porque la instrucción vivía en el turno anterior). Así que el guion
toma otra forma con el mismo objetivo:

  · todo el contenido en UN mensaje, incrustado por código en el resumen;
  · y el empujón a abrirlo cuando el cliente pregunta algo que El Pase responde.

Ejecutar:
    pytest whatsapp_agent/tests/test_pase_luna.py
    (o: python manage.py test whatsapp_agent.tests.test_pase_luna)
"""
from whatsapp_agent.pase import (bloque_resumen, respuesta_del_pase,
                                 tema_del_pase)

URL = 'https://www.aremko.cl/ventas/reserva/abc123/'


class TestTemaDelPase:
    """Qué preguntas ya responde El Pase."""

    def test_reconoce_la_pregunta_por_el_wifi(self):
        for m in ('cual es la clave del wifi?', '¿Tienen WiFi?',
                  'me pasas la clave de internet', 'como es la conexion'):
            assert tema_del_pase(m) == 'wifi', m

    def test_reconoce_la_pregunta_por_como_llegar(self):
        for m in ('como llego?', '¿Cómo se llega a Aremko?', 'cual es la direccion',
                  'me mandas la ubicacion', 'tienen mapa?', 'donde están ubicados'):
            assert tema_del_pase(m) == 'llegar', m

    def test_reconoce_la_pregunta_por_pedir_algo(self):
        for m in ('como pido algo?', 'tienen carta?', 'quiero ver el menu',
                  'se puede pedir comida'):
            assert tema_del_pase(m) == 'pedir', m

    def test_ante_la_duda_NO_dispara(self):
        """Sumar un link de más es ruido; cambiar de tema por un falso positivo
        es peor. Estas son conversaciones normales de venta."""
        for m in ('quiero reservar una tina para el sábado',
                  'cuanto cuesta el masaje?',
                  'hola',
                  'gracias!',
                  '',
                  None):
            assert tema_del_pase(m) is None, repr(m)

    def test_funciona_sin_tildes_y_en_mayusculas(self):
        assert tema_del_pase('¿CÓMO LLEGO?') == 'llegar'
        assert tema_del_pase('como llego') == 'llegar'


class TestRespuestaDelPase:

    def test_responde_LO_QUE_PREGUNTO_y_no_recita_todo(self):
        """Una cosa a la vez, igual que el resto del agente (H-088). Si a cada
        pregunta le respondiera con las cuatro secciones, sería un folleto."""
        r = respuesta_del_pase('wifi', URL)
        assert 'wifi' in r.lower()
        assert URL in r
        assert 'comanda' not in r.lower()
        assert 'mapa' not in r.lower()

    def test_cada_tema_tiene_su_frase(self):
        for tema in ('wifi', 'llegar', 'pedir'):
            assert URL in respuesta_del_pase(tema, URL), tema

    def test_sin_url_no_inventa_nada(self):
        assert respuesta_del_pase('wifi', '') == ''
        assert respuesta_del_pase('inexistente', URL) == ''


class TestBloqueDelResumen:
    """El guion de Deborah, comprimido a un mensaje."""

    def test_trae_las_cuatro_cosas_y_el_link(self):
        b = bloque_resumen(URL)
        assert URL in b
        for esperado in ('QR', 'wifi', 'llegar', 'comanda'):
            assert esperado in b.lower() or esperado in b, esperado

    def test_le_da_un_TRABAJO_en_vez_de_describirse(self):
        """El mensaje viejo decía "ahí está el link de su ficha y encontrará los
        detalles" — nadie abre eso. Este pide guardarlo."""
        assert 'Guárdalo' in bloque_resumen(URL)

    def test_la_ficha_de_masaje_solo_aparece_si_hay_masaje(self):
        assert 'acompañante' not in bloque_resumen(URL, tiene_masaje=False)
        assert 'acompañante' in bloque_resumen(URL, tiene_masaje=True)

    def test_sin_url_no_agrega_un_bloque_vacio_al_resumen(self):
        assert bloque_resumen('') == ''
        assert bloque_resumen(None) == ''

    def test_no_se_pasa_del_largo_de_un_WhatsApp(self):
        # El resumen completo ya es largo; el bloque tiene que ser un cierre,
        # no otro mensaje encima.
        assert len(bloque_resumen(URL, tiene_masaje=True)) < 600
