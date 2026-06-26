"""Ficha de Reserva del cliente (Reserva-cliente-digital) — Fase 1, solo lectura.

Página móvil con link tokenizado que el cliente abre para ver su reserva:
- Cabecera con N° de reserva + estado de pago (Pendiente / Parcialmente pagada / Pagada).
- Botón 1: Servicios contratados (lista viva, solo lectura).
- Botón 2: Tips (reusa el texto compacto de tips_reserva_view).
- Botón 3: Comanda digital → abre el sistema de comanda que YA existe. Se bloquea
  cuando el recepcionista pone la reserva en estado 'checkout'.

El token es FIRMADO (django.core.signing), no adivinable y sin migración: deriva del
SECRET_KEY, así nadie ve la reserva de otro cambiando el id en la URL.
"""

import logging

from django.core import signing
from django.http import Http404
from django.shortcuts import render, redirect

from ..models import VentaReserva, ConfiguracionTips
from .tips_reserva_view import _generar_texto_tips

logger = logging.getLogger(__name__)

FICHA_SALT = 'ficha-reserva-cliente-v1'
COTIZACION_SALT = 'cotizacion-cliente-v1'

def _clp(n):
    """Formatea un monto CLP con puntos de miles y signo: 210000 -> '$210.000', -30000 -> '−$30.000'."""
    n = int(n or 0)
    s = f"{abs(n):,}".replace(',', '.')
    return f"−${s}" if n < 0 else f"${s}"


ESTADO_PAGO_FICHA = {
    'pendiente': ('Pendiente de pago', 'pen'),
    'parcial':   ('Parcialmente pagada', 'par'),
    'pagado':    ('Pagada', 'pag'),
    'cancelado': ('Cancelada', 'can'),
}


def token_para_reserva(venta_id):
    """Token firmado (no adivinable) para la ficha de una reserva."""
    return signing.dumps(int(venta_id), salt=FICHA_SALT)


def url_ficha_reserva(venta_id):
    """URL pública completa de la ficha (para el admin / cajón)."""
    from django.urls import reverse
    from django.conf import settings
    base = getattr(settings, 'COMANDA_PUBLIC_BASE_URL', 'https://www.aremko.cl')
    return f"{base}{reverse('ventas:ficha_reserva_cliente', kwargs={'token': token_para_reserva(venta_id)})}"


def _venta_desde_token(token):
    """VentaReserva desde el token firmado, o Http404 si el token es inválido."""
    try:
        venta_id = signing.loads(token, salt=FICHA_SALT)
    except signing.BadSignature:
        raise Http404('Link inválido')
    venta = (VentaReserva.objects
             .select_related('cliente')
             .filter(id=venta_id)
             .first())
    if venta is None:
        raise Http404('Reserva no encontrada')
    return venta


def _lineas_servicios(venta):
    """Servicios + productos de la reserva como líneas para mostrar (solo lectura)."""
    lineas = []
    for rs in venta.reservaservicios.select_related('servicio').all():
        precio = rs.precio_unitario_venta if rs.precio_unitario_venta is not None else (rs.servicio.precio_base or 0)
        cant = rs.cantidad_personas or 1
        subtotal = int(precio) * cant
        nombre = rs.servicio.nombre
        es_descuento = subtotal < 0 or 'descuento' in (nombre or '').lower()
        lineas.append({
            # La línea de ajuste se muestra limpia ("Descuento"), sin el nombre crudo
            # ("Descuento_Servicios") ni su fecha/hora de relleno.
            'nombre': 'Descuento' if es_descuento else nombre,
            'fecha': None if es_descuento else rs.fecha_agendamiento,
            'hora': None if es_descuento else rs.hora_inicio,
            'monto_str': _clp(subtotal),
            'es_descuento': es_descuento,
        })
    for rp in venta.reservaproductos.select_related('producto').all():
        precio = rp.precio_unitario_venta if rp.precio_unitario_venta is not None else (rp.producto.precio_base or 0)
        cant = rp.cantidad or 1
        lineas.append({
            'nombre': rp.producto.nombre,
            'fecha': None,
            'hora': None,
            'monto_str': _clp(int(precio) * cant),
            'es_descuento': False,
            'es_producto': True,
            'cantidad': cant,
        })
    return lineas


def ficha_reserva_cliente(request, token):
    """Ficha de reserva del cliente (solo lectura)."""
    from django.urls import reverse
    venta = _venta_desde_token(token)

    estado_label, estado_cls = ESTADO_PAGO_FICHA.get(
        venta.estado_pago, ('Pendiente de pago', 'pen'))

    try:
        tips_texto = _generar_texto_tips(venta, ConfiguracionTips.get_solo())
    except Exception:  # noqa: BLE001 — los tips no deben tumbar la ficha
        logger.exception('[ficha] no se pudieron generar los tips de la reserva %s', venta.id)
        tips_texto = ''

    tipos_venta = list(
        venta.reservaservicios.select_related('servicio')
        .values_list('servicio__tipo_servicio', flat=True))
    context = {
        'venta': venta,
        'numero': venta.id,
        'cliente': venta.cliente,
        'estado_label': estado_label,
        'estado_cls': estado_cls,
        'experiencia_nombre': _experiencia_nombre(tipos_venta),
        'lineas': _lineas_servicios(venta),
        'total_str': _clp(venta.total),
        'pagado_str': _clp(venta.pagado),
        'saldo': int(venta.saldo_pendiente or 0),
        'saldo_str': _clp(venta.saldo_pendiente),
        'tips_texto': tips_texto,
        'comanda_bloqueada': venta.estado_reserva == 'checkout',
        # endpoint que refresca el token de comanda al vuelo y redirige al menú del cliente
        'comanda_url': reverse('ventas:ficha_reserva_comanda', kwargs={'token': token}),
    }
    return render(request, 'ventas/ficha_reserva_cliente.html', context)


def _obtener_o_crear_comanda(venta):
    """Comanda borrador del cliente con token válido (refresca/crea si hace falta).
    Espeja la lógica del admin (generar_link_comanda_ajax) para no duplicar criterios."""
    from django.contrib.auth import get_user_model
    from ..models import Comanda

    comanda = Comanda.objects.filter(
        venta_reserva=venta,
        token_acceso__isnull=False,
        creada_por_cliente=True,
    ).first()
    if comanda and comanda.es_link_valido():
        return comanda
    if comanda:
        comanda.generar_token_acceso()
        return comanda
    User = get_user_model()
    usuario = (User.objects.filter(username='Deborah').first()
               or User.objects.filter(is_superuser=True).first())
    comanda = Comanda.objects.create(
        venta_reserva=venta,
        estado='borrador',
        creada_por_cliente=True,
        usuario_solicita=usuario,
    )
    comanda.generar_token_acceso()
    return comanda


def ficha_comanda(request, token):
    """Botón 3: lleva a la comanda del cliente (la que ya existe), refrescando el
    token al vuelo. Bloqueada una vez hecho el checkout (regla de Jorge)."""
    venta = _venta_desde_token(token)
    if venta.estado_reserva == 'checkout':
        # Ya hizo checkout: la comanda queda cerrada, se vuelve a la ficha.
        return redirect('ventas:ficha_reserva_cliente', token=token)
    comanda = _obtener_o_crear_comanda(venta)
    return redirect(comanda.obtener_url_cliente())


# ── Cotización del cliente (Fase 3): la Ficha en modo cotización + botón Aprobar ──

def token_para_cotizacion(propuesta_id):
    """Token firmado (no adivinable) para la cotización de una propuesta."""
    return signing.dumps(str(propuesta_id), salt=COTIZACION_SALT)


def url_cotizacion(propuesta_id):
    """URL pública completa de la cotización (para el cajón / admin)."""
    from django.urls import reverse
    from django.conf import settings
    base = getattr(settings, 'COMANDA_PUBLIC_BASE_URL', 'https://www.aremko.cl')
    return f"{base}{reverse('ventas:cotizacion_cliente', kwargs={'token': token_para_cotizacion(propuesta_id)})}"


def _propuesta_desde_token(token):
    """PropuestaReserva desde el token firmado, o Http404."""
    from whatsapp_agent.models import PropuestaReserva
    try:
        propuesta_id = signing.loads(token, salt=COTIZACION_SALT)
    except signing.BadSignature:
        raise Http404('Link inválido')
    propuesta = PropuestaReserva.objects.filter(propuesta_id=propuesta_id).first()
    if propuesta is None:
        raise Http404('Cotización no encontrada')
    return propuesta


def _lineas_desde_payload(servicios_data):
    """Líneas de la cotización a partir del payload de la propuesta (servicio_id → nombre/precio)."""
    import datetime as _dt
    from ..models import Servicio
    lineas = []
    for sd in (servicios_data or []):
        s = Servicio.objects.filter(id=sd.get('servicio_id')).first()
        if s is None:
            continue
        cant = int(sd.get('cantidad_personas') or 1)
        subtotal = int(s.precio_base or 0) * cant
        nombre = s.nombre
        es_descuento = subtotal < 0 or 'descuento' in (nombre or '').lower()
        fecha = None
        if not es_descuento and sd.get('fecha'):
            try:
                fecha = _dt.datetime.strptime(sd['fecha'], '%Y-%m-%d').date()
            except (ValueError, TypeError):
                fecha = None
        lineas.append({
            'nombre': 'Descuento' if es_descuento else nombre,
            'fecha': fecha,
            'hora': None if es_descuento else sd.get('hora'),
            'monto_str': _clp(subtotal),
            'subtotal_num': subtotal,
            'es_descuento': es_descuento,
        })
    return lineas


def _experiencia_nombre(tipos):
    """Nombre de la EXPERIENCIA según los tipos de servicio (lista, con duplicados), para que el
    cliente vea una experiencia identificable y no 'servicios sueltos':
    - tina + masaje (sin cabaña)            → 'Pausa junto al río'
    - cabaña + tina + masaje, 1 noche       → 'Ritual del Río'
    - cabaña + tina + masaje, 2+ noches     → 'Refugio Aremko'
    Devuelve None si no calza un producto con nombre."""
    tipos = list(tipos)
    presentes = set(tipos) & {'tina', 'masaje', 'cabana'}
    if presentes == {'tina', 'masaje'}:
        return 'Pausa junto al río'
    if presentes == {'cabana', 'tina', 'masaje'}:
        noches_cabana = sum(1 for t in tipos if t == 'cabana')
        return 'Refugio Aremko' if noches_cabana >= 2 else 'Ritual del Río'
    return None


def _tipos_desde_payload(servicios_data):
    """Lista de tipo_servicio de los servicios del payload (con duplicados, p.ej. cabaña 2 veces
    en el Refugio → para distinguir Ritual de Refugio)."""
    from ..models import Servicio
    ids = [sd.get('servicio_id') for sd in (servicios_data or []) if sd.get('servicio_id')]
    tipo_por_id = dict(Servicio.objects.filter(id__in=ids).values_list('id', 'tipo_servicio'))
    return [tipo_por_id[sd['servicio_id']] for sd in (servicios_data or [])
            if sd.get('servicio_id') in tipo_por_id]


def _descuento_pack_de_payload(servicios_data):
    """Descuento del pack (CLP) para los servicios de la propuesta. Fuente única:
    PackDescuentoService.descuento_para_servicios (arma el carrito como espera el motor —
    masajes por persona— igual que la propuesta y la creación de la reserva)."""
    from ..services.pack_descuento_service import PackDescuentoService
    try:
        return PackDescuentoService.descuento_para_servicios(servicios_data)
    except Exception:  # noqa: BLE001 — sin descuento si el motor falla
        logger.exception('[cotización] no se pudo calcular el descuento de pack')
        return 0


def _lineas_productos_payload(productos_data):
    """Líneas de PRODUCTOS (tablas, jugos) de la propuesta, para que la cotización los muestre
    y el total cuadre con propuesta.total (que ya los incluye)."""
    from ..models import Producto
    lineas = []
    for pd in (productos_data or []):
        p = Producto.objects.filter(id=pd.get('producto_id')).first()
        if p is None:
            continue
        cant = int(pd.get('cantidad') or 1)
        subtotal = int(p.precio_base or 0) * cant
        lineas.append({
            'nombre': p.nombre, 'fecha': None, 'hora': None,
            'monto_str': _clp(subtotal), 'subtotal_num': subtotal,
            'es_descuento': False, 'es_producto': True, 'cantidad': cant,
        })
    return lineas


def _cotizacion_lineas_total(propuesta):
    """Líneas + total de la cotización (servicios + productos). Si los servicios NO traen ya una
    línea de descuento (caso pack de ciudad), aplica el descuento del pack para que el total = el
    de la reserva final. El Ritual/Refugio ya traen su línea de descuento en el payload → no se
    duplica. Los productos suman al total (igual que en propuesta.total)."""
    payload = propuesta.payload or {}
    servicios_data = payload.get('servicios', [])
    lineas = _lineas_desde_payload(servicios_data)
    lineas += _lineas_productos_payload(payload.get('productos', []))
    if not any(l['es_descuento'] for l in lineas):
        descuento = _descuento_pack_de_payload(servicios_data)
        if descuento > 0:
            lineas.append({
                'nombre': 'Descuento', 'fecha': None, 'hora': None,
                'monto_str': _clp(-descuento), 'subtotal_num': -descuento, 'es_descuento': True,
            })
    total = sum(l.get('subtotal_num', 0) for l in lineas)
    return lineas, _clp(total)


def cotizacion_cliente(request, token):
    """Cotización del cliente (Ficha en modo cotización + botón Aprobar)."""
    from django.urls import reverse
    propuesta = _propuesta_desde_token(token)

    # Si la propuesta ya se transformó en reserva, mandamos directo a la Ficha.
    if propuesta.estado == 'creada' and propuesta.reserva_id:
        return redirect('ventas:ficha_reserva_cliente',
                        token=token_para_reserva(propuesta.reserva_id))

    payload = propuesta.payload or {}
    cliente_data = payload.get('cliente', {}) or {}
    lineas, total_str = _cotizacion_lineas_total(propuesta)
    context = {
        'es_cotizacion': True,
        'cliente_nombre': (cliente_data.get('nombre') or '').split(' ')[0],
        'experiencia_nombre': _experiencia_nombre(_tipos_desde_payload(payload.get('servicios', []))),
        'lineas': lineas,
        'total_str': total_str,
        'vigente': propuesta.esta_vigente(),
        'aprobar_url': reverse('ventas:aprobar_cotizacion', kwargs={'token': token}),
    }
    return render(request, 'ventas/ficha_reserva_cliente.html', context)


def aprobar_cotizacion(request, token):
    """Botón Aprobar: crea la reserva REUSANDO el endpoint crear_reserva (idempotente,
    el mismo que usa Deborah) y redirige a la Ficha. No modifica el camino de creación."""
    from rest_framework.test import APIRequestFactory, force_authenticate
    from django.contrib.auth import get_user_model
    from django.urls import reverse
    from .luna_api_views import crear_reserva

    propuesta = _propuesta_desde_token(token)
    aprobar_url = reverse('ventas:aprobar_cotizacion', kwargs={'token': token})

    # Idempotente: si ya se creó, a la Ficha.
    if propuesta.estado == 'creada' and propuesta.reserva_id:
        return redirect('ventas:ficha_reserva_cliente',
                        token=token_para_reserva(propuesta.reserva_id))

    if request.method != 'POST':
        return redirect('ventas:cotizacion_cliente', token=token)

    # Llamada interna a crear_reserva con propuesta_id (bypass de la API key vía force_authenticate).
    factory = APIRequestFactory()
    api_req = factory.post('/api/luna/reservas/create/',
                           {'propuesta_id': propuesta.propuesta_id}, format='json')
    User = get_user_model()
    sysuser = (User.objects.filter(username='Deborah').first()
               or User.objects.filter(is_superuser=True).first())
    if sysuser is not None:
        force_authenticate(api_req, user=sysuser)
    resp = crear_reserva(api_req)

    data = getattr(resp, 'data', {}) or {}
    if getattr(resp, 'status_code', 500) in (200, 201) and data.get('success'):
        reserva_id = (data.get('reserva') or {}).get('id')
        if reserva_id:
            return redirect('ventas:ficha_reserva_cliente',
                            token=token_para_reserva(reserva_id))

    logger.error('[cotización] Aprobar falló para propuesta %s: %s',
                 propuesta.propuesta_id[:8], data.get('mensaje'))
    lineas, total_str = _cotizacion_lineas_total(propuesta)
    return render(request, 'ventas/ficha_reserva_cliente.html', {
        'es_cotizacion': True,
        'error_aprobar': data.get('mensaje') or 'No se pudo crear la reserva. Te contactamos a la brevedad.',
        'lineas': lineas,
        'total_str': total_str,
        'aprobar_url': aprobar_url,
    }, status=400)
