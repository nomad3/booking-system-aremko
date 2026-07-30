"""
Configurador de veladas — DOS puertas (landings), UN motor.

Landings de tráfico frío (reel / Google Ads): la persona arma una velada sobre una
tina, con la ambientación como sorpresa, y termina en el checkout existente.

  · /experiencia-romantica/  → sorprender a la pareja (R1/R2, de a dos).
  · /celebraciones/          → cumpleaños de a dos, cumpleaños en grupo (3-6) y
                               despedida de soltera/o.

Por qué separadas (Jorge, 2026-07-30): una sola URL mezclaba las cuatro ocasiones.
El menú decía "Experiencia Romántica" y el hero prometía "sorprende a tu pareja",
pero abajo había un botón de "Despedida de soltera" — el cliente se enredaba, y una
sola página no puede rankear a la vez para "regalo romántico pareja" y para
"cumpleaños con tina puerto varas" (intenciones de búsqueda distintas).

Lo que se separó es la VITRINA. El motor (`experiencia_romantica_submit`) sigue
siendo uno solo: mismas reglas de precio, mismo guard de stock, misma invitación.

Post-pago la persona recibe (a) el comprobante completo y (b) —solo en las ocasiones
de a dos— una invitación filtrada para enviar (ver invitacion_sorpresa_view).

Taxonomía de ambientaciones (confirmada con Jorge / Deborah, jul-2026):
  · ROMÁNTICAS — SIN color, se instalan en CUALQUIER tina.
      R1 (id 22, $32.000) base · R2 (id 23, $68.000) = R1 + ramo de flores.
  · CUMPLEAÑOS — eligen color (azul/rosado) + con/sin torta. Solo caben en las
    tinas Hornopirén, Osorno y Llaima (en las demás no hay espacio).
      Sin torta (id 24 azul / id 66 rosado, $38.000).
      Con torta (id 25 azul / id 65 rosado, $78.000).

Reutiliza el carrito de sesión y el checkout ya probados: este módulo solo arma el
carrito en el orden correcto (tina primero; la ambientación hereda su slot) y
redirige a la página de carrito.
"""
import unicodedata

from django.contrib import messages
from django.db.models import Q
from django.shortcuts import render, redirect

from ..models import Servicio, Producto
from ..services.ambientacion_bebidas import CHOCOLATES_ID


NOMBRE_CHOCOLATES = 'Caja de chocolates'

# --- Catálogo de ambientaciones (IDs reales, categoría Ambientaciones) --------
# Románticas: sin color, cualquier tina. R1 base; R2 = R1 + ramo de flores.
ROMANTICA_IDS = {'r1': 22, 'r2': 23}
# Cumpleaños: eligen color + con/sin torta. Solo en las 3 tinas con espacio.
CUMPLE_IDS = {
    ('sin_torta', 'azul'): 24, ('sin_torta', 'rosado'): 66,
    ('con_torta', 'azul'): 25, ('con_torta', 'rosado'): 65,
}
# IDs de las 4 ambientaciones de cumpleaños (para detectar la ocasión en la
# invitación/ficha por ID, no por nombre: "Decoración Simple" NO dice "cumple").
CUMPLE_AMBIENTACION_IDS = frozenset(CUMPLE_IDS.values())
ROMANTICA_AMBIENTACION_IDS = frozenset(ROMANTICA_IDS.values())
# Tinas donde SÍ caben las ambientaciones de cumpleaños (las demás no tienen
# espacio físico para montarlas). Se matchea por nombre normalizado.
CUMPLE_TINAS = ('hornopiren', 'osorno', 'llaima')

# Modo grupo (V-13): celebración de grupo tipo cumpleaños — reusa la ambientación de
# cumpleaños (color + con/sin torta). Tinas grupales por nombre; cada una define su
# capacidad en el admin (mín 3). Se cobra precio_base × N personas (Osorno/Calbuco $25.000 c/u).
GRUPO_TINAS = ('calbuco', 'osorno')
GRUPO_MIN_PERSONAS = 3

# Es una experiencia PARA DOS: la tina se cobra siempre por 2 personas, aunque sea
# una tina grupal (p.ej. Osorno se usa para el cumpleaños de a dos → 2 × precio_base,
# no × su capacidad grupal).
PERSONAS_EXPERIENCIA = 2

# Precios de respaldo por si faltara un SKU en la BD (no deberían usarse en prod).
FALLBACK = {'r1': 32000, 'r2': 68000, 'cumple_sin': 38000, 'cumple_con': 78000, 'choco': 16000}


# --- Las dos puertas (landings) ----------------------------------------------
MODO_ROMANTICA = 'romantica'
MODO_CELEBRACIONES = 'celebraciones'

# Fuente ÚNICA de qué ocasión vive en qué puerta. La usan el GET (qué botones se
# pintan) y el POST (a qué landing devolver al cliente si la validación falla).
OCASIONES_POR_MODO = {
    MODO_ROMANTICA: ('romantica',),
    MODO_CELEBRACIONES: ('cumpleanos', 'grupo', 'despedida'),
}

# Nombre de la URL de cada puerta (para los redirect de error del submit).
URL_POR_MODO = {
    MODO_ROMANTICA: 'experiencia_romantica',
    MODO_CELEBRACIONES: 'celebraciones',
}

# Botones del selector de ocasión. El id CSS importa: la foto de fondo de cada
# botón se define por #id en el template.
OCASION_BOTONES = {
    'cumpleanos': {'css_id': 'optCum', 'titulo': 'Cumpleaños', 'sub': 'Con o sin torta · de a dos'},
    'grupo': {'css_id': 'optGrupo', 'titulo': 'En grupo', 'sub': 'Cumpleaños de 3 a 6'},
    'despedida': {'css_id': 'optDespedida', 'titulo': 'Despedida', 'sub': 'De soltera/o · en grupo'},
}

# Ocasiones que solo existen si hay tinas grupales publicadas.
OCASIONES_DE_GRUPO = ('grupo', 'despedida')


def modo_de_ocasion(ocasion):
    """Puerta a la que pertenece una ocasión. Desconocida → la romántica."""
    for modo, ocasiones in OCASIONES_POR_MODO.items():
        if ocasion in ocasiones:
            return modo
    return MODO_ROMANTICA


def url_de_ocasion(ocasion):
    """Nombre de URL de la landing donde vive esa ocasión.

    Sin esto, un error de validación en un cumpleaños grupal devolvería al cliente
    a la landing romántica — justo el enredo que la separación viene a arreglar.
    """
    return URL_POR_MODO[modo_de_ocasion(ocasion)]


# Copy de cada vitrina. Vive acá y no en el template porque las dos puertas
# comparten un solo HTML (el configurador es la parte frágil: no se duplica).
COPY = {
    MODO_ROMANTICA: {
        'title': 'Experiencia Romántica · Sorprende a tu pareja | Aremko Spa Boutique',
        'meta_desc': (
            'Regálale una velada junto al río: tina caliente, casi 30 velas y la sorpresa '
            'lista al llegar. Tú la preparas en secreto; tu pareja solo recibe la invitación.'),
        'hero_img': 'servicios/IMG_2795_ydpknt',
        'hero_h1': 'Regálale una velada<br>que no va a olvidar',
        'hero_p': (
            'Una tina caliente junto al río, casi 30 velas encendidas y la sorpresa lista '
            'cuando lleguen. Tú la preparas en secreto; tu pareja solo recibe la invitación.'),
        'hero_cta': 'Armar la sorpresa',
        'kick': 'El gesto',
        'tit': 'Hay regalos que se abren. Este se enciende.',
        'lead': (
            'No es un objeto: es una velada para los dos, junto al Río Pescado. Tú eliges cada '
            'detalle <b>en complicidad con nosotros</b>, y tu pareja recibe una invitación '
            'preciosa —sin precios, sin adelantar nada— que descubre recién al llegar.'),
        'pasos': [
            ('Ármala a tu gusto, en secreto',
             'Eliges la ambientación, la tina, la fecha y la hora. Nosotros guardamos el secreto contigo.'),
            ('Envíale la invitación',
             'Una tarjeta linda para tu pareja, sin precios ni spoiler. Solo sabrá que la esperas junto al río.'),
            ('La sorpresa, lista al llegar',
             'Casi 30 velas encendidas y todo montado por nosotros antes de que crucen la puerta.'),
        ],
        'kick_armar': 'Arma tu velada',
        'tit_armar': 'Diseña la experiencia',
        'sorpresa': (
            'Tú y Aremko saben todo. Tu pareja recibe <b>solo la invitación</b> —sin precios, '
            'sin ver la ambientación—. La sorpresa se revela al llegar.'),
        'cierre': '<b>San Valentín</b> es nuestra semana más pedida. Asegura tu fecha con tiempo.',
        'cruce_url': 'celebraciones',
        'cruce_txt': '¿Es su cumpleaños o una despedida? Míralo en <b>Celebraciones</b> →',
    },
    MODO_CELEBRACIONES: {
        'title': 'Cumpleaños y celebraciones junto al río · Tina caliente en Puerto Varas | Aremko',
        'meta_desc': (
            'Celebra el cumpleaños o la despedida de soltera en una tina caliente junto al río, '
            'en Puerto Varas. Ambientación del color que elijan, con o sin torta, montada antes '
            'de que lleguen. De a dos o hasta 6 personas.'),
        'hero_img': 'servicios/cumplea%C3%B1osdamasaremko2_kroa3j',
        'hero_h1': 'Cumplir años aquí<br>se siente distinto',
        'hero_p': (
            'Un cumpleaños, una despedida de soltera o el panorama que se merecen. Tina caliente '
            'junto al río, la ambientación del color que elijan y todo montado antes de que lleguen.'),
        'hero_cta': 'Armar la celebración',
        'kick': 'La ocasión',
        'tit': 'Nada de salón. Agua caliente y río.',
        'lead': (
            'De a dos o hasta seis, con la ambientación en el color que elijan y —si quieren— la '
            'torta esperando. <b>Ustedes llegan; lo demás ya está listo.</b>'),
        'pasos': [
            ('Elige la ocasión y el color',
             'Cumpleaños de a dos, en grupo o despedida de soltera/o. Azul o rosado, con torta o sin ella.'),
            ('Reserva tu tina y tu hora',
             'Eliges la tina, el día y la hora. En grupo son hasta 4 en Calbuco y hasta 6 en Osorno.'),
            ('Llegan y está todo montado',
             'La ambientación instalada y la tina a punto antes de que crucen la puerta. Ustedes solo celebran.'),
        ],
        'kick_armar': 'Arma tu celebración',
        'tit_armar': 'Diseña la celebración',
        'sorpresa': (
            'Si quieres que sea sorpresa, nosotros guardamos el secreto: quien celebra recibe '
            '<b>solo la invitación</b> —sin precios, sin ver la ambientación—.'),
        'cierre': 'Los fines de semana se llenan primero. Asegura la fecha con tiempo.',
        'cruce_url': 'experiencia_romantica',
        'cruce_txt': '¿Quieres sorprender a tu pareja? Mira la <b>Experiencia Romántica</b> →',
    },
}


def _norm(texto):
    """minúsculas sin acentos, para matchear nombres de SKU de forma robusta."""
    t = (texto or '').lower()
    t = unicodedata.normalize('NFKD', t)
    return ''.join(c for c in t if not unicodedata.combining(c))


def resolver_ambientacion_id(ocasion, nivel=None, torta=None, color=None):
    """
    Traduce la elección del configurador → ID del Servicio de ambientación.

    ocasion='romantica' → nivel 'r1'|'r2' (sin color, cualquier tina).
    ocasion='cumpleanos' → (torta 'sin_torta'|'con_torta', color 'azul'|'rosado').

    Devuelve el ID (int) o None si la combinación no existe.
    """
    if ocasion == 'romantica':
        return ROMANTICA_IDS.get((nivel or 'r1').lower())
    if ocasion in ('cumpleanos', 'grupo', 'despedida'):
        # Grupo y despedida son celebraciones tipo cumpleaños: reusan la ambientación.
        clave = ((torta or 'sin_torta').lower(), (color or 'rosado').lower())
        return CUMPLE_IDS.get(clave)
    return None


def es_ocasion_grupo(ocasion):
    """True para las ocasiones que usan el modo grupo (grupo y despedida de soltera/o)."""
    return ocasion in ('grupo', 'despedida')


def tina_admite_cumple(nombre_tina):
    """True si la tina tiene espacio para una ambientación de cumpleaños."""
    n = _norm(nombre_tina)
    return any(c in n for c in CUMPLE_TINAS)


def tina_admite_grupo(nombre_tina):
    """True si la tina es grupal (celebración de 3+ personas). Con espacio para la
    ambientación de cumpleaños (confirmado con Jorge: Calbuco y Osorno)."""
    n = _norm(nombre_tina)
    return any(g in n for g in GRUPO_TINAS)


def _clp(n):
    """Formato chileno con punto de miles: 15000 -> '15.000'."""
    return f"{int(n or 0):,}".replace(",", ".")


def _servicio(sid):
    """Servicio activo por ID, o None."""
    if not sid:
        return None
    return Servicio.objects.filter(id=sid, activo=True).first()


def _precio(sid, fallback):
    s = _servicio(sid)
    return int(s.precio_base) if s else fallback


def _chocolates_servicio():
    return Servicio.objects.filter(
        categoria__nombre__iexact='Ambientaciones', activo=True,
        nombre__iexact=NOMBRE_CHOCOLATES,
    ).first()


def _stock_chocolates():
    """Stock actual del Producto real de chocolates (Caja Chocolate, id 42); 0 si no existe."""
    prod = Producto.objects.filter(id=CHOCOLATES_ID).only('cantidad_disponible').first()
    return int(prod.cantidad_disponible) if prod else 0


def chocolates_disponibles():
    """True solo si existe la línea de cobro Y hay stock real del Producto (>0).
    Es el guard del configurador: sin stock, los chocolates no se ofrecen ni se venden."""
    return _chocolates_servicio() is not None and _stock_chocolates() > 0


def _tinas_configurador():
    """
    Tinas candidatas: las de pareja (capacidad ≤ 2, sin add-ons de niño) MÁS
    las 3 tinas de cumpleaños (que incluyen Osorno, grupal). Cada una viene
    marcada con dónde califica: `romantica_ok` (cualquier tina de pareja) y
    `cumple_ok` (solo Hornopirén/Osorno/Llaima). El front filtra según la ocasión.
    """
    filtro = Q(capacidad_maxima__lte=2)
    for n in CUMPLE_TINAS + GRUPO_TINAS:
        filtro |= Q(nombre__icontains=n)
    qs = Servicio.objects.filter(
        tipo_servicio='tina', activo=True, publicado_web=True,
    ).filter(filtro).exclude(
        nombre__icontains='niño').exclude(nombre__icontains='nino').order_by('precio_base', 'nombre')

    tinas = []
    for t in qs:
        # Románticas/cumpleaños: para 2 → 2 × precio_base. Grupo: precio_base × N (en el front).
        total = int(t.precio_base) * PERSONAS_EXPERIENCIA
        precio_persona = int(t.precio_base)
        tinas.append({
            'id': t.id,
            'nombre': t.nombre,
            'capacidad': t.capacidad_maxima,
            'total': total,
            'total_fmt': _clp(total),
            'romantica_ok': t.capacidad_maxima <= 2,
            'cumple_ok': tina_admite_cumple(t.nombre),
            'grupo_ok': tina_admite_grupo(t.nombre),
            'precio_persona': precio_persona,
            'precio_persona_fmt': _clp(precio_persona),
        })
    return tinas


def _ocasiones_visibles(modo, tiene_tinas_grupo):
    """
    Botones del selector de ocasión de esta puerta.

    La romántica tiene una sola ocasión → devuelve [] y el template no dibuja el
    paso (un paso menos en el embudo). Las de grupo se caen solas si no hay tinas
    grupales publicadas.
    """
    if modo == MODO_ROMANTICA:
        return []
    visibles = []
    for clave in OCASIONES_POR_MODO[modo]:
        if clave in OCASIONES_DE_GRUPO and not tiene_tinas_grupo:
            continue
        visibles.append(dict(OCASION_BOTONES[clave], clave=clave))
    return visibles


def _landing(request, modo):
    """GET — renderiza el configurador con el copy y las ocasiones de esa puerta."""
    tinas = _tinas_configurador()
    chocolates = _chocolates_servicio()
    precio_choco = int(chocolates.precio_base) if chocolates else FALLBACK['choco']
    tiene_tinas_grupo = any(t['grupo_ok'] for t in tinas)
    ocasiones = _ocasiones_visibles(modo, tiene_tinas_grupo)
    # La primera ocasión de la puerta es la que arranca seleccionada.
    ocasion_default = ocasiones[0]['clave'] if ocasiones else OCASIONES_POR_MODO[modo][0]

    # El HTML ya nace con el panel y la numeración de la ocasión por defecto. Si se
    # dejara al JS, /celebraciones/ mostraría por un instante las opciones ROMÁNTICAS
    # antes de corregirse — justo el contenido equivocado que la separación evita.
    lleva_color = ocasion_default != 'romantica'
    paso_off = 0 if ocasiones else 1  # sin selector de ocasión todo corre un paso arriba

    context = {
        'modo': modo,
        'copy': COPY[modo],
        'ocasiones': ocasiones,
        'ocasion_default': ocasion_default,
        'default_lleva_color': lleva_color,
        'paso_tina': (4 if lleva_color else 3) - paso_off,
        'paso_choco': (5 if lleva_color else 4) - paso_off,
        'tinas': tinas,  # se serializa con {{ tinas|json_script }} en el template
        'tiene_tinas_cumple': any(t['cumple_ok'] for t in tinas),
        'tiene_tinas_grupo': tiene_tinas_grupo,
        'grupo_min': GRUPO_MIN_PERSONAS,
        'precio_r1': _precio(ROMANTICA_IDS['r1'], FALLBACK['r1']),
        'precio_r2': _precio(ROMANTICA_IDS['r2'], FALLBACK['r2']),
        'precio_cumple_sin': _precio(CUMPLE_IDS[('sin_torta', 'rosado')], FALLBACK['cumple_sin']),
        'precio_cumple_con': _precio(CUMPLE_IDS[('con_torta', 'rosado')], FALLBACK['cumple_con']),
        'precio_chocolates': precio_choco,
        'precio_chocolates_fmt': _clp(precio_choco),
        # Guard de stock: solo se ofrecen si existe la línea Y hay stock real (>0).
        'tiene_chocolates': chocolates_disponibles(),
    }
    return render(request, 'ventas/configurador_velada.html', context)


def experiencia_romantica_view(request):
    """Puerta 1 — sorprender a la pareja (de a dos, con invitación secreta)."""
    return _landing(request, MODO_ROMANTICA)


def celebraciones_view(request):
    """Puerta 2 — cumpleaños (de a dos o en grupo) y despedidas de soltera/o."""
    return _landing(request, MODO_CELEBRACIONES)


def _item_carrito(servicio, fecha, hora, cantidad):
    return {
        'id': servicio.id,
        'nombre': servicio.nombre,
        'precio': float(servicio.precio_base),
        'fecha': fecha,
        'hora': hora,
        'cantidad_personas': cantidad,
        'tipo_servicio': servicio.tipo_servicio,
        'subtotal': float(servicio.precio_base) * cantidad,
    }


def experiencia_romantica_submit(request):
    """POST — arma el carrito (tina + ambientación secreta + chocolates) y va al checkout."""
    if request.method != 'POST':
        # Sin POST no hay ocasión que leer: cae a la puerta por defecto.
        return redirect('experiencia_romantica')

    ocasion = (request.POST.get('ocasion') or 'romantica').strip()
    nivel = (request.POST.get('nivel') or 'r1').strip()          # románticas
    torta = (request.POST.get('torta') or 'sin_torta').strip()   # cumpleaños
    color = (request.POST.get('color') or 'rosado').strip()      # cumpleaños
    tina_id = request.POST.get('tina_id')
    fecha = request.POST.get('fecha')
    hora = request.POST.get('hora')
    quiere_chocolates = request.POST.get('chocolates') in ('1', 'true', 'on', 'True')

    # Puerta a la que vuelve el cliente si algo no valida: la suya, no la otra.
    volver = url_de_ocasion(ocasion)

    if not (tina_id and fecha and hora):
        messages.error(request, "Falta elegir la tina, la fecha y la hora.")
        return redirect(volver)

    try:
        tina = Servicio.objects.get(id=tina_id, tipo_servicio='tina')
    except Servicio.DoesNotExist:
        messages.error(request, "La tina seleccionada no existe.")
        return redirect(volver)

    # Regla de espacio: la ambientación de cumpleaños solo cabe en 3 tinas.
    if ocasion == 'cumpleanos' and not tina_admite_cumple(tina.nombre):
        messages.error(
            request,
            "La ambientación de cumpleaños solo se instala en las tinas "
            "Hornopirén, Osorno o Llaima. Elige una de esas para el cumpleaños.")
        return redirect(volver)

    # Modo grupo (grupo o despedida): tina grupal + N personas (3 … capacidad). Cobra × N.
    personas = PERSONAS_EXPERIENCIA
    if es_ocasion_grupo(ocasion):
        if not tina_admite_grupo(tina.nombre):
            messages.error(request, "Para una celebración de grupo, elige una tina grupal (Calbuco u Osorno).")
            return redirect(volver)
        try:
            personas = int(request.POST.get('personas') or 0)
        except (TypeError, ValueError):
            personas = 0
        cap = int(tina.capacidad_maxima or 0)
        if personas < GRUPO_MIN_PERSONAS or personas > cap:
            messages.error(request, f"Para {tina.nombre}, elige entre {GRUPO_MIN_PERSONAS} y {cap} personas.")
            return redirect(volver)

    amb_id = resolver_ambientacion_id(ocasion, nivel=nivel, torta=torta, color=color)
    ambientacion = _servicio(amb_id)
    if not ambientacion:
        messages.error(request, "No pudimos armar la ambientación elegida. Escríbenos y lo resolvemos.")
        return redirect(volver)

    # Carrito nuevo, en el orden que exige la regla: tina primero.
    cart = {'servicios': [], 'total': 0}

    # 1) Tina — para 2 (románticas/cumpleaños) o para N (grupo): precio_base × personas.
    cart['servicios'].append(_item_carrito(tina, fecha, hora, personas))

    # 2) Ambientación secreta — hereda el slot de la tina.
    cart['servicios'].append(_item_carrito(ambientacion, fecha, hora, 1))

    # 3) Chocolates (opcional) — solo si hay stock real (guard de stock 0).
    if quiere_chocolates:
        chocolates = _chocolates_servicio()
        if chocolates and _stock_chocolates() > 0:
            cart['servicios'].append(_item_carrito(chocolates, fecha, hora, 1))
        elif chocolates:
            messages.info(
                request,
                "Los chocolates se agotaron por hoy; armamos tu velada sin ellos "
                "(puedes agregarlos después escribiéndonos).")

    cart['total'] = sum(i['subtotal'] for i in cart['servicios'])

    request.session['cart'] = cart
    request.session['experiencia_romantica'] = True  # marca para el checkout/invitación
    request.session.modified = True

    return redirect('ventas:cart')
