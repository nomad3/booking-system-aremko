# -*- coding: utf-8 -*-
"""Encuentra gastos que parecen estar contados dos veces (Jorge 2026-08-10).

Dos formas de duplicarse, y se informan por separado porque se arreglan
distinto:

  MISMA CUENTA  — casi siempre el mismo período cargado desde dos exports
                  distintos del banco. Sobra uno.
  CUENTAS DISTINTAS — el mismo cobro atribuido a dos medios de pago (Google
                  Ads figurando en la CuentaRUT y en la Visa). Sobra el que
                  no corresponde: hay que saber cuál es el bueno.

SOLO LECTURA por defecto. Para borrar hay que decir de QUÉ cuenta, porque
sin esa decisión el sistema no puede saber cuál de los dos es el bueno:

    python manage.py revisar_duplicados
    python manage.py revisar_duplicados --eliminar-de visa_2936
    python manage.py revisar_duplicados --eliminar-de visa_2936 --solo Google
"""
from collections import defaultdict
from datetime import date

from django.core.management.base import BaseCommand


def _clp(n):
    return '$' + format(int(n), ',d').replace(',', '.')


def firma_exacta(mov):
    """Para la DOBLE CARGA: mismo día, monto y glosa IDÉNTICA.

    Comparar por comercio normalizado acá era un error peligroso: las
    comisiones de Mercado Pago y SumUp llevan el id de la venta en la glosa
    («Comisión MP del cobro 170402030994»), el normalizador se lo comía y dos
    comisiones de ventas DISTINTAS con el mismo monto parecían la misma
    (2026-08-10). Con la glosa completa eso no pasa.
    """
    return (mov.fecha, int(mov.monto), (mov.descripcion or '').strip())


def _glosa_normalizada(mov):
    """La glosa sin espacios repetidos, para comparar recortes."""
    return ' '.join((mov.descripcion or '').split()).upper()


def agrupar_por_recorte(movs):
    """Duplicados que la glosa IDÉNTICA no ve: la misma línea, recortada
    distinto por el banco o por el parser.

    El 19-08-2026 entraron cinco compras dos veces en Scotiabank ($355.295):
    «REDCOMPRA LAPIZ LOPEZ      PUE» y «REDCOMPRA LAPIZ LOPEZ» son la misma
    compra, pero la referencia se calcula sobre la glosa y al cambiar el
    recorte cambió la llave de idempotencia.

    El criterio es estrecho a propósito: misma cuenta, misma fecha, mismo
    monto, y una glosa PREFIJO de la otra. No basta con «mismo comercio»,
    porque las comisiones de Mercado Pago y SumUp llevan el id de la venta y
    dos ventas distintas del mismo monto no son un duplicado — ahí ninguna
    glosa es prefijo de la otra.
    """
    grupos, usados = [], set()
    lista = sorted(movs, key=lambda m: (m.fecha, int(m.monto), m.cuenta_id, m.id))
    for i, a in enumerate(lista):
        if a.id in usados:
            continue
        familia = [a]
        ga = _glosa_normalizada(a)
        for b in lista[i + 1:]:
            if (b.fecha, int(b.monto), b.cuenta_id) != (a.fecha, int(a.monto),
                                                        a.cuenta_id):
                continue
            if b.id in usados:
                continue
            gb = _glosa_normalizada(b)
            if ga != gb and (ga.startswith(gb) or gb.startswith(ga)):
                familia.append(b)
        if len(familia) > 1:
            for m in familia:
                usados.add(m.id)
            grupos.append(familia)
    return grupos


def firma_comercio(mov):
    """Para la ATRIBUCIÓN doble: el mismo cobro visto desde dos medios de
    pago, donde cada fuente escribe la glosa a su manera."""
    from finanzas.management.commands.detectar_recurrentes import (
        nombre_comercio)
    return (mov.fecha, int(mov.monto), nombre_comercio(mov.descripcion))


class Command(BaseCommand):
    help = 'Lista (y opcionalmente borra) gastos duplicados.'

    def add_arguments(self, parser):
        parser.add_argument('--desde', default='2026-07-01')
        parser.add_argument('--eliminar-de', default='',
                            help='Clave de la cuenta cuyos duplicados se borran.')
        parser.add_argument('--grupo', default='todos',
                            choices=['todos', 'exactos', 'recortes', 'atribucion'],
                            help='Qué grupo limpiar. «atribucion» junta cargos de '
                                 'CUENTAS distintas y ahí un duplicado aparente '
                                 'puede ser real —dos tarjetas con su propio cobro '
                                 'mensual—, así que conviene acotar.')
        parser.add_argument('--solo', default='',
                            help='Filtra por texto del comercio.')

    def handle(self, *args, **opts):
        from finanzas.models import MovimientoFinanciero

        desde = date.fromisoformat(opts['desde'])
        movs = (MovimientoFinanciero.objects
                .filter(clase='gasto', fecha__gte=desde)
                .select_related('cuenta', 'categoria').order_by('id'))

        # Las de fecha ESTIMADA quedan fuera: el histórico las cargó todas al
        # día 1 porque el correo no traía el día. Ahí «mismo día y mismo
        # monto» NO es señal de duplicado — es señal de que no sabemos las
        # fechas. Borrarlas era destruir pagos reales (Jorge 2026-08-10).
        movs = [m for m in movs if not m.fecha_estimada]

        por_exacta, por_comercio = defaultdict(list), defaultdict(list)
        for m in movs:
            por_exacta[firma_exacta(m)].append(m)
            por_comercio[firma_comercio(m)].append(m)

        def _misma_carga(lista):
            """True si todos entraron en la MISMA subida.

            Una doble carga ocurre en sesiones distintas, con minutos u horas
            de diferencia. Si dos movimientos idénticos se escribieron en el
            mismo segundo, es porque el archivo traía los dos — y existen: dos
            transferencias de $20.000 a Martín el mismo día, con la misma
            glosa porque el pegado no lleva la hora (visto 2026-08-10).
            """
            momentos = [m.creado_en for m in lista if m.creado_en]
            if len(momentos) < len(lista):
                return False
            return (max(momentos) - min(momentos)).total_seconds() < 120

        misma = {k: v for k, v in por_exacta.items()
                 if len(v) > 1 and len({m.cuenta_id for m in v}) == 1
                 and not _misma_carga(v)}
        distintas = {k: v for k, v in por_comercio.items()
                     if len(v) > 1 and len({m.cuenta_id for m in v}) > 1}

        if opts['solo']:
            aguja = opts['solo'].upper()
            misma = {k: v for k, v in misma.items() if aguja in k[2].upper()}
            distintas = {k: v for k, v in distintas.items()
                         if aguja in k[2].upper()}

        def _mostrar(titulo, grupo):
            total = sum(int(m.monto) for lista in grupo.values()
                        for m in lista[1:])
            self.stdout.write(f'\n=== {titulo}: {len(grupo)} casos · '
                              f'sobrante {_clp(total)} ===')
            for (fecha, monto, comercio), lista in sorted(
                    grupo.items(), key=lambda kv: -kv[0][1]):
                self.stdout.write(f'\n{fecha}  {comercio}  {_clp(monto)} '
                                  f'× {len(lista)}')
                for m in lista:
                    self.stdout.write(
                        f'   id {m.id:>6}  {m.cuenta.clave:<18} '
                        f'{m.fuente:<8} {(m.descripcion or "")[:52]}')
            return total

        recortes = {(g[0].fecha, int(g[0].monto), _glosa_normalizada(g[0])[:40]): g
                    for g in agrupar_por_recorte(movs)
                    if not _misma_carga(g)}
        if opts['solo']:
            aguja = opts['solo'].upper()
            recortes = {k: v for k, v in recortes.items() if aguja in k[2]}

        sobra_misma = _mostrar('MISMA CUENTA (doble carga)', misma)
        sobra_recorte = _mostrar('MISMA CUENTA (misma línea, recorte distinto)',
                                 recortes)
        sobra_dist = _mostrar('CUENTAS DISTINTAS (atribución)', distintas)
        self.stdout.write(f'\nSobrante total estimado: '
                          f'{_clp(sobra_misma + sobra_recorte + sobra_dist)}')

        objetivo = opts['eliminar_de']
        if not objetivo:
            self.stdout.write(
                '\nNada se borró. Para limpiar, repetir con '
                '--eliminar-de <clave_de_cuenta>: se borran los duplicados '
                'que estén en ESA cuenta, dejando siempre al menos uno.')
            return

        borrados = total = 0
        # `recortes` también se puede limpiar: si no entrara acá, el
        # informe encontraría duplicados que nadie puede borrar.
        elegidos = {'exactos': list(misma.values()),
                    'recortes': list(recortes.values()),
                    'atribucion': list(distintas.values())}
        if opts['grupo'] == 'todos':
            a_borrar = (elegidos['exactos'] + elegidos['recortes']
                        + elegidos['atribucion'])
        else:
            a_borrar = elegidos[opts['grupo']]
        self.stdout.write(f'\nBorrando del grupo «{opts["grupo"]}»: '
                          f'{len(a_borrar)} caso(s).')
        for lista in a_borrar:
            candidatos = [m for m in lista if m.cuenta.clave == objetivo]
            # Nunca dejar el grupo vacío: si todos son de esa cuenta, se
            # conserva el primero. Borrar el cobro entero sería peor que el
            # duplicado.
            sobrantes = (candidatos[1:] if len(candidatos) == len(lista)
                         else candidatos)
            for m in sobrantes:
                if m.traspaso_par_id:
                    self.stdout.write(f'   saltado id {m.id}: es parte de un '
                                      'traspaso, hay que deshacerlo a mano')
                    continue
                total += int(m.monto)
                borrados += 1
                m.delete()
        self.stdout.write(f'\nBorrados {borrados} movimientos de '
                          f'«{objetivo}» por {_clp(total)}.')
