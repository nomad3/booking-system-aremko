# -*- coding: utf-8 -*-
"""Tablero financiero del dueño: por mes, qué entró, qué salió, y el resultado.

Decisión de arquitectura (P-22 F1): los ingresos se leen DIRECTO de ventas.Pago
— ahí ya están día a día y por método, y así el tablero está siempre al día sin
ningún cron de sincronización. Esta app solo aporta lo que Django no tenía:
gastos, traspasos y saldos.

Honestidad del tablero: los meses sin gastos cargados muestran "—" y no un
resultado. Un resultado calculado solo con ingresos sería una mentira cómoda.
"""
from collections import defaultdict
from datetime import date, timedelta

from django.contrib.auth.decorators import user_passes_test
from django.db.models import Count, Max, Sum
from django.db.models.functions import TruncDate
from django.shortcuts import render

from conciliacion.models import MOTIVO_NO_ES_COBRO, MovimientoMP
from ventas.models import Pago

from .models import MovimientoFinanciero, SaldoMensual

# De los ~22 métodos de pago históricos a los canales reales. Los que no están
# acá caen en "Otros" con su nombre crudo — mejor visible que escondido.
CANAL_POR_METODO = {
    'mercadopago': 'Mercado Pago', 'mercadopagoaremko': 'Mercado Pago',
    'mercadopago_link': 'Mercado Pago (link)',
    'flow': 'Flow', 'webpay': 'Flow',
    'tarjeta': 'Tarjeta (SumUp)',
    'efectivo': 'Efectivo',
    'transferencia': 'Transferencia', 'scotiabank': 'Transferencia',
    'bancoestado': 'Transferencia', 'cuentarut': 'Transferencia',
    'scotiabankalda': 'Transferencia', 'bcialda': 'Transferencia',
    'bicegoalda': 'Transferencia', 'andesalda': 'Transferencia',
    'machjorge': 'Transferencia', 'machalda': 'Transferencia',
    'booking': 'Booking',
}
# NO son ingreso nuevo: el canje de giftcard es un pasivo que se libera (la
# plata entró cuando se compró la giftcard) y el descuento es un pseudo-pago.
METODOS_EXCLUIDOS = ('giftcard', 'descuento')
# Métodos que en Django significan "cobrado por Mercado Pago" — el lado sistema
# de la verificación contra la API.
METODOS_MP = ('mercadopago', 'mercadopagoaremko', 'mercadopago_link')


def _clp(n):
    return '$' + format(int(n), ',d').replace(',', '.')


def _meses(n=13):
    """Los últimos n meses como date(año, mes, 1), del más viejo al actual."""
    hoy = date.today()
    lista = []
    anio, mes = hoy.year, hoy.month
    for _ in range(n):
        lista.append(date(anio, mes, 1))
        mes -= 1
        if mes == 0:
            anio, mes = anio - 1, 12
    return list(reversed(lista))


@user_passes_test(lambda u: u.is_superuser)
def tablero(request):
    meses = _meses()
    desde = meses[0]
    hoy = date.today()

    # ── Ingresos, directo de Pago ────────────────────────────────────────────
    ingresos = defaultdict(lambda: defaultdict(int))   # mes → canal → monto
    canje_gc = defaultdict(int)
    filas = (Pago.objects.filter(fecha_pago__date__gte=desde)
             .values('fecha_pago__year', 'fecha_pago__month', 'metodo_pago')
             .annotate(t=Sum('monto')))
    for f in filas:
        m = date(f['fecha_pago__year'], f['fecha_pago__month'], 1)
        met, monto = f['metodo_pago'], int(f['t'] or 0)
        if met == 'giftcard':
            canje_gc[m] += monto
            continue
        if met in METODOS_EXCLUIDOS:
            continue
        ingresos[m][CANAL_POR_METODO.get(met, f'Otros ({met})')] += monto

    canales = sorted({c for por_canal in ingresos.values() for c in por_canal},
                     key=lambda c: -sum(ingresos[m].get(c, 0) for m in meses))

    # ── Gastos y traspasos, de esta app ──────────────────────────────────────
    gastos = defaultdict(lambda: defaultdict(int))     # mes → categoría → monto
    filas_g = (MovimientoFinanciero.objects.filter(clase='gasto', fecha__gte=desde)
               .values('fecha__year', 'fecha__month', 'categoria__nombre')
               .annotate(t=Sum('monto')))
    for f in filas_g:
        m = date(f['fecha__year'], f['fecha__month'], 1)
        gastos[m][f['categoria__nombre'] or 'Sin categoría'] += int(f['t'] or 0)

    categorias = sorted({c for por_cat in gastos.values() for c in por_cat},
                        key=lambda c: -sum(gastos[m].get(c, 0) for m in meses))

    traspasos = defaultdict(lambda: {'entra': 0, 'sale': 0, 'n': 0})
    for f in (MovimientoFinanciero.objects.filter(clase='traspaso', fecha__gte=desde)
              .values('fecha__year', 'fecha__month', 'sentido')
              .annotate(t=Sum('monto'), n=Count('id'))):
        m = date(f['fecha__year'], f['fecha__month'], 1)
        traspasos[m][f['sentido']] += int(f['t'] or 0)
        traspasos[m]['n'] += f['n']

    # Control global: todas las piernas de traspaso del período deben sumar cero.
    agg = (MovimientoFinanciero.objects.filter(clase='traspaso')
           .values('sentido').annotate(t=Sum('monto')))
    tras_totales = {r['sentido']: int(r['t'] or 0) for r in agg}
    traspasos_cuadran = (tras_totales.get('entra', 0) == tras_totales.get('sale', 0))

    saldos = list(SaldoMensual.objects.filter(periodo__gte=desde)
                  .select_related('cuenta').order_by('periodo', 'cuenta__nombre'))

    # ── Verificación Mercado Pago: sistema vs API, día a día (P-22 F2) ───────
    # El corazón de la auditoría: lo que Django registró como cobrado por MP
    # contra lo que la API de MP dice que entró. Se excluyen solo los ajenos
    # (Aremko pagador); lo que Deborah ignoró para SU tarea igual es plata que
    # entró y acá cuenta. El desfase de un día (MP aprueba de noche, se registra
    # a la mañana) es normal — la señal real es el TOTAL de la ventana.
    corte_mp = hoy - timedelta(days=13)
    por_dia = defaultdict(dict)
    for r in (Pago.objects.filter(metodo_pago__in=METODOS_MP,
                                  fecha_pago__date__gte=corte_mp)
              .annotate(d=TruncDate('fecha_pago')).values('d')
              .annotate(t=Sum('monto'), n=Count('id'))):
        por_dia[r['d']].update(sis=int(r['t'] or 0), sis_n=r['n'])
    for r in (MovimientoMP.objects.filter(fecha__date__gte=corte_mp)
              .exclude(sugerencia_motivo=MOTIVO_NO_ES_COBRO)
              .annotate(d=TruncDate('fecha')).values('d')
              .annotate(t=Sum('monto'), n=Count('id'))):
        por_dia[r['d']].update(mp=int(r['t'] or 0), mp_n=r['n'])

    verif_mp, v_sis, v_mp = [], 0, 0
    for d in sorted(por_dia):
        v = por_dia[d]
        sis, mp_t = v.get('sis', 0), v.get('mp', 0)
        dif = mp_t - sis
        v_sis += sis
        v_mp += mp_t
        verif_mp.append({
            'dia': d,
            'sistema': _clp(sis) if sis else '—', 'sistema_n': v.get('sis_n', 0),
            'mp': _clp(mp_t) if mp_t else '—', 'mp_n': v.get('mp_n', 0),
            'dif': (f'+{_clp(dif)}' if dif > 0 else f'−{_clp(-dif)}') if dif else '',
            'dif_alerta': dif != 0,
        })
    verif_dif = v_mp - v_sis
    mp_al_dia = MovimientoMP.objects.aggregate(m=Max('fecha'))['m']

    # ── Armar filas para el template (formateo acá; el template es tonto) ────
    resumen = []
    for m in meses:
        ing = sum(ingresos[m].values())
        gas = sum(gastos[m].values())
        con_gastos = m in gastos
        resumen.append({
            'mes': m, 'es_actual': (m.year, m.month) == (hoy.year, hoy.month),
            'ingresos': _clp(ing) if ing else '—',
            'gastos': _clp(gas) if con_gastos else '—',
            'canje_gc': _clp(canje_gc[m]) if canje_gc[m] else '',
            'traspasos': _clp(traspasos[m]['sale']) if traspasos[m]['n'] else '',
            'resultado': _clp(ing - gas) if (ing and con_gastos) else '—',
            'resultado_neg': con_gastos and (ing - gas) < 0,
        })

    tabla_ingresos = [{'canal': c,
                       'celdas': [_clp(ingresos[m][c]) if ingresos[m].get(c) else ''
                                  for m in meses]} for c in canales]
    tabla_gastos = [{'categoria': c,
                     'celdas': [_clp(gastos[m][c]) if gastos[m].get(c) else ''
                                for m in meses]} for c in categorias]

    return render(request, 'finanzas/tablero.html', {
        'meses': meses,
        'resumen': resumen,
        'tabla_ingresos': tabla_ingresos,
        'tabla_gastos': tabla_gastos,
        'saldos': saldos,
        'traspasos_cuadran': traspasos_cuadran,
        'tras_totales': {k: _clp(v) for k, v in tras_totales.items()},
        'hay_gastos': bool(categorias),
        'verif_mp': verif_mp,
        'verif_sis': _clp(v_sis),
        'verif_mp_total': _clp(v_mp),
        'verif_dif': ((f'+{_clp(verif_dif)}' if verif_dif > 0 else f'−{_clp(-verif_dif)}')
                      if verif_dif else '$0'),
        'verif_cuadra': verif_dif == 0,
        'mp_al_dia': mp_al_dia,
    })
