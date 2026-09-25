"""Luna busca el horario para canjear una gift card (P-52 paso 3, deploy 2b).

Jorge aprobó el flujo el 25-09-2026: el cliente manda la foto, Luna saluda y
pide el día (deploy 2a); cuando el cliente dice el día, Luna busca en la agenda
lo que INCLUYE esa gift card y ofrece una opción; si el cliente acepta, el caso
pasa a Deborah con el resumen, y ella crea la reserva y aplica la gift card con
el botón de la tarjeta. Luna nunca confirma.

Lo que incluye cada gift card no estaba en ninguna parte (la gift card solo
guarda un nombre y un monto): lo sabía Deborah de memoria. Las FICHAS salen de
los 111 canjes del último año y de lo que promete cada carta; la tabla se le
mandó a Deborah el 25-09 con 12 preguntas. Mientras no responda, cada ficha
cubre SOLO lo que dice la carta (por ejemplo, «Tina para 2» es sin
hidromasaje) y todo lo demás lo decide ella.

Las horas salen del mismo motor con que Luna vende (alternativas.py): lo que
se ofrece acá es lo que la agenda tiene libre.
"""
from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Encendido gradual (25-09-2026): con False, lo que el cliente escribe después
# de la bienvenida lo sigue viendo Deborah (deploy 2a) y este módulo solo corre
# en las pruebas con el modelo real. Se pasa a True —un deploy de una línea—
# cuando esa prueba salga bien y se haya visto la primera bienvenida real.
# Anotado en docs/PENDIENTES.md (P-52) para que no quede apagado sin querer.
LUNA_CONVERSA_EL_CANJE = False


@dataclass(frozen=True)
class Ficha:
    tipo: str                  # tipo del motor de alternativas
    personas: int              # las que cubre la gift card
    tinas: str = ''            # 'sin_hidro' | 'hidro' | 'cualquiera' | '' (lo decide el motor)
    dias: str = 'todos'        # 'todos' | 'dom_jue' | 'vie_sab'
    masaje: str = ''           # el masaje que cubre, si el tipo es masaje_solo
    agrega_deborah: str = ''   # lo que Deborah suma a mano (ambientación)
    acompanante_pagado: bool = False  # un masaje de 1: el de quien acompaña se paga


RELAJACION = 'Masaje Relajación o Descontracturante'

FICHAS = {
    # Tinas
    'tinas': Ficha('tina_sola', 2, tinas='sin_hidro'),
    'Tina hidromasaje 2 personas': Ficha('tina_sola', 2, tinas='hidro'),
    'tina_para_dos': Ficha('tina_sola', 2, tinas='cualquiera'),
    # Tina y masaje: el motor de la Pausa arma 1 tina + 2 masajes
    'pausa_junto_al_rio': Ficha('pausa', 2, tinas='sin_hidro'),
    'tinas_masajes_semana': Ficha('pausa', 2, tinas='sin_hidro', dias='dom_jue'),
    'tinas_masajes_finde': Ficha('pausa', 2, tinas='sin_hidro', dias='vie_sab'),
    'Tina Hidromasaje + masaje viernes-sabado': Ficha('pausa', 2, tinas='hidro', dias='vie_sab'),
    # Masajes
    'Masaje para 1 persona': Ficha('masaje_solo', 1, masaje=RELAJACION, acompanante_pagado=True),
    'masaje_pareja': Ficha('masaje_solo', 2, masaje=RELAJACION),
    'masaje_piedras': Ficha('masaje_solo', 1, masaje='Masaje Piedras Calientes'),
    'drenaje_linfatico': Ficha('masaje_solo', 1, masaje='Drenaje Linfatico'),
    'masaje_deportivo': Ficha('masaje_solo', 1, masaje='Masaje Deportivo'),
    # Noches en cabaña (cabaña + tina + desayuno)
    'noche_aguas_calientes': Ficha('noche_aguas_calientes', 2, tinas='sin_hidro'),
    'alojamiento_romantico': Ficha('noche_aguas_calientes', 2, tinas='sin_hidro',
                                   agrega_deborah='la ambientación romántica'),
    'alojamiento_semana': Ficha('noche_aguas_calientes', 2, tinas='sin_hidro', dias='dom_jue'),
    'alojamiento_finde': Ficha('noche_aguas_calientes', 2, tinas='sin_hidro', dias='vie_sab'),
    'ritual_del_rio': Ficha('ritual', 2),
    'refugio_aremko': Ficha('refugio', 2),
    # Veladas y celebraciones
    'tina_celebracion': Ficha('tina_sola', 2, tinas='sin_hidro', agrega_deborah='la ambientación'),
    'tina_cumpleanos': Ficha('tina_sola', 2, tinas='sin_hidro',
                             agrega_deborah='la ambientación de cumpleaños'),
}
for _nivel in ('simple', 'dulce', 'flores', 'gran'):
    FICHAS[f'velada_{_nivel}'] = Ficha('tina_sola', 2, tinas='sin_hidro',
                                       agrega_deborah='la ambientación de la velada')
    FICHAS[f'velada_{_nivel}_hidro'] = Ficha('tina_sola', 2, tinas='hidro',
                                             agrega_deborah='la ambientación de la velada')

# Python: lunes = 0 … domingo = 6.
DIAS_VALIDOS = {'todos': set(range(7)), 'dom_jue': {6, 0, 1, 2, 3}, 'vie_sab': {4, 5}}
DIAS_TEXTO = {'dom_jue': 'de domingo a jueves', 'vie_sab': 'viernes o sábado'}
TINAS_TEXTO = {'sin_hidro': 'tina sin hidromasaje', 'hidro': 'tina de hidromasaje',
               'cualquiera': 'cualquier tina'}
_MESES = ('enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto',
          'septiembre', 'octubre', 'noviembre', 'diciembre')
_DIAS_SEMANA = ('lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo')


def ficha_de(gc):
    """La ficha de esta gift card, o None si Luna no sabe qué incluye (monto
    libre, gift cards antiguas sin experiencia): esas las atiende Deborah."""
    return FICHAS.get((gc.servicio_asociado or '').strip())


def _sin_tildes(texto):
    return ''.join(c for c in unicodedata.normalize('NFKD', texto or '')
                   if not unicodedata.combining(c)).lower().strip()


def _es_hidro(nombre):
    return 'hidromasaje' in _sin_tildes(nombre)


def _es_tina(nombre):
    return _sin_tildes(nombre).startswith('tina')


def _es_cabana(nombre):
    return _sin_tildes(nombre).startswith('cabana')


def _es_masaje(nombre):
    # Ojo: «Tina HidroMASAJE» contiene «masaje» y es una tina.
    n = _sin_tildes(nombre)
    return not _es_tina(nombre) and ('masaje' in n or 'drenaje' in n)


def _cumple(ficha, itinerario):
    """¿Esta opción del motor es lo que cubre la gift card?"""
    for linea in itinerario:
        nombre = linea.get('servicio', '')
        if _es_tina(nombre):
            if ficha.tinas == 'sin_hidro' and _es_hidro(nombre):
                return False
            if ficha.tinas == 'hidro' and not _es_hidro(nombre):
                return False
        if ficha.masaje and _es_masaje(nombre) and _sin_tildes(nombre) != _sin_tildes(ficha.masaje):
            return False
    return True


def _hhmm_min(hora):
    m = re.match(r'^\s*(\d{1,2})[:.](\d{2})', str(hora or ''))
    return int(m.group(1)) * 60 + int(m.group(2)) if m else None


def _primera_hora(op):
    itin = op.get('itinerario') or []
    return (_hhmm_min(itin[0].get('hora')) if itin else None) or 0


def _elegir(opciones, hora_preferida):
    """UNA opción, con la regla de la casa de cuando Luna vende (H-081): la más
    barata y, a igual precio, la más tarde (deja el día libre). Si el cliente
    pidió una hora, la más cercana a esa hora."""
    if not opciones:
        return None
    pref = _hhmm_min(hora_preferida)
    if pref is not None:
        return min(opciones, key=lambda op: (abs(_primera_hora(op) - pref), -_primera_hora(op)))
    return min(opciones, key=lambda op: (op.get('precio_con_descuento') or 0,
                                         op.get('precio_total') or 0, -_primera_hora(op)))


def fecha_larga(fecha):
    return f'{_DIAS_SEMANA[fecha.weekday()]} {fecha.day} de {_MESES[fecha.month - 1]}'


def describir_ficha(ficha):
    """Qué incluye la gift card, en palabras (para el bloque del prompt)."""
    if ficha.tipo == 'tina_sola':
        que = f'1 {TINAS_TEXTO.get(ficha.tinas, "tina")} para {ficha.personas} personas, 2 horas'
    elif ficha.tipo == 'pausa':
        que = (f'1 {TINAS_TEXTO.get(ficha.tinas, "tina")} para 2 personas + 2 masajes de '
               'relajación (50 min)')
    elif ficha.tipo == 'masaje_solo':
        que = (f'{ficha.personas} {ficha.masaje.lower()} (50 min)' if ficha.personas > 1
               else f'1 {ficha.masaje.lower()} (50 min) para 1 persona')
    elif ficha.tipo == 'noche_aguas_calientes':
        que = f'1 noche en cabaña para 2 + {TINAS_TEXTO.get(ficha.tinas, "tina")} + desayuno'
    elif ficha.tipo == 'ritual':
        que = 'Ritual del Río: cabaña + tina + masaje en pareja + desayuno'
    elif ficha.tipo == 'refugio':
        que = 'Refugio: 2 noches en la misma cabaña + tinas + masaje en pareja + desayunos'
    else:
        que = ficha.tipo
    if ficha.dias in DIAS_TEXTO:
        que += f'; vale solo {DIAS_TEXTO[ficha.dias]}'
    if ficha.agrega_deborah:
        que += f'; {ficha.agrega_deborah} la agrega Deborah'
    return que


def _lineas_texto(itinerario, personas):
    partes = []
    for linea in itinerario:
        nombre, hora = linea.get('servicio', ''), linea.get('hora', '')
        if _es_cabana(nombre):
            partes.append(f'{nombre}, llegada {hora}' if nombre.endswith(')')
                          else f'{nombre} (llegada {hora})')
        elif _es_masaje(nombre) and personas > 1:
            partes.append(f'{personas} masajes a las {hora} ({nombre.lower()})')
        else:
            partes.append(f'{nombre} a las {hora}')
    return partes


def _con_desayuno(tipo):
    return tipo in ('noche_aguas_calientes', 'ritual', 'refugio')


def texto_opcion(ficha, fecha, itinerario, personas):
    partes = _lineas_texto(itinerario, personas)
    if not partes:
        return fecha_larga(fecha)
    cuerpo = partes[0] if len(partes) == 1 else ', '.join(partes[:-1]) + ' y ' + partes[-1]
    texto = f'{fecha_larga(fecha)}: {cuerpo}'
    if _con_desayuno(ficha.tipo):
        texto += ', con desayuno'
    return texto


def resumen_para_deborah(gc, ficha, fecha, itinerario, personas, diferencia=0):
    """Lo que Deborah ve en la bandeja para crear la reserva (máx. 200)."""
    from ventas.services.giftcard_envio import nombre_experiencia
    from ventas.services.giftcard_estado import pesos

    horas = ' + '.join(f"{l.get('servicio')} {l.get('hora')}" for l in itinerario)
    partes = ['Canje listo', nombre_experiencia(gc), f'código {gc.codigo}',
              f'{fecha:%d-%m-%Y}', horas, f'{personas} pers.']
    if diferencia:
        partes.append(f'el cliente paga {pesos(diferencia)} aparte')
    if ficha.agrega_deborah:
        partes.append(f'agregar {ficha.agrega_deborah}')
    texto = ' · '.join(partes)
    return texto if len(texto) <= 200 else texto[:199] + '…'


def _fallo(error, mensaje):
    return {'success': False, 'error': error, 'mensaje': mensaje}


def opcion_de_canje(gc, ficha, args, hoy=None):
    """Handler de la herramienta `horario_canje`. Nunca lanza."""
    from django.utils import timezone

    from . import alternativas as alternativas_mod
    from .availability import _parse_fecha, resolver_fecha

    args = args or {}
    hoy = hoy or timezone.localdate()
    r = resolver_fecha(str(args.get('fecha') or '').strip())
    if not r or r.get('error') or not r.get('fecha_iso'):
        return _fallo('fecha_invalida', (r or {}).get('error')
                      or 'No pude entender la fecha. Pregúntale al cliente qué día quiere venir.')
    if r.get('ambiguo'):
        return _fallo('fecha_ambigua', 'El día de la semana no calza con el número. Confirma la '
                                       'fecha con el cliente.')
    fecha = _parse_fecha(r['fecha_iso'])
    if fecha is None or fecha < hoy:
        return _fallo('fecha_pasada', 'Esa fecha ya pasó. Pregúntale por otro día.')
    if gc.fecha_vencimiento and fecha > gc.fecha_vencimiento:
        return _fallo('despues_del_vencimiento',
                      f'La gift card vence el {gc.fecha_vencimiento:%d-%m-%Y}. Pregúntale por un día '
                      'antes de esa fecha.')
    if fecha.weekday() not in DIAS_VALIDOS.get(ficha.dias, DIAS_VALIDOS['todos']):
        return _fallo('dia_no_incluido',
                      f'Esta gift card vale {DIAS_TEXTO[ficha.dias]}. Pregúntale por otro día; si '
                      'quiere venir igual ese día, deriva a Deborah.')

    try:
        personas = int(args.get('personas') or ficha.personas)
    except (TypeError, ValueError):
        personas = ficha.personas
    diferencia_por_persona = 0
    if personas != ficha.personas:
        if not (ficha.acompanante_pagado and personas == ficha.personas + 1):
            return _fallo('personas_distintas',
                          f'La gift card es para {ficha.personas} persona'
                          f"{'s' if ficha.personas > 1 else ''} y el cliente habla de {personas}. "
                          'Eso lo ve Deborah: deriva.')

    try:
        res = alternativas_mod.construir_alternativas(ficha.tipo, fecha.isoformat(), personas)
    except Exception as exc:  # noqa: BLE001
        logger.exception('[canje] el motor de horarios falló: %s', exc)
        return _fallo('motor', 'No pude revisar la agenda. Deriva a Deborah.')
    if res.get('error'):
        return _fallo('sin_horario', f"No pude revisar ese día: {res['error']}. Pregúntale por otro día.")
    opciones = [op for op in res.get('alternativas', []) if _cumple(ficha, op.get('itinerario', []))]
    op = _elegir(opciones, args.get('hora'))
    if op is None:
        return _fallo('sin_horario',
                      f'El {fecha_larga(fecha)} no queda horario para lo que incluye la gift card. '
                      'Pregúntale por otro día.')

    if personas > ficha.personas and ficha.tipo == 'masaje_solo':
        diferencia_por_persona = int(op['precio_total'] // personas) if personas else 0
    diferencia = diferencia_por_persona * (personas - ficha.personas)
    itinerario = op['itinerario']
    texto = texto_opcion(ficha, fecha, itinerario, personas)
    if diferencia:
        from ventas.services.giftcard_estado import pesos
        texto += f' (uno va con tu gift card y el otro se paga aparte: {pesos(diferencia)})'
    resumen = resumen_para_deborah(gc, ficha, fecha, itinerario, personas, diferencia)
    if args.get('confirmar'):
        return {'success': True, 'confirmado': True, 'resumen_para_deborah': resumen,
                'mensaje': 'Listo: el caso pasa a Deborah para crear la reserva.'}
    return {
        'success': True,
        'fecha': fecha.isoformat(),
        'dia_semana': _DIAS_SEMANA[fecha.weekday()],
        'opcion': texto,
        'diferencia_a_pagar': diferencia,
        'itinerario': itinerario,
        'mensaje': ('Ofrécele al cliente ESTA opción, tal cual y sin precio (la gift card ya '
                    'está pagada), y pregúntale si le acomoda. Si acepta, vuelve a llamar '
                    '`horario_canje` con la misma fecha y hora y `confirmar=true`.'),
    }


TOOL = {
    'type': 'function',
    'function': {
        'name': 'horario_canje',
        'description': (
            'Busca en la agenda el horario para usar la gift card que el cliente está '
            'canjeando (la del bloque CANJE DE GIFT CARD EN CURSO), con lo que esa gift card '
            'incluye. Devuelve UNA opción: ofrécela tal cual, SIN precio (la gift card ya está '
            'pagada). Si el cliente pide otra hora, vuelve a llamarla con `hora`. Cuando el '
            'cliente ACEPTE la opción, llámala otra vez con la misma fecha y hora y '
            '`confirmar=true`.'),
        'parameters': {
            'type': 'object',
            'properties': {
                'fecha': {'type': 'string',
                          'description': 'Fecha TAL CUAL la dijo el cliente ("el sábado", '
                                         '"27 de septiembre").'},
                'hora': {'type': 'string',
                         'description': 'Hora que prefiere el cliente (HH:MM), si la dijo.'},
                'personas': {'type': 'integer',
                             'description': 'SOLO si el cliente dijo que vienen más personas que '
                                            'las de la gift card.'},
                'confirmar': {'type': 'boolean',
                              'description': 'true SOLO cuando el cliente ya aceptó la opción.'},
            },
            'required': ['fecha'],
        },
    },
}


def bloque_para_luna(gc, ficha):
    """El bloque del prompt que le dice a Luna qué gift card se está canjeando."""
    from ventas.services.giftcard_envio import nombre_experiencia
    from ventas.services.giftcard_estado import estado_giftcard

    vence = f'{gc.fecha_vencimiento:%d-%m-%Y}' if gc.fecha_vencimiento else 'sin vencimiento'
    return (
        '## CANJE DE GIFT CARD EN CURSO (fuente de verdad)\n'
        f'El cliente está usando una gift card YA PAGADA: «{nombre_experiencia(gc)}» · '
        f'{estado_giftcard(gc).lower()} · vence {vence}.\n'
        f'Incluye: {describir_ficha(ficha)}.\n'
        'Reglas de este canje:\n'
        '- NO cotices ni vendas nada: no menciones precios, salvo la diferencia que te dé '
        '`horario_canje`.\n'
        '- Para ofrecer horario usa SIEMPRE `horario_canje` con el día que pide el cliente. '
        'Ofrece la opción que te devuelve, tal cual y una sola.\n'
        '- Si el cliente acepta, llama `horario_canje` con `confirmar=true`: el caso pasa a '
        'Deborah, que crea la reserva. NUNCA digas que la reserva quedó hecha.\n'
        '- Si pide algo que la gift card no incluye (otro servicio, hidromasaje cuando no '
        'corresponde, otro día de los permitidos, más personas) o algo que no sabes, responde '
        'solo con [ESCALAR: motivo].'
    )


# Con tilde a propósito: «te confirmé» afirma, «para que te confirme» no.
_RESERVA_HECHA = re.compile(
    r'\b(qued[oó]|est[aá]|dejé)\s+(reservad|agendad|confirmad|list)|'
    r'\bte\s+(reservé|agendé|confirmé)(?!\w)|'
    r'\breserva\s+(confirmada|hecha|lista)\b', re.IGNORECASE)


def afirma_reserva(texto):
    """¿El borrador dice que la reserva ya quedó? Solo Deborah confirma."""
    return bool(_RESERVA_HECHA.search(texto or ''))
