# -*- coding: utf-8 -*-
"""Qué porcentaje de las ventas se llevó cada gasto en un mes.

    python manage.py calcular_pct_ventas                        # solo calcula
    python manage.py calcular_pct_ventas --aplicar --items insumos,comisiones

Sirve para elegir el % de los costos que se mueven con las ventas, en vez de
inventarlo. Escribe SOLO los ítems que se nombren: cuáles son variables y
cuáles no lo decide Jorge, no una heurística.

Trae además el control del contrato de las masajistas (40% de la venta de
MASAJES, no de la venta total — dato de Jorge 2026-08-11), que es una cuenta
distinta y no se puede expresar con el campo actual.
"""
from datetime import date

from django.core.management.base import BaseCommand
from django.db.models import Sum

from finanzas.models import CategoriaFinanciera, MovimientoFinanciero
from finanzas.reglas import GRUPO_DEVOLUCIONES

PCT_CONTRATO_MASAJISTAS = 40      # del contrato, no de una estimación


def _clp(n):
    return '$' + format(int(n), ',d').replace(',', '.')


def ventas_de_masajes(anio, mes):
    """Lo vendido en masajes ese mes, por fecha de AGENDAMIENTO.

    La fecha del servicio y no la del pago: el honorario se genera cuando la
    masajista trabaja, no cuando el cliente transfiere. Comparar contra la
    fecha de pago mezclaría meses.
    """
    from ventas.models import ReservaServicio

    total = 0
    for rs in (ReservaServicio.objects
               .filter(fecha_agendamiento__year=anio,
                       fecha_agendamiento__month=mes,
                       servicio__categoria__nombre__icontains='masaje')
               .select_related('servicio')):
        unitario = rs.precio_unitario_venta
        if unitario is None:
            unitario = rs.servicio.precio_base if rs.servicio_id else 0
        total += int(unitario or 0) * (rs.cantidad_personas or 1)
    return total


class Command(BaseCommand):
    help = 'Calcula qué % de las ventas representó cada gasto en un mes.'

    def add_arguments(self, parser):
        parser.add_argument('--mes', default='2026-07')
        # nargs='*' y no un string suelto: Jorge corre esto desde el celular y
        # el teclado mete un espacio después de cada coma, con lo que la shell
        # parte «insumos, comisiones» en dos argumentos y argparse lo rechaza.
        # Así da lo mismo si van pegadas, separadas o mezcladas.
        parser.add_argument('--items', nargs='*', default=[],
                            help='Claves a las que ESCRIBIR el %% calculado. '
                                 'Con o sin comas: --items insumos comisiones. '
                                 'Sin esto no se escribe nada.')
        parser.add_argument('--aplicar', action='store_true')

    def handle(self, *args, **opts):
        from finanzas.views import ventas_por_mes

        anio, mes = (int(x) for x in opts['mes'].split('-'))
        ventas = ventas_por_mes(anio, mes).get(date(anio, mes, 1), 0)
        if not ventas:
            self.stdout.write(self.style.ERROR(
                f'No hay ventas registradas en {opts["mes"]}: sin base contra '
                'la cual calcular un porcentaje.'))
            return

        self.stdout.write(
            f'Ventas de {opts["mes"]} (sin giftcards ni descuentos, igual que '
            f'el tablero): {_clp(ventas)}\n')

        gastado = {
            f['categoria__id']: int(f['t'] or 0)
            for f in (MovimientoFinanciero.objects
                      .filter(clase='gasto', fecha__year=anio, fecha__month=mes,
                              categoria__isnull=False)
                      .values('categoria__id').annotate(t=Sum('monto')))}
        cats = {c.id: c for c in CategoriaFinanciera.objects.filter(
            id__in=gastado, clase='gasto')}

        self.stdout.write(self.style.MIGRATE_HEADING(
            'QUÉ % DE LAS VENTAS SE LLEVÓ CADA GASTO'))
        calculado = {}
        for cat_id, monto in sorted(gastado.items(), key=lambda x: -x[1]):
            cat = cats.get(cat_id)
            if cat is None or cat.grupo == GRUPO_DEVOLUCIONES:
                continue
            pct = round(monto * 100.0 / ventas, 1)
            calculado[cat.clave] = pct
            self.stdout.write(
                f'  {cat.nombre[:38]:<38} {_clp(monto):>12}  {pct:>5.1f}%  '
                f'[{cat.clave}]')

        # ── El contrato de las masajistas ──────────────────────────────────
        vm = ventas_de_masajes(anio, mes)
        self.stdout.write(self.style.MIGRATE_HEADING(
            '\nCONTRATO MASAJISTAS: 40% DE LA VENTA DE MASAJES'))
        if not vm:
            self.stdout.write(
                '  No se encontraron servicios de masaje agendados ese mes.')
        else:
            corresponde = int(round(vm * PCT_CONTRATO_MASAJISTAS / 100.0))
            pagado = 0
            cat_m = CategoriaFinanciera.objects.filter(
                clave='honorarios_masajistas').first()
            if cat_m:
                pagado = gastado.get(cat_m.id, 0)
            dif = pagado - corresponde
            self.stdout.write(f'  Venta de masajes del mes      {_clp(vm):>12}')
            self.stdout.write(f'  40% que les corresponde       {_clp(corresponde):>12}')
            self.stdout.write(f'  Honorarios efectivamente pagados {_clp(pagado):>9}')
            if dif > 0:
                self.stdout.write(self.style.WARNING(
                    f'  Se pagó {_clp(dif)} MÁS que el 40% del contrato.'))
            elif dif < 0:
                self.stdout.write(
                    f'  Se pagó {_clp(-dif)} menos que el 40% del contrato.')
            else:
                self.stdout.write(self.style.SUCCESS('  Calza exacto.'))
            equiv = round(pagado * 100.0 / ventas, 1) if pagado else 0
            self.stdout.write(
                f'\n  OJO: el campo de la web mide contra las ventas TOTALES, no\n'
                f'  contra la venta de masajes. En {opts["mes"]} los honorarios\n'
                f'  fueron el {equiv}% del total — pero ese número se desarma en\n'
                f'  cuanto cambie la mezcla entre tinas, cabañas y masajes.\n'
                f'  Para el contrato hace falta que el % pueda apuntar a la\n'
                f'  venta de una familia de servicios.')

        # ── Escritura, solo lo que se nombre ───────────────────────────────
        # Cada trozo puede venir con comas pegadas («insumos,comisiones») o ser
        # una clave suelta con la coma colgando («insumos,»).
        claves = [c.strip() for trozo in opts['items']
                  for c in str(trozo).split(',') if c.strip()]
        if not claves:
            self.stdout.write(self.style.WARNING(
                '\nNo se escribió nada. Para fijar un %, nombrá los ítems:\n'
                '  --aplicar --items insumos,comisiones,impuestos'))
            return

        desconocidas = [c for c in claves if c not in calculado]
        if desconocidas:
            self.stdout.write(self.style.ERROR(
                f'Sin gasto en {opts["mes"]}, no se puede calcular su %: '
                + ', '.join(desconocidas)))
        aplicables = [c for c in claves if c in calculado]
        for clave in aplicables:
            self.stdout.write(f'  {clave} → {calculado[clave]}% de las ventas')
        if not opts['aplicar']:
            self.stdout.write(self.style.WARNING(
                'MODO LECTURA: agregá --aplicar para escribirlos.'))
            return
        for clave in aplicables:
            CategoriaFinanciera.objects.filter(clave=clave).update(
                presupuesto_pct_ventas=calculado[clave])
        self.stdout.write(self.style.SUCCESS(
            f'\nListo: {len(aplicables)} ítem(s) pasaron a medirse como % de '
            'las ventas.'))
