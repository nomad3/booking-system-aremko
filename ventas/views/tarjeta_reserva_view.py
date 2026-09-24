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

import datetime
import json
import logging
import re
import time
from contextlib import contextmanager

from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
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


# Un pago idéntico a menos de esto NO se pregunta: se rechaza. Nadie cobra dos
# veces lo mismo, con el mismo medio, en medio minuto; un doble clic sí.
SEGUNDOS_PAGO_CALCADO = 30


# Espacio propio para los candados de la tarjeta (primer entero de pg_advisory_lock),
# para no chocar con ningún otro uso. El segundo entero es el id de la reserva.
ESPACIO_CANDADO_TARJETA = 20260921
ESPERA_MAXIMA_CANDADO = 20.0      # segundos; un cobro con boleta al SII tarda ~9


@contextmanager
def _reserva_en_exclusiva(venta_id):
    """Un solo pedido a la vez por reserva.

    El servidor corre con 3 procesos en paralelo. Un doble clic manda dos pedidos
    con décimas de segundo de diferencia y cada proceso toma uno: los dos
    preguntaban «¿hay un pago igual reciente?» ANTES de que el otro guardara el
    suyo, y los dos guardaban (reserva 6869, 20-09-2026: $58.000 dos veces en el
    mismo segundo). Con los productos pasaba lo mismo con la comanda (6865: dos
    comandas gemelas en el mismo segundo).

    Es un candado CONSULTIVO de Postgres (`pg_advisory_lock`), de sesión, y NO una
    transacción con `select_for_update`, a propósito. La primera versión fue una
    transacción y la prueba contra Postgres real la tumbó antes de salir: al
    guardar un pago corre una cadena de señales que se traga varios errores de
    base —el aviso de «pago completo» de un cliente sin correo falla con un NOT
    NULL y sigue—. Fuera de una transacción eso es inofensivo; adentro, el primer
    error deja la transacción inválida y el PAGO se pierde. Habría impedido cobrarle
    a cualquier cliente sin correo.

    Nunca impide cobrar: si en 20 segundos no consigue el candado, sigue sin él. Para
    entonces el otro pedido ya guardó su pago y la guarda lo ve igual. En sqlite
    (pruebas) no hay candados ni procesos paralelos: no hace nada.
    """
    from django.db import connection

    if connection.vendor != 'postgresql':
        yield
        return

    clave = [ESPACIO_CANDADO_TARJETA, int(venta_id)]
    tomado = False
    try:
        fin = time.monotonic() + ESPERA_MAXIMA_CANDADO
        while True:
            with connection.cursor() as cursor:
                cursor.execute('SELECT pg_try_advisory_lock(%s, %s)', clave)
                tomado = bool(cursor.fetchone()[0])
            if tomado or time.monotonic() >= fin:
                break
            time.sleep(0.15)
        if not tomado:
            logger.warning('[tarjeta] no se consiguió el candado de la reserva %s en %.0f s; '
                           'se sigue sin él', venta_id, ESPERA_MAXIMA_CANDADO)
    except Exception:  # noqa: BLE001 — un candado que falla no puede impedir un cobro
        logger.exception('[tarjeta] no se pudo tomar el candado de la reserva %s', venta_id)
    try:
        yield
    finally:
        if tomado:
            try:
                with connection.cursor() as cursor:
                    cursor.execute('SELECT pg_advisory_unlock(%s, %s)', clave)
            except Exception:  # noqa: BLE001
                # La conexión es persistente: si no se suelta acá, el candado viviría
                # hasta que la conexión se cierre. Se cierra para soltarlo seguro.
                logger.exception('[tarjeta] no se pudo soltar el candado de la reserva %s; '
                                 'se cierra la conexión', venta_id)
                connection.close()


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
    productos = list(venta.reservaproductos.select_related('producto'))
    # Los descuentos se leen como plata rebajada, en la lista de la familia a
    # la que pertenecen (Jorge, 05-09-2026: "vendemos una tina para 6 personas
    # y cobramos solo 5" = descuento de servicios; "dos café y cobramos uno" =
    # de productos). Antes productos mostraba "59× Descuento -1000".
    try:
        _marcar_descuentos(servicios, 'servicio', 'cantidad_personas')
        _marcar_descuentos(productos, 'producto', 'cantidad')
    except Exception:  # noqa: BLE001 — la tarjeta abre igual sin esto
        logger.exception('[tarjeta] no se pudieron marcar los descuentos (venta %s)',
                         venta.pk)
        for linea in list(servicios) + list(productos):
            linea.es_descuento = False
    _marcar_estado_de_cocina(venta, productos)
    pagos = list(venta.pagos.select_related('giftcard').order_by('fecha_pago'))
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
        ids_visibles=[r.producto_id for r in productos])

    # La ubicación del cliente se guarda como COMUNA, igual que en el admin
    # (el campo `ciudad` es texto libre y el propio modelo lo desaconseja).
    # Los accesos rápidos son los mismos 7 del admin: casi todos los clientes
    # son de esas ciudades y así se resuelve con un toque, sin buscar entre 346.
    from ventas.models import Comuna

    giftcards_vendidas = _giftcards_vendidas(venta)

    return render(request, 'ventas/tarjeta_reserva.html', {
        'venta': venta,
        'servicios': servicios,
        # Para el botón «Agregar de la lista»: los servicios que no ocupan
        # una hora no necesitan el calendario, y por él son un trámite.
        'catalogo_servicios': _servicios_de_lista(),
        # Viene puesta para que agregar sea un toque: es la fecha de los
        # servicios de la reserva, la misma que usa el descuento.
        'fecha_sugerida': _fecha_del_descuento(venta),
        'productos': productos,
        'pagos': pagos,
        'giftcards_vendidas': giftcards_vendidas,
        'giftcards_enviables': sum(1 for g in giftcards_vendidas if g['enviable'] and g['telefono']),
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

    # La guarda y el alta van JUNTAS y bajo candado: separadas, dos pedidos
    # simultáneos pasaban los dos la guarda antes de que ninguno guardara.
    confirmado = bool(request.POST.get('confirmar_repetido'))
    try:
        with _reserva_en_exclusiva(venta_id):
            # Envuelto: quien está al otro lado es Deborah con un cliente al frente, y
            # un aviso que revienta sería peor que el duplicado que intenta evitar.
            try:
                anterior = _pago_igual_reciente(venta, monto, metodo)
            except Exception:  # noqa: BLE001
                logger.warning('[tarjeta] no se pudo revisar si el pago se repite')
                anterior = None
            if anterior is not None:
                segundos = (timezone.now() - anterior.fecha_pago).total_seconds()
                monto_str = f'${monto:,}'.replace(',', '.')
                if segundos < SEGUNDOS_PAGO_CALCADO:
                    # Calcado y recién hecho: es un doble clic, o alguien que apretó de
                    # nuevo porque la boleta tardaba. NO se pregunta —el 20-09 Ernesto
                    # aceptó la pregunta sin leerla y salieron dos boletas reales,
                    # folios 69078 y 69079— y tampoco vale haber confirmado.
                    logger.warning('[tarjeta] pago calcado rechazado: reserva %s, %s %s, '
                                   'a %.1f s del pago %s', venta_id, monto_str, metodo,
                                   segundos, anterior.pk)
                    return JsonResponse({
                        'ok': False,
                        'duplicado': True,
                        'mensaje': (f'Ese pago de {monto_str} ya quedó registrado hace '
                                    f'{int(segundos)} segundos. No se guardó otra vez. Si de '
                                    'verdad es OTRO pago igual, espera un momento y guárdalo '
                                    'de nuevo.'),
                    }, status=409)
                if not confirmado:
                    # Aviso de repetido: se pregunta UNA vez y quien cobra decide.
                    # Bloquear de plano dejaría sin registrar dos pagos iguales legítimos.
                    hace = timezone.localtime(anterior.fecha_pago).strftime('%H:%M')
                    return JsonResponse({
                        'ok': False,
                        'repetido': True,
                        'mensaje': (f'Ya hay un pago de {monto_str} con este mismo medio '
                                    f'a las {hace}. ¿Es un pago DISTINTO?'),
                    }, status=409)
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


# ---------------------------------------------------------------------------
# Canje de gift card (Jorge, 24-09-2026, «paso 1»). La tarjeta ya creaba la
# reserva, sumaba servicios, descuentos y pagos: faltaba justo lo que distingue
# a un canje, pagar con la gift card, y cada vez había que salir al admin a
# buscarla (23 canjes en 90 días, 22 a mano). Se busca por código —o por el
# nombre de quien la recibió—, se VE antes de usarla y se aplica con un toque
# por lo que falte pagar. El canje no boletea: la boleta se emitió al venderla.
# ---------------------------------------------------------------------------

MAX_RESULTADOS_GIFTCARD = 6


def _pesos(n):
    return f'${int(n or 0):,}'.replace(',', '.')


def _codigo_limpio(texto):
    """Los códigos son 12 letras y números en mayúscula; el cliente los dicta
    con espacios, guiones o en minúscula."""
    return re.sub(r'[^0-9A-Za-z]', '', texto or '').upper()


# Letras y números que se confunden al leer o dictar un código: los códigos
# mezclan las 26 letras con los 10 dígitos, y la fuente de la carta dibuja la O
# igual que el cero (prueba del 24-09-2026: «OGEFH03K7B2J» empieza con la LETRA
# O y en el PDF y en la tarjeta se ve como un cero). Para buscar, se compara
# todo en una forma donde O=0 e I=1.
PARES_AMBIGUOS = (('O', '0'), ('I', '1'))


def _forma_canonica(codigo):
    for letra, numero in PARES_AMBIGUOS:
        codigo = codigo.replace(letra, numero)
    return codigo


def _codigo_canonico_sql():
    from django.db.models import Value
    from django.db.models.functions import Replace, Upper

    expr = Upper('codigo')
    for letra, numero in PARES_AMBIGUOS:
        expr = Replace(expr, Value(letra), Value(numero))
    return expr


def _compra_sin_pagar(gc):
    """¿La venta donde se compró esta gift card todavía debe plata?

    No se lee del campo `estado`, que significa dos cosas según quién lo
    escribió: «compra sin pagar» (la venta por Luna o la web la crea así y la
    pasa a «cobrado» al pagarse) y «vigente, con saldo por usar» (el canje
    parcial y el ajuste de saldo la dejan «por_cobrar»). La venta de origen no
    tiene esa ambigüedad. Una gift card no ligada a ninguna venta —vendida a
    mano en el admin— no se puede comprobar y se da por pagada: así se venden.
    En prod, 24-09-2026: de 121 vigentes ligadas, 3 con la venta debiendo, y 4
    ya pagadas marcadas «por_cobrar».
    """
    venta = gc.venta_reserva if gc.venta_reserva_id else None
    return venta is not None and int(venta.saldo_pendiente or 0) > 0


def estado_giftcard(gc, hoy=None):
    """El estado en palabras, para quien la tiene en la mano. El campo `estado`
    no sirve para esto (ver _compra_sin_pagar): se deriva del saldo, el
    vencimiento y la venta donde se compró."""
    hoy = hoy or timezone.localdate()
    saldo = int(gc.monto_disponible or 0)
    if gc.fecha_vencimiento and gc.fecha_vencimiento < hoy:
        return 'Vencida'
    if saldo <= 0:
        return 'Usada'
    if _compra_sin_pagar(gc):
        return 'Por cobrar'
    if saldo < int(gc.monto_inicial or 0):
        return f'Le quedan {_pesos(saldo)}'
    return 'Lista para usar'


def _nombre_experiencia(gc):
    from ventas.models import GiftCardExperiencia
    clave = (gc.servicio_asociado or '').strip()
    if not clave:
        return 'Gift card de monto libre'
    nombre = (GiftCardExperiencia.objects.filter(id_experiencia=clave)
              .values_list('nombre', flat=True).first())
    if nombre:
        return nombre
    legible = clave.replace('_', ' ')
    return legible[:1].upper() + legible[1:]


def _ficha_giftcard(gc, venta):
    """Lo que hay que ver ANTES de usarla, y cuánto se aplicaría a esta reserva.

    `problema` impide aplicarla; `aviso` pide confirmar. Una compra sin pagar
    no se bloquea —quien cobra puede saber que se pagó por fuera—, pero se
    pregunta, y se le recuerda dónde registrar ese pago.
    """
    hoy = timezone.localdate()
    saldo = int(gc.monto_disponible or 0)
    pendiente = int(venta.saldo_pendiente or 0)
    problema, aviso = '', ''
    if gc.venta_reserva_id == venta.pk:
        problema = 'Esta gift card se vendió en ESTA reserva: no puede pagarse a sí misma.'
    elif gc.fecha_vencimiento and gc.fecha_vencimiento < hoy:
        problema = f'Venció el {gc.fecha_vencimiento:%d-%m-%Y}.'
    elif saldo <= 0:
        uso = (Pago.objects.filter(giftcard=gc, metodo_pago='giftcard')
               .order_by('-fecha_pago').values_list('venta_reserva_id', flat=True).first())
        problema = 'Ya fue usada' + (f' en la reserva #{uso}' if uso else '') + '.'
    elif pendiente <= 0:
        problema = 'Esta reserva no tiene saldo por pagar: agrega primero los servicios.'
    elif _compra_sin_pagar(gc):
        aviso = (f'La venta donde se compró esta gift card (reserva #{gc.venta_reserva_id}) '
                 f'todavía debe {_pesos(gc.venta_reserva.saldo_pendiente)}. Si ya se pagó, '
                 'registra ese pago en esa reserva. ¿La aplico igual?')
    comprador = gc.comprador_nombre or (
        gc.cliente_comprador.nombre if gc.cliente_comprador_id else '')
    para = gc.destinatario_nombre or (
        gc.cliente_destinatario.nombre if gc.cliente_destinatario_id else '')
    return {
        'id': gc.pk,
        'codigo': gc.codigo,
        'experiencia': _nombre_experiencia(gc),
        'para': (para or '').strip(),
        'compro': (comprador or '').strip(),
        'monto_inicial': int(gc.monto_inicial or 0),
        'saldo': saldo,
        'vence': gc.fecha_vencimiento.strftime('%d-%m-%Y') if gc.fecha_vencimiento else '',
        'vendida_en': gc.venta_reserva_id,
        'estado': estado_giftcard(gc, hoy),
        'aplicar': 0 if problema else min(saldo, pendiente),
        'problema': problema,
        'aviso': aviso,
    }


@staff_required
def tarjeta_buscar_giftcard(request, venta_id):
    """Busca la gift card a canjear en esta reserva. Solo mira; no toca nada.

    Por código (exacto, o su comienzo si el cliente dicta una parte) y, si no
    aparece, por el nombre de quien la recibió o la compró — entre las que
    todavía se pueden usar.
    """
    from ventas.models import GiftCard

    venta = get_object_or_404(VentaReserva, pk=venta_id)
    texto = (request.GET.get('q') or '').strip()
    if len(texto) < 3:
        return JsonResponse({'ok': False, 'mensaje': 'Escribe el código de la gift card '
                             '(o al menos 3 letras del nombre).'}, status=400)
    base = GiftCard.objects.select_related('cliente_comprador', 'cliente_destinatario',
                                          'venta_reserva')
    codigo = _codigo_limpio(texto)
    encontradas = []
    if len(codigo) >= 6:
        exacta = base.filter(codigo__iexact=codigo).first()
        if exacta:
            encontradas = [exacta]
        else:
            # Leído con cero por O o con uno por I; completo o solo el comienzo.
            canon = _forma_canonica(codigo)
            con_canon = base.annotate(canon=_codigo_canonico_sql())
            encontradas = (list(con_canon.filter(canon=canon)[:MAX_RESULTADOS_GIFTCARD])
                           or list(con_canon.filter(canon__startswith=canon)
                                   .order_by('-id')[:MAX_RESULTADOS_GIFTCARD]))
    if not encontradas and re.search(r'[^\W\d_]{3,}', texto):
        encontradas = list(
            base.filter(fecha_vencimiento__gte=timezone.localdate(), monto_disponible__gt=0)
            .filter(Q(destinatario_nombre__icontains=texto)
                    | Q(comprador_nombre__icontains=texto)
                    | Q(cliente_destinatario__nombre__icontains=texto)
                    | Q(cliente_comprador__nombre__icontains=texto))
            .order_by('fecha_vencimiento')[:MAX_RESULTADOS_GIFTCARD])
    if not encontradas:
        return JsonResponse({'ok': False, 'mensaje': f'No encontré una gift card con «{texto}». '
                             'Revisa el código con el cliente.'}, status=404)
    return JsonResponse({'ok': True,
                         'giftcards': [_ficha_giftcard(gc, venta) for gc in encontradas]})


@staff_required
@require_POST
def tarjeta_aplicar_giftcard(request, venta_id):
    """Paga la reserva con la gift card: lo que falte pagar, hasta su saldo.

    Mismo camino que un pago normal: el candado de la reserva y
    `Pago.objects.create`, cuyas validaciones del modelo (vencimiento, saldo) y
    `GiftCard.usar()` descuentan el saldo. Sin transacción que lo envuelva, a
    propósito (ver _reserva_en_exclusiva). Todo se relee DENTRO del candado: el
    saldo de la reserva y el de la gift card pueden haber cambiado desde que se
    buscó, y un segundo clic encuentra la gift card ya usada o la reserva pagada.
    """
    from ventas.models import GiftCard

    venta = get_object_or_404(VentaReserva, pk=venta_id)
    try:
        gc_id = int(request.POST.get('giftcard_id') or 0)
    except (TypeError, ValueError):
        gc_id = 0
    confirmado = bool(request.POST.get('confirmar_por_cobrar'))
    try:
        with _reserva_en_exclusiva(venta_id):
            venta.refresh_from_db()
            gc = (GiftCard.objects.select_related('cliente_comprador', 'cliente_destinatario',
                                                  'venta_reserva')
                  .filter(pk=gc_id).first())
            if gc is None:
                return JsonResponse({'ok': False, 'mensaje': 'No encontré esa gift card. '
                                     'Búscala de nuevo.'}, status=404)
            ficha = _ficha_giftcard(gc, venta)
            if ficha['problema']:
                return JsonResponse({'ok': False, 'mensaje': ficha['problema']}, status=400)
            if ficha['aviso'] and not confirmado:
                return JsonResponse({'ok': False, 'confirmar': True,
                                     'mensaje': ficha['aviso']}, status=409)
            monto = ficha['aplicar']
            pago = Pago.objects.create(venta_reserva=venta, monto=monto, metodo_pago='giftcard',
                                       giftcard=gc, usuario=request.user)
            if ficha['aviso']:
                # No se toca el estado de la gift card (ver _compra_sin_pagar): el
                # pago que falta va en la reserva donde se vendió. Queda quién decidió.
                logger.warning('[tarjeta] gift card %s canjeada en la reserva %s con su venta '
                               '(#%s) debiendo; lo confirmó %s', gc.codigo, venta_id,
                               gc.venta_reserva_id, request.user)
    except ValidationError as exc:
        mensaje = ' '.join(getattr(exc, 'messages', None) or [str(exc)])
        return JsonResponse({'ok': False, 'mensaje': mensaje or 'La gift card no se pudo usar.'},
                            status=400)
    except Exception as exc:  # noqa: BLE001
        logger.exception('[tarjeta] no se pudo aplicar la gift card %s a la reserva %s: %s',
                         gc_id, venta_id, exc)
        return JsonResponse({'ok': False, 'mensaje': 'No se pudo aplicar la gift card. '
                             'Inténtalo desde el admin.'}, status=400)

    venta.refresh_from_db()
    gc.refresh_from_db()
    falta = int(venta.saldo_pendiente or 0)
    mensaje = f'Gift card aplicada: {_pesos(monto)}.'
    if int(gc.monto_disponible or 0) > 0:
        mensaje += f' A la gift card le quedan {_pesos(gc.monto_disponible)}.'
    if falta > 0:
        mensaje += (f' Faltan {_pesos(falta)} por pagar: cóbralos aparte o, si el precio de '
                    'la experiencia subió, usa «Aplicar descuento».')
    return JsonResponse({
        'ok': True,
        'mensaje': mensaje,
        'pago_id': pago.pk,
        'total': int(venta.total or 0),
        'pagado': int(venta.pagado or 0),
        'saldo': falta,
    })


# ---------------------------------------------------------------------------
# Gift cards VENDIDAS en esta reserva (Jorge, 24-09-2026, «paso 2»): verlas,
# copiar el código y mandarle el PDF al comprador por WhatsApp o de nuevo por
# email. La tarjeta de una venta de gift card se veía vacía («sin servicios,
# sin productos») y los PDF se mandaban a mano desde la bandeja.
# ---------------------------------------------------------------------------

def _contacto_comprador(gc, venta):
    """(teléfono, email, nombre) de quien COMPRÓ la gift card."""
    comprador = gc.cliente_comprador if gc.cliente_comprador_id else venta.cliente
    telefono = ((getattr(comprador, 'telefono', '') or '') or (venta.cliente.telefono or '')
                or (gc.comprador_telefono or '')).strip()
    email = ((getattr(comprador, 'email', '') or '') or (venta.cliente.email or '')
             or (gc.comprador_email or '')).strip()
    nombre = ((getattr(comprador, 'nombre', '') or '') or (gc.comprador_nombre or '')).strip()
    return telefono, email, nombre


def _codigo_liberado(gc):
    """El código se muestra y se envía solo con la compra pagada (Jorge,
    24-09-2026: «sí»), la misma regla del email automático: no regalar una gift
    card sin cobrarla. Si ese email ya salió, esconderlo acá no protege nada."""
    return not _compra_sin_pagar(gc) or bool(gc.enviado_email)


def _motivo_no_se_reenvia(gc, hoy=None):
    """Por qué esta gift card NO se vuelve a enviar, o '' si se puede.

    Una usada entera o vencida se ve vigente en el PDF —monto original, «vale
    hasta»— y quien la recibe cree que tiene un regalo (prueba del 24-09-2026:
    la de Alda, ya canjeada, salió con «Vale hasta el 06-01-2027»). El código
    se sigue pudiendo copiar: sirve para buscarla."""
    hoy = hoy or timezone.localdate()
    if gc.fecha_vencimiento and gc.fecha_vencimiento < hoy:
        return f'Venció el {gc.fecha_vencimiento:%d-%m-%Y}: no se reenvía.'
    if int(gc.monto_disponible or 0) <= 0:
        return 'Ya se usó entera: no se reenvía.'
    return ''


def _giftcards_vendidas(venta):
    try:
        cartas = list(venta.giftcards.select_related('cliente_comprador', 'venta_reserva')
                      .order_by('id'))
    except Exception:  # noqa: BLE001 — la tarjeta abre igual sin esto
        logger.exception('[tarjeta] no se pudieron leer las gift cards de la venta %s', venta.pk)
        return []
    filas = []
    for gc in cartas:
        telefono, email, _ = _contacto_comprador(gc, venta)
        liberado = _codigo_liberado(gc)
        no_se_reenvia = _motivo_no_se_reenvia(gc) if liberado else ''
        filas.append({
            'id': gc.pk,
            'experiencia': _nombre_experiencia(gc),
            'para': (gc.destinatario_nombre or '').strip(),
            'monto': int(gc.monto_inicial or 0),
            'vence': gc.fecha_vencimiento,
            'estado': estado_giftcard(gc),
            'liberado': liberado,
            'enviable': liberado and not no_se_reenvia,
            'no_se_reenvia': no_se_reenvia,
            'codigo': gc.codigo if liberado else '',
            'enviado_email': bool(gc.enviado_email),
            'enviado_whatsapp': bool(gc.enviado_whatsapp),
            'telefono': telefono,
            'email': email,
        })
    return filas


def _giftcard_de_la_venta(request, venta_id):
    """La gift card pedida, SOLO si se vendió en esta reserva."""
    from ventas.models import GiftCard
    try:
        gc_id = int(request.POST.get('giftcard_id') or 0)
    except (TypeError, ValueError):
        return None
    return (GiftCard.objects.select_related('cliente_comprador', 'venta_reserva')
            .filter(pk=gc_id, venta_reserva_id=venta_id).first())


@staff_required
@require_POST
def tarjeta_enviar_giftcard_whatsapp(request, venta_id):
    """Manda el PDF de la gift card al comprador por WhatsApp.

    Solo con la compra pagada y dentro de la ventana de 24 horas (regla de
    Meta: fuera de ella un archivo no llega y el sistema creería que sí). Si ya
    se había enviado, pregunta antes de repetir. Bajo el candado de la reserva
    y releyendo la gift card: un doble clic encuentra la marca de «enviada».
    """
    venta = get_object_or_404(VentaReserva.objects.select_related('cliente'), pk=venta_id)
    with _reserva_en_exclusiva(venta_id):
        gc = _giftcard_de_la_venta(request, venta_id)
        if gc is None:
            return JsonResponse({'ok': False, 'mensaje': 'Esa gift card no es de esta reserva.'},
                                status=404)
        if not _codigo_liberado(gc):
            return JsonResponse({'ok': False, 'mensaje': 'La compra todavía no está pagada: '
                                 'registra el pago y después envíala.'}, status=400)
        motivo_no = _motivo_no_se_reenvia(gc)
        if motivo_no:
            return JsonResponse({'ok': False, 'mensaje': motivo_no}, status=400)
        telefono, _, nombre = _contacto_comprador(gc, venta)
        if not telefono:
            return JsonResponse({'ok': False, 'mensaje': 'El comprador no tiene teléfono '
                                 'registrado.'}, status=400)
        if gc.enviado_whatsapp and not request.POST.get('reenviar'):
            return JsonResponse({'ok': False, 'ya_enviada': True,
                                 'mensaje': 'Esta gift card ya se envió por WhatsApp. '
                                            '¿Enviarla de nuevo?'}, status=409)
        from facturacion.services.envio_whatsapp import ventana_abierta
        if not ventana_abierta(telefono):
            return JsonResponse({'ok': False, 'fuera_de_ventana': True,
                                 'mensaje': 'El cliente no ha escrito en las últimas 24 horas y '
                                            'WhatsApp no deja enviarle archivos. Usa «Reenviar '
                                            'por email», o pídele que escriba y vuelve a '
                                            'intentarlo.'}, status=400)
        try:
            from ventas.services.giftcard_envio import enviar_por_whatsapp
            enviado, motivo = enviar_por_whatsapp(gc, telefono, nombre, _nombre_experiencia(gc))
        except Exception as exc:  # noqa: BLE001
            logger.exception('[tarjeta] falló el envío por WhatsApp de la gift card %s: %s',
                             gc.codigo, exc)
            enviado, motivo = False, str(exc)
    if not enviado:
        logger.warning('[tarjeta] gift card %s no se envió por WhatsApp: %s', gc.codigo, motivo)
        return JsonResponse({'ok': False, 'mensaje': 'No se pudo enviar por WhatsApp. Inténtalo de '
                             'nuevo o usa «Reenviar por email».'}, status=400)
    logger.info('[tarjeta] gift card %s enviada por WhatsApp a %s por %s', gc.codigo,
                telefono, request.user)
    return JsonResponse({'ok': True, 'mensaje': f'Gift card enviada por WhatsApp al {telefono}.'})


@staff_required
@require_POST
def tarjeta_reenviar_giftcard_email(request, venta_id):
    """Vuelve a mandar el email de la gift card al comprador."""
    venta = get_object_or_404(VentaReserva.objects.select_related('cliente'), pk=venta_id)
    gc = _giftcard_de_la_venta(request, venta_id)
    if gc is None:
        return JsonResponse({'ok': False, 'mensaje': 'Esa gift card no es de esta reserva.'},
                            status=404)
    if not _codigo_liberado(gc):
        return JsonResponse({'ok': False, 'mensaje': 'La compra todavía no está pagada: '
                             'registra el pago y después envíala.'}, status=400)
    motivo_no = _motivo_no_se_reenvia(gc)
    if motivo_no:
        return JsonResponse({'ok': False, 'mensaje': motivo_no}, status=400)
    _, email, nombre = _contacto_comprador(gc, venta)
    if not email:
        return JsonResponse({'ok': False, 'mensaje': 'El comprador no tiene correo registrado.'},
                            status=400)
    try:
        from ventas.services.giftcard_envio import reenviar_por_email
        ok = reenviar_por_email(gc, email, nombre)
    except Exception as exc:  # noqa: BLE001
        logger.exception('[tarjeta] falló el reenvío por email de la gift card %s: %s',
                         gc.codigo, exc)
        ok = False
    if not ok:
        return JsonResponse({'ok': False, 'mensaje': 'No se pudo enviar el correo. Inténtalo de '
                             'nuevo en un rato.'}, status=400)
    logger.info('[tarjeta] gift card %s reenviada por email a %s por %s', gc.codigo, email,
                request.user)
    return JsonResponse({'ok': True, 'mensaje': f'Gift card reenviada por email a {email}.'})


def _comanda_del_producto(venta, producto, usuario, venta_id):
    """La MISMA regla que corre al guardar la reserva en el admin: si el producto es
    de cocina y ninguna comanda lo cubre, nace una comanda Pendiente (reserva 6859,
    19-09-2026). Defensivo y con su propio savepoint: un fallo acá no puede deshacer
    la venta del producto, que ya quedó en la cuenta."""
    try:
        from ventas.services.comanda_productos import asegurar_comanda_de_productos
        with transaction.atomic():
            return asegurar_comanda_de_productos(venta, usuario=usuario, origen='Tarjeta')
    except Exception as exc:  # noqa: BLE001
        logger.exception('[tarjeta] el producto %s quedó en la reserva %s pero NO se '
                         'pudo crear su comanda: %s', producto.pk, venta_id, exc)
        return None


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

    comanda = None
    try:
        # Bajo candado: dos pedidos simultáneos (un doble clic) creaban dos líneas y,
        # desde que cada producto genera su comanda, dos comandas gemelas o una con el
        # doble de unidades (reserva 6865, 20-09-2026). En fila, el segundo ve lo que
        # hizo el primero.
        with _reserva_en_exclusiva(venta_id):
            linea = ReservaProducto.objects.create(
                venta_reserva=venta, producto=producto, cantidad=cantidad,
                precio_unitario_venta=producto.precio_base)
            venta.calcular_total()
            comanda = _comanda_del_producto(venta, producto, request.user, venta_id)
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
            # Recién agregado y con comanda nueva: está Pendiente. Sin comanda es
            # algo que no se prepara, y va sin etiqueta.
            'estado': 'pendiente' if comanda is not None else None,
        },
        'comanda': {'id': comanda.id} if comanda is not None else None,
    })


# --- Descuentos -------------------------------------------------------------
# Aremko descuenta con un item de -1 peso y la CANTIDAD como monto: 10.000 de
# cantidad = $10.000 de descuento. Es un truco que ya lleva años y que la
# contabilidad entiende, así que NO se cambia — pero obliga a quien cobra a
# pensar en "cantidad de personas" cuando lo que quiere es rebajar plata, y en
# la tarjeta se leía "Descuento_Servicios · 30000 pers.".
#
# Acá se le da su propia puerta: se escribe el monto en pesos y el sistema
# arma la línea. Por debajo es exactamente lo mismo de siempre.
DESCUENTO_MAXIMO = 2_000_000


def _etiqueta_descuento(nombre):
    """El nombre del item de descuento, sin el monto pegado al final.

    Los items se llaman "Descuento -1000", "Descuento_Servicios",
    "Descuento Socios del Club -1.000". El monto va aparte y en grande, así
    que repetirlo en el nombre solo estorba — pero "Socios del Club" SÍ
    importa: dice por qué se descontó.
    """
    import re

    limpio = re.sub(r'[-−]\s*[\d.,]+\s*$', '', (nombre or '').strip())
    limpio = limpio.replace('_', ' ').strip(' -')
    # "Descuento Servicios" dentro de un bloque que ya se llama SERVICIOS es
    # decir lo mismo dos veces.
    for sobra in ('Servicios', 'Servicio', 'Productos', 'Producto'):
        if limpio.lower() == f'descuento {sobra}'.lower():
            return 'Descuento'
    return limpio or 'Descuento'


ETIQUETAS_ESTADO = {'pendiente': 'Pendiente', 'procesando': 'En proceso',
                    'entregada': 'Entregado'}


def _marcar_estado_de_cocina(venta, productos):
    """Le pone a cada producto su estado de cocina (Jorge, 19-09-2026: «sería
    conveniente que en la ficha se vea el estado de cada producto»).

    Es el MISMO reparto por cantidad que usan la agenda, el admin y la entrega:
    la tarjeta no puede decir una cosa y la agenda otra. Lo que no se prepara
    (gift cards, descuentos) queda sin etiqueta.
    """
    from ventas.services.comanda_productos import estados_para_mostrar
    try:
        estados = estados_para_mostrar(venta, solo_cocina=True)
    except Exception:  # noqa: BLE001 — una etiqueta no puede tumbar la tarjeta
        logger.exception('[tarjeta] no se pudo calcular el estado de cocina de la reserva %s',
                         venta.pk)
        estados = {}
    for linea in productos:
        linea.estado_cocina = estados.get(linea.pk)
        linea.estado_cocina_label = ETIQUETAS_ESTADO.get(linea.estado_cocina, '')


def _marcar_descuentos(lineas, campo_item, campo_cantidad):
    """Anota cada línea: si es descuento, con qué etiqueta y por cuánto.

    Se hace acá y no en la plantilla por la trampa de locale de Django —la
    misma que hace que el total diga "$141 000" con espacio— y porque un
    descuento se ve distinto en las dos listas: en servicios la cantidad son
    "personas" y en productos un "5×", y ninguna de las dos cosa es cierta
    para un descuento.
    """
    for linea in lineas:
        item = getattr(linea, campo_item, None)
        precio = getattr(item, 'precio_base', 0) or 0
        linea.es_descuento = precio < 0
        if linea.es_descuento:
            monto = int(getattr(linea, campo_cantidad, 0) or 0) * abs(int(precio))
            linea.etiqueta = _etiqueta_descuento(getattr(item, 'nombre', ''))
            linea.monto_descuento = f'−${monto:,}'.replace(',', '.')
    return lineas


def _fecha_del_descuento(venta):
    """La fecha de los servicios que se están descontando.

    NO la de la venta. `fecha_reserva` es cuándo se VENDIÓ, y en una reserva
    tomada con anticipación las dos cosas se separan: la 6747 se vendió el
    04/09 para el 16/09, y el descuento habría caído doce días antes de la
    visita que descuenta. Deborah, poniéndolos a mano, siempre los deja en la
    fecha de los servicios — los seis últimos revisados así estaban.

    Se toma la PRIMERA fecha con servicio de verdad (los descuentos previos no
    cuentan, o se irían arrastrando entre ellos). Si no hay ninguno todavía,
    cae en la fecha de venta, y si tampoco hay, en hoy.
    """
    from ventas.models import ReservaServicio

    primera = (ReservaServicio.objects
               .filter(venta_reserva=venta)
               .exclude(servicio__precio_base__lt=0)
               .order_by('fecha_agendamiento')
               .values_list('fecha_agendamiento', flat=True)
               .first())
    if primera:
        return primera
    cuando = getattr(venta, 'fecha_reserva', None)
    return cuando.date() if cuando else timezone.localdate()


def _item_descuento(en_productos):
    """El item de -1 peso que sirve de descuento, o None.

    Se busca por precio y nombre en vez de fijar el id: si alguien lo
    recrea en el admin, esto lo encuentra igual. Si hubiera varios, gana el
    de menor id — el más antiguo, que es el que tiene el historial.
    """
    from ventas.models import Producto, Servicio

    modelo = Producto if en_productos else Servicio
    return (modelo.objects.filter(precio_base=-1,
                                  nombre__istartswith='descuento')
            .order_by('pk').first())


@staff_required
@require_POST
def tarjeta_aplicar_descuento(request, venta_id):
    """Rebaja un monto en pesos de los servicios o de los productos.

    Jorge (05-09-2026): "monto libre no más". No hay descuentos con nombre —
    quien cobra escribe cuánto y listo.
    """
    venta = get_object_or_404(VentaReserva, pk=venta_id)

    crudo = (request.POST.get('monto') or '').strip().replace('.', '')
    if not crudo.isdigit() or int(crudo) < 1:
        return JsonResponse({'ok': False, 'mensaje': 'Escribe cuánto descontar.'},
                            status=400)
    monto = int(crudo)
    # Un tope alto pero real: protege del cero de más (100.000 -> 1.000.000)
    # sin estorbar un descuento grande de verdad.
    if monto > DESCUENTO_MAXIMO:
        return JsonResponse(
            {'ok': False,
             'mensaje': f'${monto:,}'.replace(',', '.') + ' es demasiado. '
                        'Si es correcto, hazlo desde el admin.'},
            status=400)

    en_productos = request.POST.get('destino') == 'productos'
    item = _item_descuento(en_productos)
    if item is None:
        donde = 'productos' if en_productos else 'servicios'
        return JsonResponse(
            {'ok': False, 'mensaje': f'No encuentro el item de descuento de {donde}. '
                                     'Hay que crearlo en el admin.'}, status=400)

    try:
        if en_productos:
            from ventas.models import ReservaProducto
            ReservaProducto.objects.create(
                venta_reserva=venta, producto=item, cantidad=monto,
                precio_unitario_venta=item.precio_base)
        else:
            from ventas.models import ReservaServicio
            fecha = _fecha_del_descuento(venta)
            ReservaServicio.objects.create(
                venta_reserva=venta, servicio=item,
                fecha_agendamiento=fecha,
                hora_inicio='00:00', cantidad_personas=monto,
                precio_unitario_venta=item.precio_base)
        venta.calcular_total()
    except Exception as exc:  # noqa: BLE001
        logger.exception('[tarjeta] no se pudo descontar $%s en la reserva %s: %s',
                         monto, venta_id, exc)
        return JsonResponse({'ok': False, 'mensaje': 'No se pudo aplicar el '
                             'descuento. Inténtalo desde el admin.'}, status=400)

    venta.refresh_from_db()
    return JsonResponse({
        'ok': True,
        'total': int(venta.total or 0),
        'pagado': int(venta.pagado or 0),
        'saldo': int(venta.saldo_pendiente or 0),
        'descuento': monto,
    })


# --- Agregar servicio desde una lista ---------------------------------------
# El calendario está hecho para lo que OCUPA una hora: muestra la grilla y se
# elige el hueco libre. Pero hay servicios que no ocupan ninguna —chocolates,
# desayuno de una cabaña, comisión de Booking— y para ésos el calendario es un
# trámite: elegir fecha, esperar la grilla, elegir una hora que da lo mismo.
#
# Jorge (05-09-2026): "también debe dar la posibilidad de elegir servicios de
# una lista, la lista visible del admin de django". Se da la lista completa,
# como el admin — pero el admin NO valida disponibilidad, y por acá sí se
# valida: agregar una tina a una hora ocupada es sobreventa, y eso no se
# arregla después.
TIPOS_CON_HORARIO = ('tina', 'cabana', 'masaje')


def _servicios_de_lista():
    """Los servicios activos, sin los descuentos.

    Los descuentos tienen su propio botón desde el 05-09-2026, donde se
    escribe el monto en pesos. Dejarlos también acá sería ofrecer el camino
    confuso —"cantidad" que en realidad son pesos— que se acaba de sacar.
    """
    from ventas.models import Servicio

    return (Servicio.objects.filter(activo=True)
            .exclude(precio_base__lt=0)
            .select_related('categoria')
            .order_by('categoria__nombre', 'nombre'))


@staff_required
@require_POST
def tarjeta_agregar_servicio_lista(request, venta_id):
    """Agrega un servicio elegido de la lista, sin pasar por el calendario."""
    from ventas.models import ReservaServicio, Servicio

    venta = get_object_or_404(VentaReserva, pk=venta_id)

    try:
        servicio = Servicio.objects.get(pk=request.POST.get('servicio_id'), activo=True)
    except (Servicio.DoesNotExist, ValueError, TypeError):
        return JsonResponse({'ok': False, 'mensaje': 'Elige un servicio de la lista.'},
                            status=400)
    # Mismo criterio que el selector: un descuento entra por su propio botón.
    if (servicio.precio_base or 0) < 0:
        return JsonResponse(
            {'ok': False, 'mensaje': 'Los descuentos se aplican con el botón '
                                     '«Aplicar descuento».'}, status=400)

    crudo = (request.POST.get('cantidad') or '1').strip()
    if not crudo.isdigit() or int(crudo) < 1:
        return JsonResponse({'ok': False, 'mensaje': 'Cantidad inválida.'}, status=400)
    cantidad = int(crudo)

    fecha = _fecha_del_descuento(venta)          # la de los servicios de la reserva
    cruda_fecha = (request.POST.get('fecha') or '').strip()
    if cruda_fecha:
        try:
            fecha = datetime.datetime.strptime(cruda_fecha, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({'ok': False, 'mensaje': 'Fecha inválida.'}, status=400)

    hora = (request.POST.get('hora') or '').strip() or '00:00'

    # Lo que ocupa un horario se valida. El admin no lo hace y por eso el
    # calendario existe; acá se aprovecha la misma función que ya usa el resto
    # del sistema en vez de escribir otra.
    if servicio.tipo_servicio in TIPOS_CON_HORARIO:
        try:
            from ventas.calendar_utils import verificar_disponibilidad
            libre = verificar_disponibilidad(servicio, fecha, hora, cantidad)
        except Exception:  # noqa: BLE001
            logger.exception('[tarjeta] no se pudo verificar disponibilidad de %s',
                             servicio.pk)
            libre = False
        if not libre:
            return JsonResponse(
                {'ok': False,
                 'mensaje': f'{servicio.nombre} no está disponible el '
                            f'{fecha:%d/%m} a las {hora}. Usa el calendario '
                            'para ver los horarios libres.'}, status=400)

    try:
        ReservaServicio.objects.create(
            venta_reserva=venta, servicio=servicio,
            fecha_agendamiento=fecha, hora_inicio=hora,
            cantidad_personas=cantidad,
            precio_unitario_venta=servicio.precio_base)
        venta.calcular_total()
    except Exception as exc:  # noqa: BLE001
        logger.exception('[tarjeta] no se pudo agregar el servicio %s a la '
                         'reserva %s: %s', servicio.pk, venta_id, exc)
        return JsonResponse({'ok': False, 'mensaje': 'No se pudo agregar el '
                             'servicio. Inténtalo desde el admin.'}, status=400)

    venta.refresh_from_db()
    return JsonResponse({
        'ok': True,
        'total': int(venta.total or 0),
        'pagado': int(venta.pagado or 0),
        'saldo': int(venta.saldo_pendiente or 0),
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
