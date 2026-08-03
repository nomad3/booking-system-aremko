"""El Pase en la conversación de Luna.

Jorge armó un guion para Deborah (H-096): le manda El Pase apenas paga y lo
recorre con el cliente paso a paso — el QR, las claves de wifi, cómo llegar, la
comanda — y cada paso termina cuando el cliente dice "sí, lo veo". Funciona
porque hay una persona al otro lado leyendo al cliente y esperando su respuesta.

**Luna no puede hacer ese baile de cinco turnos.** Está documentado dos veces en
este mismo repo: H-085 (no encadena bien dos llamadas) y H-090 (narró un cambio
en vez de ejecutarlo, porque la instrucción vivía en el turno anterior). Pedirle
que sostenga un guion de cinco confirmaciones es pedirle exactamente lo que hace
mal. Así que acá el guion toma otra forma, con el mismo objetivo:

  1. **Todo el contenido en un solo mensaje**, incrustado por CÓDIGO en el
     resumen de la reserva. No depende de que el modelo se acuerde.
  2. **El empujón a abrirlo llega cuando el cliente pregunta.** Si pide la clave
     del wifi, cómo llegar o cómo pedir algo, la respuesta es su Pase. Ahí sí
     abre la pantalla, y es de a uno — igual que con Deborah, pero conducido por
     el cliente en vez de por el guion.

Ese punto 2 además tapa un hueco real: Luna **no tiene** los datos del wifi. Hoy
si se los piden, no puede responder.
"""
import re

# Lo que el cliente pregunta y El Pase ya responde. Sin tildes ni mayúsculas:
# el mensaje se normaliza antes de comparar.
_TEMAS = {
    'wifi': (r'\bwi-?fi\b', r'\bclave[s]?\b.*\b(internet|red|wifi)\b',
             r'\b(internet|conexion)\b'),
    'llegar': (r'\bcomo\s+(llego|llegar|se\s+llega)\b', r'\bubicacion\b',
               r'\bdirecci[o]n\b', r'\bmapa\b', r'\bwaze\b',
               r'\bd[o]nde\s+(est[a]n?|queda|es)\b'),
    'pedir': (r'\b(comanda|carta|men[u])\b',
              r'\bc[o]mo\s+(pido|pedir|encargo)\b',
              r'\bpedir\s+(algo|comida|tabla|jugo)'),
}


def _normalizar(texto):
    """Minúsculas y sin tildes, para no escribir cada patrón cuatro veces."""
    t = (texto or '').lower()
    for a, b in (('á', 'a'), ('é', 'e'), ('í', 'i'), ('ó', 'o'), ('ú', 'u'), ('ü', 'u')):
        t = t.replace(a, b)
    return t


def tema_del_pase(mensaje):
    """'wifi' | 'llegar' | 'pedir' | None — qué está preguntando el cliente.

    Función PURA. Devuelve None ante la duda: agregar el link de más es ruido,
    pero cambiar de tema por un falso positivo es peor.
    """
    t = _normalizar(mensaje)
    if not t.strip():
        return None
    for tema, patrones in _TEMAS.items():
        if any(re.search(p, t) for p in patrones):
            return tema
    return None


# Una frase por tema: responde lo que preguntó y de paso le enseña dónde vive.
# Nada de listar las cuatro cosas cada vez — eso es el mensaje del resumen, acá
# se responde UNA pregunta (misma disciplina que H-088).
_RESPUESTAS = {
    'wifi': 'Las claves de wifi de cada sector están en tu Pase, en la sección '
            '*Tips*: {url}',
    'llegar': 'En tu Pase tienes el botón que abre el mapa directo: {url}',
    'pedir': 'Puedes pedir desde tu tina o cabaña con la *comanda digital* de tu '
             'Pase, sin moverte: {url}',
}


def respuesta_del_pase(tema, url):
    """El texto que se le suma a la respuesta, o '' si no aplica."""
    plantilla = _RESPUESTAS.get(tema)
    if not plantilla or not url:
        return ''
    return plantilla.format(url=url)


def bloque_resumen(url, tiene_masaje=False):
    """El Pase dentro del resumen que recibe el cliente al reservar.

    Es la versión comprimida del guion de Deborah: mismo contenido, un solo
    mensaje. Cierra pidiendo que lo guarde —darle un TRABAJO— en vez de
    describirlo, que era justamente por qué nadie lo abría.
    """
    if not url:
        return ''
    lineas = [
        '━━━━━━━━━━━━━━━',
        '🔑 *Tu Pase para Aremko*',
        url,
        '',
        'Adentro encuentras:',
        '🎫 El código QR que muestras al llegar',
        '📶 Las claves de wifi',
        '📍 Cómo llegar',
        '🛎️ La comanda, para pedir desde tu tina sin moverte',
    ]
    if tiene_masaje:
        # El paso que más rinde del guion de Deborah: la ficha llega llena y El
        # Pase entra al teléfono de una segunda persona.
        lineas.append('💆 La ficha de bienestar — compártela con tu acompañante '
                      'para que la complete antes de venir')
    lineas += ['', 'Guárdalo, lo vas a necesitar al llegar.']
    return '\n'.join(lineas)
