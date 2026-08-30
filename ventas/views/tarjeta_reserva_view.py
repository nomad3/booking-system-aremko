"""Tarjeta de Reserva — la reserva en el celular (Fase 1: lectura + copiar Pase).

El admin de Django es insufrible en un teléfono: tablas anchas, selects
diminutos, y cada guardado reenvía y revalida el formulario COMPLETO con todos
sus inlines. Esta tarjeta es la alternativa móvil: una pantalla liviana, la
plata primero, y botones que hacen UNA cosa cada uno.

Fase 1 (Jorge, 2026-08-30): lectura + botón que COPIA el mensaje del Pase sin
mostrarlo — Deborah lo pega en el cajón de la bandeja omnicanal.
Fase 2 (2026-08-30): agregar pago con guardado chico (tarjeta_agregar_pago).
Fase 3 (2026-08-30): agregar producto (tarjeta_agregar_producto).
Fase 4 (2026-08-30): agregar servicio — SIN código nuevo de disponibilidad: la
tarjeta abre calendario_seleccion (el mismo del admin) en un overlay y define
window.servicioAgregado, el protocolo que ese calendario ya habla. Todo vive
en la plantilla.
Fase 5 (2026-08-30): crear reserva con datos mínimos (nueva_reserva) — el
teléfono manda: se normaliza con Cliente.normalize_phone y si el cliente ya
existe se usa SU ficha, sin pisarle el nombre. Y datos complementarios
(comentarios + documento fiscal) colapsados, con guardado chico
(tarjeta_editar_datos). Las cinco fases del boceto de Jorge quedan completas.
Fase 6 (2026-08-30): editar la cantidad de personas tocando la línea del
servicio. La guarda es el contrato del propio admin («Para cabañas: cantidad
de cabañas (siempre 1). Para tinas: cantidad de personas»): las CABAÑAS se
bloquean —ahí cantidad multiplica el precio completo de la cabaña— y tinas y
masajes se editan, porque su valor unitario ES por persona. OJO: la lista
TINAS_PRECIO_PLANO del checkout NO sirve de vara acá — nombra a todas las
tinas reales (puyehue, villarrica…) porque gobierna el precio de la VITRINA
web, y usarla dejaría la fase inútil para su primer caso de uso.

La vista es deliberadamente liviana: tres queries con select_related y ningún
cálculo — total/pagado/saldo son campos almacenados. Nada de ficha 360.
"""
from __future__ import annotations

import logging

from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from ventas.models import Cliente, Pago, Producto, ReservaProducto, VentaReserva
from ventas.views.ficha_reserva_view import mensaje_pase

logger = logging.getLogger(__name__)

# Los medios de pago que ofrece la tarjeta son LOS DEL MODELO — ya hay 22
# códigos repetidos en 5 lugares del sistema y no va a haber una sexta copia.
# Se excluyen solo dos, por semántica:
#   · giftcard — Pago.save() exige el objeto GiftCard y valida su saldo y
#     vencimiento; desde la tarjeta no se elige una giftcard. Eso es del admin.
#   · descuento — no es plata que entró: actualizar_saldo() lo excluye del
#     pagado. Registrarlo como "pago" desde el celular cuadraría caja de mentira.
METODOS_PAGO_TARJETA = tuple(
    (codigo, nombre) for codigo, nombre in Pago.METODOS_PAGO
    if codigo not in ('giftcard', 'descuento'))


def staff_required(view_func):
    """Decorador para requerir que el usuario sea staff."""
    decorated_view = user_passes_test(lambda u: u.is_staff)(view_func)
    return login_required(decorated_view)


@staff_required
def tarjeta_reserva(request, venta_id):
    venta = get_object_or_404(
        VentaReserva.objects.select_related('cliente'), pk=venta_id)

    servicios = list(venta.reservaservicios.select_related('servicio').order_by(
        'fecha_agendamiento', 'hora_inicio', 'id'))
    # Qué líneas pueden editar personas desde la tarjeta: todas menos las
    # cabañas. En una cabaña, "cantidad" son cabañas (siempre 1) y tocarla
    # multiplica el precio completo; en tinas y masajes el valor unitario ES
    # por persona, así que editar personas es exactamente lo que corresponde.
    for r in servicios:
        r.editable = r.servicio.tipo_servicio != 'cabana'
    productos = venta.reservaproductos.select_related('producto')
    pagos = venta.pagos.order_by('fecha_pago')

    # Catálogo para el selector: LA MISMA función que usa el admin al agregar
    # productos a una reserva (productos_vendibles: menú de comanda del
    # cliente + venta en mesón, con stock). La primera versión filtró solo
    # venta_meson y era estrecha por el otro lado: los productos del menú del
    # cliente (jugos) habrían desaparecido de la tarjeta — lo destapó Jorge
    # preguntando si eran los mismos productos que en el admin.
    from ventas.admin import productos_vendibles

    catalogo = productos_vendibles()

    return render(request, 'ventas/tarjeta_reserva.html', {
        'venta': venta,
        'servicios': servicios,
        'productos': productos,
        'pagos': pagos,
        'mensaje_pase': mensaje_pase(venta),
        'debe': int(venta.saldo_pendiente or 0) > 0,
        'metodos_pago': METODOS_PAGO_TARJETA,
        'catalogo': catalogo,
    })


@staff_required
@require_POST
def tarjeta_agregar_pago(request, venta_id):
    """Crea UN pago y devuelve los totales frescos. Nada más.

    Éste es el corazón de la fase 2: en el admin, registrar un pago reenvía y
    revalida el formulario COMPLETO con todos sus inlines — por eso es lento.
    Acá es un POST chico: un insert, y el recálculo de totales que Pago.save()
    ya hace solo (llama a calcular_total()).

    Falla con mensaje, nunca con un 500 pelado: quien está al otro lado es
    Deborah con un cliente al frente.
    """
    venta = get_object_or_404(VentaReserva, pk=venta_id)

    # Deborah escribe "$60.000" o "60000": se aceptan las dos. Puntos y $ se
    # limpian; lo que quede tiene que ser un número entero de pesos.
    crudo = (request.POST.get('monto') or '').strip()
    limpio = crudo.replace('$', '').replace('.', '').replace(' ', '')
    if not limpio.isdigit() or int(limpio) <= 0:
        return JsonResponse(
            {'ok': False, 'mensaje': 'Monto inválido. Escribe solo el número, ej: 30000.'},
            status=400)
    monto = int(limpio)

    metodo = (request.POST.get('metodo_pago') or '').strip()
    if metodo not in {codigo for codigo, _ in METODOS_PAGO_TARJETA}:
        return JsonResponse({'ok': False, 'mensaje': 'Método de pago no válido.'},
                            status=400)

    try:
        pago = Pago.objects.create(venta_reserva=venta, monto=monto,
                                   metodo_pago=metodo, usuario=request.user)
    except Exception as exc:  # noqa: BLE001
        logger.exception('[tarjeta] no se pudo crear el pago de $%s (%s) para la '
                         'reserva %s: %s', monto, metodo, venta_id, exc)
        return JsonResponse({'ok': False, 'mensaje': 'No se pudo guardar el pago. '
                             'Inténtalo desde el admin.'}, status=400)

    venta.refresh_from_db()
    return JsonResponse({
        'ok': True,
        'total': int(venta.total or 0),
        'pagado': int(venta.pagado or 0),
        'saldo': int(venta.saldo_pendiente or 0),
        'pago': {
            'monto': int(pago.monto),
            'metodo': pago.get_metodo_pago_display(),
            'hora': timezone.localtime(pago.fecha_pago).strftime('%d/%m %H:%M'),
        },
    })


@staff_required
@require_POST
def tarjeta_agregar_producto(request, venta_id):
    """Agrega UN producto a la reserva y devuelve los totales frescos.

    Dos reglas del negocio que este endpoint respeta y no reinventa:

    · El stock se descuenta al ENTREGAR, no al vender: la señal
      actualizar_inventario solo toca inventario cuando la línea tiene
      fecha_entrega. Acá se crea SIN fecha (vendido, no entregado) — igual
      que el admin. La validación de stock de más abajo es la misma guarda
      que agregar_producto(): no vender lo que no hay.

    · El precio se CONGELA al momento de la venta (precio_unitario_venta):
      si mañana el catálogo sube, lo ya vendido no cambia. Es el propósito
      documentado del campo.
    """
    venta = get_object_or_404(VentaReserva, pk=venta_id)

    try:
        producto = Producto.objects.get(pk=request.POST.get('producto_id'))
    except (Producto.DoesNotExist, ValueError, TypeError):
        return JsonResponse({'ok': False, 'mensaje': 'Elige un producto de la lista.'},
                            status=400)

    # El mismo criterio que el selector (productos_vendibles del admin): lo
    # que no es vendible por el personal no entra ni desde una pestaña
    # desactualizada. Esos productos se manejan en el admin.
    if not (producto.venta_meson or producto.comanda_cliente):
        return JsonResponse(
            {'ok': False, 'mensaje': f'{producto.nombre} no es de venta al '
                                     'cliente: se agrega desde el admin.'},
            status=400)

    crudo = (request.POST.get('cantidad') or '').strip()
    if not crudo.isdigit() or int(crudo) < 1:
        return JsonResponse({'ok': False, 'mensaje': 'Cantidad inválida.'}, status=400)
    cantidad = int(crudo)

    if cantidad > producto.cantidad_disponible:
        return JsonResponse(
            {'ok': False, 'mensaje': f'Queda(n) {producto.cantidad_disponible} '
                                     f'de {producto.nombre}.'},
            status=400)

    try:
        linea = ReservaProducto.objects.create(
            venta_reserva=venta, producto=producto, cantidad=cantidad,
            precio_unitario_venta=producto.precio_base)
        venta.calcular_total()
    except Exception as exc:  # noqa: BLE001
        logger.exception('[tarjeta] no se pudo agregar %sx producto %s a la '
                         'reserva %s: %s', cantidad, producto.pk, venta_id, exc)
        return JsonResponse({'ok': False, 'mensaje': 'No se pudo agregar el producto. '
                             'Inténtalo desde el admin.'}, status=400)

    venta.refresh_from_db()
    return JsonResponse({
        'ok': True,
        'total': int(venta.total or 0),
        'pagado': int(venta.pagado or 0),
        'saldo': int(venta.saldo_pendiente or 0),
        'producto': {
            'nombre': producto.nombre,
            'cantidad': cantidad,
            'subtotal': int(linea.precio_unitario_venta * cantidad),
        },
    })


@staff_required
def tarjetas_lista(request):
    """Lista móvil de reservas: lo mínimo para ENCONTRAR una y abrir su tarjeta.

    Jorge (2026-08-30): el listado del admin en el celular es una tabla de
    diez columnas con scroll horizontal. Acá va lo que pidió y nada más:
    número, fecha y cliente, con un buscador — y cada fila abre la tarjeta.

    El buscador entiende lo que Deborah escribiría: un número corto es el id
    de la reserva; un número largo, un teléfono; texto, el nombre; y una fecha
    (02/09/2026 o 2026-09-02) trae las reservas de ese día. Todo en UN campo:
    en el celular, elegir "buscar por..." es un paso de más.
    """
    from datetime import datetime as _dt

    from django.db.models import Q

    q = (request.GET.get('q') or '').strip()
    reservas = VentaReserva.objects.select_related('cliente')

    if q:
        cond = Q(cliente__nombre__icontains=q)
        solo_digitos = ''.join(ch for ch in q if ch.isdigit())
        if solo_digitos:
            if len(solo_digitos) <= 7:
                cond |= Q(id=int(solo_digitos))
            cond |= Q(cliente__telefono__icontains=solo_digitos)
        for formato in ('%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d'):
            try:
                f = _dt.strptime(q, formato).date()
                cond |= Q(fecha_reserva__date=f)
                cond |= Q(reservaservicios__fecha_agendamiento=f)
                break
            except ValueError:
                continue
        reservas = reservas.filter(cond).distinct()

    reservas = list(reservas.order_by('-id')[:50])
    return render(request, 'ventas/tarjetas_lista.html', {
        'reservas': reservas,
        'q': q,
        'hay_mas': len(reservas) == 50,
    })


@staff_required
def nueva_reserva(request):
    """Crear una reserva con lo mínimo: teléfono y nombre. Nada más.

    El teléfono manda. Se normaliza con Cliente.normalize_phone (el mismo
    normalizador que usa Cliente.save) y se busca ANTES de crear: si el
    cliente ya existe se usa su ficha tal cual, sin pisarle el nombre — los
    clientes duplicados por formato de teléfono ya costaron una limpieza
    masiva (normalize_and_merge_clients).

    Al crear, directo a la tarjeta: ahí están los botones para armar el resto.
    """
    contexto = {'telefono': '', 'nombre': ''}
    if request.method != 'POST':
        return render(request, 'ventas/nueva_reserva.html', contexto)

    crudo = (request.POST.get('telefono') or '').strip()
    nombre = (request.POST.get('nombre') or '').strip()
    contexto.update(telefono=crudo, nombre=nombre)

    telefono = Cliente.normalize_phone(crudo) if crudo else None
    if not telefono:
        contexto['error'] = 'Ese teléfono no se entiende. Ej: 912345678.'
        return render(request, 'ventas/nueva_reserva.html', contexto)

    cliente = Cliente.objects.filter(telefono=telefono).first()
    if cliente is None:
        if not nombre:
            contexto['error'] = 'Es un cliente nuevo: falta el nombre.'
            return render(request, 'ventas/nueva_reserva.html', contexto)
        try:
            cliente = Cliente.objects.create(nombre=nombre, telefono=telefono)
        except (ValidationError, Exception) as exc:  # noqa: BLE001
            logger.exception('[tarjeta] no se pudo crear el cliente %s: %s',
                             telefono, exc)
            contexto['error'] = 'No se pudo crear el cliente. Revisa el teléfono.'
            return render(request, 'ventas/nueva_reserva.html', contexto)

    # fecha_reserva admite NULL, pero un nulo esconde la venta de los reportes
    # que filtran por fecha. Se estampa el momento de la creación.
    venta = VentaReserva.objects.create(cliente=cliente,
                                        fecha_reserva=timezone.now())
    logger.info('[tarjeta] reserva %s creada para %s por %s',
                venta.pk, cliente.telefono, request.user.username)
    return redirect('ventas:tarjeta_reserva', venta_id=venta.pk)


@staff_required
@require_POST
def tarjeta_editar_datos(request, venta_id):
    """Guarda SOLO los datos complementarios: comentarios y documento fiscal.

    update_fields a propósito: este endpoint no puede tocar totales, estados
    ni nada que no sea suyo — un guardado parcial que pisa campos ajenos es el
    mismo tipo de bug que la vista previa que mutaba datos.
    """
    venta = get_object_or_404(VentaReserva, pk=venta_id)
    venta.comentarios = (request.POST.get('comentarios') or '').strip()
    venta.numero_documento_fiscal = (request.POST.get('numero_documento_fiscal')
                                     or '').strip()
    venta.save(update_fields=['comentarios', 'numero_documento_fiscal'])
    return JsonResponse({'ok': True})


@staff_required
@require_POST
def tarjeta_editar_servicio(request, venta_id):
    """Cambia SOLO la cantidad de personas de UNA línea de servicio.

    La guarda que importa: esto se permite únicamente donde el precio es por
    persona. En cabañas y tinas de precio plano, cantidad_personas es el
    mecanismo del precio (AR-014: precio × capacidad_maxima), no un dato del
    grupo — cambiarla cobraría mal. Esas líneas se editan en el admin, con
    ojos de quien sabe lo que toca.
    """
    venta = get_object_or_404(VentaReserva, pk=venta_id)
    try:
        linea = (venta.reservaservicios.select_related('servicio')
                 .get(pk=request.POST.get('linea_id')))
    except Exception:  # noqa: BLE001 — pk inválido o de OTRA reserva: mismo trato
        return JsonResponse({'ok': False, 'mensaje': 'Línea no encontrada.'},
                            status=404)

    if linea.servicio.tipo_servicio == 'cabana':
        return JsonResponse(
            {'ok': False, 'mensaje': 'En una cabaña la cantidad no son '
                                     'personas: se edita en el admin.'},
            status=400)

    crudo = (request.POST.get('cantidad') or '').strip()
    if not crudo.isdigit() or int(crudo) < 1:
        return JsonResponse({'ok': False, 'mensaje': 'Cantidad inválida.'}, status=400)
    cantidad = int(crudo)

    # Piso Y techo del catálogo. El piso importa tanto como el techo: una
    # tina con mínimo 2 editada a 1 persona se cobraría bajo tarifa.
    piso = int(linea.servicio.capacidad_minima or 0)
    if piso and cantidad < piso:
        return JsonResponse(
            {'ok': False, 'mensaje': f'{linea.servicio.nombre} pide mínimo '
                                     f'{piso} persona(s).'},
            status=400)
    tope = int(linea.servicio.capacidad_maxima or 0)
    if tope and cantidad > tope:
        return JsonResponse(
            {'ok': False, 'mensaje': f'{linea.servicio.nombre} admite hasta '
                                     f'{tope} persona(s).'},
            status=400)

    linea.cantidad_personas = cantidad
    linea.save(update_fields=['cantidad_personas'])
    venta.calcular_total()
    venta.refresh_from_db()

    precio = linea.precio_unitario_venta
    if precio is None:
        precio = linea.servicio.precio_base
    return JsonResponse({
        'ok': True,
        'total': int(venta.total or 0),
        'pagado': int(venta.pagado or 0),
        'saldo': int(venta.saldo_pendiente or 0),
        'linea': {'personas': cantidad, 'subtotal': int(precio * cantidad)},
    })
