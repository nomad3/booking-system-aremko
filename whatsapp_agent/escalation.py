"""Reglas de escalamiento y saneamiento de la salida del LLM (defensa en profundidad).

- pre_escalar(): heurística por palabras clave ANTES de gastar tokens. Atrapa los
  casos claros donde NO queremos que el agente conteste (pide humano, reclamo,
  sentimiento muy negativo). Defensa en profundidad junto al juicio del LLM.
- parse_escalada(): el LLM marca con un prefijo [ESCALAR: motivo] cuando él mismo
  decide derivar (ambigüedad, fuera de catálogo, baja confianza).
- sanear_salida(): trunca/limpia el texto del modelo (tope muy por debajo de los
  4096 chars de WhatsApp; colapsa saltos de línea).
"""

import re

MAX_SALIDA_CHARS = 1000

# Frases que fuerzan derivación a humano sin pasar por el LLM.
_PALABRAS_ESCALAR = (
    'hablar con una persona', 'hablar con alguien', 'hablar con un humano',
    'atencion humana', 'atención humana', 'una persona real', 'un ejecutivo',
    'con un humano', 'persona real',
    'reclamo', 'queja', 'estafa', 'estafr', 'fraude', 'demanda', 'denunc',
    'abogado', 'sernac', 'me robaron', 'pesimo', 'pésimo', 'verguenza',
    'vergüenza', 'nunca mas', 'nunca más', 'indignado', 'indignada',
)

_PREFIJO_ESCALAR = re.compile(r'^\s*\[?\s*escalar\s*[:\]]?\s*', re.IGNORECASE)


def pre_escalar(body):
    """Devuelve un motivo (str) si el mensaje debe escalar por heurística, o None."""
    texto = (body or '').lower()
    if not texto.strip():
        # Entrante vacío / solo media: que lo vea un humano.
        return 'mensaje sin texto (probable adjunto)'
    for frase in _PALABRAS_ESCALAR:
        if frase in texto:
            return f'palabra clave de escalamiento: "{frase}"'
    return None


def parse_escalada(texto):
    """Detecta si el LLM pidió escalar con el prefijo [ESCALAR: motivo].

    Devuelve (escalar: bool, motivo: str, texto_limpio: str).
    """
    crudo = (texto or '').strip()
    if not crudo:
        return False, '', ''
    # Aceptar "[ESCALAR: x]", "ESCALAR: x", "[ESCALAR]" al inicio.
    if re.match(r'^\s*\[?\s*escalar', crudo, re.IGNORECASE):
        sin_prefijo = _PREFIJO_ESCALAR.sub('', crudo)
        sin_prefijo = sin_prefijo.rstrip(']').strip()
        motivo = sin_prefijo[:180] or 'el agente decidió derivar a una persona'
        return True, motivo, ''
    return False, '', crudo


def sanear_salida(texto):
    """Limpia y acota el texto del modelo antes de exponerlo como borrador."""
    t = (texto or '').strip()
    if not t:
        return ''
    # Colapsar 3+ saltos de línea a 2.
    t = re.sub(r'\n{3,}', '\n\n', t)
    if len(t) > MAX_SALIDA_CHARS:
        t = t[:MAX_SALIDA_CHARS].rstrip() + '…'
    return t
