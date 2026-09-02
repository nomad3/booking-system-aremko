"""
Builders de "alternativas de horario" unificadas para el botón de la bandeja (H-061).

Generaliza el endpoint de Pausa (H-059) a los otros casos. El botón de la bandeja
(aremko-cli) manda `tipo + fecha + personas` y recibe una lista de alternativas
concretas, cada una con un `texto_sugerido` listo para pegar en el borrador — sin
depender de que Luna interprete "¿más tarde?".

FASE 1: pausa, tina_sola, masaje_solo, noche_aguas_calientes.
FASE 2 (2026-07-13): ritual, refugio. Ambos tienen precio FIJO (Ritual $210k
dom-jue / $240k vie-sáb; Refugio $290k plano) e itinerario armado por
packs.disponibilidad_ritual/refugio; la dimensión "horario" que varía es el
SLOT DE MASAJE (uno de los 4 del Programa 15:30/18:00/20:30/21:45 que esté
libre) — cada slot libre es una alternativa, con la misma cabaña+tina y el
mismo precio. Refugio: masaje solo la primera noche.

Shape unificado de cada alternativa:
  {
    "titulo": "Tina Hidromasaje Llaima · 18:00",   # etiqueta del botón
    "precio_total": 60000,                          # int CLP, sin descuento
    "precio_con_descuento": 60000,                  # int CLP, tras pack (== total si no hay)
    "hay_descuento": false,
    "texto_sugerido": "Tina ... a las 18:00 hrs para 2 personas, $60.000.",
    "itinerario": [{"servicio": "Tina ...", "hora": "18:00", "servicio_id": 12}]
                                                # 1..N líneas; servicio_id solo
                                                # en las que se agendan
  }

Nota de negocio (confirmada por Jorge 2026-07-06):
- Masaje: 1 persona = 1 masaje, 2 personas = 2 masajes (mismo horario). El precio
  es `precio_por_persona × personas`; la disponibilidad del slot se mira a nivel
  de 1 masajista (mismo criterio que Pausa, packs.py), excluyendo los 4 slots del
  Programa Ritual/Refugio.
- Tina: se consulta con las personas reales (la tina debe tener cupo para el grupo).
"""
from .availability import disponibilidad, _parse_fecha, MASAJE_SLOTS_PROGRAMA_MIN
from .grounding import formatear_precio
from . import packs

# Fase 1 (simples) + Fase 2 (ritual/refugio). Se conservan los subgrupos como
# referencia histórica; TODOS pasan por _BUILDERS.
TIPOS_FASE1 = ('pausa', 'tina_sola', 'masaje_solo', 'noche_aguas_calientes')
TIPOS_FASE2 = ('ritual', 'refugio', 'dia')
# Fase 3 (H-108): tipos SIN agenda — el endpoint no les exige `fecha`.
TIPOS_SIN_FECHA = ('giftcard',)
TIPOS_VALIDOS = TIPOS_FASE1 + TIPOS_FASE2 + TIPOS_SIN_FECHA

NOMBRES = {
    'pausa': 'Pausa junto al río',
    'tina_sola': 'Tina',
    'masaje_solo': 'Masaje',
    'noche_aguas_calientes': 'Noche de Aguas Calientes',
    'ritual': 'Ritual del Río',
    'refugio': 'Refugio Aremko',
    'dia': 'Cabaña y spa por el día',
    'giftcard': 'Gift Card',
}

# Tope de alternativas por respuesta (evita abrumar la bandeja con decenas de botones).
MAX_ALTERNATIVAS = 12
# Noche de Aguas Calientes combina cabañas × tinas, así que crece rápido. Tope de
# Jorge (2026-08-14): 6. En el cajón se muestran de a una y él o Deborah eligen
# cuál enviar, así que el tope es para que la lista sea manejable, no para esconder.
MAX_ALTERNATIVAS_NOCHE = 6


def _linea(origen, nombre, hora):
    """Una línea del itinerario, con el ID del servicio cuando se conoce.

    El nombre solo sirve para leer; para convertir una alternativa en cotización
    hace falta el `servicio_id` — sin él, el cajón tendría que adivinar por
    texto, que es como se cuela el error el día que haya dos tinas de nombre
    parecido. `origen` es el dict del motor (trae servicio_id); va en None
    cuando la línea es informativa y no se agenda («Llegada y desayuno»).
    """
    linea = {'servicio': nombre, 'hora': hora}
    sid = (origen or {}).get('servicio_id')
    if sid:
        linea['servicio_id'] = int(sid)
    return linea


def _alt(titulo, precio_total, precio_con_descuento, hay_descuento, texto_sugerido, itinerario):
    return {
        'titulo': titulo,
        'precio_total': int(precio_total),
        'precio_con_descuento': int(precio_con_descuento),
        'hay_descuento': bool(hay_descuento),
        'texto_sugerido': texto_sugerido,
        'itinerario': itinerario,
    }


def _personas_txt(personas):
    return f"{personas} persona" + ('s' if personas > 1 else '')


# ---------------------------------------------------------------------------
# tina_sola
# ---------------------------------------------------------------------------

def _tina_sola(fecha, personas):
    res = disponibilidad(fecha, personas, 'tina', limite=None)
    if res.get('error'):
        return {'error': res['error']}
    alts = []
    for s in res.get('servicios', []):
        precio = int(s['precio_total'])  # ya viene × personas
        for hora in (s.get('slots_libres') or []):
            texto = (f"{s['nombre']} a las {hora} hrs para {_personas_txt(personas)}, "
                     f"{formatear_precio(precio)}.")
            alts.append(_alt(
                titulo=f"{s['nombre']} · {hora}",
                precio_total=precio, precio_con_descuento=precio, hay_descuento=False,
                texto_sugerido=texto,
                itinerario=[_linea(s, s['nombre'], hora)]))
    alts.sort(key=lambda a: a['itinerario'][0]['hora'])
    return {'fecha': res.get('fecha'), 'alternativas': alts[:MAX_ALTERNATIVAS]}


# ---------------------------------------------------------------------------
# masaje_solo (1 persona = 1 masaje, N personas = N masajes mismo horario)
# ---------------------------------------------------------------------------

def _masaje_solo(fecha, personas):
    # Disponibilidad del slot a nivel de 1 masajista (mismo criterio que Pausa);
    # excluye los 4 slots del Programa Ritual/Refugio (incluir_slots_programa=False).
    res = disponibilidad(fecha, 1, 'masaje', limite=None)
    if res.get('error'):
        return {'error': res['error']}
    alts = []
    for s in res.get('servicios', []):
        precio = int(s['precio_por_persona']) * personas  # N masajes
        unidad = f"{personas} masaje" + ('s' if personas > 1 else '')
        for hora in (s.get('slots_libres') or []):
            texto = (f"{s['nombre']} a las {hora} hrs ({unidad} para {_personas_txt(personas)}), "
                     f"{formatear_precio(precio)}.")
            alts.append(_alt(
                titulo=f"{s['nombre']} · {hora}",
                precio_total=precio, precio_con_descuento=precio, hay_descuento=False,
                texto_sugerido=texto,
                itinerario=[_linea(s, s['nombre'], hora)]))
    alts.sort(key=lambda a: a['itinerario'][0]['hora'])
    return {'fecha': res.get('fecha'), 'alternativas': alts[:MAX_ALTERNATIVAS]}


# ---------------------------------------------------------------------------
# noche_aguas_calientes (cabaña + tina, sin masaje)
# ---------------------------------------------------------------------------

def _noche_aguas_calientes(fecha, personas):
    # `todas=True`: cada cabaña con cada tina, no una sola tina repetida (Jorge,
    # 2026-08-14). Vienen ordenadas de la tina más tarde a la más temprana —esa
    # sigue siendo la preferida— y se topean en 6: en el cajón se muestran de a
    # una y Deborah elige cuál mandarle al cliente.
    res = packs.disponibilidad_pack_cabana_tina(fecha, personas=personas, todas=True)
    if res.get('error'):
        return {'error': res['error']}
    alts = []
    for op in (res.get('alternativas') or res.get('opciones', [])):
        cab = op['cabana']
        tina = op.get('tina')
        itin = [_linea(cab, cab['nombre'], cab['hora_check_in'])]
        partes = [f"{cab['nombre']} (check-in {cab['hora_check_in']})"]
        if tina:
            itin.append(_linea(tina, tina['nombre'], tina['hora']))
            partes.append(f"{tina['nombre']} a las {tina['hora']} hrs")
        precio = int(op['precio_total'])
        precio_desc = int(op.get('precio_con_descuento', precio))
        texto = (f"Noche de Aguas Calientes: {' + '.join(partes)}, desayuno incluido, "
                 f"{formatear_precio(precio_desc)} para dos.")
        titulo = cab['nombre'] + (f" · tina {tina['hora']}" if tina else " · sin tina")
        alts.append(_alt(
            titulo=titulo, precio_total=precio, precio_con_descuento=precio_desc,
            hay_descuento=bool(op.get('hay_descuento')), texto_sugerido=texto,
            itinerario=itin))
    return {'fecha': res.get('fecha'), 'alternativas': alts[:MAX_ALTERNATIVAS_NOCHE]}


# ---------------------------------------------------------------------------
# pausa (adaptador del pack tina+masaje de H-059 al shape unificado)
# ---------------------------------------------------------------------------

def _pausa(fecha, personas):
    res = packs.disponibilidad_pack_tina_masaje(fecha, personas=personas, todas=True)
    if res.get('error'):
        return {'error': res['error']}
    alts = []
    for a in res.get('alternativas', []):
        tina, masaje = a['tina'], a['masaje']
        if a['hay_descuento']:
            precio_txt = (f"por un total de {formatear_precio(a['precio_con_descuento'])} "
                          f"(con descuento de pack; precio normal {formatear_precio(a['precio_total'])})")
        else:
            precio_txt = f"por un total de {formatear_precio(a['precio_total'])}"
        texto = (f"{tina['nombre']} a las {tina['hora']} hrs y "
                 f"{masaje['nombre']} a las {masaje['hora']} hrs, {precio_txt}.")
        alts.append(_alt(
            titulo=f"{a['etiqueta']} · tina {tina['hora']} / masaje {masaje['hora']}",
            precio_total=a['precio_total'], precio_con_descuento=a['precio_con_descuento'],
            hay_descuento=a['hay_descuento'], texto_sugerido=texto,
            itinerario=[_linea(tina, tina['nombre'], tina['hora']),
                        _linea(masaje, masaje['nombre'], masaje['hora'])]))
    return {'fecha': res.get('fecha'), 'alternativas': alts[:MAX_ALTERNATIVAS]}


# ---------------------------------------------------------------------------
# ritual / refugio (Fase 2): precio fijo, varía el slot de masaje del Programa
# ---------------------------------------------------------------------------

def _slots_masaje_programa_libres(f, personas=2):
    """Horas de los 4 slots del Programa (15:30/18:00/20:30/21:45) LIBRES para
    masaje de `personas` ese día, ordenadas. Reusa la misma disponibilidad que
    usa el Ritual/Refugio (incluir_slots_programa=True)."""
    masajes = disponibilidad(f, personas, 'masaje', limite=None,
                             incluir_slots_programa=True).get('servicios', [])
    libres = set()
    for m in masajes:
        for s in (m.get('slots_libres') or []):
            mn = packs.hhmm_a_min(s)
            if mn in MASAJE_SLOTS_PROGRAMA_MIN:
                libres.add(mn)
    return [packs.min_a_hhmm(x) for x in sorted(libres)]


def _ritual(fecha, personas):
    base = packs.disponibilidad_ritual(fecha)
    if base.get('error'):
        return {'error': base['error']}
    if not base.get('disponible'):
        return {'fecha': base.get('fecha'), 'alternativas': []}
    itin = base['itinerario']
    cab, tina, masaje = itin['cabana'], itin['tina'], itin['masaje']
    precio = int(base['precio_total'])
    promo = ' (precio promoción domingo a jueves)' if base.get('es_domjue') else ''
    f = _parse_fecha(base['fecha'])
    slots = _slots_masaje_programa_libres(f, 2) or [masaje['hora']]
    alts = []
    for hora_masaje in slots:
        texto = (f"Ritual del Río en {cab['nombre']} (check-in {cab['hora_check_in']}): "
                 f"tina {tina['nombre']} a las {tina['hora']} hrs y masaje a las {hora_masaje} hrs, "
                 f"desayuno incluido, {formatear_precio(precio)} para dos{promo}.")
        alts.append(_alt(
            titulo=f"Ritual · masaje {hora_masaje}",
            precio_total=precio, precio_con_descuento=precio, hay_descuento=False,
            texto_sugerido=texto,
            itinerario=[_linea(cab, cab['nombre'], cab['hora_check_in']),
                        _linea(tina, tina['nombre'], tina['hora']),
                        _linea(masaje, masaje['nombre'], hora_masaje)]))
    return {'fecha': base['fecha'], 'alternativas': alts}


def _refugio(fecha, personas):
    base = packs.disponibilidad_refugio(fecha)
    if base.get('error'):
        return {'error': base['error']}
    if not base.get('disponible'):
        return {'fecha': base.get('fecha'), 'alternativas': []}
    itin = base['itinerario']
    cab, tina1, tina2, masaje = itin['cabana'], itin['tina'], itin['tina2'], itin['masaje']
    precio = int(base['precio_total'])
    f = _parse_fecha(base['fecha'])
    slots = _slots_masaje_programa_libres(f, 2) or [masaje['hora']]  # masaje = primera noche
    alts = []
    for hora_masaje in slots:
        texto = (f"Refugio Aremko: 2 noches en {cab['nombre']} (llegada {base['fecha']}, "
                 f"salida {base.get('fecha_salida')}). Tina cada día "
                 f"(noche 1 {tina1['nombre']} {tina1['hora']} hrs, noche 2 {tina2['nombre']} "
                 f"{tina2['hora']} hrs), masaje la primera noche a las {hora_masaje} hrs, "
                 f"desayuno incluido ambas mañanas, {formatear_precio(precio)} para dos.")
        alts.append(_alt(
            titulo=f"Refugio · masaje {hora_masaje}",
            precio_total=precio, precio_con_descuento=precio, hay_descuento=False,
            texto_sugerido=texto,
            itinerario=[_linea(cab, f"{cab['nombre']} (2 noches)", cab['hora_check_in']),
                        _linea(tina1, f"{tina1['nombre']} (noche 1)", tina1['hora']),
                        _linea(tina2, f"{tina2['nombre']} (noche 2)", tina2['hora']),
                        _linea(masaje, masaje['nombre'], hora_masaje)]))
    return {'fecha': base['fecha'], 'alternativas': alts}


def _dia(fecha, personas):
    """«Cabaña y spa por el día»: una alternativa por combinación vendible.

    A diferencia del Ritual, acá no se varía el masaje sobre una base fija: el
    motor ya decidió qué combinaciones de masaje y tina NO se pisan, y en qué
    orden conviene ofrecerlas. Mostrar cada una como alternativa deja que
    Deborah elija por el cliente ("¿prefieres partir con el masaje o con el
    agua?") sin poder armar una que se pise.
    """
    base = packs.disponibilidad_dia(fecha)
    if base.get('error'):
        return {'error': base['error']}
    if not base.get('disponible'):
        return {'fecha': base.get('fecha'), 'alternativas': [],
                'nota': base.get('nota')}

    itin = base['itinerario']
    cab = itin['cabana']
    precio = int(base['precio_total'])
    f = _parse_fecha(base['fecha'])

    # Las combinaciones que de verdad están libres ese día, en el orden de
    # preferencia del motor (primero las que dan las ocho horas).
    masajes = disponibilidad(f, 2, 'masaje', limite=None).get('servicios', [])
    tinas = disponibilidad(f, 2, 'tina', limite=None).get('servicios', [])
    alts = []
    for masaje_hora, tina_hora in packs.DIA_COMBINACIONES:
        masaje = packs._servicio_con_hora(masajes, masaje_hora)
        tina, _ = packs._tina_con_hora(tinas, tina_hora)
        if masaje is None or tina is None:
            continue
        primero = 'masaje' if masaje_hora < tina_hora else 'tina'
        texto = (f"Cabaña y spa por el día en {cab['nombre']}: llegada 10:00 con "
                 f"desayuno, masaje para dos a las {masaje_hora} hrs y "
                 f"{tina['nombre']} a las {tina_hora} hrs. La cabaña queda a su "
                 f"disposición durante todo el día. Es alojamiento diurno: no se "
                 f"pernocta, vuelven a dormir a su casa. "
                 f"{formatear_precio(precio)} para dos.")
        alts.append(_alt(
            titulo=f"Por el día · {primero} primero ({masaje_hora}/{tina_hora})",
            precio_total=precio, precio_con_descuento=precio, hay_descuento=False,
            texto_sugerido=texto,
            itinerario=[_linea(None, 'Llegada y desayuno', '10:00'),
                        _linea(masaje, masaje['nombre'], masaje_hora),
                        _linea(tina, tina['nombre'], tina_hora)]))
    return {'fecha': base['fecha'], 'alternativas': alts}


# ---------------------------------------------------------------------------
# giftcard (H-108): el catálogo publicado, sin fecha ni horario
# ---------------------------------------------------------------------------

def _giftcard(fecha, personas):
    """Una alternativa por experiencia publicada del catálogo.

    `fecha` y `personas` se ignoran a propósito: una gift card no ocupa slot
    —vale 1 año y quien la recibe agenda después—, así que acá no hay
    disponibilidad que consultar. Ese es además el argumento de venta, y por
    eso va dentro de cada `texto_sugerido`.

    La fuente es catalogo_giftcards() — la MISMA que vende Luna (H-105) y que
    pinta la vitrina web: activar una experiencia en el admin la hace aparecer
    en la bandeja sin deploy. Sin tope, a diferencia de los otros builders: el
    catálogo lo cura Jorge en el admin y hoy no llega a diez; cortarlo acá
    sería esconderle tarjetas a Deborah sin aviso.

    Una experiencia sin monto fijo ni montos sugeridos se OMITE: un botón sin
    precio no ofrece nada vendible.
    """
    from .giftcards import catalogo_giftcards

    alts = []
    # texto_completo: la descripción va TAL CUAL al cliente; el recorte de 120
    # del catálogo de Luna cortaba palabras al medio («bosque nativ.»).
    for e in catalogo_giftcards(texto_completo=True).get('experiencias', []):
        descripcion = (e.get('descripcion') or '').strip().rstrip('.')
        detalle = f" — {descripcion}" if descripcion else ''
        if e.get('precio'):
            precio = int(e['precio'])
            titulo = e['nombre']
            precio_frase = f"Valor {formatear_precio(precio)}"
        elif e.get('montos_sugeridos'):
            sugeridos = [int(m) for m in e['montos_sugeridos']]
            precio = min(sugeridos)
            titulo = f"{e['nombre']} · monto a elección"
            precio_frase = ('Monto a tu elección (sugeridos: '
                            + ' / '.join(formatear_precio(m) for m in sugeridos)
                            + ')')
        else:
            continue
        texto = (f"Gift Card «{e['nombre']}»{detalle}. {precio_frase}. "
                 f"Vale por 1 año y quien la recibe elige cuándo usarla.")
        alts.append(_alt(
            titulo=titulo, precio_total=precio, precio_con_descuento=precio,
            hay_descuento=False, texto_sugerido=texto,
            # Sin horas que agendar: la bandeja debe tolerar itinerario vacío.
            itinerario=[]))
    return {'fecha': None, 'alternativas': alts}


_BUILDERS = {
    'pausa': _pausa,
    'tina_sola': _tina_sola,
    'masaje_solo': _masaje_solo,
    'noche_aguas_calientes': _noche_aguas_calientes,
    'ritual': _ritual,
    'refugio': _refugio,
    'dia': _dia,
    'giftcard': _giftcard,
}


def construir_alternativas(tipo, fecha, personas):
    """Entrada única. Devuelve dict con shape unificado o {'error': ...}.

    {'tipo', 'fecha', 'personas', 'nombre_experiencia', 'alternativas': [...]}
    """
    tipo = (tipo or '').strip().lower()
    builder = _BUILDERS.get(tipo)
    if builder is None:
        return {'error': f"tipo inválido: '{tipo}'. Válidos: {', '.join(TIPOS_VALIDOS)}"}
    res = builder(fecha, personas)
    if res.get('error'):
        return {'error': res['error']}
    return {
        'tipo': tipo,
        'fecha': res.get('fecha'),
        'personas': personas,
        'nombre_experiencia': NOMBRES[tipo],
        'alternativas': res.get('alternativas', []),
    }
