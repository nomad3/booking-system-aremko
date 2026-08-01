"""H-089 — pedir un extra que ya viene en la ambientación superior ofrece el cambio.

Caso real (Jorge, 2026-08-01): el cliente tenía la Ambientación romántica R1 en el
carrito y preguntó "y se puede incluir un ramo de flores?" → Luna escaló con
"consulta de producto no disponible".

Dos cosas estaban mal, no una:
  1. El Producto "Ramo de flores" existe y tiene stock, pero NO está
     `publicado_web`, y los tres caminos de producto de Luna exigen ese flag.
  2. Publicarlo tampoco era la respuesta: R1 ($32.000) + ramo suelto ($38.000) =
     $70.000, mientras que la R2 —que es exactamente R1 + ramo— cuesta $68.000.
     Venderlo suelto era ofrecer la combinación más cara y peor armada.

Decisión de Jorge: que Luna OFREZCA subir a R2, y que el filtro `publicado_web`
siga mandando para el resto de los productos.

`upgrade_por_extra` solo DETECTA la oportunidad — no toca el carrito ni decide
precios. Ofrecer y confirmar sigue el flujo normal (H-083: nada entra sin que el
cliente lo acepte).

Ejecutar:
    python manage.py test whatsapp_agent.tests.test_h089_upgrade_ambientacion
"""
import inspect

from django.test import SimpleTestCase

from whatsapp_agent import agent as agente_mod
from whatsapp_agent.agent import upgrade_por_extra

R1, R2 = 22, 23


def _item_servicio(servicio_id, nombre='X'):
    return {'tipo': 'servicio', 'servicio_id': servicio_id, 'nombre': nombre}


class UpgradePorExtraTest(SimpleTestCase):

    def test_el_caso_real_r1_mas_ramo_de_flores(self):
        carrito = [_item_servicio(99, 'Tina Hornopirén'), _item_servicio(R1, 'Ambientación R1')]
        up = upgrade_por_extra('y se puede incluir un ramo de flores?', carrito)
        self.assertIsNotNone(up)
        self.assertEqual(up['base_id'], R1)
        self.assertEqual(up['destino_id'], R2)
        # El índice tiene que apuntar a la R1, no a la tina.
        self.assertEqual(up['indice'], 1)

    def test_basta_con_decir_flores(self):
        up = upgrade_por_extra('quiero flores', [_item_servicio(R1)])
        self.assertEqual((up or {}).get('destino_id'), R2)

    def test_mayusculas_y_tildes_no_importan(self):
        for texto in ('RAMO DE FLORES', 'un Ramo', 'unas FLÖRES'):
            self.assertIsNotNone(upgrade_por_extra(texto, [_item_servicio(R1)]), texto)

    def test_otro_extra_no_dispara_el_upgrade(self):
        # Un jugo o unos chocolates NO vienen incluidos en la R2: siguen su camino.
        for texto in ('un jugo de frambuesa', 'chocolates', 'una tabla de quesos'):
            self.assertIsNone(upgrade_por_extra(texto, [_item_servicio(R1)]), texto)

    def test_sin_ambientacion_en_el_carrito_no_aplica(self):
        # Pide un ramo sin tener R1: no hay nada que "subir", va por su camino.
        self.assertIsNone(upgrade_por_extra('un ramo de flores', [_item_servicio(99)]))
        self.assertIsNone(upgrade_por_extra('un ramo de flores', []))
        self.assertIsNone(upgrade_por_extra('un ramo de flores', None))

    def test_si_ya_tiene_la_superior_no_hay_upgrade(self):
        # Con la R2 puesta el ramo YA está incluido: no se ofrece cambiar nada.
        self.assertIsNone(upgrade_por_extra('un ramo de flores', [_item_servicio(R2)]))

    def test_solo_mira_items_de_tipo_servicio(self):
        # Un producto que casualmente tenga ese id no debe confundirse con la R1.
        producto = {'tipo': 'producto', 'servicio_id': R1, 'producto_id': R1}
        self.assertIsNone(upgrade_por_extra('un ramo de flores', [producto]))

    def test_mensaje_vacio_no_dispara_nada(self):
        for texto in ('', None, '   '):
            self.assertIsNone(upgrade_por_extra(texto, [_item_servicio(R1)]), repr(texto))

    def test_item_corrupto_no_rompe(self):
        # servicio_id ausente o basura: se salta el ítem en vez de reventar.
        carrito = [{'tipo': 'servicio'}, {'tipo': 'servicio', 'servicio_id': 'abc'},
                   None, _item_servicio(R1)]
        up = upgrade_por_extra('un ramo', carrito)
        self.assertEqual((up or {}).get('base_id'), R1)


class UpgradeSeEvaluaAntesDeResolverTest(SimpleTestCase):
    """El orden importa, y ya nos mordió una vez.

    La primera versión chequeaba el upgrade DENTRO de "si el producto no resuelve".
    Cuando Jorge publicó el "Ramo de flores" (2026-08-01), el producto pasó a
    resolver → el chequeo dejó de ejecutarse y Luna habría vendido R1 + ramo
    ($70.000) en vez de ofrecer la R2 ($68.000). Un cambio de DATOS desactivó un
    fix de código en silencio.

    Se fija por inspección del fuente: el upgrade tiene que evaluarse ANTES del
    filtro `publicado_web` que resuelve el producto.
    """

    def _cuerpo_del_handler(self):
        fuente = inspect.getsource(agente_mod)
        ini = fuente.index("if name == 'agregar_producto_carrito'")
        fin = fuente.index("if name == 'ver_carrito'", ini)
        return fuente[ini:fin]

    def test_el_upgrade_va_antes_de_resolver_el_producto(self):
        cuerpo = self._cuerpo_del_handler()
        pos_upgrade = cuerpo.index('oferta_upgrade_ambientacion(')
        pos_resolucion = cuerpo.index('publicado_web=True')
        self.assertLess(
            pos_upgrade, pos_resolucion,
            'El upgrade debe evaluarse ANTES de resolver el producto: si no, publicar '
            'el extra suelto desactiva el fix sin que nadie se entere.')

    def test_no_quedo_duplicado_el_bloque(self):
        # Hubo un momento con dos copias (una inline y el helper): una sola fuente.
        self.assertEqual(
            inspect.getsource(agente_mod).count("'error': 'conviene_upgrade_ambientacion'"), 1)
