# -*- coding: utf-8 -*-
"""H-092: `external_id` no puede quedar sin asignar en el ejecutor de tools.

Caso real (2026-08-12, 14:08 en prod): un cliente con una cotización de gift card
preguntó *"puedo agregar un jugo natural?"*, eligió arándanos, y Luna derivó a una
persona con «no se pudo agregar el producto a la reserva existente». En el log:

    ERROR Agente WA: tool buscar_reservas_cliente falló:
    local variable 'external_id' referenced before assignment

La causa no era el catálogo ni el prompt: varias ramas de `_tool_executor_con_contexto`
hacían `external_id = phone if phone else ...` DENTRO de su propio `if`. Eso convierte
el nombre en local de toda la función, así que las ramas que solo lo leen reventaban
con UnboundLocalError — y con ellas, la venta.

El test es estático a propósito: el ejecutor es un closure con un LLM detrás, y lo que
falla acá es la forma del código, no su comportamiento en runtime.
"""
import ast

from django.test import SimpleTestCase

from whatsapp_agent import agent


def _nodo_del_ejecutor():
    # Se parsea el archivo entero (y no `inspect.getsource` de la función anidada)
    # para no pelear con la indentación del closure.
    with open(agent.__file__.replace('.pyc', '.py'), encoding='utf-8') as fh:
        arbol = ast.parse(fh.read())
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.FunctionDef) and nodo.name == '_tool_executor_con_contexto':
            return nodo
    raise AssertionError('No se encontró _tool_executor_con_contexto')


class ExternalIdSiempreLigadoTests(SimpleTestCase):

    def test_external_id_se_asigna_en_el_cuerpo_no_solo_dentro_de_ifs(self):
        """Debe existir una asignación a nivel del cuerpo de la función, de modo que
        toda rama que lo lea lo encuentre ligado."""
        cuerpo = _nodo_del_ejecutor().body
        asignado_arriba = any(
            isinstance(st, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == 'external_id' for t in st.targets)
            for st in cuerpo
        )
        self.assertTrue(
            asignado_arriba,
            'external_id debe asignarse en el cuerpo de _tool_executor_con_contexto. '
            'Si solo se asigna dentro de ramas `if`, las tools que únicamente lo leen '
            '(buscar_reservas_cliente, verificar_cliente) mueren con UnboundLocalError.')

    def test_ninguna_lectura_precede_a_la_primera_asignacion(self):
        """Red de seguridad por si alguien mueve la asignación hacia abajo: la primera
        aparición de `external_id` en la función tiene que ser una escritura."""
        nodo = _nodo_del_ejecutor()
        apariciones = sorted(
            (n.lineno, n.col_offset, isinstance(n.ctx, ast.Store))
            for n in ast.walk(nodo)
            if isinstance(n, ast.Name) and n.id == 'external_id'
        )
        self.assertTrue(apariciones, 'external_id desapareció del ejecutor')
        _, _, es_escritura = apariciones[0]
        self.assertTrue(
            es_escritura,
            'La primera mención de external_id en _tool_executor_con_contexto es una '
            'LECTURA. Cualquier tool que llegue ahí sin pasar por una rama que lo '
            'asigne va a reventar con UnboundLocalError (H-092).')
