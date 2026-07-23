"""
Experiencia Romántica — configurador "sorpresa para tu pareja" (Fase 1, Puerta B).

Landing de tráfico frío (reel / Google Ads): la persona arma una velada romántica
o un cumpleaños sobre una tina, con la ambientación como sorpresa secreta, y
termina en el checkout existente. Post-pago recibe (a) el comprobante completo y
(b) una invitación filtrada para enviarle a su pareja (ver invitacion_sorpresa_view).

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

from ..models import Servicio


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

# Precios de respaldo por si faltara un SKU en la BD (no deberían usarse en prod).
FALLBACK = {'r1': 32000, 'r2': 68000, 'cumple_sin': 38000, 'cumple_con': 78000, 'choco': 16000}


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
    if ocasion == 'cumpleanos':
        clave = ((torta or 'sin_torta').lower(), (color or 'rosado').lower())
        return CUMPLE_IDS.get(clave)
    return None


def tina_admite_cumple(nombre_tina):
    """True si la tina tiene espacio para una ambientación de cumpleaños."""
    n = _norm(nombre_tina)
    return any(c in n for c in CUMPLE_TINAS)


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


def _tinas_configurador():
    """
    Tinas candidatas: las de pareja (capacidad ≤ 2, sin add-ons de niño) MÁS
    las 3 tinas de cumpleaños (que incluyen Osorno, grupal). Cada una viene
    marcada con dónde califica: `romantica_ok` (cualquier tina de pareja) y
    `cumple_ok` (solo Hornopirén/Osorno/Llaima). El front filtra según la ocasión.
    """
    filtro = Q(capacidad_maxima__lte=2)
    for n in CUMPLE_TINAS:
        filtro |= Q(nombre__icontains=n)
    qs = Servicio.objects.filter(
        tipo_servicio='tina', activo=True, publicado_web=True,
    ).filter(filtro).exclude(
        nombre__icontains='niño').exclude(nombre__icontains='nino').order_by('precio_base', 'nombre')

    tinas = []
    for t in qs:
        # Precio mostrado = plano por capacidad_maxima (AR-014), igual que en /tinas/.
        total = int(t.precio_base) * t.capacidad_maxima
        tinas.append({
            'id': t.id,
            'nombre': t.nombre,
            'capacidad': t.capacidad_maxima,
            'total': total,
            'total_fmt': _clp(total),
            'romantica_ok': t.capacidad_maxima <= 2,
            'cumple_ok': tina_admite_cumple(t.nombre),
        })
    return tinas


def experiencia_romantica_view(request):
    """GET — renderiza el configurador."""
    tinas = _tinas_configurador()
    chocolates = _chocolates_servicio()
    precio_choco = int(chocolates.precio_base) if chocolates else FALLBACK['choco']

    context = {
        'tinas': tinas,  # se serializa con {{ tinas|json_script }} en el template
        'tiene_tinas_cumple': any(t['cumple_ok'] for t in tinas),
        'precio_r1': _precio(ROMANTICA_IDS['r1'], FALLBACK['r1']),
        'precio_r2': _precio(ROMANTICA_IDS['r2'], FALLBACK['r2']),
        'precio_cumple_sin': _precio(CUMPLE_IDS[('sin_torta', 'rosado')], FALLBACK['cumple_sin']),
        'precio_cumple_con': _precio(CUMPLE_IDS[('con_torta', 'rosado')], FALLBACK['cumple_con']),
        'precio_chocolates': precio_choco,
        'precio_chocolates_fmt': _clp(precio_choco),
        'tiene_chocolates': chocolates is not None,
    }
    return render(request, 'ventas/experiencia_romantica.html', context)


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
        return redirect('experiencia_romantica')

    ocasion = (request.POST.get('ocasion') or 'romantica').strip()
    nivel = (request.POST.get('nivel') or 'r1').strip()          # románticas
    torta = (request.POST.get('torta') or 'sin_torta').strip()   # cumpleaños
    color = (request.POST.get('color') or 'rosado').strip()      # cumpleaños
    tina_id = request.POST.get('tina_id')
    fecha = request.POST.get('fecha')
    hora = request.POST.get('hora')
    quiere_chocolates = request.POST.get('chocolates') in ('1', 'true', 'on', 'True')

    if not (tina_id and fecha and hora):
        messages.error(request, "Falta elegir la tina, la fecha y la hora.")
        return redirect('experiencia_romantica')

    try:
        tina = Servicio.objects.get(id=tina_id, tipo_servicio='tina')
    except Servicio.DoesNotExist:
        messages.error(request, "La tina seleccionada no existe.")
        return redirect('experiencia_romantica')

    # Regla de espacio: la ambientación de cumpleaños solo cabe en 3 tinas.
    if ocasion == 'cumpleanos' and not tina_admite_cumple(tina.nombre):
        messages.error(
            request,
            "La ambientación de cumpleaños solo se instala en las tinas "
            "Hornopirén, Osorno o Llaima. Elige una de esas para el cumpleaños.")
        return redirect('experiencia_romantica')

    amb_id = resolver_ambientacion_id(ocasion, nivel=nivel, torta=torta, color=color)
    ambientacion = _servicio(amb_id)
    if not ambientacion:
        messages.error(request, "No pudimos armar la ambientación elegida. Escríbenos y lo resolvemos.")
        return redirect('experiencia_romantica')

    # Carrito nuevo, en el orden que exige la regla: tina primero.
    cart = {'servicios': [], 'total': 0}

    # 1) Tina — precio plano por capacidad_maxima (AR-014).
    cart['servicios'].append(_item_carrito(tina, fecha, hora, tina.capacidad_maxima))

    # 2) Ambientación secreta — hereda el slot de la tina.
    cart['servicios'].append(_item_carrito(ambientacion, fecha, hora, 1))

    # 3) Chocolates (opcional) — misma categoría, mismo slot.
    if quiere_chocolates:
        chocolates = _chocolates_servicio()
        if chocolates:
            cart['servicios'].append(_item_carrito(chocolates, fecha, hora, 1))

    cart['total'] = sum(i['subtotal'] for i in cart['servicios'])

    request.session['cart'] = cart
    request.session['experiencia_romantica'] = True  # marca para el checkout/invitación
    request.session.modified = True

    return redirect('ventas:cart')
