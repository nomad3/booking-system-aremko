"""Clasificador de correcciones del agente (H-010 parte 2).

Compara el borrador propuesto por el agente con lo que la persona realmente envió,
consulta el catálogo vivo, y clasifica la corrección para rutearla a su lugar:
- hecho_catalogo → cambio de precio/disponibilidad (lo aprueba Jorge; MVP: mostrar)
- regla → política → se agrega al Conocimiento del agente
- tono / puntual → no genera sugerencia (evita ruido)

Las funciones de prompt/parseo son puras (testeables sin DB/LLM).
"""

import json
import logging
import re
import unicodedata
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

# Qué correcciones de Deborah enseñan algo (encargo PROMPT_JEV_AREMKO.md, etapa 1).
# Va en código y no en un prompt: decide qué le cuesta plata al sistema y qué puede
# terminar tocando el Conocimiento. Los umbrales son deterministas.
LARGO_MINIMO = 40          # «ya», «te llamo»: ningún borrador habría ganado
PARECIDO_RETOQUE = 0.5     # desde aquí, Deborah retocó el borrador, no lo descartó
_RE_CIFRA = re.compile(r'\b\d{1,2}:\d{2}\b|\$\s?\d[\d.]*\d')


def _normalizado(texto):
    """Minúsculas, sin tildes y con los espacios colapsados. Pura."""
    t = unicodedata.normalize('NFD', (texto or '').lower())
    t = ''.join(c for c in t if unicodedata.category(c) != 'Mn')
    return re.sub(r'\s+', ' ', t).strip()


def _cifras(texto):
    return {c.replace(' ', '') for c in _RE_CIFRA.findall(texto or '')}


def grupo_de_la_correccion(borrador, enviado):
    """'vacio', 'corto', 'retoque_cifra', 'retoque_parecido' o 'sustantivo'. Pura.

    Los criterios del encargo, en su orden: los dos textos con algo; lo enviado de al
    menos 40 caracteres; si el borrador traía una hora o un precio y lo enviado repite
    alguna de esas cifras, Luna acertó (retoque); si se parecen ≥ 0,5, también es un
    retoque. Lo que queda es un desacuerdo sustantivo: Deborah descartó el borrador y
    escribió otra cosa con contenido. Medido el 25-09: 2.281 de 4.839 en 90 días."""
    if not (borrador or '').strip() or not (enviado or '').strip():
        return 'vacio'
    if len(enviado.strip()) < LARGO_MINIMO:
        return 'corto'
    cifras = _cifras(borrador)
    if cifras and cifras & _cifras(enviado):
        return 'retoque_cifra'
    if SequenceMatcher(None, _normalizado(borrador), _normalizado(enviado)).ratio() >= PARECIDO_RETOQUE:
        return 'retoque_parecido'
    return 'sustantivo'


def es_desacuerdo_sustantivo(borrador, enviado):
    """True si esta corrección enseña algo: Deborah descartó el borrador y escribió otra
    cosa con contenido. Pura."""
    return grupo_de_la_correccion(borrador, enviado) == 'sustantivo'


# Encargo JEV, etapa 3: el modelo de decisión (Jev) elige el tipo con su confianza; el
# texto propuesto lo sigue redactando el camino de siempre, y solo cuando vale la pena.
CONFIANZA_MINIMA = 0.70     # una decisión con 0,55 no es una decisión
PARECIDO_REPETIDA = 0.75    # desde aquí, dos reglas dicen lo mismo
PREGUNTAS_CORRECCION = {
    # Corrida en seco del 25-09-2026 (50 correcciones reales): con solo «¿qué cambió?», 8 de
    # 9 propuestas eran falsos «hecho_catalogo» —Deborah le ofreció a ESE cliente otra hora
    # u otra tina— y muchas «correcciones» no corregían nada: Deborah pasaba al paso
    # siguiente («me indica nombre, RUT, correo y ciudad»). Lo que manda es qué hizo ella.
    'que_hizo': {
        'type': 'choice',
        'instructions': ('Mira la conversación y compara lo que propuso el asistente con lo que '
                         'la persona del equipo realmente envió al cliente. ¿Qué hizo la persona?'),
        'criteria': {
            'corrigio_dato': ('Corrigió algo que el asistente dijo mal: un precio, qué incluye un '
                              'servicio, si algo existe o se vende, o una condición'),
            'avanzo_el_proceso': ('Dio el paso siguiente de la venta que el asistente no dio: pedir '
                                  'los datos para reservar, confirmar, o enviar el pago o los datos '
                                  'de transferencia'),
            'otra_opcion_para_ese_cliente': ('Le ofreció a ese cliente otra hora, otra tina, otra '
                                             'cabaña u otra combinación, según la disponibilidad '
                                             'de ese momento'),
            'otra_cosa': ('Respondió otra cosa, saludó, se despidió, o dijo lo mismo con otras '
                          'palabras'),
        },
    },
    'que_cambio': {
        'type': 'choice',
        'instructions': ('Compara el borrador que propuso el asistente con lo que la persona del '
                         'equipo realmente envió al cliente. ¿Qué cambió?'),
        'criteria': {
            'hecho_catalogo': ('Cambia un PRECIO del catálogo, o que un servicio o producto exista o '
                               'se venda. NO es esto ofrecerle a ese cliente otra hora, otra tina u '
                               'otra combinación'),
            'regla': ('Cambia una política o el cómo: qué ofrecer, qué no, condiciones, qué incluye '
                      'algo, cuándo pedir los datos o el pago'),
            'tono': 'La misma información, solo mejor redactada, más corta o más cálida',
            'puntual': ('Algo de ese cliente: otra hora, otra tina u otra combinación para él, un '
                        'saludo o un typo. No generaliza'),
        },
    },
    'generaliza': {
        'type': 'noul',
        'instructions': '¿Esta corrección aplicaría igual a otro cliente que preguntara lo mismo?',
    },
    # Junio de 2026: el clasificador propuso «enviar un link» 7 veces y se aprobó otra vez
    # lo que ya estaba. Lo que ya está en el Conocimiento no se vuelve a proponer.
    'ya_esta': {
        'type': 'noul',
        'instructions': '¿Lo que enseña esta corrección ya está dicho en el Conocimiento actual?',
    },
}
# Lo único que enseña: corregir un dato mal dicho o dar el paso de venta que Luna no dio.
ACCIONES_QUE_ENSENAN = {'corrigio_dato', 'avanzo_el_proceso'}
PISTAS_DE_REDACCION = {
    ('corrigio_dato', 'hecho_catalogo'): (
        'la persona corrigió un dato del catálogo que el asistente dijo mal (un precio, o que un '
        'servicio o producto exista). Describe el cambio en `texto_propuesto` y pon la referencia '
        'en `ref_catalogo`.'),
    ('corrigio_dato', 'regla'): (
        'la persona corrigió algo que el asistente dijo mal (qué incluye un servicio o una '
        'condición). En `texto_propuesto` escribe la regla GENERAL en una línea, no el caso.'),
    ('avanzo_el_proceso', 'regla'): (
        'la persona dio el paso siguiente de la venta que el asistente no dio (pedir los datos, '
        'confirmar o el pago). En `texto_propuesto` escribe como regla GENERAL, en una línea, '
        'cuándo y qué hacer; no describas este caso.'),
}


MENSAJES_DE_CONTEXTO = 6


def contexto_de_la_correccion(fb, mensajes=MENSAJES_DE_CONTEXTO):
    """La conversación hasta el mensaje del cliente que el borrador respondía, como texto
    «[Cliente]: … / [Aremko]: …», o '' si no se encuentra. Solo lectura.

    Probado en prod (25-09-2026): con solo el borrador y lo enviado, 3 de 5 correcciones
    reales quedaron «no concluyentes» (confianza 0,29-0,46). Sin la pregunta del cliente,
    «Los lunes cerramos a las 21:30» no se sabe si es una regla o una respuesta a ese
    cliente. El encargo lo advertía: con fragmentos la confianza cae; con contexto, sube."""
    from ventas.models import WhatsAppMessage

    try:
        entrante = (WhatsAppMessage.objects.filter(wa_message_id=fb.wa_message_id)
                    .only('phone', 'timestamp').first() if fb.wa_message_id else None)
        phone = entrante.phone if entrante else fb.phone
        hasta = entrante.timestamp if entrante else fb.created_at
        filas = list(WhatsAppMessage.objects.filter(phone=phone, timestamp__lte=hasta)
                     .exclude(msg_type='reaction').order_by('-timestamp')
                     .values_list('direction', 'body', 'msg_type')[:max(1, mensajes)])
    except Exception:  # noqa: BLE001 — sin contexto se clasifica igual, con menos confianza
        logger.exception('Aprendizaje: no se pudo armar el contexto del feedback %s', fb.pk)
        return ''
    lineas = []
    for direccion, cuerpo, tipo in reversed(filas):
        quien = 'Cliente' if direccion == 'in' else 'Aremko'
        texto = (cuerpo or '').strip().replace('\n', ' ')[:300] or f'({tipo})'
        lineas.append(f'[{quien}]: {texto}')
    return '\n'.join(lineas)


def _repetida(texto, conocimiento):
    """Qué dice lo mismo que `texto`: una línea del Conocimiento o una sugerencia anterior
    (pendiente, aprobada o descartada), o '' si nada. Una descartada tampoco se repite."""
    from .models import SugerenciaAprendizaje

    t = _normalizado(texto)
    if not t:
        return ''
    for linea in (conocimiento or '').splitlines():
        if linea.strip() and SequenceMatcher(None, t, _normalizado(linea)).ratio() >= PARECIDO_REPETIDA:
            return 'ya está en el Conocimiento'
    for s in SugerenciaAprendizaje.objects.exclude(texto_propuesto='').only(
            'id', 'estado', 'texto_propuesto'):
        if SequenceMatcher(None, t, _normalizado(s.texto_propuesto)).ratio() >= PARECIDO_REPETIDA:
            return f'repite la sugerencia #{s.id} ({s.estado})'
    return ''


def clasificar_con_jev(config, borrador, enviado, referencia='', contexto=''):
    """Como `clasificar()` —el mismo dict, más `confianza`—, pero el tipo lo decide Jev.

    - `contexto`: la conversación hasta la pregunta del cliente (`contexto_de_la_correccion`);
      sin ella Jev clasifica a ciegas y la confianza cae.
    - Jev sin opinión (None) → el clasificador de siempre, tal cual.
    - Manda «¿qué hizo la persona?» (`que_hizo`). Confianza < 0,70 → `error` «no
      concluyente»: queda sin procesar para una persona. Nunca «puntual» en silencio, que
      es el defecto que se arregla.
    - Otra opción para ese cliente u otra cosa → puntual, sin sugerencia. Solo enseñan
      «corrigió un dato» (catálogo si es un precio o que algo exista; si no, regla) y
      «avanzó el proceso» (regla), si generalizan y no están ya en el Conocimiento.
    - Si vale la pena, el texto lo redacta el camino de siempre; si repite una línea del
      Conocimiento o una sugerencia anterior, no se propone de nuevo.
    """
    from . import grounding
    from .decisiones import decidir

    base = {'tipo': 'puntual', 'texto_propuesto': '', 'ref_catalogo': '', 'motivo': '',
            'modelo': '', 'error': '', 'confianza': None}
    if (borrador or '').strip() == (enviado or '').strip():
        base['motivo'] = 'sin cambios'
        return base
    try:
        catalogo = grounding.catalogo_vivo()
    except Exception as exc:  # noqa: BLE001
        logger.exception('Aprendizaje: error armando catálogo: %s', exc)
        catalogo = '(catálogo no disponible)'
    estado = {'catalogo': catalogo, 'conocimiento': config.conocimiento or '',
              'borrador': borrador or '', 'enviado': enviado or ''}
    if contexto:
        estado['conversacion_hasta_la_pregunta'] = contexto
    r = decidir(estado, PREGUNTAS_CORRECCION, uso='aprendizaje.correccion',
                referencia=str(referencia or ''))
    if r is None:
        logger.warning('Aprendizaje: Jev sin opinión (feedback %s); va el clasificador de siempre',
                       referencia)
        return clasificar(config, borrador, enviado)

    que_hizo, confianza = r.opcion('que_hizo'), r.confianza('que_hizo')
    base.update(modelo=r.modelo or 'jev', confianza=confianza)
    opciones = PREGUNTAS_CORRECCION['que_hizo']['criteria']
    if que_hizo not in opciones or confianza is None or confianza < CONFIANZA_MINIMA:
        base['error'] = f'no concluyente: {que_hizo or "sin respuesta"} con confianza {confianza or 0:.2f}'
        return base
    if que_hizo not in ACCIONES_QUE_ENSENAN:
        base.update(tipo='puntual', motivo=f'{que_hizo} (confianza {confianza:.2f})')
        return base
    tipo = ('hecho_catalogo' if que_hizo == 'corrigio_dato'
            and r.opcion('que_cambio') == 'hecho_catalogo' else 'regla')
    base.update(tipo=tipo, motivo=f'{que_hizo} → {tipo} (confianza {confianza:.2f})')

    generaliza, ya_esta = r.si_no('generaliza'), r.si_no('ya_esta')
    if generaliza is not None and generaliza < 0.5:
        base.update(tipo='puntual', motivo=f'{tipo} que no generaliza (p={generaliza:.2f})')
        return base
    if ya_esta is not None and ya_esta >= 0.5:
        base.update(tipo='puntual', motivo=f'ya está en el Conocimiento (p={ya_esta:.2f})')
        return base

    # Jev decide; no escribe. La pista le dice al redactor qué se decidió.
    redaccion = clasificar(config, borrador, enviado, pista=PISTAS_DE_REDACCION[(que_hizo, tipo)])
    if redaccion.get('error'):
        base['error'] = redaccion['error']
        return base
    texto = (redaccion.get('texto_propuesto') or '').strip()
    if not texto:
        base['error'] = f'{tipo} sin texto propuesto: que lo mire una persona'
        return base
    repetida = _repetida(texto, config.conocimiento)
    if repetida:
        base.update(tipo='puntual', motivo=repetida[:300])
        return base
    base.update(texto_propuesto=texto[:1000],
                ref_catalogo=(redaccion.get('ref_catalogo') or '')[:200],
                motivo=f"{que_hizo}: {redaccion.get('motivo') or base['motivo']}"[:300],
                modelo=f"{r.modelo or 'jev'} + {redaccion.get('modelo', '')}"[:120])
    return base


TIPOS = {'hecho_catalogo', 'regla', 'tono', 'puntual'}
# Solo estos generan una sugerencia para aprobar (los demás son ruido).
TIPOS_ACCIONABLES = {'hecho_catalogo', 'regla'}

PROMPT_VERSION = 'clasif-f1-2026-06-14'


def build_clasificador_system(catalogo_texto, conocimiento):
    """System prompt del clasificador. Pura."""
    conocimiento = (conocimiento or '').strip() or '(sin reglas aún)'
    return f"""Eres un clasificador de correcciones del agente de Aremko Spa. Comparas lo que el
AGENTE PROPUSO (borrador) con lo que una PERSONA del equipo ENVIÓ (corregido) a un cliente.
Tu trabajo: entender QUÉ cambió y clasificar la corrección para aplicarla en el lugar correcto.

CATÁLOGO ACTUAL (precios y capacidad en vivo):
{catalogo_texto}

REGLAS/CONOCIMIENTO ACTUAL DEL AGENTE:
{conocimiento}

Clasifica la corrección en UNO de estos tipos:
- "hecho_catalogo": cambia un PRECIO, DISPONIBILIDAD o EXISTENCIA de un servicio/producto, y
  DIFIERE del catálogo de arriba (ej. el agente dijo $25.000 y se corrigió a $30.000). En
  `texto_propuesto` describe el cambio en una frase; en `ref_catalogo` pon "ítem · campo · valor".
- "regla": cambia el CÓMO o una POLÍTICA (qué se reserva online, qué ofrecer o no, condiciones,
  aclaraciones que aplican SIEMPRE). En `texto_propuesto` escribe la REGLA en UNA línea, lista
  para agregar al Conocimiento (general, no específica de un cliente).
- "tono": misma información, solo más cálida/breve/mejor redactada.
- "puntual": algo específico de ESE cliente, un saludo personalizado, o un typo. NO generaliza.

Responde SOLO un JSON válido, sin texto adicional ni explicaciones:
{{"tipo": "...", "texto_propuesto": "...", "ref_catalogo": "...", "motivo": "..."}}
Ante la duda entre regla y puntual, elige "puntual" (no ensuciar el Conocimiento)."""


def build_clasificador_user(borrador, enviado, pista=''):
    """User prompt del clasificador. Pura. `pista` (encargo JEV): lo que ya decidió el modelo
    de decisión, para que la redacción sea la regla general y no el caso; vacía = idéntico."""
    return (
        'BORRADOR (lo que propuso el agente):\n'
        f'«{(borrador or "").strip()}»\n\n'
        'ENVIADO (lo que la persona realmente mandó al cliente):\n'
        f'«{(enviado or "").strip()}»\n\n'
        + (f'NOTA: {pista}\n\n' if pista else '') +
        'Clasifica la corrección y responde solo el JSON.'
    )


def parse_clasificacion(texto):
    """Extrae y valida el JSON del clasificador. Pura. Devuelve dict normalizado."""
    crudo = (texto or '').strip()
    data = {}
    if crudo:
        # Tomar el primer bloque {...} por si el modelo agrega texto alrededor.
        m = re.search(r'\{.*\}', crudo, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group(0))
            except (ValueError, TypeError):
                data = {}
    tipo = str(data.get('tipo', '')).strip().lower()
    if tipo not in TIPOS:
        tipo = 'puntual'
    return {
        'tipo': tipo,
        'texto_propuesto': str(data.get('texto_propuesto', '')).strip()[:1000],
        'ref_catalogo': str(data.get('ref_catalogo', '')).strip()[:200],
        'motivo': str(data.get('motivo', '')).strip()[:300],
    }


def procesar_pendientes(limite=50, *, solo_sustantivos=False, en_seco=False, dias=None,
                        forzar_jev=False):
    """Clasifica el feedback editado sin procesar y crea las sugerencias accionables.

    Lo usan el comando `procesar_aprendizaje` y el endpoint (H-013). Idempotente:
    marca `procesado=True` salvo en error del LLM (para reintentar). Lote acotado.
    Devuelve {procesados, creadas, errores, detalle:[...]}.

    Encargo JEV, etapa 4 (sin argumentos, todo igual que antes):
    - `solo_sustantivos`: solo las correcciones que enseñan algo
      (`es_desacuerdo_sustantivo`), de la más reciente a la más antigua. Procesar las
      otras produce miles de «tono»/«puntual» y ninguna regla.
    - `dias`: solo las de los últimos N días (Jorge, 25-09-2026: 30).
    - `en_seco`: clasifica e informa, SIN crear sugerencias y SIN marcar procesado.
    - `forzar_jev`: usa Jev aunque el interruptor esté apagado (la corrida en seco que Jorge
      lee antes de prender nada).
    """
    from datetime import timedelta

    from django.utils import timezone

    from .agent import get_config
    from .models import AgenteFeedback, SugerenciaAprendizaje

    config = get_config()
    limite = max(1, int(limite or 50))
    pendientes = AgenteFeedback.objects.filter(editado=True, procesado=False)
    if dias:
        pendientes = pendientes.filter(created_at__gte=timezone.now() - timedelta(days=int(dias)))
    if solo_sustantivos:
        elegidos = []
        for fb in pendientes.order_by('-created_at').iterator(chunk_size=200):
            if es_desacuerdo_sustantivo(fb.borrador, fb.enviado):
                elegidos.append(fb)
                if len(elegidos) >= limite:
                    break
        pendientes = elegidos
    else:
        pendientes = list(pendientes.order_by('created_at')[:limite])
    procesados = creadas = errores = 0
    detalle = []
    # Encargo JEV: con el interruptor apagado, exactamente el camino de siempre.
    usar_jev = forzar_jev or bool(getattr(config, 'usar_jev_en_aprendizaje', False))
    for fb in pendientes:
        d = (clasificar_con_jev(config, fb.borrador, fb.enviado, referencia=fb.id,
                                contexto=contexto_de_la_correccion(fb)) if usar_jev
             else clasificar(config, fb.borrador, fb.enviado))
        fila = {'feedback_id': fb.id}
        if en_seco:
            fila.update(fecha=fb.created_at, borrador=(fb.borrador or '')[:220],
                        enviado=(fb.enviado or '')[:220], confianza=d.get('confianza'),
                        motivo=d.get('motivo', ''))
        if d.get('error'):
            errores += 1
            detalle.append(dict(fila, estado='error', error=d['error']))
            continue  # NO marcar procesado → se reintenta (o lo mira una persona)
        if d['tipo'] in TIPOS_ACCIONABLES:
            if not en_seco:
                SugerenciaAprendizaje.objects.create(
                    feedback=fb, phone=fb.phone, tipo=d['tipo'],
                    texto_propuesto=d['texto_propuesto'], ref_catalogo=d['ref_catalogo'],
                    motivo=d['motivo'], borrador=fb.borrador, enviado=fb.enviado,
                    modelo=d.get('modelo', ''),
                )
                logger.info('Aprendizaje: sugerencia %s del feedback %s', d['tipo'], fb.id)
            creadas += 1
            detalle.append(dict(fila, tipo=d['tipo'], texto=d['texto_propuesto'][:120]
                                if not en_seco else d['texto_propuesto']))
        else:
            detalle.append(dict(fila, tipo=d['tipo']))
        if not en_seco:
            fb.procesado = True
            fb.save(update_fields=['procesado'])
        procesados += 1
    logger.info('Aprendizaje: %s procesados, %s sugerencias, %s sin concluir o con error '
                '(en seco=%s, jev=%s)', procesados, creadas, errores, en_seco, usar_jev)
    return {'procesados': procesados, 'creadas': creadas, 'errores': errores, 'detalle': detalle}


def clasificar(config, borrador, enviado, pista=''):
    """Clasifica una corrección vía LLM. Devuelve dict (+'modelo','error'). No lanza."""
    from . import grounding
    from .agent import _modelo_efectivo

    base = {'tipo': 'puntual', 'texto_propuesto': '', 'ref_catalogo': '', 'motivo': '',
            'modelo': '', 'error': ''}

    if (borrador or '').strip() == (enviado or '').strip():
        base['motivo'] = 'sin cambios'
        return base

    try:
        catalogo = grounding.catalogo_vivo()
    except Exception as exc:  # noqa: BLE001
        logger.exception('Aprendizaje: error armando catálogo: %s', exc)
        catalogo = '(catálogo no disponible)'

    system = build_clasificador_system(catalogo, config.conocimiento)
    user = build_clasificador_user(borrador, enviado, pista)
    modelo = _modelo_efectivo(config)

    try:
        from destino_puerto_varas.services.llm.openrouter_provider import OpenRouterProvider
        resultado = OpenRouterProvider().generate(
            system_prompt=system, user_prompt=user, model=modelo,
            max_tokens=300, temperature=0.0,  # determinista para clasificar
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception('Aprendizaje: provider lanzó excepción: %s', exc)
        base['error'] = str(exc)[:200]
        return base

    if not resultado.ok:
        base['error'] = resultado.error[:200]
        base['modelo'] = modelo
        return base

    parsed = parse_clasificacion(resultado.text)
    parsed['modelo'] = modelo
    parsed['error'] = ''
    return parsed
