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

from ..models import VentaReserva, ConfiguracionTips, ConfiguracionResumen
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


def _url_masaje_ficha(token_formulario):
    """URL pública completa de la ficha de bienestar de UN participante de masaje
    (mismo patrón que url_ficha_reserva; la vista 'masaje_ficha' ya existe —
    Conexión-Masajes, whatsapp_agent no la toca)."""
    from django.urls import reverse
    from django.conf import settings
    base = getattr(settings, 'COMANDA_PUBLIC_BASE_URL', 'https://www.aremko.cl')
    return f"{base}{reverse('masaje_ficha', kwargs={'token': token_formulario})}"


def _participantes_masaje_ficha(venta, tipos_venta):
    """Participantes de masaje de la reserva (comprador primero, luego acompañantes),
    con la URL de SU ficha de bienestar y si ya la completaron — para los botones
    de la Ficha de Reserva. Lista vacía si la reserva no tiene masaje."""
    if 'masaje' not in tipos_venta:
        return []
    participantes = sorted(
        venta.participantes_masaje.all(),
        key=lambda p: (0 if p.tipo_participante == 'comprador' else 1, p.id),
    )
    resultado = []
    for p in participantes:
        es_titular = p.tipo_participante == 'comprador'
        resultado.append({
            'es_titular': es_titular,
            'nombre': p.nombre or ('Titular' if es_titular else 'Tu acompañante'),
            'completada': bool(p.ficha_bienestar_id),
            'url': _url_masaje_ficha(p.token_formulario),
        })
    return resultado


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


# F-01 (plan Ficha): medir aperturas de la ficha. Se registra la PRIMERA apertura real
# por reserva como un MovimientoCliente (sin migración), filtrando bots / preview de link
# (WhatsApp, Facebook, etc.) para no inflar la métrica. La bandeja de aremko-cli puede
# leer esto para mostrar "✓ abrió la ficha".
_BOTS_UA = ('bot', 'crawler', 'spider', 'facebookexternalhit', 'whatsapp',
            'preview', 'slurp', 'bingpreview', 'embedly', 'quora link', 'redditbot')


def _registrar_apertura_ficha(request, venta):
    """Registra (una vez por reserva) que el cliente abrió su ficha. Defensivo: nunca
    debe tumbar la ficha ni bloquear su carga."""
    try:
        ua = (request.META.get('HTTP_USER_AGENT') or '').lower()
        if not ua or any(b in ua for b in _BOTS_UA):
            return  # sin UA o bot/preview → no cuenta como apertura del cliente
        if not getattr(venta, 'cliente_id', None):
            return
        from ..models import MovimientoCliente
        ya_abrio = MovimientoCliente.objects.filter(
            venta_reserva=venta, tipo_movimiento='ficha_abierta').exists()
        if ya_abrio:
            return
        MovimientoCliente.objects.create(
            cliente=venta.cliente, venta_reserva=venta,
            tipo_movimiento='ficha_abierta',
            comentarios='El cliente abrió su ficha por primera vez (F-01).')
    except Exception:  # noqa: BLE001 — medir nunca debe romper la ficha
        logger.exception('[ficha] no se pudo registrar apertura (reserva %s)',
                         getattr(venta, 'id', '?'))


def ficha_reserva_cliente(request, token):
    """Ficha de reserva del cliente (solo lectura)."""
    from django.urls import reverse
    venta = _venta_desde_token(token)
    _registrar_apertura_ficha(request, venta)  # F-01: medir aperturas

    estado_label, estado_cls = ESTADO_PAGO_FICHA.get(
        venta.estado_pago, ('Pendiente de pago', 'pen'))

    config_tips = ConfiguracionTips.get_solo()
    try:
        tips_texto = _generar_texto_tips(venta, config_tips)
    except Exception:  # noqa: BLE001 — los tips no deben tumbar la ficha
        logger.exception('[ficha] no se pudieron generar los tips de la reserva %s', venta.id)
        tips_texto = ''

    try:
        config_pago = ConfiguracionResumen.get_solo()
        datos_transferencia = config_pago.datos_transferencia
        pago_nombre = config_pago.nombre_beneficiario
        pago_cuenta = config_pago.numero_cuenta_transferencia
        pago_correo = config_pago.correo_confirmacion_pago
    except Exception:  # noqa: BLE001 — los datos de pago no deben tumbar la ficha
        logger.exception('[ficha] no se pudo obtener datos_transferencia (reserva %s)', venta.id)
        datos_transferencia = pago_nombre = pago_cuenta = pago_correo = ''

    tipos_venta = list(
        venta.reservaservicios.select_related('servicio')
        .values_list('servicio__tipo_servicio', flat=True))

    try:
        participantes_masaje = _participantes_masaje_ficha(venta, tipos_venta)
    except Exception:  # noqa: BLE001 — las fichas de masaje no deben tumbar la ficha
        logger.exception('[ficha] no se pudieron obtener participantes de masaje (reserva %s)', venta.id)
        participantes_masaje = []

    # Invitación sorpresa: si la reserva incluye una ambientación (categoría
    # Ambientaciones), el comprador puede enviarle a su pareja una invitación
    # filtrada (sin precios ni ambientación). Sirve para cualquier método de pago
    # y para reservas creadas por Luna/Deborah — no solo el retorno de Flow.
    invitacion_url = None
    try:
        if venta.reservaservicios.filter(servicio__categoria__nombre__iexact='Ambientaciones').exists():
            from .invitacion_sorpresa_view import url_invitacion_sorpresa
            invitacion_url = url_invitacion_sorpresa(venta.id)
    except Exception:  # noqa: BLE001 — nunca tumbar la ficha por esto
        invitacion_url = None

    # F2-C — "Personaliza tu velada": el comprador elige su bebida incluida (secreta,
    # $0) desde la ficha, solo si hay ambientación y aún no se sirvió.
    bebida_personalizable = False
    bebida_sel = None
    try:
        from ..services.ambientacion_bebidas import bebida_editable, bebida_actual
        if bebida_editable(venta):
            bebida_personalizable = True
            bebida_sel = bebida_actual(venta)
    except Exception:  # noqa: BLE001 — nunca tumbar la ficha por esto
        bebida_personalizable = False

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
        'datos_transferencia': datos_transferencia,
        'pago_nombre': pago_nombre,
        'pago_cuenta': pago_cuenta,
        'pago_correo': pago_correo,
        'maps_url': config_tips.link_google_maps,
        'participantes_masaje': participantes_masaje,
        'comanda_bloqueada': venta.estado_reserva == 'checkout',
        # endpoint que refresca el token de comanda al vuelo y redirige al menú del cliente
        'comanda_url': reverse('ventas:ficha_reserva_comanda', kwargs={'token': token}),
        # pago online del saldo (MP Checkout Pro, hasta 12 cuotas) — Fase 2, 2026-07-06
        'pagar_url': reverse('ventas:ficha_reserva_pagar', kwargs={'token': token}),
        # invitación sorpresa para la pareja (solo si la reserva tiene ambientación)
        'invitacion_url': invitacion_url,
        # F2-C — "Personaliza tu velada" (bebida incluida, secreta, $0)
        'bebida_personalizable': bebida_personalizable,
        'bebida_sel': bebida_sel,
        'personalizar_bebida_url': reverse('ventas:ficha_personalizar_bebida', kwargs={'token': token}),
        'bebida_guardado': request.GET.get('bebida'),
    }
    return render(request, 'ventas/ficha_reserva_cliente.html', context)


def ficha_reserva_pagar(request, token):
    """El cliente paga su saldo online desde la ficha (MP Checkout Pro, cuotas).

    Crea la preferencia al momento del clic (cobra el SALDO vigente, no un
    monto congelado — si Deborah registró un abono entremedio, el link sale
    por lo que realmente falta) y redirige al checkout de Mercado Pago. El
    webhook registra el pago solo (external_reference = reserva). Si no hay
    saldo o MP falla, el cliente vuelve a la ficha — nunca a un error.
    """
    venta = _venta_desde_token(token)
    saldo = float(venta.saldo_pendiente or 0)
    if saldo <= 0:
        return redirect('ventas:ficha_reserva_cliente', token=token)

    from ..services.mercadopago_service import mercadopago_service
    resultado = mercadopago_service.create_payment_link(
        reserva_id=venta.id,
        amount=saldo,
        description=f'Reserva Aremko #{venta.id}',
        customer_email=(venta.cliente.email or '') if venta.cliente else '',
        customer_name=(venta.cliente.nombre or '') if venta.cliente else '',
    )
    if resultado.get('success') and resultado.get('payment_link'):
        return redirect(resultado['payment_link'])

    logger.error('[ficha] no se pudo crear link MP para reserva %s: %s',
                 venta.id, resultado.get('error'))
    return redirect('ventas:ficha_reserva_cliente', token=token)


def _bebida_ids_desde_post(post):
    """Mapea el form de 'Personaliza tu velada' (F2-C) a ids de Producto de bebida.
    La validación final (lista blanca) la hace personalizar_bebida()."""
    from ..services.ambientacion_bebidas import JUGOS, AGUAS, VINO_ID, ESPUMANTE_ID
    tipo = (post.get('bebida') or 'jugos').strip().lower()
    if tipo == 'vino':
        return [VINO_ID]
    if tipo == 'espumante':
        return [ESPUMANTE_ID]
    if tipo == 'aguas':
        gas = (post.get('agua') or 'con_gas').strip().lower()
        gas = gas if gas in AGUAS else 'con_gas'
        return [AGUAS[gas], AGUAS[gas]]  # 2 aguas del tipo elegido
    # jugos (default): 2 sabores de frambuesa/arándano/melón
    j1 = (post.get('jugo_1') or 'frambuesa').strip().lower()
    j2 = (post.get('jugo_2') or 'arandano').strip().lower()
    j1 = j1 if j1 in JUGOS else 'frambuesa'
    j2 = j2 if j2 in JUGOS else 'arandano'
    return [JUGOS[j1], JUGOS[j2]]


def ficha_personalizar_bebida(request, token):
    """F2-C: el comprador elige/cambia su bebida incluida (secreta, $0) desde la ficha.

    La bebida no se cobra (solo mueve inventario el día de la visita) y no aparece
    en la invitación de la pareja, así que se mantiene la sorpresa. Redirige de vuelta
    a la ficha con ?bebida=<estado> para mostrar un aviso."""
    from django.urls import reverse
    venta = _venta_desde_token(token)
    if request.method != 'POST':
        return redirect('ventas:ficha_reserva_cliente', token=token)
    from ..services.ambientacion_bebidas import personalizar_bebida
    try:
        estado = personalizar_bebida(venta, _bebida_ids_desde_post(request.POST))
    except Exception:  # noqa: BLE001 — nunca tumbar la ficha por esto
        logger.exception('[ficha] falló personalizar bebida (reserva %s)', venta.id)
        estado = 'error'
    return redirect(
        reverse('ventas:ficha_reserva_cliente', kwargs={'token': token}) + f'?bebida={estado}')


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
    - cabaña + tina, SIN masaje, 1 noche    → 'Noche de Aguas Calientes' (H-057)
    Devuelve None si no calza un producto con nombre (ej. cabaña+tina de 2+ noches sin
    masaje, o servicios sueltos que no arman ninguno de los 4 programas)."""
    tipos = list(tipos)
    presentes = set(tipos) & {'tina', 'masaje', 'cabana'}
    if presentes == {'tina', 'masaje'}:
        return 'Pausa junto al río'
    if presentes == {'cabana', 'tina', 'masaje'}:
        noches_cabana = sum(1 for t in tipos if t == 'cabana')
        return 'Refugio Aremko' if noches_cabana >= 2 else 'Ritual del Río'
    if presentes == {'cabana', 'tina'}:
        noches_cabana = sum(1 for t in tipos if t == 'cabana')
        return 'Noche de Aguas Calientes' if noches_cabana == 1 else None
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
