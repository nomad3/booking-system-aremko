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

import json
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


def _metodos_pago_visibles():
    """Lo que el selector OFRECE: los mismos medios que muestra el admin.

    Hasta el 04-09-2026 la tarjeta armaba su lista directo del modelo y se
    saltaba el interruptor `visible_al_cobrar`: mostraba 20 opciones donde el
    admin mostraba 11, incluidas las cuentas personales que se ocultaron en
    agosto (mach jorge, bci alda, copec alda…). Dos caminos para la misma
    lista, y solo uno respetaba la decisión ya tomada.

    El daño no era cosmético. «Transferencia a Mercado Pago» quedaba en la
    posición 16 de 20, y quien cobraba elegía «MercadoPago» —que está en la 6
    y NO boletea— para registrar transferencias. Resultado: la pregunta de la
    boleta no aparecía y la venta se quedaba sin documento.

    Se evalúa en cada request, no al importar: `codigos_visibles_al_cobrar`
    cachea con TTL y se invalida por señal cuando alguien toca un medio en el
    admin. Congelarlo en una constante de módulo perdería justamente eso.
    """
    try:
        from facturacion.medios import filtrar_choices_pago
        return filtrar_choices_pago(METODOS_PAGO_TARJETA)
    except Exception:  # noqa: BLE001 — tabla sin sembrar, deploy a medias
        # Ante la duda, mostrar todo: un selector corto de más deja a Deborah
        # sin poder registrar un cobro real, que es peor que uno largo.
        return list(METODOS_PAGO_TARJETA)


def staff_required(view_func):
    """Decorador para requerir que el usuario sea staff."""
    decorated_view = user_passes_test(lambda u: u.is_staff)(view_func)
    return login_required(decorated_view)


# Ventana para considerar sospechoso un pago repetido. El caso real que lo
# motivó fueron 6 segundos (Deborah no vio la confirmación y volvió a guardar),
# pero 10 minutos cubre también al que se distrae. No bloquea: dos personas
# pagando $20.000 cada una en efectivo es normal — solo pregunta.
MINUTOS_PAGO_REPETIDO = 10


def _pago_igual_reciente(venta, monto, metodo):
    """Un pago idéntico a esta misma reserva hace pocos minutos, o None.

    Nació de un caso real (04-09-2026, reserva 6742): el mismo cobro quedó
    registrado dos veces con 6 segundos de diferencia, la reserva marcó
    $120.000 sobre un total de $60.000, y —peor— se emitieron DOS boletas
    electrónicas por la misma venta. El sistema no dijo nada.
    """
    import datetime

    from django.utils import timezone

    try:
        desde = timezone.now() - datetime.timedelta(minutes=MINUTOS_PAGO_REPETIDO)
        return (venta.pagos.filter(monto=monto, metodo_pago=metodo,
                                   fecha_pago__gte=desde)
                .order_by('-fecha_pago').first())
    except Exception:  # noqa: BLE001 — avisar nunca puede impedir un cobro
        return None


def _codigos_que_boletean():
    """Códigos de medio de pago marcados para emitir boleta, o vacío si no se
    puede leer. Ante la duda NO se pregunta: preguntar de más empuja a emitir
    un documento que el operador ya emitió, y un duplicado ante el SII cuesta
    más de arreglar que una boleta que falta."""
    try:
        from facturacion.models import MedioPago
        return list(MedioPago.objects.filter(genera_boleta=True)
                    .values_list('codigo', flat=True))
    except Exception:  # noqa: BLE001 — tabla sin sembrar, deploy a medias
        return []


# Los mismos accesos rápidos que el admin: la gran mayoría de los
# clientes vive en estas ciudades.
COMUNAS_RAPIDAS = ('Puerto Varas', 'Puerto Montt', 'Osorno',
                   'Santiago', 'Valparaíso', 'Temuco', 'Concepción')


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
    pagos = list(venta.pagos.order_by('fecha_pago'))
    # Cada pago con su boleta, para que Deborah la vea sin salir de la tarjeta
    # (Jorge, 04-09-2026). Los que todavía nadie resolvió llevan la marca para
    # decidir ahí mismo — hasta ahora eso solo se veía en el listado aparte,
    # que es un repaso posterior.
    try:
        from facturacion.models import BoletaElectronica
        from facturacion.services.decision import pagos_sin_resolver

        boletas = {b.pago_id: b for b in BoletaElectronica.objects
                   .filter(pago__in=pagos)
                   .exclude(estado__in=('error', 'pendiente'))}
        pendientes = {p.pk for p in pagos_sin_resolver(venta)}
        for pago in pagos:
            pago.boleta = boletas.get(pago.pk)
            pago.falta_decidir = pago.pk in pendientes
    except Exception:  # noqa: BLE001 — la tarjeta abre igual sin esto
        logger.exception('[tarjeta] no se pudieron leer las boletas de la venta %s',
                         venta.pk)
        for pago in pagos:
            pago.boleta = None
            pago.falta_decidir = False

    # Catálogo del selector: SOLO los marcados «Venta en Mesón», con stock
    # (Jorge, 01-09-2026). Antes se usaba `productos_vendibles`, que suma el
    # menú de comanda del CLIENTE —lo que él ve en su link— y eso alargaba la
    # lista con cosas que en el mesón no se venden. Los ya guardados en esta
    # reserva se incluyen igual, para que una reserva antigua con un producto
    # descatalogado siga abriéndose.
    from ventas.admin import productos_de_meson

    catalogo = productos_de_meson(
        ids_visibles=list(productos.values_list('producto_id', flat=True)))

    # La ubicación del cliente se guarda como COMUNA, igual que en el admin
    # (el campo `ciudad` es texto libre y el propio modelo lo desaconseja).
    # Los accesos rápidos son los mismos 7 del admin: casi todos los clientes
    # son de esas ciudades y así se resuelve con un toque, sin buscar entre 346.
    from ventas.models import Comuna

    return render(request, 'ventas/tarjeta_reserva.html', {
        'venta': venta,
        'servicios': servicios,
        'productos': productos,
        'pagos': pagos,
        'mensaje_pase': mensaje_pase(venta),
        'debe': int(venta.saldo_pendiente or 0) > 0,
        'metodos_pago': _metodos_pago_visibles(),
        # Códigos que SÍ boletean: la tarjeta pregunta «¿generar la boleta?»
        # solo cuando corresponde. En un cobro con tarjeta o link, el voucher
        # del operador ya ES la boleta y preguntar invitaría a duplicar.
        'medios_que_boletean': json.dumps(_codigos_que_boletean()),
        'catalogo': catalogo,
        'comunas': Comuna.objects.select_related('region').order_by('nombre'),
        'comunas_rapidas': COMUNAS_RAPIDAS,
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
    # La guarda del servidor usa la lista COMPLETA, no la filtrada: si alguien
    # tenía la pantalla abierta cuando se ocultó un medio, su cobro no debe
    # rebotar. Ocultar es para no ofrecer, no para prohibir lo ya elegido.
    if metodo not in {codigo for codigo, _ in METODOS_PAGO_TARJETA}:
        return JsonResponse({'ok': False, 'mensaje': 'Método de pago no válido.'},
                            status=400)

    # Aviso de repetido: se pregunta UNA vez y quien cobra decide. Bloquear
    # de plano dejaría sin registrar dos pagos iguales legítimos.
    if not request.POST.get('confirmar_repetido'):
        # Envuelto también acá, no solo dentro: quien está al otro lado es
        # Deborah con un cliente al frente, y un aviso que revienta sería peor
        # que el duplicado que intenta evitar.
        try:
            anterior = _pago_igual_reciente(venta, monto, metodo)
        except Exception:  # noqa: BLE001
            logger.warning('[tarjeta] no se pudo revisar si el pago se repite')
            anterior = None
        if anterior is not None:
            hace = timezone.localtime(anterior.fecha_pago).strftime('%H:%M')
            return JsonResponse({
                'ok': False,
                'repetido': True,
                'mensaje': (f'Ya hay un pago de ${monto:,} con este mismo medio '
                            f'a las {hace}. ¿Es un pago DISTINTO?'.replace(',', '.')),
            }, status=409)

    try:
        pago = Pago.objects.create(venta_reserva=venta, monto=monto,
                                   metodo_pago=metodo, usuario=request.user)
    except Exception as exc:  # noqa: BLE001
        logger.exception('[tarjeta] no se pudo crear el pago de $%s (%s) para la '
                         'reserva %s: %s', monto, metodo, venta_id, exc)
        return JsonResponse({'ok': False, 'mensaje': 'No se pudo guardar el pago. '
                             'Inténtalo desde el admin.'}, status=400)

    # La boleta va DESPUÉS y aparte: el pago ya está guardado, así que si la
    # emisión falla no se pierde la plata registrada — se informa y queda en el
    # listado de revisión. Al revés (emitir dentro del guardado) un problema con
    # el SII dejaría a Deborah sin poder cobrar.
    boleta_msg = _resolver_boleta_del_pago(pago, request)

    venta.refresh_from_db()
    return JsonResponse({
        'ok': True,
        'total': int(venta.total or 0),
        'pagado': int(venta.pagado or 0),
        'saldo': int(venta.saldo_pendiente or 0),
        'boleta': boleta_msg,
        'pago': {
            'monto': int(pago.monto),
            'metodo': pago.get_metodo_pago_display(),
            'hora': timezone.localtime(pago.fecha_pago).strftime('%d/%m %H:%M'),
        },
    })


def _resolver_boleta_del_pago(pago, request):
    """Actúa sobre la respuesta a «¿Desea generar la boleta electrónica?».

    Tres caminos, y ninguno puede voltear el pago que ya se guardó:
    · «sí»  → se emite. Si el SII falla, se informa y el pago queda listado.
    · «no»  → se deja constancia de QUIÉN decidió no emitir. Sin ese registro,
              un pago sin boleta es indistinguible de un olvido.
    · nada  → el medio no boletea (el voucher del operador ya es la boleta) o
              la pregunta no llegó: no se inventa una decisión.
    """
    respuesta = (request.POST.get('emitir_boleta') or '').strip().lower()
    if respuesta not in ('si', 'sí', 'no'):
        return ''
    if respuesta == 'no':
        try:
            from facturacion.models import DecisionSinBoleta
            DecisionSinBoleta.objects.get_or_create(
                pago=pago, defaults={'usuario': request.user})
            return 'Sin boleta: queda en el listado de revisión.'
        except Exception as exc:  # noqa: BLE001
            logger.exception('[tarjeta] no se pudo registrar el «no» del pago %s: %s',
                             pago.pk, exc)
            return 'No se pudo registrar la decisión; revísalo en el admin.'
    try:
        from facturacion.services.emisor import emitir_boleta_para_pago
        boleta, mensaje = emitir_boleta_para_pago(pago)
    except Exception as exc:  # noqa: BLE001
        logger.exception('[tarjeta] falló la emisión del pago %s: %s', pago.pk, exc)
        return 'El pago quedó guardado, pero la boleta falló. Está en el listado.'
    if boleta is None:
        return f'Sin boleta: {mensaje}'
    # Avisarle al cliente va DESPUÉS y aparte: la boleta ya existe ante el SII
    # y un problema de WhatsApp no puede cambiar eso. Si la ventana de 24h
    # está cerrada no se manda nada acá — esas las junta el proceso diario en
    # un solo mensaje, que es lo que se paga.
    aviso = ''
    try:
        from facturacion.services.envio_whatsapp import enviar_pdf_al_cliente
        enviado, motivo = enviar_pdf_al_cliente(boleta)
        aviso = ' · enviada al cliente' if enviado else ''
        if not enviado:
            logger.info('[tarjeta] boleta %s no se envió ahora: %s',
                        boleta.folio, motivo)
    except Exception as exc:  # noqa: BLE001
        logger.warning('[tarjeta] fallo al avisar de la boleta %s: %s',
                       getattr(boleta, 'folio', None), exc)
    return f'Boleta {boleta.folio or "(en proceso)"}: {mensaje}{aviso}'


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

    # El mismo criterio que el selector: lo que no es de mesón no entra ni
    # desde una pestaña vieja que todavía lo muestre en su lista.
    if not producto.venta_meson:
        return JsonResponse(
            {'ok': False, 'mensaje': f'{producto.nombre} no está marcado para '
                                     'venta en mesón: se agrega desde el admin.'},
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
    """Guarda los datos complementarios de la reserva Y los del cliente.

    La reserva se crea con lo mínimo —nombre y teléfono— porque al teléfono
    hay que atender rápido. El resto (correo, RUT, comuna) llega después, y
    éste es el lugar donde se completa sin abrir el admin.

    update_fields a propósito: este endpoint no puede tocar totales, estados
    ni nada que no sea suyo — un guardado parcial que pisa campos ajenos es el
    mismo tipo de bug que la vista previa que mutaba datos. Por eso el cliente
    se guarda con su propia lista de campos: el teléfono y el nombre no se
    tocan desde acá.
    """
    from django.core.exceptions import ValidationError
    from django.core.validators import validate_email

    from ventas.models import Comuna

    venta = get_object_or_404(VentaReserva, pk=venta_id)
    venta.comentarios = (request.POST.get('comentarios') or '').strip()
    venta.numero_documento_fiscal = (request.POST.get('numero_documento_fiscal')
                                     or '').strip()
    venta.save(update_fields=['comentarios', 'numero_documento_fiscal'])

    cliente = venta.cliente
    if cliente is None:
        return JsonResponse({'ok': True})

    email = (request.POST.get('email') or '').strip()
    if email:
        try:
            validate_email(email)
        except ValidationError:
            # Un correo mal escrito no avisa: simplemente no llega. Mejor
            # rechazarlo acá que descubrirlo cuando la confirmación rebote.
            return JsonResponse(
                {'ok': False, 'mensaje': f'El correo «{email}» no parece válido.'},
                status=400)

    campos = ['email', 'documento_identidad']
    cliente.email = email or None
    cliente.documento_identidad = (request.POST.get('documento_identidad')
                                   or '').strip() or None

    comuna_id = (request.POST.get('comuna') or '').strip()
    if comuna_id:
        comuna = Comuna.objects.filter(pk=comuna_id).select_related('region').first()
        if comuna is None:
            return JsonResponse({'ok': False, 'mensaje': 'Comuna no encontrada.'},
                                status=400)
        cliente.comuna = comuna
        # 'region' va en la lista aunque no se le asigne nada: Cliente.save()
        # la deriva de la comuna (Plan Geo E1), y sin nombrarla acá
        # update_fields no la escribiría — quedaría la comuna nueva con la
        # región vieja.
        campos += ['comuna', 'region']
    elif cliente.comuna_id:
        cliente.comuna = None
        cliente.region = None
        campos += ['comuna', 'region']

    cliente.save(update_fields=campos)
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
