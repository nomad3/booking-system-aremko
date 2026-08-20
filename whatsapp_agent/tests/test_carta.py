# -*- coding: utf-8 -*-
"""Carta de precios para aperturas genéricas (P-34).

Lo que clava esta suite:

· El orden es SIEMPRE de menor a mayor precio — la escalera parte en lo más
  económico (tesis de Jorge: el que pregunta «¿precios?» necesita ver que se
  puede partir barato, no la vitrina premium).
· Los precios de servicios salen del catálogo vivo con los mismos filtros que
  el resto del prompt (publicado, activo, sin complementos) y la aritmética
  (tina ×2, cabaña ×capacidad) la hace Python, nunca el LLM.
· Sin carta (''), el prompt NO incluye el bloque 2b: comportamiento histórico.
· carta_de_precios() jamás lanza — ante error devuelve '' y Luna sigue.
"""
from django.test import TestCase

from ventas.models import CategoriaServicio, Servicio
from whatsapp_agent import prompt
from whatsapp_agent.carta import (construir_carta, carta_de_precios,
                                  PAUSA_DESDE)
from whatsapp_agent.packs import REFUGIO_PRECIO_PLANO, RITUAL_PRECIO_DOMJUE


class ConstruirCartaTest(TestCase):

    def test_ordena_de_menor_a_mayor(self):
        texto = construir_carta(masaje=40000, tina_simple=50000,
                                tina_hidro=60000, cabana=110000)
        lineas = [l for l in texto.splitlines() if l.startswith('✓')]
        self.assertEqual(len(lineas), 8)  # 4 sueltos + 4 experiencias
        self.assertIn('Masaje', lineas[0])          # $40.000 primero
        self.assertIn('$40.000', lineas[0])
        self.assertIn('Refugio', lineas[-1])        # $290.000 último
        self.assertIn('$290.000', lineas[-1])

    def test_desde_va_donde_corresponde(self):
        texto = construir_carta(masaje=40000, tina_simple=50000)
        self.assertIn('— $40.000', texto)           # masaje: precio único
        self.assertIn('— desde $50.000', texto)     # tina: hay variantes
        # Refugio es plano todos los días: sin «desde».
        self.assertIn(f'— ${REFUGIO_PRECIO_PLANO:,}'.replace(',', '.'), texto)

    def test_categoria_sin_servicios_se_omite(self):
        texto = construir_carta(masaje=None, tina_simple=50000)
        self.assertNotIn('Masaje', texto)
        # Las 4 experiencias van siempre (sus precios son de packs/constantes).
        for nombre in ('Pausa', 'Noche de Aguas', 'Ritual', 'Refugio'):
            self.assertIn(nombre, texto)

    def test_cierra_con_una_sola_pregunta(self):
        texto = construir_carta(masaje=40000)
        self.assertTrue(texto.rstrip().endswith('¿Cuál te gustaría ver con fecha y hora?'))
        self.assertEqual(texto.count('?'), 1)


class CartaDePreciosTest(TestCase):
    """La parte con BD: filtros y aritmética por tipo."""

    def _servicio(self, nombre, tipo, precio, cap_max=2, publicado=True,
                  activo=True):
        cat, _ = CategoriaServicio.objects.get_or_create(nombre='Spa')
        return Servicio.objects.create(
            nombre=nombre, tipo_servicio=tipo, precio_base=precio,
            duracion=120, categoria=cat, capacidad_minima=1,
            capacidad_maxima=cap_max, publicado_web=publicado, activo=activo)

    def test_tina_por_persona_se_multiplica_por_dos(self):
        self._servicio('Tina Hornopiren', 'tina', 25000)
        self._servicio('Tina Hidromasaje Llaima', 'tina', 30000)
        texto = carta_de_precios()
        self.assertIn('Tina caliente junto al río (2 horas, para 2) — desde $50.000', texto)
        self.assertIn('Tina con hidromasaje (2 horas, para 2) — desde $60.000', texto)

    def test_cabana_usa_precio_total_por_noche(self):
        # Mismo criterio que el catálogo del prompt: precio_base × capacidad
        # (mostrar el valor de 1 persona fue un bug real).
        self._servicio('Cabaña Laurel', 'cabana', 55000, cap_max=2)
        texto = carta_de_precios()
        self.assertIn('Cabaña boutique (noche para 2, desayuno incluido) — desde $110.000', texto)

    def test_toma_la_tina_mas_barata_como_desde(self):
        self._servicio('Tina Tronador', 'tina', 25000)
        self._servicio('Tina Puyehue', 'tina', 27000)
        self.assertIn('desde $50.000', carta_de_precios())

    def test_no_publicado_o_inactivo_queda_fuera(self):
        self._servicio('Tina Oculta', 'tina', 10000, publicado=False)
        self._servicio('Tina Apagada', 'tina', 12000, activo=False)
        texto = carta_de_precios()
        self.assertNotIn('$20.000', texto)
        self.assertNotIn('$24.000', texto)
        self.assertNotIn('Tina caliente junto al río', texto)  # no quedó ninguna

    def test_sin_catalogo_igual_lista_las_experiencias(self):
        texto = carta_de_precios()
        self.assertIn('Pausa junto al río', texto)
        self.assertIn(f'${PAUSA_DESDE:,}'.replace(',', '.'), texto)


class PromptConCartaTest(TestCase):

    def _sp(self, carta):
        return prompt.build_system_prompt(
            'Asistente Aremko.', 'SERVICIOS PUBLICADOS:\nTina',
            'https://www.aremko.cl/', fecha_hoy='2026-08-20 (jueves)',
            carta=carta)

    def test_con_carta_aparece_el_bloque_la_excepcion_y_el_ejemplo(self):
        sp = self._sp('CARTA-DE-PRUEBA-XYZ')
        self.assertIn('# 2b. CARTA DE PRECIOS', sp)
        self.assertIn('CARTA-DE-PRUEBA-XYZ', sp)
        self.assertIn('PROHIBIDO hacer preguntas de calificación antes', sp)
        # La excepción quedó escrita DENTRO de la regla de personas-primero.
        self.assertIn('salvo la APERTURA GENÉRICA cuando existe la CARTA', sp)
        # Y el few-shot enseña el caso (los ejemplos mandan más que las reglas).
        self.assertIn('Hola, precios porfa', sp)

    def test_sin_carta_no_hay_bloque_ni_ejemplo(self):
        # Si carta_de_precios() falló y vino vacía, el prompt NO debe apuntar
        # a una sección inexistente: ni bloque 2b ni el few-shot de la carta.
        sp = self._sp('')
        self.assertNotIn('# 2b.', sp)
        self.assertNotIn('envíala tal cual', sp)
        self.assertNotIn('Hola, precios porfa', sp)
