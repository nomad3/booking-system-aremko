"""
Vista para mostrar la agenda operativa del día con servicios y productos
organizados cronológicamente desde la hora actual en adelante.
"""

from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db.models import Q, Min
from django.db import transaction
from django.utils import timezone
from datetime import datetime, time, timedelta
from collections import defaultdict
import json
import logging
from ..models import ReservaServicio, ReservaProducto, VentaReserva, Comanda, DetalleComanda

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Checkout: quién se va hoy y cuánto debe
# ---------------------------------------------------------------------------
# Una estadía NO tiene "fecha de salida" en la BD: se guarda una ReservaServicio
# POR NOCHE, con la misma cabaña en fechas consecutivas. La salida es una
# DERIVACIÓN: última noche + 1 día.
#
# Por eso la consulta obvia ("cabañas con fecha_agendamiento = ayer") está mal:
# también agarra a quien LLEGÓ ayer y se queda 2 noches — ese sale mañana y
# todavía está alojado. La regla correcta es que esa reserva no tenga NINGUNA
# noche de cabaña de hoy en adelante.
DIAS_REZAGADOS_CHECKOUT = 3  # se arrastran salidas viejas SOLO si quedaron debiendo


# ---------------------------------------------------------------------------
# Qué comandas tiene que ver cocina HOY
# ---------------------------------------------------------------------------
# Caso real (Jorge 2026-08-02, reserva 6479): confirmó dos pedidos, quedaron
# bien guardados en 'pendiente'... y no aparecieron en la agenda ni sonó nada.
#
# La regla anterior tenía dos casos y le faltaba el tercero:
#   1. fecha_entrega_objetivo definida → debe caer HOY.
#   2. Sin fecha objetivo → algún ReservaServicio de la reserva debe ser HOY.
# La 6479 no tenía NINGÚN servicio, así que el caso 2 no podía cumplirse jamás:
# comandas HUÉRFANAS, sin fecha propia y sin un servicio del cual colgarse.
# Invisibles para siempre, no solo ese día. De ahí el caso 3.
#
# Además se cayó el filtro `creada_por_cliente=True`: a cocina le importa el
# ESTADO del pedido, no quién lo tecleó. Ese filtro dejaba invisibles todas las
# comandas que el admin crea solo (`_asegurar_comanda_de_productos` no marca ese
# campo — y hace bien, porque NO las creó el cliente): el 2026-08-02 se perdieron
# así las #701, #702 y #705.
#
# Vive en UNA función porque la página y el polling del sonido consumen lo mismo.
# Antes era la misma consulta copiada en dos lugares, que es exactamente cómo un
# arreglo se aplica a medias.
ESTADOS_COCINA = ('pendiente', 'procesando')


def comandas_para_cocina(hoy):
    """Comandas que hay que preparar HOY, vengan de donde vengan."""
    sin_objetivo = Q(fecha_entrega_objetivo__isnull=True)
    return (
        Comanda.objects.filter(estado__in=ESTADOS_COCINA)
        .filter(
            # 1. Tiene fecha de entrega propia y es hoy.
            Q(fecha_entrega_objetivo__date=hoy)
            # 2. Sin fecha propia: se cuelga de un servicio de hoy.
            | (sin_objetivo & Q(venta_reserva__reservaservicios__fecha_agendamiento=hoy))
            # 3. Sin fecha propia y la reserva NO tiene servicios: no hay de qué
            #    colgarse, así que manda el día en que se pidió. Sin esto, el
            #    pedido no aparece NUNCA.
            | (sin_objetivo
               & Q(venta_reserva__reservaservicios__isnull=True)
               & Q(fecha_solicitud__date=hoy))
        )
        .distinct()
        .select_related('venta_reserva__cliente', 'usuario_procesa')
        # Etapa destino-comanda: prefetch servicios para calcular destino sin N+1
        .prefetch_related('detalles__producto', 'venta_reserva__reservaservicios__servicio')
        .order_by('fecha_solicitud')
    )


def _ids_de_reserva(agenda_ordenada):
    """Todas las reservas que aparecen hoy en la agenda, sin repetir."""
    ids = set()
    for bloque in agenda_ordenada or []:
        for item in (bloque.get('items') or []):
            rid = item.get('reserva_id')
            if rid:
                ids.add(rid)
    return ids


def _llegadas_de_la_agenda(agenda_ordenada):
    """{reserva_id: '15:04'} para pintar quién ya está adentro.

    Una sola consulta para toda la pantalla, y el formato de hora resuelto acá:
    la plantilla solo imprime lo que recibe.
    """
    from ..llegadas import hora_local, llegadas_de
    return {rid: hora_local(cuando)
            for rid, cuando in llegadas_de(_ids_de_reserva(agenda_ordenada)).items()}


def comandas_fuera_de_hoy(hoy):
    """Pendientes que NO entran hoy (quedan para otro día).

    Se muestran como contador en la agenda: una comanda que no aparece y no
    avisa es indistinguible de una que se perdió — que es justo lo que pasó.
    """
    return (
        Comanda.objects.filter(estado__in=ESTADOS_COCINA)
        .exclude(pk__in=comandas_para_cocina(hoy).values('pk'))
        .count()
    )


def _clp(n):
    """15000 → '15.000'. Se formatea acá y no con `floatformat` en el template:
    el separador de miles depende del locale y `es-CL` ya rompió números antes
    (ver el fix de {% localize off %} en el JSON-LD)."""
    return f"{int(n or 0):,}".replace(",", ".")


# Verificado contra producción el 2026-08-14, preparando la sincronización con
# Booking/Airbnb: `tipo_servicio='cabana'` NO significa «es una cabaña». Trae
# también «Persona Adicional en Cabaña» (43) y «Hora Adicional Cabaña» (44), que
# son modificadores de precio, no lugares donde dormir. La reserva 6381 tiene la
# Torre y una persona adicional el MISMO día: contando filas son 2 noches, y fue
# 1. Son 48 filas de adicionales sobre 1.207.
#
# Se distinguen por capacidad: las 5 cabañas reales admiten 2 personas; los dos
# adicionales, 1. No es un campo que signifique «alojamiento» —el día que exista
# una cabaña individual esto se rompe— pero es el mejor dato disponible sin
# tocar el modelo, y vive en UN solo lugar a propósito: la agenda y el calendario
# que se exporta a las OTAs tienen que contar exactamente las mismas noches.
CAPACIDAD_MINIMA_ALOJAMIENTO = 2


def filtro_alojamiento():
    """Los `filter(**...)` que dejan solo cabañas de verdad."""
    return {'servicio__tipo_servicio': 'cabana',
            'servicio__capacidad_maxima__gte': CAPACIDAD_MINIMA_ALOJAMIENTO}


def salidas_para_checkout(hoy, dias_rezagados=DIAS_REZAGADOS_CHECKOUT):
    """Reservas que hacen checkout hoy + las que salieron antes debiendo.

    Devuelve una lista de dicts ordenada: primero las que deben (mayor saldo
    arriba), después las pagadas. Cada dict trae total/pagado/saldo por separado
    a propósito: `saldo_pendiente` es un campo ALMACENADO y ya hubo un bug en
    `actualizar_saldo` (H-060) — mostrando los tres juntos, una inconsistencia
    salta a la vista en vez de esconderse en un solo número.
    """
    desde = hoy - timedelta(days=dias_rezagados)
    ayer = hoy - timedelta(days=1)

    # Noches de cabaña en la ventana (la última de cada reserva define la salida).
    noches = ReservaServicio.objects.filter(
        **filtro_alojamiento(),
        fecha_agendamiento__gte=desde,
        fecha_agendamiento__lte=ayer,
        venta_reserva__isnull=False,
    ).exclude(
        venta_reserva__estado_reserva='cancelada'
    ).select_related('servicio', 'venta_reserva__cliente')

    # Agrupar por reserva: fecha de llegada, de última noche y qué cabañas.
    por_reserva = {}
    for n in noches:
        v = n.venta_reserva
        d = por_reserva.setdefault(v.id, {
            'venta': v, 'primera_noche': n.fecha_agendamiento,
            'ultima_noche': n.fecha_agendamiento, 'cabanas': set(), 'noches': 0,
        })
        d['primera_noche'] = min(d['primera_noche'], n.fecha_agendamiento)
        d['ultima_noche'] = max(d['ultima_noche'], n.fecha_agendamiento)
        d['cabanas'].add(n.servicio.nombre)
        d['noches'] += 1

    if not por_reserva:
        return []

    # ¿Sigue alojado? Si la reserva tiene una noche de cabaña de HOY en adelante,
    # todavía no se va — no importa que también tenga noches viejas.
    siguen = set(
        ReservaServicio.objects.filter(
            **filtro_alojamiento(),
            fecha_agendamiento__gte=hoy,
            venta_reserva_id__in=list(por_reserva.keys()),
        ).values_list('venta_reserva_id', flat=True)
    )

    salidas = []
    for venta_id, d in por_reserva.items():
        if venta_id in siguen:
            continue  # sigue alojado: su checkout es otro día
        v = d['venta']
        saldo = int(v.saldo_pendiente or 0)
        salida = d['ultima_noche'] + timedelta(days=1)
        dias_atras = (hoy - salida).days
        # Las viejas solo interesan si quedaron debiendo; las de hoy, siempre.
        if dias_atras > 0 and saldo <= 0:
            continue
        salidas.append({
            'reserva_id': venta_id,
            'cliente': getattr(v.cliente, 'nombre', '') or 'Sin nombre',
            'telefono': getattr(v.cliente, 'telefono', '') or '',
            'cabanas': ', '.join(sorted(d['cabanas'])),
            'noches': d['noches'],
            'llegada': d['primera_noche'],
            'salida': salida,
            'dias_atras': dias_atras,      # 0 = se va hoy; >0 = rezagado
            'total': int(v.total or 0),
            'pagado': int(v.pagado or 0),
            'saldo': saldo,
            'total_fmt': _clp(v.total),
            'pagado_fmt': _clp(v.pagado),
            'saldo_fmt': _clp(saldo),
            'estado_pago': v.estado_pago,
            'debe': saldo > 0,
            # Para que el botón de check-out sepa si esta salida ya se cerró
            # (si no, al recargar la agenda el botón reaparecería como si nada).
            'estado_reserva': v.estado_reserva,
            'cerrada': v.estado_reserva == 'checkout',
        })

    # Deudores primero (mayor saldo arriba), después las pagadas por hora natural.
    salidas.sort(key=lambda s: (not s['debe'], -s['saldo'], s['salida']))
    return salidas


# ---------------------------------------------------------------------------
# Cálculo de destino sugerido para comandas (cocina/bar)
# ---------------------------------------------------------------------------
# Regla de negocio:
#   - Solo tinas             → TINA
#   - Solo cabañas           → CABAÑA
#   - Tinas + cabañas        → TINA por defecto, ALERT (puede pedir cabaña)
#   - Tinas + masajes        → TINA (masaje nunca lleva comanda)
#   - Cabañas + masajes      → CABAÑA (masaje nunca lleva comanda)
#   - Tinas + cabañas + masajes → aplica regla mixta (ignora masaje)
#   - Solo masajes / sin tipos relevantes → SIN_DESTINO (raro tener comanda)
def calcular_destino_comanda(venta_reserva, hoy=None):
    """Devuelve dict con destino sugerido + horario para una comanda.

    Muestra el NOMBRE ESPECÍFICO + HORARIO del servicio reservado.
    Aremko tiene 8 tinas y varias cabañas — la cocina necesita saber a
    cuál y a qué hora exactamente, sin entrar a la reserva.

    Args:
        venta_reserva: instancia de VentaReserva (idealmente con
        reservaservicios__servicio prefetched)
        hoy: fecha de referencia (default = hoy local). Servicios cuya
        fecha_agendamiento coincide con `hoy` muestran su HH:MM normal;
        los de otro día (típico: alojamiento multi-día) muestran "(en curso)"
        para no confundir con el horario de hoy.

    Returns:
        {
            'destino': 'tina' | 'cabana' | 'sin_destino',
            'label': str   ("Tina Hidromasaje Hornopirén · 18:00" o
                            "Cabaña Calbuco · (en curso)" si multi-día),
            'icon': str    ('🛁', '🏠', '❓'),
            'verificar': bool  (True si hay tina+cabaña → cocina confirma),
            'razon_verificar': str  ("también hay Cabaña Calbuco · 14:00 — confirmar destino"),
        }
    """
    if venta_reserva is None:
        return {
            'destino': 'sin_destino', 'label': 'SIN DESTINO', 'icon': '❓',
            'verificar': True, 'razon_verificar': 'sin reserva asociada',
        }

    if hoy is None:
        hoy = timezone.localtime(timezone.now()).date()

    # Recolectar (nombre, hora_formateada) por tipo
    tinas = []      # list of (nombre, label_hora)
    cabanas = []
    for rs in venta_reserva.reservaservicios.all():
        if not rs.servicio or not rs.servicio.tipo_servicio:
            continue
        tipo = rs.servicio.tipo_servicio
        if tipo not in ('tina', 'cabana'):
            continue
        nombre = (rs.servicio.nombre or '').strip()
        if not nombre:
            continue
        # Hora: si es hoy, mostrar HH:MM. Si es otro día (alojamiento multi-día),
        # marcar "(en curso)" para no confundir con horario de hoy.
        if rs.fecha_agendamiento == hoy:
            hora_label = rs.hora_inicio or ''
        else:
            hora_label = '(en curso)'

        item = (nombre, hora_label)
        if tipo == 'tina' and item not in tinas:
            tinas.append(item)
        elif tipo == 'cabana' and item not in cabanas:
            cabanas.append(item)

    def _fmt(items):
        """('Tina X', '18:00') → 'Tina X · 18:00'; concatena múltiples con ' + '."""
        parts = []
        for nombre, hora in items:
            parts.append(f'{nombre} · {hora}' if hora else nombre)
        return ' + '.join(parts)

    tiene_tina = bool(tinas)
    tiene_cabana = bool(cabanas)

    if tiene_tina and tiene_cabana:
        return {
            'destino': 'tina',
            'label': _fmt(tinas),
            'icon': '🛁',
            'verificar': True,
            'razon_verificar': f'también hay {_fmt(cabanas)} — confirmar destino',
        }
    if tiene_tina:
        return {
            'destino': 'tina',
            'label': _fmt(tinas),
            'icon': '🛁',
            'verificar': False, 'razon_verificar': '',
        }
    if tiene_cabana:
        return {
            'destino': 'cabana',
            'label': _fmt(cabanas),
            'icon': '🏠',
            'verificar': False, 'razon_verificar': '',
        }
    return {
        'destino': 'sin_destino', 'label': 'SIN DESTINO', 'icon': '❓',
        'verificar': True,
        'razon_verificar': 'reserva sin tina ni cabaña — revisar',
    }


def staff_required(view_func):
    """Decorador para requerir que el usuario sea staff"""
    decorated_view = user_passes_test(lambda u: u.is_staff)(view_func)
    return login_required(decorated_view)

@staff_required
def manual_recepcion(request):
    """El ciclo completo de una reserva, para el equipo de recepción.

    Vive DENTRO del sistema y no como documento aparte por una razón práctica:
    acá se actualiza cuando cambia el flujo. Un manual que envejece es peor que
    no tener manual — enseña a hacer algo que ya no existe y nadie se entera.
    """
    return render(request, 'ventas/manual_recepcion.html')


@staff_required
def agenda_operativa(request):
    """
    Vista principal de la agenda operativa del día.
    Muestra todos los servicios y productos pendientes desde la hora actual,
    organizados cronológicamente.
    """
    # Obtener fecha y hora actuales en zona horaria local
    ahora = timezone.localtime(timezone.now())
    hoy = ahora.date()
    hora_actual = ahora.time()

    # Si se especifica una hora de inicio (para testing), usarla
    hora_inicio_param = request.GET.get('desde_hora')
    if hora_inicio_param:
        try:
            hora_actual = datetime.strptime(hora_inicio_param, '%H:%M').time()
        except:
            pass  # Usar hora actual si hay error

    # Modo debug para ver todos los servicios del día
    debug_mode = request.GET.get('debug', '').lower() == 'true'
    if debug_mode:
        hora_actual = time(0, 0)  # Mostrar desde las 00:00 en modo debug

    # Filtro de vista: actual (desde hora actual), todos (todo el día), pasados (anteriores a hora actual), pendientes_pago
    filtro_vista = request.GET.get('filtro', 'actual')
    if filtro_vista not in ['actual', 'todos', 'pasados', 'pendientes_pago', 'checkout']:
        filtro_vista = 'actual'  # Default seguro

    # Aplicar filtro
    hora_filtro_inicio = hora_actual
    hora_filtro_fin = time(23, 59)

    if filtro_vista in ('todos', 'checkout'):
        # Checkout es una tarea de CIERRE: debajo del panel conviene ver el día
        # completo, no solo lo que queda desde la hora actual.
        hora_filtro_inicio = time(0, 0)  # Desde las 00:00
        hora_filtro_fin = time(23, 59)
    elif filtro_vista == 'pasados':
        hora_filtro_inicio = time(0, 0)
        hora_filtro_fin = hora_actual  # Hasta la hora actual
    elif filtro_vista == 'pendientes_pago':
        hora_filtro_inicio = time(0, 0)  # Todo el día
        hora_filtro_fin = time(23, 59)

    # Determinar rango de fechas según filtro
    if filtro_vista == 'pendientes_pago':
        # Incluir día actual y día anterior (para cabañas con alojamiento)
        ayer = hoy - timedelta(days=1)
        fecha_filtro = Q(fecha_agendamiento=hoy) | Q(fecha_agendamiento=ayer)
    else:
        # Solo día actual
        fecha_filtro = Q(fecha_agendamiento=hoy)

    # Obtener servicios según filtro de fecha
    # Primero filtrar servicios que tienen venta_reserva asociada
    # Excluir servicios de descuento que no son servicios reales
    servicios = ReservaServicio.objects.filter(
        fecha_filtro,
        venta_reserva__isnull=False  # Asegurar que hay venta_reserva
    ).exclude(
        venta_reserva__estado_reserva='cancelada'
    ).exclude(
        servicio__nombre__icontains='descuento'  # Excluir servicios de descuento
    ).select_related(
        'servicio',
        'venta_reserva__cliente'
    ).order_by('fecha_agendamiento', 'hora_inicio')

    # Filtrar servicios según el filtro seleccionado
    servicios_pendientes = []
    for servicio in servicios:
        try:
            # Validar que hora_inicio existe y tiene formato correcto
            if not servicio.hora_inicio:
                continue

            # Para filtro de pendientes_pago, verificar estado de pago primero
            if filtro_vista == 'pendientes_pago':
                estado_pago = servicio.venta_reserva.estado_pago if servicio.venta_reserva else None
                if estado_pago not in ['pendiente', 'parcial']:
                    continue  # Saltar servicios pagados o sin estado

            # Determinar fecha del servicio para cálculos de hora
            fecha_servicio = servicio.fecha_agendamiento
            servicio_hora = datetime.strptime(servicio.hora_inicio, '%H:%M').time()

            # Calcular hora de fin basado en la duración del servicio
            if servicio.servicio and hasattr(servicio.servicio, 'duracion') and servicio.servicio.duracion:
                hora_inicio_dt = datetime.combine(fecha_servicio, servicio_hora)
                hora_fin_dt = hora_inicio_dt + timedelta(minutes=int(servicio.servicio.duracion))
                hora_fin = hora_fin_dt.time()

                # Marcar si está en curso o ya pasó (solo relevante para día actual)
                if fecha_servicio == hoy:
                    en_curso = (servicio_hora < hora_actual and hora_fin > hora_actual)
                    es_pasado = (hora_fin <= hora_actual)
                else:
                    # Servicios de ayer siempre son pasados
                    en_curso = False
                    es_pasado = True

                servicio.en_curso = en_curso
                servicio.es_pasado = es_pasado
                servicio.hora_fin = hora_fin.strftime('%H:%M')

                # Aplicar filtro según vista seleccionada
                if filtro_vista == 'pendientes_pago':
                    # Ya filtrado por estado_pago arriba, incluir todos
                    servicios_pendientes.append(servicio)
                elif filtro_vista == 'todos':
                    # Mostrar todos los servicios del día
                    servicios_pendientes.append(servicio)
                elif filtro_vista == 'pasados':
                    # Mostrar solo servicios que ya terminaron
                    if fecha_servicio == hoy and hora_fin <= hora_actual:
                        servicios_pendientes.append(servicio)
                    elif fecha_servicio < hoy:
                        servicios_pendientes.append(servicio)
                else:  # filtro_vista == 'actual'
                    # Mostrar servicios futuros o en curso (comportamiento original)
                    if fecha_servicio == hoy and (servicio_hora >= hora_actual or en_curso):
                        servicios_pendientes.append(servicio)
            else:
                # Si no hay duración, usar lógica simplificada
                if fecha_servicio == hoy:
                    servicio.en_curso = False
                    servicio.es_pasado = (servicio_hora < hora_actual)
                else:
                    servicio.en_curso = False
                    servicio.es_pasado = True
                servicio.hora_fin = None

                if filtro_vista == 'pendientes_pago':
                    servicios_pendientes.append(servicio)
                elif filtro_vista == 'todos':
                    servicios_pendientes.append(servicio)
                elif filtro_vista == 'pasados':
                    if fecha_servicio < hoy or (fecha_servicio == hoy and servicio_hora < hora_actual):
                        servicios_pendientes.append(servicio)
                else:  # filtro_vista == 'actual'
                    if fecha_servicio == hoy and servicio_hora >= hora_actual:
                        servicios_pendientes.append(servicio)
        except Exception as e:
            # Log del error pero continuar con otros servicios
            continue

    # Buscar desayunos del día siguiente para preparar hoy
    # NO buscar desayunos si es filtro de pagos pendientes (no es relevante)
    manana = hoy + timedelta(days=1)

    # Solo buscar desayunos si la hora actual es antes de las 23:00 Y no es filtro de pagos pendientes
    desayunos_manana = []
    if hora_actual <= time(23, 0) and filtro_vista != 'pendientes_pago':
        desayunos_manana = ReservaServicio.objects.filter(
            fecha_agendamiento=manana,
            servicio__nombre__icontains='desayuno',
            venta_reserva__isnull=False
        ).exclude(
            venta_reserva__estado_reserva='cancelada'
        ).select_related(
            'servicio',
            'venta_reserva__cliente'
        ).order_by('hora_inicio')

    # Organizar por hora (y opcionalmente por fecha si es filtro de pagos pendientes)
    if filtro_vista == 'pendientes_pago':
        # Para pagos pendientes, organizar primero por fecha, luego por hora
        agenda_por_fecha = defaultdict(lambda: defaultdict(list))
        agenda_por_hora = defaultdict(list)  # Definir también por si se necesita para desayunos
    else:
        agenda_por_hora = defaultdict(list)

    for servicio in servicios_pendientes:
        hora_key = servicio.hora_inicio

        # Lógica inteligente para determinar dónde mostrar los productos
        productos_a_entregar = []

        # Obtener todos los servicios del día de esta reserva
        servicios_del_dia = ReservaServicio.objects.filter(
            venta_reserva=servicio.venta_reserva,
            fecha_agendamiento=hoy
        ).exclude(
            servicio__nombre__icontains='descuento'
        ).select_related('servicio').order_by('hora_inicio')

        # Los productos se muestran en TODAS las tarjetas de la reserva (decisión
        # Jorge 2026-07-18): máxima visibilidad — el badge de estado + el botón
        # "✓ Entregar" evitan la doble preparación. (Regla anterior: solo en la
        # primera tina/cabaña/masaje; los productos quedaban escondidos si la
        # tina era tarde, ej. cabaña 16:00 con tina 22:00.)
        mostrar_productos_aqui = True

        # Solo procesar productos si este servicio debe mostrarlos
        if mostrar_productos_aqui:
            # Verificar si la reserva tiene un servicio de desayuno hoy
            tiene_desayuno_hoy = servicios_del_dia.filter(
                servicio__nombre__icontains='desayuno'
            ).exists()

            # Determinar si el servicio actual es de desayuno
            es_servicio_desayuno = servicio.servicio and 'desayuno' in servicio.servicio.nombre.lower()

            # Estado de preparación por producto: cruza con las comandas de la
            # reserva (la fuente de verdad del flujo cocina). Si hay varias
            # comandas con el mismo producto, gana la más reciente. Sin comanda
            # → 'pendiente' (nadie lo ha preparado).
            estado_por_producto = {}
            detalles_comanda = DetalleComanda.objects.filter(
                comanda__venta_reserva=servicio.venta_reserva,
            ).exclude(
                # borrador/pendiente_pago/pago_fallido son carritos WhatsApp sin
                # concretar; cancelada no se prepara.
                comanda__estado__in=('cancelada', 'borrador', 'pendiente_pago', 'pago_fallido'),
            ).select_related('comanda').order_by('comanda__fecha_solicitud')
            for det in detalles_comanda:
                est = det.comanda.estado
                if est == 'pago_confirmado':
                    est = 'pendiente'  # pagada por el cliente pero aún sin preparar
                estado_por_producto[det.producto_id] = est  # la más reciente pisa

            # Obtener productos de la reserva que NO sean descuentos
            # y que no hayan sido entregados en días anteriores
            productos = ReservaProducto.objects.filter(
                venta_reserva=servicio.venta_reserva
            ).filter(
                # Incluir solo productos con fecha_entrega de hoy o sin fecha_entrega (NULL)
                Q(fecha_entrega__isnull=True) | Q(fecha_entrega=hoy)
            ).select_related('producto')

            for producto in productos:
                # Verificar si el producto existe
                if not producto.producto:
                    continue

                # Verificar si es un descuento
                try:
                    nombre_producto = str(producto.producto.nombre or "").strip()
                    precio_producto = float(producto.producto.precio_base or 0)

                    es_descuento = any([
                        'descuento' in nombre_producto.lower(),
                        'discount' in nombre_producto.lower(),
                        'dto' in nombre_producto.lower(),
                        precio_producto < 0,
                        nombre_producto.startswith('-'),
                    ])

                    # Si NO es descuento, verificar si debe mostrarse
                    if not es_descuento:
                        # Si es un producto de desayuno (café, etc.)
                        es_producto_desayuno = any([
                            'cafe' in nombre_producto.lower(),
                            'café' in nombre_producto.lower(),
                            'desayuno' in nombre_producto.lower(),
                            'marley' in nombre_producto.lower(),  # Café Marley
                            'jugo' in nombre_producto.lower(),
                            'leche' in nombre_producto.lower(),
                            'pan' in nombre_producto.lower(),
                            'mantequilla' in nombre_producto.lower(),
                            'mermelada' in nombre_producto.lower()
                        ])

                        # Lógica especial para productos de desayuno
                        if es_producto_desayuno and tiene_desayuno_hoy and not es_servicio_desayuno:
                            # Si hay desayuno hoy y el servicio actual NO es desayuno,
                            # NO mostrar productos de desayuno (ya se entregaron en la mañana)
                            continue

                        # Si pasó todos los filtros, agregar el producto con su
                        # estado de preparación (para el badge en el template).
                        producto.estado_comanda = estado_por_producto.get(
                            producto.producto_id, 'pendiente')
                        productos_a_entregar.append(producto)
                except Exception:
                    # En caso de error, no incluir el producto
                    continue

        # Agregar a la agenda (con verificaciones de seguridad)
        if servicio.servicio and servicio.venta_reserva and servicio.venta_reserva.cliente:
            # Obtener estado de pago y montos
            venta = servicio.venta_reserva
            estado_pago = venta.estado_pago
            total = venta.total
            pagado = venta.pagado
            saldo_pendiente = venta.saldo_pendiente

            # Verificar si el servicio es de ayer
            fecha_servicio = servicio.fecha_agendamiento
            es_de_ayer = (fecha_servicio < hoy)

            item_data = {
                'servicio': servicio,
                'tipo': 'servicio',
                'nombre': servicio.servicio.nombre,
                'cliente': servicio.venta_reserva.cliente.nombre,
                'reserva_id': servicio.venta_reserva.id,
                'cantidad_personas': servicio.cantidad_personas or 1,
                'productos': productos_a_entregar,
                'es_proximo': False,  # Se marcará después
                'en_curso': getattr(servicio, 'en_curso', False),  # Si está en ejecución
                'es_pasado': getattr(servicio, 'es_pasado', False),  # Si ya terminó
                'es_de_ayer': es_de_ayer,  # Si es del día anterior
                'fecha_servicio': fecha_servicio.strftime('%d/%m/%Y'),  # Fecha formateada
                'hora_fin': getattr(servicio, 'hora_fin', None),  # Hora de finalización
                'duracion': servicio.servicio.duracion if servicio.servicio else None,  # Duración en minutos
                'estado_pago': estado_pago,
                'total': total,
                'pagado': pagado,
                'saldo_pendiente': saldo_pendiente,
                'estado_reserva': servicio.venta_reserva.estado_reserva,  # Agregar estado de la reserva
                'comentarios': (venta.comentarios or '').strip(),  # Comentario de la reserva (instrucciones operativas)
            }

            # Agregar a la estructura correspondiente según el filtro
            if filtro_vista == 'pendientes_pago':
                # Agrupar por fecha y luego por hora
                fecha_key = fecha_servicio.strftime('%Y-%m-%d')
                agenda_por_fecha[fecha_key][hora_key].append(item_data)
            else:
                # Agrupar solo por hora
                agenda_por_hora[hora_key].append(item_data)

    # Agregar desayunos del día siguiente si los hay
    if desayunos_manana:
        # Agrupar desayunos por preparación
        desayunos_info = []
        for desayuno in desayunos_manana:
            if desayuno.servicio and desayuno.venta_reserva and desayuno.venta_reserva.cliente:
                desayunos_info.append({
                    'cliente': desayuno.venta_reserva.cliente.nombre,
                    'hora_servicio': desayuno.hora_inicio,
                    'cantidad_personas': desayuno.cantidad_personas or 1,
                    'reserva_id': desayuno.venta_reserva.id,
                    'estado_pago': desayuno.venta_reserva.estado_pago
                })

        # Agregar bloque de preparación de desayunos a las 17:10
        # Pero solo si aún no ha pasado la hora de fin (23:00)
        hora_inicio_prep = time(17, 10)
        hora_fin_prep = time(23, 0)

        # Determinar si está en curso
        en_curso_prep = hora_inicio_prep <= hora_actual <= hora_fin_prep

        # Solo agregar si es futuro o está en curso
        if hora_actual <= hora_fin_prep:
            # Si ya pasó la hora de inicio, agregarlo en la hora actual para que aparezca
            hora_key_prep = '17:10' if hora_actual < hora_inicio_prep else hora_actual.strftime('%H:%M')

            agenda_por_hora['17:10'].append({
                'tipo': 'preparacion_desayuno',
                'nombre': f'Preparación de Desayunos - {len(desayunos_info)} servicio(s) para mañana',
                'cliente': 'Múltiples clientes',
                'es_preparacion': True,
                'cantidad_desayunos': len(desayunos_info),
                'desayunos_detalle': desayunos_info,
                'es_proximo': False,
                'en_curso': en_curso_prep,
                'hora_fin': '23:00',
                'duracion': 350,  # 5 horas 50 minutos
                'estado_pago': 'preparacion',  # Estado especial
                'total': 0,
                'pagado': 0,
                'saldo_pendiente': 0
            })

    # Convertir a lista ordenada y marcar servicios urgentes
    agenda_ordenada = []
    hora_limite_urgente = (ahora + timedelta(minutes=30)).time()

    if filtro_vista == 'pendientes_pago':
        # Para pagos pendientes, organizar por fecha y hora con secciones claras
        ayer = hoy - timedelta(days=1)

        # Mapas para nombres en español (sin depender de locale)
        dias_semana = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
        meses = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
                 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']

        # Procesar primero servicios de AYER (si existen)
        ayer_key = ayer.strftime('%Y-%m-%d')
        if ayer_key in agenda_por_fecha:
            # Formatear fecha en español
            dia_semana_ayer = dias_semana[ayer.weekday()]
            mes_ayer = meses[ayer.month - 1]
            fecha_texto_ayer = f"📅 AYER - {dia_semana_ayer} {ayer.day} de {mes_ayer}, {ayer.year}"

            # Agregar header de sección para AYER
            agenda_ordenada.append({
                'tipo_seccion': 'header_fecha',
                'fecha': ayer,
                'fecha_texto': fecha_texto_ayer,
                'es_ayer': True
            })

            # Agregar horas de ayer ordenadas
            for hora in sorted(agenda_por_fecha[ayer_key].keys()):
                hora_obj = datetime.strptime(hora, '%H:%M').time()
                agenda_ordenada.append({
                    'hora': hora,
                    'es_urgente': False,  # Servicios de ayer no son urgentes
                    'es_de_ayer': True,
                    'items': agenda_por_fecha[ayer_key][hora]
                })

        # Procesar servicios de HOY (si existen)
        hoy_key = hoy.strftime('%Y-%m-%d')
        if hoy_key in agenda_por_fecha:
            # Formatear fecha en español
            dia_semana_hoy = dias_semana[hoy.weekday()]
            mes_hoy = meses[hoy.month - 1]
            fecha_texto_hoy = f"📅 HOY - {dia_semana_hoy} {hoy.day} de {mes_hoy}, {hoy.year}"

            # Agregar header de sección para HOY
            agenda_ordenada.append({
                'tipo_seccion': 'header_fecha',
                'fecha': hoy,
                'fecha_texto': fecha_texto_hoy,
                'es_hoy': True
            })

            # Agregar horas de hoy ordenadas
            for hora in sorted(agenda_por_fecha[hoy_key].keys()):
                hora_obj = datetime.strptime(hora, '%H:%M').time()
                es_urgente = hora_obj <= hora_limite_urgente
                agenda_ordenada.append({
                    'hora': hora,
                    'es_urgente': es_urgente,
                    'es_de_hoy': True,
                    'items': agenda_por_fecha[hoy_key][hora]
                })
    else:
        # Lógica normal: organizar solo por hora
        for hora in sorted(agenda_por_hora.keys()):
            hora_obj = datetime.strptime(hora, '%H:%M').time()
            es_urgente = hora_obj <= hora_limite_urgente

            agenda_ordenada.append({
                'hora': hora,
                'es_urgente': es_urgente,
                'items': agenda_por_hora[hora]
            })

    # Calcular estadísticas (filtrar headers de sección que no tienen items)
    bloques_con_items = [h for h in agenda_ordenada if 'items' in h]

    total_servicios = sum(len(h['items']) for h in bloques_con_items) if bloques_con_items else 0
    # Sumar las CANTIDADES de productos SIN duplicar: el mismo producto aparece
    # en todas las tarjetas de su reserva, pero se cuenta una sola vez.
    productos_unicos = {}
    for h in bloques_con_items:
        for item in h.get('items', []):
            for producto in item.get('productos', []):
                productos_unicos[producto.id] = producto.cantidad
    total_productos = sum(productos_unicos.values()) if productos_unicos else 0
    # Contar servicios en curso
    servicios_en_curso = sum(
        1 for h in bloques_con_items
        for item in h.get('items', [])
        if item.get('en_curso', False)
    ) if bloques_con_items else 0

    # Contar servicios por estado de pago
    servicios_pagados = sum(
        1 for h in bloques_con_items
        for item in h.get('items', [])
        if item.get('estado_pago') == 'pagado'
    ) if bloques_con_items else 0

    servicios_parcial = sum(
        1 for h in bloques_con_items
        for item in h.get('items', [])
        if item.get('estado_pago') == 'parcial'
    ) if bloques_con_items else 0

    servicios_pendientes_pago = sum(
        1 for h in bloques_con_items
        for item in h.get('items', [])
        if item.get('estado_pago') == 'pendiente'
    ) if bloques_con_items else 0

    # Identificar próximos servicios (próxima hora) - solo en bloques con items
    if bloques_con_items:
        # Marcar items de la primera hora como próximos
        for item in bloques_con_items[0]['items']:
            item['es_proximo'] = True

    # En modo debug, agregar información adicional
    debug_info = None
    if debug_mode:
        # Contar todos los servicios antes de filtrar (excluyendo descuentos)
        todos_servicios = ReservaServicio.objects.filter(
            fecha_agendamiento=hoy
        ).exclude(
            servicio__nombre__icontains='descuento'
        ).count()

        # Servicios por estado (excluyendo descuentos)
        servicios_por_estado = {}
        for servicio in ReservaServicio.objects.filter(
            fecha_agendamiento=hoy
        ).exclude(
            servicio__nombre__icontains='descuento'
        ).select_related('venta_reserva', 'servicio'):
            if servicio.servicio:  # Verificar que el servicio existe
                estado = servicio.venta_reserva.estado_reserva if servicio.venta_reserva else 'sin_reserva'
                servicios_por_estado[estado] = servicios_por_estado.get(estado, 0) + 1

        # Mostrar algunos servicios de ejemplo (excluyendo descuentos)
        primeros_servicios = []
        for servicio in ReservaServicio.objects.filter(
            fecha_agendamiento=hoy
        ).exclude(
            servicio__nombre__icontains='descuento'
        ).select_related('servicio', 'venta_reserva__cliente')[:5]:
            if servicio.servicio:  # Verificar que el servicio existe
                primeros_servicios.append({
                    'id': servicio.id,
                    'servicio': servicio.servicio.nombre,
                    'hora': servicio.hora_inicio,
                    'cliente': servicio.venta_reserva.cliente.nombre if servicio.venta_reserva and servicio.venta_reserva.cliente else 'Sin cliente',
                    'estado': servicio.venta_reserva.estado_reserva if servicio.venta_reserva else 'Sin reserva'
                })

        # Contar productos filtrados como descuento
        productos_descuento_filtrados = []
        total_productos_filtrados = 0
        for venta in VentaReserva.objects.filter(fecha_venta=hoy):
            for prod in ReservaProducto.objects.filter(venta_reserva=venta).select_related('producto'):
                if prod.producto:
                    try:
                        nombre = str(prod.producto.nombre or "").strip()
                        precio = float(prod.producto.precio_base or 0)
                        if 'descuento' in nombre.lower() or precio < 0:
                            total_productos_filtrados += 1
                            if len(productos_descuento_filtrados) < 5:  # Solo mostrar primeros 5
                                productos_descuento_filtrados.append({
                                    'nombre': nombre,
                                    'precio': precio
                                })
                    except:
                        pass

        debug_info = {
            'total_servicios_hoy': todos_servicios,
            'servicios_filtrados': len(servicios),
            'servicios_pendientes': len(servicios_pendientes),
            'servicios_en_curso': servicios_en_curso,
            'servicios_por_estado': servicios_por_estado,
            'primeros_servicios': primeros_servicios,
            'productos_descuento_filtrados': productos_descuento_filtrados,
            'total_productos_descuento': total_productos_filtrados,
            'hora_actual_str': hora_actual.strftime('%H:%M'),
            'fecha_hoy': hoy.strftime('%Y-%m-%d')
        }

    # --- Comandas que cocina tiene que preparar hoy (sección destacada) ---
    comandas_pendientes = comandas_para_cocina(hoy)

    comandas_data = []
    for c in comandas_pendientes:
        tiempo_espera = timezone.now() - c.fecha_solicitud
        minutos = int(tiempo_espera.total_seconds() // 60)
        items = [
            {'nombre': d.producto.nombre, 'cantidad': d.cantidad}
            for d in c.detalles.select_related('producto').all()
        ]
        cliente_nombre = ''
        if c.venta_reserva and c.venta_reserva.cliente:
            cliente_nombre = c.venta_reserva.cliente.nombre
        destino = calcular_destino_comanda(c.venta_reserva, hoy=hoy)
        comandas_data.append({
            'id': c.id,
            'estado': c.estado,
            'cliente': cliente_nombre,
            'reserva_id': c.venta_reserva_id,
            'minutos_espera': minutos,
            'items': items,
            'usuario_procesa': c.usuario_procesa.get_short_name() if c.usuario_procesa else None,
            # Destino sugerido para cocina/bar (regla tina/cabaña/masaje)
            'destino': destino['destino'],
            'destino_label': destino['label'],
            'destino_icon': destino['icon'],
            'destino_verificar': destino['verificar'],
            'destino_razon': destino['razon_verificar'],
        })

    # Checkout: quién se va hoy y cuánto debe. Se calcula SIEMPRE (es barato) para
    # poder mostrar el contador en el botón aunque el filtro activo sea otro.
    try:
        checkouts = salidas_para_checkout(hoy)
    except Exception:  # noqa: BLE001 — la agenda nunca se cae por este bloque
        logger.exception('Agenda operativa: falló el cálculo de checkouts')
        checkouts = []
    checkout_deudores = [c for c in checkouts if c['debe']]
    checkout_por_cobrar = _clp(sum(c['saldo'] for c in checkout_deudores))
    checkout_salen_hoy = sum(1 for c in checkouts if c['dias_atras'] == 0)

    context = {
        'agenda': agenda_ordenada,
        'fecha_actual': hoy.strftime('%d/%m/%Y'),
        'hora_actual': hora_actual.strftime('%H:%M'),
        'hora_generacion': ahora.strftime('%H:%M'),
        'total_servicios': total_servicios,
        'servicios_en_curso': servicios_en_curso,
        'total_productos': total_productos,
        'servicios_pagados': servicios_pagados,
        'servicios_parcial': servicios_parcial,
        'servicios_pendientes_pago': servicios_pendientes_pago,
        'tiene_tareas': len(agenda_ordenada) > 0,
        'debug_mode': debug_mode,
        'debug_info': debug_info,
        'filtro_vista': filtro_vista,
        'comandas_pendientes': comandas_data,
        'comandas_otro_dia': comandas_fuera_de_hoy(hoy),
        'llegadas': _llegadas_de_la_agenda(agenda_ordenada),
        'checkouts': checkouts,
        'checkout_por_cobrar': checkout_por_cobrar,
        'checkout_deudores': checkout_deudores,
        'checkout_salen_hoy': checkout_salen_hoy,
    }

    return render(request, 'ventas/agenda_operativa.html', context)


# ---------------------------------------------------------------------------
# AJAX: polling de comandas pendientes
# ---------------------------------------------------------------------------

@staff_required
@require_http_methods(["GET"])
def comandas_pendientes_api(request):
    """Comandas por preparar hoy (polling del aviso sonoro).

    Usa la MISMA función que la página, a propósito: si el sonido y la pantalla
    consultaran distinto, cocina oiría avisos de comandas que no puede ver.
    """
    hoy = timezone.localtime(timezone.now()).date()

    comandas = comandas_para_cocina(hoy)

    data = []
    for c in comandas:
        tiempo_espera = timezone.now() - c.fecha_solicitud
        minutos = int(tiempo_espera.total_seconds() // 60)
        items = [
            {'nombre': d.producto.nombre, 'cantidad': d.cantidad}
            for d in c.detalles.select_related('producto').all()
        ]
        cliente_nombre = ''
        if c.venta_reserva and c.venta_reserva.cliente:
            cliente_nombre = c.venta_reserva.cliente.nombre
        destino = calcular_destino_comanda(c.venta_reserva, hoy=hoy)
        data.append({
            'id': c.id,
            'estado': c.estado,
            'cliente': cliente_nombre,
            'reserva_id': c.venta_reserva_id,
            'minutos_espera': minutos,
            'items': items,
            'usuario_procesa': c.usuario_procesa.get_short_name() if c.usuario_procesa else None,
            'destino': destino['destino'],
            'destino_label': destino['label'],
            'destino_icon': destino['icon'],
            'destino_verificar': destino['verificar'],
            'destino_razon': destino['razon_verificar'],
        })

    return JsonResponse({'success': True, 'comandas': data})


# ---------------------------------------------------------------------------
# AJAX: marcar llegada a mano (el plan B del QR)
# ---------------------------------------------------------------------------

@staff_required
@require_http_methods(["POST"])
def marcar_llegada_api(request):
    """Marca la llegada desde la agenda, sin QR de por medio.

    Este camino NO es un respaldo de segunda: es como se ha trabajado siempre
    —llega alguien, dice su nombre, se busca en la agenda del día— y tiene que
    seguir funcionando igual de bien. Sin celular, sin batería, sin señal o con
    un cliente que nunca abrió El Pase, recepción marca acá y sigue.

    Body JSON: { reserva_id: int }
    """
    from ..llegadas import VIA_MANUAL, hora_local, registrar_llegada

    try:
        data = json.loads(request.body)
        venta = VentaReserva.objects.select_related('cliente').get(
            id=data.get('reserva_id'))
    except (ValueError, TypeError, VentaReserva.DoesNotExist):
        return JsonResponse({'success': False, 'error': 'Reserva no encontrada'},
                            status=404)

    cuando, recien = registrar_llegada(venta, usuario=request.user, via=VIA_MANUAL)
    if cuando is None:
        return JsonResponse({'success': False, 'error': 'No se pudo registrar'},
                            status=500)
    # `recien=False` (ya estaba marcada) NO es un error: la respuesta es exitosa
    # igual, con la hora real de llegada.
    venta.refresh_from_db(fields=['estado_reserva'])
    return JsonResponse({'success': True, 'recien': recien,
                         'hora': hora_local(cuando),
                         'estado_reserva': venta.estado_reserva})


@staff_required
@require_http_methods(["POST"])
def marcar_checkout_api(request):
    """Cierra la estadía desde la agenda: deja la reserva en 'Check-out'.

    El caso real es el mostrador: el huésped entrega la llave y se va. Hasta
    ahora había que abrir la reserva en el admin y cambiar el estado a mano, y
    lo que cuesta dos pantallas se hace "después" — o no se hace.

    Cerrar con saldo pendiente SÍ está permitido (a veces el cobro se acuerda
    aparte), pero la confirmación la pide el navegador y el saldo queda escrito
    en el movimiento.

    Body JSON: { reserva_id: int }
    """
    from ..llegadas import hora_local, registrar_salida

    try:
        data = json.loads(request.body)
        venta = VentaReserva.objects.select_related('cliente').get(
            id=data.get('reserva_id'))
    except (ValueError, TypeError, VentaReserva.DoesNotExist):
        return JsonResponse({'success': False, 'error': 'Reserva no encontrada'},
                            status=404)

    cuando, recien = registrar_salida(venta, usuario=request.user)
    if cuando is None:
        return JsonResponse({'success': False, 'error': 'No se pudo registrar el check-out'},
                            status=500)
    # `recien=False` (ya estaba cerrada) no es un error: se responde igual de
    # bien, con la hora real en que se cerró.
    venta.refresh_from_db(fields=['estado_reserva'])
    return JsonResponse({'success': True, 'recien': recien,
                         'hora': hora_local(cuando),
                         'estado_reserva': venta.estado_reserva})


# ---------------------------------------------------------------------------
# AJAX: cambiar estado de una comanda (registra usuario logueado)
# ---------------------------------------------------------------------------

@staff_required
@require_http_methods(["POST"])
def comanda_cambiar_estado_api(request):
    """
    Cambia el estado de una comanda y registra el usuario que hizo el cambio.
    Body JSON: { comanda_id: int, nuevo_estado: 'procesando'|'entregada' }
    """
    try:
        data = json.loads(request.body)
        comanda_id = data.get('comanda_id')
        nuevo_estado = data.get('nuevo_estado')

        if nuevo_estado not in ('procesando', 'entregada'):
            return JsonResponse({'success': False, 'error': 'Estado no válido'}, status=400)

        # Sin filtrar por `creada_por_cliente`: la agenda ahora muestra también
        # las comandas que crea el admin, y los botones tienen que funcionar
        # sobre TODO lo que se muestra. El acceso ya lo cuida @staff_required.
        comanda = Comanda.objects.get(id=comanda_id)

        if nuevo_estado == 'procesando':
            comanda.estado = 'procesando'
            comanda.usuario_procesa = request.user
            comanda.fecha_inicio_proceso = timezone.now()
            comanda.save()
        elif nuevo_estado == 'entregada':
            comanda.estado = 'entregada'
            comanda.fecha_entrega = timezone.now()
            if not comanda.usuario_procesa:
                comanda.usuario_procesa = request.user
            comanda.save()  # save() propaga fecha_entrega a ReservaProducto

        return JsonResponse({
            'success': True,
            'comanda_id': comanda.id,
            'nuevo_estado': comanda.estado,
            'usuario': request.user.get_short_name() or request.user.username,
        })

    except Comanda.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Comanda no encontrada'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@staff_required
@require_http_methods(["POST"])
def producto_marcar_entregado_api(request):
    """1-click desde la agenda: marca ENTREGADO un producto de una reserva.

    Si una comanda real de cocina ya contiene el producto, ESA comanda pasa a
    'entregada' (con sus timestamps, igual que comanda_cambiar_estado_api). Si
    ninguna lo cubre, se crea una comanda directamente en 'entregada' con ese
    producto. Idempotente: si ya estaba entregada, responde success sin tocar.
    Body JSON: { reserva_producto_id: int }
    """
    try:
        data = json.loads(request.body)
        rp = (ReservaProducto.objects
              .select_related('venta_reserva', 'producto')
              .get(id=data.get('reserva_producto_id')))
    except (ValueError, TypeError, ReservaProducto.DoesNotExist):
        return JsonResponse({'success': False, 'error': 'Producto de reserva no encontrado'}, status=404)

    try:
        with transaction.atomic():
            det = (
                DetalleComanda.objects
                .filter(comanda__venta_reserva_id=rp.venta_reserva_id, producto_id=rp.producto_id)
                .exclude(comanda__estado__in=('cancelada', 'borrador', 'pendiente_pago', 'pago_fallido'))
                .select_related('comanda')
                .order_by('-comanda__fecha_solicitud')
                .first()
            )
            if det:
                comanda = det.comanda
                if comanda.estado != 'entregada':
                    comanda.estado = 'entregada'
                    comanda.fecha_entrega = timezone.now()
                    if not comanda.usuario_procesa:
                        comanda.usuario_procesa = request.user
                    comanda.save()  # save() propaga fecha_entrega a ReservaProducto
            else:
                comanda = Comanda.objects.create(
                    venta_reserva=rp.venta_reserva,
                    estado='entregada',
                    usuario_solicita=request.user,
                    usuario_procesa=request.user,
                    fecha_entrega=timezone.now(),
                    notas_generales='[Agenda] Marcado entregado con 1 click',
                )
                DetalleComanda.objects.create(
                    comanda=comanda,
                    producto=rp.producto,
                    cantidad=rp.cantidad,
                    precio_unitario=rp.precio_unitario_venta or rp.producto.precio_base or 0,
                )
        return JsonResponse({'success': True, 'comanda_id': comanda.id, 'estado': 'entregada'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)