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


_UUID_RE = r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}'


def _quitar_ids_internos(t):
    """Quita el propuesta_id (UUID) que el modelo a veces filtra al cliente.
    El `propuesta_id` es interno (lo usan Deborah/aremko-cli), NO va en el mensaje al cliente.
    Determinístico en código porque la regla de prompt no siempre se respeta."""
    # "(con la )?propuesta( ID|n.°)? : <uuid>"  y  "ID: <uuid>"
    t = re.sub(r'(?i)\b(con\s+(la\s+)?)?propuesta\s*(id|n[°ºo.]*)?\s*:?\s*' + _UUID_RE, '', t)
    t = re.sub(r'(?i)\bid\s*:?\s*' + _UUID_RE, '', t)
    t = re.sub(_UUID_RE, '', t)  # cualquier UUID suelto restante
    # Limpiar lo que pudo quedar huérfano al sacar el ID.
    t = re.sub(r'\(\s*\)', '', t)          # paréntesis vacíos "()"
    t = re.sub(r'[ \t]{2,}', ' ', t)       # espacios dobles
    t = re.sub(r'\s+([.,;:])', r'\1', t)   # espacio antes de puntuación
    t = re.sub(r',\s*([.;:])', r'\1', t)   # ", ." → "."
    return t


_DIAS_CANON = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']
_MESES_NUM = {
    'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6,
    'julio': 7, 'agosto': 8, 'septiembre': 9, 'setiembre': 9, 'octubre': 10,
    'noviembre': 11, 'diciembre': 12,
}


def _sin_acento(s):
    return (s.lower()
            .replace('á', 'a').replace('é', 'e').replace('í', 'i')
            .replace('ó', 'o').replace('ú', 'u'))


# "sábado 28 de junio", "el domingo 28 de junio de 2026"
_DIA_FECHA_RE = re.compile(
    r'(?i)\b(lunes|martes|mi[ée]rcoles|jueves|viernes|s[áa]bado|domingo)\b'
    r'(\s+el)?\s+(\d{1,2})\s+de\s+'
    r'(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre)'
    r'(?:\s+de\s+(\d{4}))?'
)


def _corregir_dia_semana(t):
    """Corrige el nombre del día cuando NO calza con la fecha (N de mes).

    El LLM a veces escribe "mañana, sábado 28 de junio" cuando el 28 es domingo:
    mezcla el día de hoy con la fecha de mañana. El número+mes es el ancla real
    (lo que el cliente/staff usan para agendar), así que recalculamos el día en
    código y reemplazamos solo el nombre del día si está mal. Determinístico
    porque la regla de prompt ("usa el dia_semana de la herramienta") no siempre
    se respeta — y un día mal puesto genera overbooking.
    """
    from datetime import date as _date
    try:
        from django.utils import timezone
        hoy = timezone.localtime(timezone.now()).date()
    except Exception:  # noqa: BLE001
        hoy = _date.today()

    def _fix(m):
        dia_txt, _el, num_txt, mes_txt, anio_txt = m.groups()
        try:
            num = int(num_txt)
            mes = _MESES_NUM[_sin_acento(mes_txt)]
            anio = int(anio_txt) if anio_txt else hoy.year
            try:
                f = _date(anio, mes, num)
            except ValueError:
                return m.group(0)  # fecha inválida (ej. 31 de febrero): no tocar
            # Sin año explícito y la fecha ya pasó → asumir el próximo año (igual que resolver_fecha)
            if not anio_txt and f < hoy:
                f = _date(hoy.year + 1, mes, num)
            correcto = _DIAS_CANON[f.weekday()]
            if _sin_acento(correcto) == _sin_acento(dia_txt):
                return m.group(0)  # ya está bien
            # Preservar mayúscula inicial del día original
            reemplazo = correcto.capitalize() if dia_txt[:1].isupper() else correcto
            return m.group(0).replace(dia_txt, reemplazo, 1)
        except Exception:  # noqa: BLE001 — nunca tumbar el borrador por esto
            return m.group(0)

    return _DIA_FECHA_RE.sub(_fix, t)


# H-045 (2026-07-22): caso real — Luna agregó un masaje al carrito con ÉXITO (la tool devolvió
# success=true, quedó en el carrito con el precio y descuento correctos) y aun así le dijo al
# cliente "hubo un problema... no está disponible". No fue un error del sistema (el campo `error`
# de la sugerencia quedó vacío, no corrió ningún chequeo de disponibilidad) — fue el modelo
# perdiendo el hilo en un turno con contexto muy largo (58k tokens, varias tools encadenadas).
# Mientras un humano revisa cada borrador esto lo detecta una lectura atenta; el día que se manden
# solas, nadie lo agarra y se pierde una venta. Esta guardia es la versión en código de esa
# lectura atenta: si el texto suena a fracaso PERO alguna tool que mutó el carrito/propuesta en
# el mismo turno tuvo éxito, es una contradicción — no se manda, se escala a humano.
TOOLS_MUTAN_CARRITO = (
    'confirmar_reserva_carrito', 'confirmar_ritual', 'confirmar_refugio',
    'agregar_servicio_carrito', 'agregar_producto_carrito',
    # También crea una propuesta real: un texto que suene a fracaso encima de
    # una gift card ya propuesta es la misma contradicción que con el carrito.
    'preparar_giftcard',
)
_PATRON_CONTRADICCION = re.compile(
    r'hubo un problema|no se pudo|no logr[ée]|no logramos|no fue posible|'
    r'no est[aá] disponible|no hab[ií]a disponibilidad',
    re.IGNORECASE,
)


def tool_result_ok(res):
    """True si el resultado de una tool fue exitoso (sin error, success no-False)."""
    return isinstance(res, dict) and not res.get('error') and res.get('success', True) is not False


def hay_contradiccion_exito_vs_texto(texto, tool_calls_executed):
    """True si el texto final suena a fracaso pero alguna tool que mutó el carrito/propuesta en
    este mismo turno devolvió éxito (H-045). No identifica LA causa de la alucinación, solo evita
    que llegue al cliente sin que un humano la vea primero."""
    if not _PATRON_CONTRADICCION.search(texto or ''):
        return False
    return any(
        tc.get('name') in TOOLS_MUTAN_CARRITO and tool_result_ok(tc.get('result'))
        for tc in (tool_calls_executed or [])
    )


# H-090: el espejo del guardia anterior. Ahí el texto negaba una tool exitosa; acá
# AFIRMA una acción que NINGUNA tool hizo. Caso real (Jorge 2026-08-01): tras
# aceptar cambiar la R1 por la R2, Luna escribió "La Ambientación romántica R2 ha
# sido agregada a tu carrito" sin haber llamado una sola herramienta — el carrito
# seguía con la R1. Si nadie mira el panel, Deborah manda una cotización que NO
# coincide con lo que el cliente cree que aceptó.
# La TILDE es la que decide, y no es un detalle: "agregué" (lo hice) vs "agregue"
# (subjuntivo: "¿quieres que la agregue?"). Sin exigirla, la red escalaba una de las
# frases más comunes de Luna — lo cazó su propio test.
_PATRON_AFIRMA_MUTACION = re.compile(
    r'\b(ha sido|han sido|fue|fueron|qued[óo]|quedaron)\s+'
    r'(agregad|a[ñn]adid|sumad|incorporad|cambiad|actualizad|quitad|eliminad)|'
    r'\b(agregué|añadí|anadí|sumé|cambié|actualicé|quité|eliminé)\b|'
    r'\b(agregad|a[ñn]adid|sumad|cambiad)[oa]s?\s+(a|en)\s+tu\s+(carrito|reserva)',
    re.IGNORECASE,
)


def afirma_mutacion_sin_tool(texto, tool_calls_executed):
    """True si el texto dice que algo se agregó/cambió pero ninguna tool lo hizo.

    Solo dispara cuando NINGUNA tool que muta el carrito corrió con éxito en este
    turno: si alguna sí corrió, la afirmación es legítima y no se toca. Es una red
    de seguridad, no un detector de intenciones — ante la duda, deja pasar.
    """
    if not _PATRON_AFIRMA_MUTACION.search(texto or ''):
        return False
    hubo_mutacion = any(
        tc.get('name') in TOOLS_MUTAN_CARRITO and tool_result_ok(tc.get('result'))
        for tc in (tool_calls_executed or [])
    )
    return not hubo_mutacion


def sanear_salida(texto):
    """Limpia y acota el texto del modelo antes de exponerlo como borrador."""
    t = (texto or '').strip()
    if not t:
        return ''
    # Quitar IDs internos (propuesta_id) que el modelo a veces copia al mensaje.
    t = _quitar_ids_internos(t)
    # Corregir día de la semana que no calza con la fecha (evita overbooking).
    t = _corregir_dia_semana(t)
    # Colapsar 3+ saltos de línea a 2.
    t = re.sub(r'\n{3,}', '\n\n', t)
    if len(t) > MAX_SALIDA_CHARS:
        t = t[:MAX_SALIDA_CHARS].rstrip() + '…'
    return t.strip()
