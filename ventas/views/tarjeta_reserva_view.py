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
Falta: creación con datos mínimos.

La vista es deliberadamente liviana: tres queries con select_related y ningún
cálculo — total/pagado/saldo son campos almacenados. Nada de ficha 360.
"""
from __future__ import annotations

import logging

from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from ventas.models import Pago, Producto, ReservaProducto, VentaReserva
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

    servicios = venta.reservaservicios.select_related('servicio').order_by(
        'fecha_agendamiento', 'hora_inicio', 'id')
    productos = venta.reservaproductos.select_related('producto')
    pagos = venta.pagos.order_by('fecha_pago')

    # Catálogo para el selector: solo lo que HAY. Ofrecer un producto sin
    # stock es prometerle al cliente algo que no se le puede entregar.
    catalogo = (Producto.objects.filter(cantidad_disponible__gt=0)
                .select_related('categoria')
                .order_by('categoria__nombre', 'nombre'))

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
