# -*- coding: utf-8 -*-
"""De qué hablan las conversaciones que NUNCA llegaron a cotización (P-31).

El embudo dice DÓNDE se pierde la venta; esto dice POR QUÉ. Medido el
2026-08-18 sobre 60 días de WhatsApp:

  · 1.911 teléfonos escribieron · 257 recibieron cotización · **1.655 no**
  · de los que no: 330 mandaron 1 mensaje, 359 mandaron 2-3, **966 mandaron 4+**
  · y **solo 2** quedaron sin respuesta nuestra

Ese último número es el que ordena el trabajo: la explicación barata («no
alcanzamos a contestar») está descartada. Contestamos, el cliente conversa
—966 con cuatro mensajes o más— y aun así no sale cotización. Eso no se
averigua contando: hay que leer lo que dicen.

Decisiones de diseño:

· **Se clasifica una vez y se guarda.** Cuesta plata y no cambia solo. Se
  rehace únicamente si llegaron mensajes nuevos (`ultimo_mensaje_visto`).
· **Se manda el ARRANQUE de la conversación, no toda.** La intención se
  declara en los primeros mensajes; mandar cien turnos multiplica el costo sin
  mejorar la etiqueta.
· **Temperatura 0 y taxonomía cerrada**, con `otro` obligado a explicarse. Si
  `otro` crece, la taxonomía está mal — es el termómetro del propio diseño.
· **Nunca lanza.** Un error de red deja esa conversación sin clasificar y el
  lote sigue: un análisis a medias sirve, un comando caído no.
"""
import json
import logging
import time

from whatsapp_agent.models import TemaConversacion

logger = logging.getLogger(__name__)

# Cuántos mensajes del arranque se mandan y cuánto se recorta cada uno. Con 20
# turnos de 300 caracteres alcanza para entender de qué se trata y el costo por
# conversación queda acotado y predecible.
MAX_MENSAJES = 20
MAX_CARACTERES = 300

TEMAS_VALIDOS = {t for t, _ in TemaConversacion.TEMA_CHOICES}
CONFIANZAS_VALIDAS = {c for c, _ in TemaConversacion.CONFIANZA_CHOICES}

# Sube cuando cambian las categorías. Las filas etiquetadas con una versión
# vieja se rehacen solas: mezclar dos taxonomías en el mismo conteo da un
# número que no significa nada, y mirándolo no se nota.
VERSION_TAXONOMIA = 2

SYSTEM = """Eres analista de un spa boutique en Puerto Varas, Chile (Aremko: \
tinas calientes, cabañas, masajes junto al río).

Vas a leer el ARRANQUE de una conversación de WhatsApp que NO terminó en \
reserva. Tu trabajo es decir por qué, eligiendo UNA categoría.

Categorías (usá el código exacto):
- dijo_que_pagaba: quedó de transferir o pagar y no lo hizo.
- freno_en_los_datos: se le pidió un dato para cotizar (nombre, correo, RUT, \
cantidad de personas) y desapareció ahí.
- lo_iba_a_pensar: dijo explícitamente que lo consultaba, lo pensaba o avisaba, y no volvió.
- silencio_tras_info: se le pasó precio, fotos, cupo o link, y dejó de responder \
sin decir nada.
- sin_cupo: quería una fecha u hora que no estaba disponible.
- reserva_existente: ya tenía reserva; consulta cambios, atrasos, cómo llegar o qué incluye.
- info_general: pregunta suelta (ubicación, horarios, formas de pago) sin intención de compra.
- no_ofrecemos: pidió algo que el spa no vende o ya no tiene.
- postventa: reclamo, comentario o agradecimiento DESPUÉS de haber ido.
- no_es_cliente: proveedor, vendedor, número equivocado o spam.
- otro: no calza en ninguna. SOLO si de verdad no calza.

ORDEN DE PRIORIDAD cuando más de una podría aplicar — elegí la que esté MÁS \
CERCA del cierre, porque es la que más caro sale perder:
1º dijo_que_pagaba · 2º freno_en_los_datos · 3º lo_iba_a_pensar · 4º silencio_tras_info

Devolvé JSON y NADA más:
{"tema": "<código>", "motivo": "<máx 15 palabras, en español de Chile>", "confianza": "alta|media|baja"}

Reglas:
- "motivo" describe ESTA conversación en concreto, no repite el nombre de la categoría.
- La diferencia entre lo_iba_a_pensar y silencio_tras_info es si el cliente DIJO \
algo antes de desaparecer o simplemente dejó de contestar.
- Si el cliente nunca dijo qué quería, es info_general con confianza baja, no otro.
- Nunca inventes datos que no estén en los mensajes."""


def texto_de_conversacion(mensajes):
    """Los mensajes al formato que lee el modelo: '[cliente]' / '[aremko]'."""
    lineas = []
    for m in mensajes[:MAX_MENSAJES]:
        quien = 'cliente' if m.direction == 'in' else 'aremko'
        cuerpo = (m.body or '').strip().replace('\n', ' ')
        if not cuerpo:
            cuerpo = f'({m.msg_type or "adjunto"})'
        lineas.append(f'[{quien}] {cuerpo[:MAX_CARACTERES]}')
    return '\n'.join(lineas)


def interpretar_respuesta(crudo):
    """El JSON del modelo → (tema, motivo, confianza), saneado.

    Un modelo puede devolver el JSON envuelto en ```json, una categoría que no
    existe o texto suelto. Nada de eso puede tumbar el lote: lo que no se
    entiende cae en 'otro' con confianza baja, que además lo deja visible en el
    informe en vez de esconderlo.
    """
    texto = (crudo or '').strip()
    if texto.startswith('```'):
        texto = texto.split('```')[1] if '```' in texto[3:] else texto[3:]
        texto = texto.lstrip('json').strip()
    try:
        datos = json.loads(texto[texto.index('{'):texto.rindex('}') + 1])
    except (ValueError, TypeError):
        return 'otro', 'respuesta del modelo ilegible', 'baja'

    tema = str(datos.get('tema', '')).strip()
    if tema not in TEMAS_VALIDOS:
        return 'otro', f'categoría desconocida: {tema[:40]}', 'baja'
    confianza = str(datos.get('confianza', '')).strip().lower()
    if confianza not in CONFIANZAS_VALIDAS:
        confianza = 'media'
    return tema, str(datos.get('motivo', ''))[:200], confianza


def _modelo():
    from whatsapp_agent.agent import _modelo_efectivo
    from whatsapp_agent.models import WhatsAppAgentConfig
    try:
        return _modelo_efectivo(WhatsAppAgentConfig.get_solo())
    except Exception:  # noqa: BLE001 — el default del proveedor sirve igual
        return None


# Marca los intentos que fallaron por el proveedor y NO por el contenido. Se
# guardan igual —para no perder el rastro— pero el comando los vuelve a tomar.
MOTIVO_FALLA_TECNICA = 'falló la llamada al modelo'
INTENTOS = 2


def _una_llamada(generar, mensajes, modelo):
    """(crudo, error). `error` no vacío = falló la llamada, no el contenido."""
    try:
        r = generar(SYSTEM, texto_de_conversacion(mensajes), modelo)
    except Exception as e:  # noqa: BLE001 — una caída no puede matar el lote
        return '', str(e)[:120]
    # LLMResult nunca lanza: informa el problema en `.error` y deja `.text`
    # vacío. Sin mirar ese campo, un 429 o un timeout se guardaba como si el
    # modelo hubiera contestado cualquier cosa — y como quedaba «clasificada»,
    # no se reintentaba nunca. En el lote de prueba fueron 3 de 25.
    error = (getattr(r, 'error', '') or '').strip()
    crudo = (getattr(r, 'content', None) or getattr(r, 'text', None) or '').strip()
    if error:
        return '', error[:120]
    if not crudo:
        return '', 'el modelo devolvió una respuesta vacía'
    return crudo, ''


def clasificar_conversacion(mensajes, generar=None):
    """(tema, motivo, confianza, modelo) para UNA conversación. No lanza.

    Devuelve None si la llamada falló las dos veces: esa conversación queda sin
    clasificar y el comando la vuelve a tomar. Distinto de que el modelo haya
    contestado algo ilegible, que sí es información y se guarda como 'otro'.
    """
    if generar is None:
        from destino_puerto_varas.services.llm.openrouter_provider import OpenRouterProvider
        proveedor = OpenRouterProvider()

        def generar(system, user, model):
            return proveedor.generate(system_prompt=system, user_prompt=user,
                                      model=model, temperature=0)

    modelo = _modelo()
    for intento in range(INTENTOS):
        crudo, error = _una_llamada(generar, mensajes, modelo)
        if not error:
            tema, motivo, confianza = interpretar_respuesta(crudo)
            return tema, motivo, confianza, (modelo or '')
        logger.warning('[temas] intento %s falló: %s', intento + 1, error)
        if intento + 1 < INTENTOS:
            time.sleep(2)  # un respiro: casi siempre es límite de tasa
    return None
