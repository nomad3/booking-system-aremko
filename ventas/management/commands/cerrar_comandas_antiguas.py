"""cerrar_comandas_antiguas
==========================

Cierra las comandas que quedaron abiertas de visitas que YA PASARON.

De dónde sale (Jorge, 2026-08-03): el aviso nuevo de la Agenda Operativa mostró
**83 comandas pendientes de otros días**. Ese contador se agregó justamente para
que nada quedara invisible (H-095), pero 83 es tanto que el aviso se vuelve ruido
de fondo y deja de servir. Son pedidos que nadie marcó como entregados y quedaron
abiertos para siempre.

REGLA (la que pidió Jorge): se cierra solo si **todos los servicios de la reserva
son anteriores a hoy**. Si la reserva tiene un servicio de hoy o futuro, la
comanda sigue viva — cocina todavía la tiene que preparar.

Reservas sin servicios (existen — ver H-095): manda la fecha objetivo de la
comanda, y si tampoco hay, el día en que se pidió.

INVENTARIO — lo importante
--------------------------
Pasar una comanda a 'entregada' dispara `entregar_inventario()`, que descuenta
stock. PERO el cron `procesar_entregas_comandas_vencidas` ya descuenta el
inventario de las comandas cuya fecha objetivo pasó, y es idempotente (solo toca
`ReservaProducto` con `fecha_entrega` nula). O sea: para las comandas viejas el
stock normalmente YA se descontó y cerrarlas no mueve nada.

"Normalmente" no es "siempre", así que el modo de solo lectura informa **cuántas
líneas moverían inventario de verdad** antes de que alguien apriete el botón. Ese
es el número con el que se decide.

Uso:
    python manage.py cerrar_comandas_antiguas              # SOLO INFORMA
    python manage.py cerrar_comandas_antiguas --aplicar    # cierra
    python manage.py cerrar_comandas_antiguas --dias 7     # solo lo anterior a hace 7 días
"""
from collections import Counter

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from ventas.models import Comanda, ReservaProducto

ESTADOS_ABIERTOS = ('pendiente', 'procesando')


def fecha_de_referencia(comanda):
    """Cuándo "correspondía" esta comanda. None si no se puede determinar.

    Prioridad: el ÚLTIMO servicio de la reserva (si la visita terminó, la
    comanda ya no tiene sentido) → fecha objetivo → fecha de solicitud.
    """
    venta = comanda.venta_reserva
    if venta:
        fechas = [rs.fecha_agendamiento
                  for rs in venta.reservaservicios.all()
                  if rs.fecha_agendamiento]
        if fechas:
            return max(fechas)
    if comanda.fecha_entrega_objetivo:
        return timezone.localtime(comanda.fecha_entrega_objetivo).date()
    if comanda.fecha_solicitud:
        return timezone.localtime(comanda.fecha_solicitud).date()
    return None


def comandas_a_cerrar(corte):
    """Las que quedaron abiertas de visitas anteriores a `corte`.

    Devuelve [(comanda, fecha_referencia)] — la fecha viaja para poder mostrarla
    sin recalcularla.
    """
    candidatas = (Comanda.objects
                  .filter(estado__in=ESTADOS_ABIERTOS)
                  .select_related('venta_reserva')
                  .prefetch_related('venta_reserva__reservaservicios', 'detalles__producto')
                  .order_by('id'))
    salida = []
    for c in candidatas:
        ref = fecha_de_referencia(c)
        if ref and ref < corte:
            salida.append((c, ref))
    return salida


def productos_involucrados(comandas):
    """[(nombre, unidades, en_cuantas_comandas, stock_actual)] ordenado por unidades.

    Lo pidió Jorge para revisar el inventario ANTES de cerrar nada: saber qué
    productos y cuántas unidades están metidas en esas comandas, y compararlo
    contra el stock que hay hoy.
    """
    unidades = Counter()
    apariciones = Counter()
    stock = {}
    for comanda, _ref in comandas:
        vistos = set()
        for d in comanda.detalles.all():
            if not d.producto_id:
                continue
            nombre = d.producto.nombre if d.producto else f'(producto {d.producto_id})'
            unidades[nombre] += int(d.cantidad or 0)
            if d.producto_id not in vistos:
                apariciones[nombre] += 1
                vistos.add(d.producto_id)
            if d.producto is not None:
                stock[nombre] = d.producto.cantidad_disponible
    return sorted(
        ((n, unidades[n], apariciones[n], stock.get(n)) for n in unidades),
        key=lambda x: -x[1])


def lineas_que_moverian_stock(comandas):
    """Cuántos ReservaProducto se descontarían al cerrar (los que NO tienen
    fecha_entrega). Si sale 0, cerrar es puramente contable."""
    ids = [c.venta_reserva_id for c, _ in comandas if c.venta_reserva_id]
    if not ids:
        return 0
    productos = set()
    for c, _ in comandas:
        for d in c.detalles.all():
            productos.add((c.venta_reserva_id, d.producto_id))
    if not productos:
        return 0
    return sum(
        1 for rp in ReservaProducto.objects
        .filter(venta_reserva_id__in=ids, fecha_entrega__isnull=True)
        .values_list('venta_reserva_id', 'producto_id')
        if tuple(rp) in productos
    )


class Command(BaseCommand):
    help = 'Cierra comandas abiertas de visitas ya pasadas. Solo informa salvo --aplicar.'

    def add_arguments(self, parser):
        parser.add_argument('--aplicar', action='store_true',
                            help='Ejecuta el cierre. Sin esto, SOLO informa.')
        parser.add_argument('--dias', type=int, default=0,
                            help='Margen: solo cierra lo anterior a hace N días (default 0 = ayer y antes).')

    def handle(self, *args, **opts):
        hoy = timezone.localtime(timezone.now()).date()
        corte = hoy - timezone.timedelta(days=opts['dias']) if opts['dias'] else hoy

        abiertas = Comanda.objects.filter(estado__in=ESTADOS_ABIERTOS).count()
        objetivo = comandas_a_cerrar(corte)

        self.stdout.write(f'Hoy: {hoy} · corte: anteriores a {corte}')
        self.stdout.write(f'Comandas abiertas en total: {abiertas}')
        self.stdout.write(f'De visitas ya pasadas (a cerrar): {len(objetivo)}')
        self.stdout.write(f'Se quedan abiertas (hoy o futuro): {abiertas - len(objetivo)}')

        if not objetivo:
            self.stdout.write(self.style.SUCCESS('Nada que cerrar.'))
            return

        # Distribución por mes, para ver de dónde vienen sin listar 83 líneas.
        por_mes = Counter(ref.strftime('%Y-%m') for _, ref in objetivo)
        self.stdout.write('\nPor mes de la visita:')
        for mes in sorted(por_mes):
            self.stdout.write(f'  {mes}: {por_mes[mes]}')

        self.stdout.write('\nMás antigua: %s · más reciente: %s' % (
            min(r for _, r in objetivo), max(r for _, r in objetivo)))

        # Qué hay adentro, para poder revisar el inventario de esos productos.
        productos = productos_involucrados(objetivo)
        if productos:
            self.stdout.write('\nPRODUCTOS EN ESAS COMANDAS')
            self.stdout.write('  %-42s %8s %10s %8s' % (
                'Producto', 'Unidades', 'Comandas', 'Stock'))
            self.stdout.write('  ' + '-' * 71)
            for nombre, uds, veces, stk in productos:
                corto = nombre if len(nombre) <= 42 else nombre[:39] + '...'
                self.stdout.write('  %-42s %8d %10d %8s' % (
                    corto, uds, veces, '—' if stk is None else stk))
            self.stdout.write('  ' + '-' * 71)
            self.stdout.write('  %-42s %8d %10d' % (
                'TOTAL', sum(p[1] for p in productos), len(objetivo)))

        # EL número con el que se decide.
        mueven = lineas_que_moverian_stock(objetivo)
        if mueven:
            self.stdout.write(self.style.WARNING(
                f'\n⚠️  {mueven} línea(s) de producto DESCONTARÍAN inventario al cerrar '
                '(no tienen fecha de entrega todavía).'))
        else:
            self.stdout.write(self.style.SUCCESS(
                '\n✅ Ninguna línea mueve inventario: el cron ya lo descontó. '
                'Cerrar es puramente contable.'))

        if not opts['aplicar']:
            self.stdout.write(self.style.NOTICE(
                '\nMODO LECTURA — no se cambió nada. Para ejecutar: --aplicar'))
            return

        cerradas = 0
        ahora = timezone.now()
        for comanda, _ref in objetivo:
            try:
                with transaction.atomic():
                    comanda.estado = 'entregada'
                    if not comanda.fecha_entrega:
                        comanda.fecha_entrega = ahora
                    comanda.save()   # dispara entregar_inventario(), que es idempotente
                cerradas += 1
            except Exception as exc:  # noqa: BLE001 — una mala no puede frenar las 82 buenas
                self.stderr.write(f'  ✗ comanda {comanda.id}: {exc}')

        self.stdout.write(self.style.SUCCESS(
            f'\n✅ {cerradas} comanda(s) cerradas. '
            f'Quedan abiertas: {Comanda.objects.filter(estado__in=ESTADOS_ABIERTOS).count()}'))
