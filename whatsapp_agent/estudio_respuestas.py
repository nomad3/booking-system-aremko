# -*- coding: utf-8 -*-
"""Estudio de primeras respuestas (P-34): por qué el 52% recibe precio y se apaga.

Idea de Jorge (2026-08-18): «Algo les llamó la atención de las publicaciones y
nuestra primera respuesta no les invita a seguir una conversación. Deberíamos
estudiar tipos de respuestas a estas preguntas y ver cuáles generan mejores
resultados.»

Método (datos antes de construir): en vez de rediseñar el guion a ciegas, se
mide TODA la población con rasgos DETERMINISTAS (regex/conteos, sin LLM) sobre
la primera respuesta que incluyó un precio, y se compara:

  · Grupo MURIÓ  — conversaciones clasificadas `silencio_tras_info` (P-31):
    recibieron precio/info y no volvieron a escribir.
  · Grupo COTIZÓ — conversaciones que llegaron a una PropuestaReserva: el
    éxito de este escalón del embudo.

Si un rasgo (cerrar preguntando, ofrecer horarios concretos, largo, velocidad)
separa a los dos grupos, ese es el material del guion nuevo. La correlación no
prueba causa — el cliente decidido responde a cualquier cosa — por eso el
comando también imprime muestras REALES para leer, que es donde está el matiz.
"""
import re

PATRON_PRECIO = re.compile(r'\$\s?\d')
PATRON_HORARIO = re.compile(r'\b\d{1,2}:\d{2}\b')
LETRA_O_DIGITO = re.compile(r'[A-Za-zÁÉÍÓÚÜáéíóúüÑñ0-9]')


def termina_preguntando(texto):
    """True si después del ÚLTIMO signo de pregunta no hay más contenido real
    (emojis y puntuación de cierre no cuentan como contenido)."""
    t = (texto or '')
    idx = t.rfind('?')
    if idx == -1:
        return False
    return not LETRA_O_DIGITO.search(t[idx + 1:])


def rasgos_de_respuesta(texto):
    """Rasgos deterministas de UNA respuesta (los candidatos a explicar por
    qué una conversación siguió o murió)."""
    t = (texto or '').strip()
    return {
        'largo': len(t),
        'n_precios': len(PATRON_PRECIO.findall(t)),
        'menciona_horarios': bool(PATRON_HORARIO.search(t)),
        'tiene_link': 'http' in t.lower(),
        'tiene_pregunta': ('?' in t) or ('¿' in t),
        'termina_preguntando': termina_preguntando(t),
    }


def analizar_conversacion(mensajes):
    """Análisis de una conversación: la primera respuesta CON PRECIO y qué
    pasó después.

    `mensajes`: [(direction, body, timestamp)] ordenados por timestamp.
    Devuelve None si la conversación nunca recibió una respuesta con precio —
    ese subgrupo se cuenta aparte: morir SIN que te digan el precio es otro
    problema (fricción/demora), no un problema de guion.
    """
    respuesta = None
    ultimo_in_previo = None
    for i, (direction, body, ts) in enumerate(mensajes):
        if direction == 'out' and PATRON_PRECIO.search(body or ''):
            respuesta = (i, body, ts)
            break
        if direction == 'in':
            ultimo_in_previo = ts

    if respuesta is None:
        return None

    i, body, ts = respuesta
    despues = mensajes[i + 1:]
    n_in_despues = sum(1 for d, _, _ in despues if d == 'in')

    gap_seg = None
    if ultimo_in_previo is not None:
        gap_seg = max(0, (ts - ultimo_in_previo).total_seconds())

    analisis = rasgos_de_respuesta(body)
    analisis.update({
        'texto': body,
        'gap_seg': gap_seg,
        'respuesta_rapida': gap_seg is not None and gap_seg < 90,
        'cliente_respondio': n_in_despues > 0,
        'n_in_despues': n_in_despues,
    })
    return analisis


def _pct(parte, total):
    return round(100 * parte / total, 1) if total else 0.0


def resumen_grupo(analisis):
    """Agregados de una lista de análisis (los None ya vienen filtrados)."""
    n = len(analisis)
    if not n:
        return {'n': 0}
    con_gap = [a['gap_seg'] for a in analisis if a['gap_seg'] is not None]
    return {
        'n': n,
        'largo_promedio': round(sum(a['largo'] for a in analisis) / n),
        'pct_termina_preguntando': _pct(
            sum(1 for a in analisis if a['termina_preguntando']), n),
        'pct_tiene_pregunta': _pct(
            sum(1 for a in analisis if a['tiene_pregunta']), n),
        'pct_menciona_horarios': _pct(
            sum(1 for a in analisis if a['menciona_horarios']), n),
        'pct_tiene_link': _pct(sum(1 for a in analisis if a['tiene_link']), n),
        'pct_respuesta_rapida': _pct(
            sum(1 for a in analisis if a['respuesta_rapida']), n),
        'gap_mediano_seg': (sorted(con_gap)[len(con_gap) // 2]
                            if con_gap else None),
        'pct_cliente_respondio': _pct(
            sum(1 for a in analisis if a['cliente_respondio']), n),
        'promedio_precios_por_mensaje': round(
            sum(a['n_precios'] for a in analisis) / n, 1),
    }
