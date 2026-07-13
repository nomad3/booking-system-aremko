"""
Builders de "alternativas de horario" unificadas para el botón de la bandeja (H-061).

Generaliza el endpoint de Pausa (H-059) a los otros casos. El botón de la bandeja
(aremko-cli) manda `tipo + fecha + personas` y recibe una lista de alternativas
concretas, cada una con un `texto_sugerido` listo para pegar en el borrador — sin
depender de que Luna interprete "¿más tarde?".

FASE 1 (este archivo): pausa, tina_sola, masaje_solo, noche_aguas_calientes.
FASE 2 (pendiente): ritual, refugio (necesitan variar los 4 slots de masaje del
Programa + la restricción de misma cabaña 2 noches).

Shape unificado de cada alternativa:
  {
    "titulo": "Tina Hidromasaje Llaima · 18:00",   # etiqueta del botón
    "precio_total": 60000,                          # int CLP, sin descuento
    "precio_con_descuento": 60000,                  # int CLP, tras pack (== total si no hay)
    "hay_descuento": false,
    "texto_sugerido": "Tina ... a las 18:00 hrs para 2 personas, $60.000.",
    "itinerario": [{"servicio": "Tina ...", "hora": "18:00"}]   # 1..N líneas con hora
  }

Nota de negocio (confirmada por Jorge 2026-07-06):
- Masaje: 1 persona = 1 masaje, 2 personas = 2 masajes (mismo horario). El precio
  es `precio_por_persona × personas`; la disponibilidad del slot se mira a nivel
  de 1 masajista (mismo criterio que Pausa, packs.py), excluyendo los 4 slots del
  Programa Ritual/Refugio.
- Tina: se consulta con las personas reales (la tina debe tener cupo para el grupo).
"""
from .availability import disponibilidad
from .grounding import formatear_precio
from . import packs

TIPOS_FASE1 = ('pausa', 'tina_sola', 'masaje_solo', 'noche_aguas_calientes')
TIPOS_FASE2 = ('ritual', 'refugio')
TIPOS_VALIDOS = TIPOS_FASE1 + TIPOS_FASE2

NOMBRES = {
    'pausa': 'Pausa junto al río',
    'tina_sola': 'Tina',
    'masaje_solo': 'Masaje',
    'noche_aguas_calientes': 'Noche de Aguas Calientes',
    'ritual': 'Ritual del Río',
    'refugio': 'Refugio Aremko',
}

# Tope de alternativas por respuesta (evita abrumar la bandeja con decenas de botones).
MAX_ALTERNATIVAS = 12


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
                itinerario=[{'servicio': s['nombre'], 'hora': hora}]))
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
                itinerario=[{'servicio': s['nombre'], 'hora': hora}]))
    alts.sort(key=lambda a: a['itinerario'][0]['hora'])
    return {'fecha': res.get('fecha'), 'alternativas': alts[:MAX_ALTERNATIVAS]}


# ---------------------------------------------------------------------------
# noche_aguas_calientes (cabaña + tina, sin masaje)
# ---------------------------------------------------------------------------

def _noche_aguas_calientes(fecha, personas):
    res = packs.disponibilidad_pack_cabana_tina(fecha, personas=personas)
    if res.get('error'):
        return {'error': res['error']}
    alts = []
    for op in res.get('opciones', []):
        cab = op['cabana']
        tina = op.get('tina')
        itin = [{'servicio': cab['nombre'], 'hora': cab['hora_check_in']}]
        partes = [f"{cab['nombre']} (check-in {cab['hora_check_in']})"]
        if tina:
            itin.append({'servicio': tina['nombre'], 'hora': tina['hora']})
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
    return {'fecha': res.get('fecha'), 'alternativas': alts[:MAX_ALTERNATIVAS]}


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
            itinerario=[{'servicio': tina['nombre'], 'hora': tina['hora']},
                        {'servicio': masaje['nombre'], 'hora': masaje['hora']}]))
    return {'fecha': res.get('fecha'), 'alternativas': alts[:MAX_ALTERNATIVAS]}


_BUILDERS = {
    'pausa': _pausa,
    'tina_sola': _tina_sola,
    'masaje_solo': _masaje_solo,
    'noche_aguas_calientes': _noche_aguas_calientes,
}


def construir_alternativas(tipo, fecha, personas):
    """Entrada única. Devuelve dict con shape unificado o {'error': ...}.

    {'tipo', 'fecha', 'personas', 'nombre_experiencia', 'alternativas': [...]}
    """
    tipo = (tipo or '').strip().lower()
    if tipo in TIPOS_FASE2:
        return {'error': f"el tipo '{tipo}' aún no está disponible (Fase 2)"}
    builder = _BUILDERS.get(tipo)
    if builder is None:
        return {'error': f"tipo inválido: '{tipo}'. Válidos: {', '.join(TIPOS_FASE1)}"}
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
