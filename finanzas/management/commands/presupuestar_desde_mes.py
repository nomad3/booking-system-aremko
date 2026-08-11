# -*- coding: utf-8 -*-
"""Carga los presupuestos a partir de lo que se gastó de verdad en un mes.

    python manage.py presupuestar_desde_mes                        # solo mira
    python manage.py presupuestar_desde_mes --aplicar              # escribe

Pedido de Jorge (2026-08-11): partir con el 70% del gasto de julio. No es un
pronóstico, es una meta de recorte — el reporte va a marcar en rojo todo lo que
no llegue a esa meta, y eso es lo que se busca.

Por defecto NO escribe y NO pisa lo que ya tenga presupuesto: se propone solo
para los ítems que están en cero. Con --pisar se reemplaza todo.
"""
from datetime import date

from django.core.management.base import BaseCommand
from django.db.models import Sum

from finanzas.models import CategoriaFinanciera, MovimientoFinanciero
from finanzas.reglas import GRUPO_DEVOLUCIONES, GRUPOS_FAMILIA

# Lo que no tiene sentido presupuestar:
# - «Por clasificar» y el vale vista sin destino (grupo otros): ponerle una
#   meta a lo que todavía no sabemos qué es sería presupuestar la ignorancia.
# - Devoluciones: no son un costo, son una venta que se deshizo. El reporte
#   las resta de los ingresos, así que una meta ahí no significa nada.
GRUPOS_SIN_PRESUPUESTO = ('otros', GRUPO_DEVOLUCIONES)


def _redondear(monto):
    """Al millar más cercano, pero nunca a cero si hubo gasto: un presupuesto
    de $0 se lee como «sin definir» y el ítem desaparecería del control."""
    valor = int(round(monto / 1000.0) * 1000)
    return valor if valor else 1000


def _clp(n):
    return '$' + format(int(n), ',d').replace(',', '.')


class Command(BaseCommand):
    help = 'Presupuestos iniciales = % del gasto real de un mes.'

    def add_arguments(self, parser):
        parser.add_argument('--mes', default='2026-07',
                            help='Mes base AAAA-MM (por defecto 2026-07).')
        parser.add_argument('--factor', type=float, default=0.7,
                            help='Proporción del gasto real (0.7 = 70%%).')
        parser.add_argument('--aplicar', action='store_true',
                            help='Sin esto solo muestra lo que haría.')
        parser.add_argument('--pisar', action='store_true',
                            help='También reemplaza los presupuestos ya puestos.')

    def handle(self, *args, **opts):
        anio, mes = (int(x) for x in opts['mes'].split('-'))
        factor = opts['factor']

        gastado = {
            f['categoria__id']: int(f['t'] or 0)
            for f in (MovimientoFinanciero.objects
                      .filter(clase='gasto', fecha__year=anio, fecha__month=mes,
                              categoria__isnull=False)
                      .values('categoria__id').annotate(t=Sum('monto')))}
        if not gastado:
            self.stdout.write(self.style.ERROR(
                f'No hay gastos cargados en {opts["mes"]}. Nada que calcular.'))
            return

        cats = {c.id: c for c in CategoriaFinanciera.objects.filter(
            id__in=gastado, clase='gasto')}

        propuestas, saltados_grupo, saltados_puestos = [], [], []
        for cat_id, monto in sorted(gastado.items(), key=lambda x: -x[1]):
            cat = cats.get(cat_id)
            if cat is None:
                continue
            if cat.grupo in GRUPOS_SIN_PRESUPUESTO:
                saltados_grupo.append((cat, monto))
                continue
            if cat.presupuesto_mensual and not opts['pisar']:
                saltados_puestos.append((cat, monto))
                continue
            propuestas.append((cat, monto, _redondear(monto * factor)))

        pct = int(round(factor * 100))
        self.stdout.write(
            f'Base: {opts["mes"]} · presupuesto = {pct}% del gasto real\n')

        familia, negocio = [], []
        for fila in propuestas:
            (familia if fila[0].grupo in GRUPOS_FAMILIA else negocio).append(fila)

        for titulo, filas in (('GASTOS DEL NEGOCIO', negocio),
                              ('RETIROS DE LA FAMILIA', familia)):
            if not filas:
                continue
            self.stdout.write(self.style.MIGRATE_HEADING(f'\n{titulo}'))
            for cat, real, nuevo in filas:
                self.stdout.write(
                    f'  {cat.nombre[:38]:<38} {_clp(real):>12} → {_clp(nuevo):>12}')
            self.stdout.write(
                f'  {"TOTAL":<38} {_clp(sum(f[1] for f in filas)):>12} → '
                f'{_clp(sum(f[2] for f in filas)):>12}')

        if familia:
            # Recortar un retiro no es la misma decisión que recortar un costo:
            # esa conversación es con la familia, no con una planilla.
            self.stdout.write(self.style.WARNING(
                '\nOJO: los retiros también quedaron con meta. Si esa no es la '
                'conversación que querés tener ahora, bórrales el presupuesto '
                'a mano en el plan de cuentas.'))

        for titulo, filas in (
                ('Sin presupuestar (por clasificar / devoluciones)', saltados_grupo),
                ('Ya tenían presupuesto, no se tocan (usa --pisar)', saltados_puestos)):
            if filas:
                self.stdout.write(f'\n{titulo}:')
                for cat, monto in filas:
                    self.stdout.write(f'  {cat.nombre[:38]:<38} {_clp(monto):>12}')

        if not opts['aplicar']:
            self.stdout.write(self.style.WARNING(
                '\nMODO LECTURA: no se escribió nada. Con --aplicar se guardan '
                f'los {len(propuestas)} presupuestos de arriba.'))
            return

        for cat, _real, nuevo in propuestas:
            cat.presupuesto_mensual = nuevo
            cat.save(update_fields=['presupuesto_mensual'])
        self.stdout.write(self.style.SUCCESS(
            f'\nListo: {len(propuestas)} presupuestos escritos.'))
