"""
Experiencia Romántica — configurador "sorpresa para tu pareja" (Fase 1, Puerta B).

Landing de tráfico frío (reel / Google Ads): la persona arma una noche romántica
o de cumpleaños sobre una tina, con la ambientación como sorpresa secreta, y
termina en el checkout existente. Post-pago recibe (a) el comprobante completo y
(b) una invitación filtrada para enviarle a su pareja (ver invitacion_sorpresa_view).

Reutiliza el carrito de sesión y el checkout ya probados: este módulo solo arma el
carrito en el orden correcto (tina primero; la ambientación hereda su slot) y
redirige a la página de carrito.
"""
import unicodedata

from django.contrib import messages
from django.shortcuts import render, redirect

from ..models import Servicio


NOMBRE_CHOCOLATES = 'Caja de chocolates'


def _norm(texto):
    """minúsculas sin acentos, para matchear nombres de SKU de forma robusta."""
    t = (texto or '').lower()
    t = unicodedata.normalize('NFKD', t)
    return ''.join(c for c in t if not unicodedata.combining(c))


def resolver_ambientacion(ocasion, color, ambientacion_servicios):
    """
    Mapea (ocasión, color) → uno de los 4 SKUs reales de decoración.

    ocasion: 'romantica' (Decoración Simple) | 'cumpleanos' (Decoración Cumpleaños con Torta)
    color:   'azul' | 'rosado'
    ambientacion_servicios: iterable de Servicio de la categoría Ambientaciones.

    Solo considera los SKUs cuyo nombre contiene 'decoracion' (excluye la Caja de
    chocolates, que vive en la misma categoría). Devuelve el Servicio o None.
    """
    candidatos = [s for s in ambientacion_servicios if 'decoracion' in _norm(s.nombre)]
    want_cumple = (ocasion == 'cumpleanos')
    color_n = _norm(color)

    # 1) match exacto ocasión + color
    for s in candidatos:
        n = _norm(s.nombre)
        if ('cumple' in n) == want_cumple and color_n and color_n in n:
            return s
    # 2) fallback: solo por ocasión (si faltara la variante de color)
    for s in candidatos:
        n = _norm(s.nombre)
        if ('cumple' in n) == want_cumple:
            return s
    return None


def _ambientacion_qs():
    return Servicio.objects.filter(
        categoria__nombre__iexact='Ambientaciones', activo=True,
    )


def experiencia_romantica_view(request):
    """GET — renderiza el configurador."""
    ambientaciones = list(_ambientacion_qs())

    # Precios reales para el total en vivo (con fallback defensivo por si falta un SKU).
    romantica = resolver_ambientacion('romantica', 'rosado', ambientaciones)
    cumple = resolver_ambientacion('cumpleanos', 'rosado', ambientaciones)
    chocolates = next((s for s in ambientaciones if _norm(s.nombre) == _norm(NOMBRE_CHOCOLATES)), None)

    # Tinas para 2 (las de pareja) — excluye add-ons de niño (capacidad 1).
    tinas_qs = Servicio.objects.filter(
        tipo_servicio='tina', activo=True, publicado_web=True,
        capacidad_maxima__gte=2,
    ).order_by('precio_base', 'nombre')
    # Precio mostrado = plano por capacidad_maxima (AR-014), igual que en /tinas/.
    tinas = [{
        'id': t.id,
        'nombre': t.nombre,
        'capacidad': t.capacidad_maxima,
        'total': int(t.precio_base) * t.capacidad_maxima,
    } for t in tinas_qs]

    context = {
        'tinas': tinas,
        'precio_romantica': int(romantica.precio_base) if romantica else 38000,
        'precio_cumple': int(cumple.precio_base) if cumple else 78000,
        'precio_chocolates': int(chocolates.precio_base) if chocolates else 15000,
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
    color = (request.POST.get('color') or 'rosado').strip()
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

    ambientaciones = list(_ambientacion_qs())
    ambientacion = resolver_ambientacion(ocasion, color, ambientaciones)
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
        chocolates = next(
            (s for s in ambientaciones if _norm(s.nombre) == _norm(NOMBRE_CHOCOLATES)), None
        )
        if chocolates:
            cart['servicios'].append(_item_carrito(chocolates, fecha, hora, 1))

    cart['total'] = sum(i['subtotal'] for i in cart['servicios'])

    request.session['cart'] = cart
    request.session['experiencia_romantica'] = True  # marca para el checkout/invitación
    request.session.modified = True

    return redirect('ventas:cart')
