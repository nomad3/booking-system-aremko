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

from .models import (CategoriaFinanciera, CuentaFinanciera,
                     MovimientoFinanciero, SaldoMensual)
from .reglas import GRUPO_DEVOLUCIONES, GRUPOS_FAMILIA

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


GRUPO_COLABORADOR = 'Finanzas colaborador'


def puede_ver_finanzas(u):
    """Superusuario, o miembro del grupo colaborador (Alda; mañana un
    contador). El resto del staff NO ve finanzas — decisión de Jorge:
    «no quiero que muchas personas metan mano en estos reportes»."""
    return u.is_superuser or u.groups.filter(name=GRUPO_COLABORADOR).exists()


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


@user_passes_test(puede_ver_finanzas)
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
    # mes → (grupo, categoría) → monto. Los grupos son el plan de cuentas de
    # Jorge (2026-08-08); los grupos "personales_*" son retiros de la familia
    # y se restan aparte para mostrar el resultado OPERACIONAL del negocio.
    gastos = defaultdict(lambda: defaultdict(int))
    familia_mes = defaultdict(int)
    devoluciones_mes = defaultdict(int)
    filas_g = (MovimientoFinanciero.objects.filter(clase='gasto', fecha__gte=desde)
               .values('fecha__year', 'fecha__month', 'categoria__nombre',
                       'categoria__grupo')
               .annotate(t=Sum('monto')))
    for f in filas_g:
        m = date(f['fecha__year'], f['fecha__month'], 1)
        clave = (f['categoria__grupo'] or 'otros',
                 f['categoria__nombre'] or 'Sin categoría')
        monto = int(f['t'] or 0)
        gastos[m][clave] += monto
        if clave[0] in GRUPOS_FAMILIA:
            familia_mes[m] += monto
        elif clave[0] == GRUPO_DEVOLUCIONES:
            devoluciones_mes[m] += monto

    # Congelar AQUÍ qué meses tienen gastos de verdad: cualquier acceso posterior
    # a gastos[m] crea la llave en el defaultdict y "todos los meses tendrían
    # gastos $0" (visto en prod 2026-08-08). Igual con familia_mes: solo .get().
    meses_con_gastos = set(gastos)

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
        con_gastos = m in meses_con_gastos
        gas_total = sum((gastos.get(m) or {}).values()) if con_gastos else 0
        fam = familia_mes.get(m, 0)
        dev = devoluciones_mes.get(m, 0)
        # Devoluciones: contra-ingreso (el Pago original queda registrado),
        # así que restan de los ingresos y NO cuentan como gasto del negocio.
        gas_negocio = gas_total - fam - dev
        ing_neto = ing - dev
        resumen.append({
            'mes': m, 'es_actual': (m.year, m.month) == (hoy.year, hoy.month),
            'ingresos': _clp(ing_neto) if (ing or dev) else '—',
            'devoluciones': (_clp(dev) if dev else '') if con_gastos else '',
            # "gastos" = los del NEGOCIO (sin retiros de la familia).
            'gastos': _clp(gas_negocio) if con_gastos else '—',
            'retiros': (_clp(fam) if fam else '') if con_gastos else '—',
            'canje_gc': _clp(canje_gc[m]) if canje_gc[m] else '',
            'traspasos': _clp(traspasos[m]['sale']) if traspasos[m]['n'] else '',
            # `con_gastos` es el único guard honesto: los ingresos salen de Pago
            # (fuente siempre completa), así que ing=0 es un cero real — con
            # gastos cargados el resultado se muestra aunque sea todo pérdida.
            'resultado': _clp(ing_neto - gas_negocio) if con_gastos else '—',
            'resultado_neg': con_gastos and (ing_neto - gas_negocio) < 0,
            'resultado_final': _clp(ing_neto - gas_negocio - fam) if con_gastos else '—',
            'final_neg': con_gastos and (ing_neto - gas_negocio - fam) < 0,
        })

    tabla_ingresos = [{'canal': c,
                       'celdas': [_clp(ingresos[m][c]) if ingresos[m].get(c) else ''
                                  for m in meses]} for c in canales]
    # Tabla agrupada: fila de subtotal por grupo (en el orden del plan de
    # cuentas) y debajo sus categorías, solo si el grupo tiene más de una.
    tabla_gastos = []
    for g, g_nombre in CategoriaFinanciera.GRUPOS:
        if g == 'ingresos':
            continue
        cats_g = sorted({c for m in meses_con_gastos
                         for (gg, c) in (gastos.get(m) or {}) if gg == g})
        if not cats_g:
            continue
        celdas_g = [sum((gastos.get(m) or {}).get((g, c), 0) for c in cats_g)
                    for m in meses]
        tabla_gastos.append({'es_grupo': True, 'nombre': g_nombre,
                             'celdas': [_clp(v) if v else '' for v in celdas_g]})
        if len(cats_g) > 1:
            for c in cats_g:
                celdas = [(gastos.get(m) or {}).get((g, c), 0) for m in meses]
                tabla_gastos.append({'es_grupo': False, 'nombre': c,
                                     'celdas': [_clp(v) if v else ''
                                                for v in celdas]})

    # Pedido de Jorge 2026-08-08: todo lo mensual del más NUEVO al más viejo
    # (el mes en curso primero), igual que el flujo de caja.
    resumen.reverse()
    verif_mp.reverse()
    for fila in tabla_ingresos:
        fila['celdas'].reverse()
    for fila in tabla_gastos:
        fila['celdas'].reverse()
    meses = list(reversed(meses))

    return render(request, 'finanzas/tablero.html', {
        'meses': meses,
        'resumen': resumen,
        'tabla_ingresos': tabla_ingresos,
        'tabla_gastos': tabla_gastos,
        'saldos': saldos,
        'traspasos_cuadran': traspasos_cuadran,
        'tras_totales': {k: _clp(v) for k, v in tras_totales.items()},
        'hay_gastos': bool(meses_con_gastos),
        'verif_mp': verif_mp,
        'verif_sis': _clp(v_sis),
        'verif_mp_total': _clp(v_mp),
        'verif_dif': ((f'+{_clp(verif_dif)}' if verif_dif > 0 else f'−{_clp(-verif_dif)}')
                      if verif_dif else '$0'),
        'verif_cuadra': verif_dif == 0,
        'mp_al_dia': mp_al_dia,
    })


MESES_ES = ('', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
            'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre')
MESES_ABREV = ('', 'Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
               'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic')
# Nombres cortos para los encabezados de los reportes: con el nombre completo
# las columnas se estiran y la tabla no cabe en pantalla (Jorge 2026-08-09).
NOMBRE_CORTO_CUENTA = {
    'mercado_pago': 'Mercado Pago',
    'bancoestado': 'BancoEstado Chequera',
    'scotiabank': 'Scotiabank',
    'efectivo': 'Efectivo',
    'visa_2936': 'Visa ••••2936',
    'mach': 'Mach',
    'sumup_transito': 'SumUp tránsito',
    'scotiabank_alda': 'Scotia Alda',
    'cuentarut_jorge': 'CuentaRUT Jorge',
}
# Los gastos parten en julio 2026 (corte decidido 2026-08-08): antes de eso
# no hay datos y las columnas vacías solo estorbarían.
INICIO_GASTOS = date(2026, 7, 1)


def url_movimientos(grupo=None, cat_id=None, ano=None, mes=None,
                    cuenta_id=None):
    """Enlace al listado de movimientos del admin, ya filtrado — ahí mismo se
    reasigna la categoría en la lista (Jorge 2026-08-09: «cómo abro esa
    cuenta para cambiar el gasto de cuenta»)."""
    partes = ['clase__exact=gasto']
    if cat_id:
        partes.append(f'categoria__id__exact={cat_id}')
    elif grupo:
        partes.append(f'categoria__grupo__exact={grupo}')
    if ano:
        partes.append(f'fecha__year={ano}')
    if mes:
        partes.append(f'fecha__month={mes}')
    if cuenta_id:
        partes.append(f'cuenta__id__exact={cuenta_id}')
    return '/admin/finanzas/movimientofinanciero/?' + '&'.join(partes)


def _tabla_matriz(datos, columnas, ids=None, enlace=None):
    """Arma las filas del plan de cuentas contra columnas arbitrarias.

    datos: {(grupo, categoría): {col: monto}} · columnas: claves ordenadas.
    ids: {(grupo, categoría): id} para enlazar la fila de categoría.
    enlace: f(grupo, cat_id, columna_o_None) → URL. Cada cifra con plata
    queda clicable hacia los movimientos que la componen.
    Misma agrupación del tablero: subtotal por grupo y debajo sus categorías
    solo si el grupo tiene más de una.
    """
    ids = ids or {}
    filas = []
    tot_col = {c: 0 for c in columnas}
    tot_general = 0

    def _celda(valor, grupo, cat_id, col):
        return {'txt': _clp(valor) if valor else '',
                'url': enlace(grupo, cat_id, col) if (enlace and valor) else ''}

    for g, g_nombre in CategoriaFinanciera.GRUPOS:
        if g == 'ingresos':
            continue
        cats_g = sorted({cat for (gg, cat) in datos if gg == g})
        if not cats_g:
            continue
        celdas_g = []
        for c in columnas:
            v = sum(datos[(g, cat)].get(c, 0) for cat in cats_g)
            celdas_g.append(v)
            tot_col[c] += v
        total_g = sum(celdas_g)
        tot_general += total_g
        filas.append({
            'es_grupo': True, 'nombre': g_nombre,
            'celdas': [_celda(v, g, None, c)
                       for v, c in zip(celdas_g, columnas)],
            'total': _celda(total_g, g, None, None)})
        if len(cats_g) > 1:
            for cat in cats_g:
                cat_id = ids.get((g, cat))
                celdas = [datos[(g, cat)].get(c, 0) for c in columnas]
                filas.append({
                    'es_grupo': False, 'nombre': cat,
                    'celdas': [_celda(v, g, cat_id, c)
                               for v, c in zip(celdas, columnas)],
                    'total': _celda(sum(celdas), g, cat_id, None)})
    return (filas,
            [_clp(tot_col[c]) if tot_col[c] else '—' for c in columnas],
            _clp(tot_general))


def _param_ano(request, hoy):
    try:
        return int(request.GET.get('ano', hoy.year))
    except (TypeError, ValueError):
        return hoy.year


@user_passes_test(puede_ver_finanzas)
def gastos_mes(request):
    """Reporte de Jorge 2026-08-09: qué se gastó (plan de cuentas, filas)
    cruzado con DESDE QUÉ cuenta salió la plata (columnas), mes a elección."""
    hoy = date.today()
    ano = _param_ano(request, hoy)
    try:
        mes = min(max(int(request.GET.get('mes', hoy.month)), 1), 12)
    except (TypeError, ValueError):
        mes = hoy.month

    datos = defaultdict(lambda: defaultdict(int))
    tot_cuenta = defaultdict(int)
    nombres, ids, cuenta_ids = {}, {}, {}
    for f in (MovimientoFinanciero.objects
              .filter(clase='gasto', fecha__year=ano, fecha__month=mes)
              .values('categoria__grupo', 'categoria__nombre', 'categoria__id',
                      'cuenta__clave', 'cuenta__nombre', 'cuenta__id')
              .annotate(t=Sum('monto'))):
        clave = (f['categoria__grupo'] or 'otros',
                 f['categoria__nombre'] or 'Sin categoría')
        monto = int(f['t'] or 0)
        cta = f['cuenta__clave']
        nombres[cta] = f['cuenta__nombre']
        cuenta_ids[cta] = f['cuenta__id']
        ids[clave] = f['categoria__id']
        datos[clave][cta] += monto
        tot_cuenta[cta] += monto

    # Solo las cuentas que generaron gastos este mes; la que más gasta primero.
    claves = sorted(tot_cuenta, key=lambda c: -tot_cuenta[c])
    filas, tot_columnas, tot_general = _tabla_matriz(
        datos, claves, ids,
        lambda g, cid, cta: url_movimientos(
            grupo=g, cat_id=cid, ano=ano, mes=mes,
            cuenta_id=cuenta_ids.get(cta) if cta else None))

    return render(request, 'finanzas/gastos_mes.html', {
        'ano': ano, 'mes': mes, 'nombre_mes': MESES_ES[mes],
        'anos': list(range(INICIO_GASTOS.year, hoy.year + 1)),
        'meses_sel': [(i, MESES_ES[i]) for i in range(1, 13)],
        'cuentas': [{'corto': NOMBRE_CORTO_CUENTA.get(c, nombres[c]),
                     'largo': nombres[c]} for c in claves],
        'filas': filas,
        'tot_columnas': tot_columnas,
        'tot_general': tot_general,
    })


@user_passes_test(puede_ver_finanzas)
def gastos_ano(request):
    """Reporte de Jorge 2026-08-09: el plan de cuentas contra los meses del
    año elegido — lo que se gasta mes a mes, de un vistazo."""
    hoy = date.today()
    ano = _param_ano(request, hoy)
    m_ini = INICIO_GASTOS.month if ano == INICIO_GASTOS.year else 1
    meses_nums = list(range(m_ini, 13))

    datos = defaultdict(lambda: defaultdict(int))
    ids = {}
    for f in (MovimientoFinanciero.objects
              .filter(clase='gasto', fecha__year=ano)
              .values('categoria__grupo', 'categoria__nombre', 'categoria__id',
                      'fecha__month')
              .annotate(t=Sum('monto'))):
        clave = (f['categoria__grupo'] or 'otros',
                 f['categoria__nombre'] or 'Sin categoría')
        ids[clave] = f['categoria__id']
        datos[clave][f['fecha__month']] += int(f['t'] or 0)

    filas, tot_columnas, tot_general = _tabla_matriz(
        datos, meses_nums, ids,
        lambda g, cid, m: url_movimientos(grupo=g, cat_id=cid, ano=ano, mes=m))

    return render(request, 'finanzas/gastos_ano.html', {
        'ano': ano,
        'anos': list(range(INICIO_GASTOS.year, hoy.year + 1)),
        'columnas': [{'num': m, 'nombre': MESES_ABREV[m],
                      'largo': MESES_ES[m],
                      'es_actual': (ano, m) == (hoy.year, hoy.month)}
                     for m in meses_nums],
        'filas': filas,
        'tot_columnas': tot_columnas,
        'tot_general': tot_general,
    })


NOMBRE_CUENTA_CARTOLA = {'bancoestado': 'BancoEstado Chequera Electrónica',
                         'scotiabank': 'Scotiabank',
                         'scotiabank_alda': 'Scotiabank Alda (personal)',
                         'cuentarut_jorge': 'CuentaRUT Jorge (personal)'}


@user_passes_test(puede_ver_finanzas)
def cargar_cartola(request):
    """Carga de cartolas bancarias (P-22 F4 paso 3): BancoEstado (.xlsx) y
    Scotiabank (.xls) — el banco se detecta por los bytes del archivo.

    Flujo en dos golpes, nada se escribe sin confirmar: (1) subir archivo →
    propuesta con chequeos (cadena de saldos, totales) y el estado de cada
    fila (nuevo / ya está / en histórico / revisar); (2) botón Confirmar →
    se escriben los nuevos (fuente=captura) y los cierres de mes que el
    archivo cubre. El payload viaja firmado.
    """
    from django.core import signing

    from .services import (CUENTA_ALDA_NUMERO, estado_fila_cartola,
                           parsear_cartola_alda, parsear_cartola_bancoestado,
                           parsear_cartola_scotiabank, registrar_filas_alda,
                           registrar_filas_cartola)

    ctx = {}

    if request.method == 'POST' and request.POST.get('confirmar'):
        try:
            payload = signing.loads(request.POST.get('payload', ''), max_age=3600)
        except signing.BadSignature:
            ctx['error'] = ('La propuesta expiró o viene alterada — '
                            'sube el archivo de nuevo.')
        else:
            cuenta_clave = payload.get('cuenta', 'bancoestado')
            convertidos = 0
            if cuenta_clave == 'scotiabank_alda':
                creados, saltados, convertidos = registrar_filas_alda(
                    payload['filas'], payload.get('cierres_mes'))
            else:
                creados, saltados = registrar_filas_cartola(
                    payload['filas'], payload.get('cierres_mes'),
                    cuenta_clave=cuenta_clave)
            ctx['resultado'] = {
                'creados': creados, 'saltados': saltados,
                'convertidos': convertidos,
                'cuenta': NOMBRE_CUENTA_CARTOLA.get(cuenta_clave, cuenta_clave),
                'cierres': [(m, _clp(s)) for m, s
                            in sorted((payload.get('cierres_mes') or {}).items())],
            }

    elif request.method == 'POST' and request.FILES.get('archivo'):
        archivo = request.FILES['archivo']
        magia = archivo.read(4)
        archivo.seek(0)
        try:
            if magia.startswith(b'PK'):            # zip → xlsx BancoEstado
                cuenta_clave = 'bancoestado'
                datos = parsear_cartola_bancoestado(archivo)
            elif magia.startswith(b'\xd0\xcf'):    # OLE2 → xls Scotiabank
                cuenta_clave = 'scotiabank'
                datos = parsear_cartola_scotiabank(archivo)
            elif magia.startswith(b';'):           # texto ';' → BSA.dat Alda
                datos = parsear_cartola_alda(archivo)
                if CUENTA_ALDA_NUMERO not in datos['cuenta_numero']:
                    raise ValueError(
                        f"Este BSA.dat es de la cuenta {datos['cuenta_numero']}"
                        ' — por ahora solo está mapeada la cuenta personal de '
                        'Alda (99-00138-96).')
                cuenta_clave = 'scotiabank_alda'
            else:
                raise ValueError('No reconozco el archivo: se esperan el .xlsx '
                                 'de BancoEstado, el .xls de Scotiabank o el '
                                 'BSA.dat de la cuenta de Alda.')
        except ValueError as e:
            ctx['error'] = str(e)
        except Exception:
            ctx['error'] = ('No pude leer el archivo — ¿es el export del '
                            'portal del banco?')
        else:
            for f in datos['filas']:
                f['estado'] = estado_fila_cartola(cuenta_clave, f)
                if date.fromisoformat(f['fecha']) < date(2026, 7, 1):
                    f['estado'] = 'fuera_cobertura'
                f['monto_fmt'] = _clp(f['abono'] or f['cargo'])
                f['saldo_fmt'] = _clp(f['saldo'])
            nuevas = [f for f in datos['filas'] if f['estado'] == 'nuevo']
            # Solo cierres que falten o difieran de lo ya guardado — así
            # re-subir el mismo archivo termina en "nada nuevo", no en un
            # botón de confirmar vacío.
            cierres_pend = {}
            for mes_iso, saldo in datos['cierres_mes'].items():
                anio, mes = (int(x) for x in mes_iso.split('-'))
                if not SaldoMensual.objects.filter(
                        cuenta__clave=cuenta_clave, periodo=date(anio, mes, 1),
                        saldo_cierre=saldo).exists():
                    cierres_pend[mes_iso] = saldo
            ctx['datos'] = datos
            ctx['cuenta_nombre'] = NOMBRE_CUENTA_CARTOLA[cuenta_clave]
            ctx['n_nuevas'] = len(nuevas)
            ctx['n_ya'] = len(datos['filas']) - len(nuevas)
            ctx['n_revisar'] = sum(1 for f in datos['filas'] if f['estado'] == 'revisar')
            ctx['saldo_inicial_fmt'] = _clp(datos['saldo_inicial'])
            ctx['saldo_final_fmt'] = _clp(datos['saldo_final_resumen'])
            ctx['abonos_fmt'] = _clp(datos['total_abonos'])
            ctx['cargos_fmt'] = _clp(datos['total_cargos'])
            ctx['cierres_fmt'] = [(m, _clp(s)) for m, s in sorted(cierres_pend.items())]
            if nuevas or cierres_pend:
                ctx['payload'] = signing.dumps(
                    {'cuenta': cuenta_clave, 'filas': nuevas,
                     'cierres_mes': cierres_pend})

    return render(request, 'finanzas/cargar_cartola.html', ctx)


@user_passes_test(puede_ver_finanzas)
def cargar_movimientos(request):
    """Carga por PEGADO para cuentas sin export (P-22 F7b).

    La CuentaRUT de Jorge (portal Personas) no da el .xlsx que sí da la
    Chequera, así que sus movimientos se pegan tal como se leen en la app:
    una línea por movimiento, `fecha ; glosa ; monto` con el monto NEGATIVO
    cuando es cargo. Mismo flujo de dos golpes de las cartolas: propuesta
    con estados y confirmación; nada se escribe antes.
    """
    from django.core import signing

    from .services import (CUENTAS_PUENTE, estado_fila_cartola,
                           preparar_filas_manual, registrar_filas_puente)

    cuentas = list(CuentaFinanciera.objects.filter(
        clave__in=CUENTAS_PUENTE).order_by('nombre'))
    ctx = {'cuentas': cuentas,
           'cuenta_sel': request.POST.get('cuenta') or 'cuentarut_jorge',
           'texto': request.POST.get('texto', '')}

    if request.method == 'POST' and request.POST.get('confirmar'):
        try:
            payload = signing.loads(request.POST.get('payload', ''), max_age=3600)
        except signing.BadSignature:
            ctx['error'] = ('La propuesta expiró o viene alterada — '
                            'pega los movimientos de nuevo.')
        else:
            cuenta_clave = payload['cuenta']
            creados, saltados, convertidos = registrar_filas_puente(
                payload['filas'], cuenta_clave)
            ctx['resultado'] = {
                'creados': creados, 'saltados': saltados,
                'convertidos': convertidos,
                'cuenta': NOMBRE_CUENTA_CARTOLA.get(cuenta_clave, cuenta_clave),
            }
            ctx['texto'] = ''

    elif request.method == 'POST' and request.POST.get('texto', '').strip():
        cuenta_clave = ctx['cuenta_sel']
        if cuenta_clave not in CUENTAS_PUENTE:
            ctx['error'] = 'Esa cuenta no acepta carga por pegado.'
        elif not CuentaFinanciera.objects.filter(clave=cuenta_clave).exists():
            ctx['error'] = ('La cuenta todavía no existe: correr '
                            '«python manage.py sembrar_finanzas» en la Shell.')
        else:
            filas, errores = preparar_filas_manual(request.POST['texto'],
                                                   cuenta_clave)
            for f in filas:
                f['estado'] = estado_fila_cartola(cuenta_clave, f)
                if date.fromisoformat(f['fecha']) < date(2026, 7, 1):
                    f['estado'] = 'fuera_cobertura'
                f['monto_fmt'] = _clp(f['abono'] or f['cargo'])
                f['es_abono'] = bool(f['abono'])
            nuevas = [f for f in filas if f['estado'] == 'nuevo']
            ctx['filas'] = filas
            ctx['errores'] = errores
            ctx['cuenta_nombre'] = NOMBRE_CUENTA_CARTOLA.get(cuenta_clave,
                                                             cuenta_clave)
            ctx['n_nuevas'] = len(nuevas)
            ctx['n_otras'] = len(filas) - len(nuevas)
            ctx['total_cargos'] = _clp(sum(f['cargo'] for f in nuevas))
            if nuevas:
                ctx['payload'] = signing.dumps({'cuenta': cuenta_clave,
                                                'filas': nuevas})

    return render(request, 'finanzas/cargar_movimientos.html', ctx)


@user_passes_test(puede_ver_finanzas)
def calzar_retiros(request):
    """Decir a mano qué retiro corresponde a cada abono desde Aremko.

    Sin el calce, la misma plata se cuenta dos veces: como retiro al salir de
    Aremko y como gasto al gastarse desde la cuenta puente. El automático
    exige monto idéntico y a veces no coincide.
    """
    from .services import (abonos_por_calzar, calzar_abono_con_retiro,
                           candidatos_de_calce)

    ctx = {}

    if request.method == 'POST':
        try:
            abono = MovimientoFinanciero.objects.get(
                pk=request.POST.get('abono'), clase='ingreso',
                categoria__clave='abono_aremko_por_calzar')
            retiro = MovimientoFinanciero.objects.get(
                pk=request.POST.get('retiro'), clase='gasto')
        except (MovimientoFinanciero.DoesNotExist, ValueError):
            ctx['error'] = ('No encontré ese par — quizá alguien ya lo calzó. '
                            'Recarga la página.')
        else:
            comun, resto_a, resto_r = calzar_abono_con_retiro(abono, retiro)
            ctx['resultado'] = {
                'comun': _clp(comun),
                'resto_abono': _clp(resto_a) if resto_a else '',
                'resto_retiro': _clp(resto_r) if resto_r else '',
                'cuenta': abono.cuenta.nombre,
            }

    pendientes = []
    for a in abonos_por_calzar():
        pendientes.append({
            'obj': a, 'monto_fmt': _clp(a.monto),
            'candidatos': [
                {'id': c.id,
                 'texto': (f"{c.fecha:%d-%m} · {_clp(c.monto)} · "
                           f"{c.cuenta.nombre} · "
                           f"{(c.descripcion or c.categoria.nombre)[:60]}"),
                 'igual': int(c.monto) == int(a.monto)}
                for c in candidatos_de_calce(a)[:12]],
        })
    ctx['pendientes'] = pendientes
    ctx['total_pend'] = _clp(sum(int(p['obj'].monto) for p in pendientes))
    return render(request, 'finanzas/calzar_retiros.html', ctx)


# Orden fijo de las cuentas de caja en el flujo. La Visa queda FUERA a
# propósito: es crédito (deuda), no caja — sus gastos igual están en el
# tablero, y el pago de la tarjeta aparecerá como cargo en la cuenta que
# la pague.
CUENTAS_FLUJO = ('mercado_pago', 'bancoestado', 'scotiabank', 'efectivo')
# Cuentas puente: personales, pero con plata de Aremko adentro esperando
# pagar cuentas. Van EN el flujo (si no, un traspaso Scotiabank→CuentaRUT
# hacía desaparecer la plata del total sin ninguna fila que lo explicara —
# lo pilló Jorge el 2026-08-09) pero suman a su propio subtotal.
CUENTAS_PUENTE_FLUJO = ('cuentarut_jorge', 'scotiabank_alda')
TODAS_FLUJO = CUENTAS_FLUJO + CUENTAS_PUENTE_FLUJO
INICIO_FLUJO = date(2026, 8, 1)   # decisión de Jorge 2026-08-08


@user_passes_test(puede_ver_finanzas)
def flujo_caja(request):
    """El flujo de la caja real (P-22 F4 paso 4): día a día desde hoy hacia
    el 1 de agosto — entradas, salidas y saldo por cuenta y total.

    saldo(cuenta, día) = ancla (cierre julio en SaldoMensual) + acumulado de
    movimientos. Entradas de MP vienen de la API (MovimientoMP sin ajenos);
    entradas de efectivo, de los Pago en efectivo; el resto vive en
    MovimientoFinanciero. Cuentas sin ancla muestran «—» y quedan fuera del
    total — el número que se muestra es verificable o no se muestra.
    """
    from .models import CuentaFinanciera

    hoy = date.today()
    cuentas = {c.clave: c for c in
               CuentaFinanciera.objects.filter(clave__in=TODAS_FLUJO)}
    presentes = [c for c in TODAS_FLUJO if c in cuentas]
    caja_aremko = [c for c in CUENTAS_FLUJO if c in cuentas]
    puente = [c for c in CUENTAS_PUENTE_FLUJO if c in cuentas]

    anclas = {s.cuenta.clave: int(s.saldo_cierre)
              for s in SaldoMensual.objects.filter(
                  periodo=date(2026, 7, 1), cuenta__clave__in=TODAS_FLUJO)}

    # ── Netos por día y cuenta ───────────────────────────────────────────────
    netos = defaultdict(lambda: defaultdict(int))
    entradas_dia = defaultdict(int)   # sin traspasos: plata nueva de verdad
    salidas_dia = defaultdict(int)
    for r in (MovimientoFinanciero.objects
              .filter(fecha__gte=INICIO_FLUJO, cuenta__clave__in=TODAS_FLUJO)
              .values('fecha', 'cuenta__clave', 'sentido', 'clase')
              .annotate(t=Sum('monto'))):
        monto = int(r['t'] or 0)
        signo = 1 if r['sentido'] == 'entra' else -1
        netos[r['fecha']][r['cuenta__clave']] += signo * monto
        if r['clase'] != 'traspaso':
            if r['sentido'] == 'entra':
                entradas_dia[r['fecha']] += monto
            else:
                salidas_dia[r['fecha']] += monto

    # Cobros de MP: la API es la fuente (no están en MovimientoFinanciero).
    for r in (MovimientoMP.objects.filter(fecha__date__gte=INICIO_FLUJO)
              .exclude(sugerencia_motivo=MOTIVO_NO_ES_COBRO)
              .annotate(d=TruncDate('fecha')).values('d')
              .annotate(t=Sum('monto'))):
        monto = int(r['t'] or 0)
        netos[r['d']]['mercado_pago'] += monto
        entradas_dia[r['d']] += monto

    # Efectivo que entra: los Pago en efectivo del sistema.
    for r in (Pago.objects.filter(metodo_pago='efectivo',
                                  fecha_pago__date__gte=INICIO_FLUJO)
              .annotate(d=TruncDate('fecha_pago')).values('d')
              .annotate(t=Sum('monto'))):
        monto = int(r['t'] or 0)
        netos[r['d']]['efectivo'] += monto
        entradas_dia[r['d']] += monto

    # ── Detalle por día: TODOS los movimientos, para expandir cada fila ─────
    from django.utils import timezone as _tz
    detalles = defaultdict(list)
    for m in (MovimientoFinanciero.objects
              .filter(fecha__gte=INICIO_FLUJO, cuenta__clave__in=TODAS_FLUJO)
              .select_related('cuenta', 'categoria').order_by('id')):
        detalles[m.fecha].append({
            'desc': m.descripcion or (m.categoria.nombre if m.categoria else ''),
            'cuenta': m.cuenta.nombre,
            'extra': 'traspaso' if m.clase == 'traspaso'
                     else (m.categoria.nombre if m.categoria else ''),
            'monto_fmt': _clp(m.monto), 'sentido': m.sentido,
        })
    for mv in (MovimientoMP.objects.filter(fecha__date__gte=INICIO_FLUJO)
               .exclude(sugerencia_motivo=MOTIVO_NO_ES_COBRO).order_by('fecha')):
        detalles[_tz.localtime(mv.fecha).date()].append({
            'desc': mv.glosa or f'Cobro MP {mv.mp_payment_id}',
            'cuenta': 'Mercado Pago', 'extra': 'cobro API',
            'monto_fmt': _clp(mv.monto), 'sentido': 'entra',
        })
    for p in (Pago.objects.filter(metodo_pago='efectivo',
                                  fecha_pago__date__gte=INICIO_FLUJO)
              .order_by('fecha_pago')):
        detalles[_tz.localtime(p.fecha_pago).date()].append({
            'desc': (f'Pago en efectivo (reserva #{p.venta_reserva_id})'
                     if p.venta_reserva_id else 'Pago en efectivo'),
            'cuenta': 'Efectivo', 'extra': 'sistema',
            'monto_fmt': _clp(p.monto), 'sentido': 'entra',
        })

    # ── Acumular del 1-ago a hoy, y presentar de hoy hacia atrás ────────────
    saldos = {c: anclas.get(c) for c in presentes}
    filas = []
    d = INICIO_FLUJO
    while d <= hoy:
        for c in presentes:
            if saldos[c] is not None:
                saldos[c] += netos[d][c]

        def _suma(claves):
            vivos = [saldos[c] for c in claves if saldos[c] is not None]
            return sum(vivos) if vivos else None

        t_caja, t_puente = _suma(caja_aremko), _suma(puente)
        t_total = None if t_caja is None and t_puente is None else \
            (t_caja or 0) + (t_puente or 0)
        movs = sorted(detalles[d], key=lambda x: 0 if x['sentido'] == 'entra' else 1)
        filas.append({
            'dia': d,
            'entradas': _clp(entradas_dia[d]) if entradas_dia[d] else '',
            'salidas': _clp(salidas_dia[d]) if salidas_dia[d] else '',
            'saldos': [(_clp(saldos[c]) if saldos[c] is not None else '—')
                       for c in presentes],
            'total_caja': _clp(t_caja) if t_caja is not None else '—',
            'total_puente': _clp(t_puente) if t_puente is not None else '—',
            'total': _clp(t_total) if t_total is not None else '—',
            'movs': movs, 'n_movs': len(movs),
        })
        d += timedelta(days=1)
    filas.reverse()

    # ── Frescura por cuenta: hasta cuándo llega cada fuente ─────────────────
    frescura = []
    mp_max = MovimientoMP.objects.aggregate(m=Max('fecha'))['m']
    frescura.append(('Mercado Pago', 'API cada hora · datos al '
                     + (mp_max.strftime('%d-%m %H:%M') if mp_max else 'sin datos')))
    for clave, nombre in (('bancoestado', 'BancoEstado'),
                          ('scotiabank', 'Scotiabank'),
                          ('scotiabank_alda', 'Scotia Alda'),
                          ('cuentarut_jorge', 'CuentaRUT Jorge')):
        if clave not in cuentas:
            continue
        ult = (MovimientoFinanciero.objects
               .filter(cuenta__clave=clave, fuente='captura')
               .aggregate(m=Max('fecha'))['m'])
        frescura.append((NOMBRE_CORTO_CUENTA.get(clave, nombre),
                         ('cartola hasta el ' + ult.strftime('%d-%m'))
                         if ult else 'sin cartola cargada'))
    frescura.append(('Efectivo', 'pagos en efectivo del sistema, en vivo'))

    sin_ancla = [cuentas[c].nombre for c in presentes if c not in anclas]

    return render(request, 'finanzas/flujo_caja.html', {
        'filas': filas,
        'nombres_cuentas': [
            {'nombre': NOMBRE_CORTO_CUENTA.get(c, cuentas[c].nombre),
             'largo': cuentas[c].nombre, 'es_puente': c in CUENTAS_PUENTE_FLUJO}
            for c in presentes],
        'hay_puente': bool(puente),
        'frescura': frescura,
        'sin_ancla': sin_ancla,
        'inicio': INICIO_FLUJO,
        'n_columnas': len(presentes) + 6,
    })
