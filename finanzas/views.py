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
import calendar
from datetime import date, timedelta

from django.contrib.auth.decorators import user_passes_test
from django.db.models import Count, Max, Sum
from django.db.models.functions import TruncDate
from django.shortcuts import render, redirect

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
    # Cada transferencia a SU cuenta (Jorge 2026-08-10: «¿a qué cuenta? son
    # varias, deberían mostrarse todas»). Juntarlas en un solo «Transferencia»
    # escondía en qué bolsillo cayó cada peso.
    'transferencia': 'Transferencia (cuenta sin especificar)',
    'bancoestado': 'Transferencia · BancoEstado',
    'scotiabank': 'Transferencia · Scotiabank',
    'cuentarut': 'Transferencia · CuentaRUT Jorge',
    'scotiabankalda': 'Transferencia · Scotiabank Alda',
    'bcialda': 'Transferencia · BCI Alda',
    'bicegoalda': 'Transferencia · Bicego Alda',
    'andesalda': 'Transferencia · Andes Alda',
    'machjorge': 'Mach Jorge', 'machalda': 'Mach Alda',
    'copecjorge': 'Copec Jorge', 'copecalda': 'Copec Alda',
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
    # Los COBROS se comparan contra los cobros: la API de MP no reporta las
    # devoluciones, así que netearlas de este lado hacía aparecer cada
    # devolución como «plata que entró sin registrarse» (visto por Jorge
    # 2026-08-10 con una reserva anulada y vuelta a tomar). Van en su propia
    # columna: son un hecho, no un descuadre.
    corte_mp = hoy - timedelta(days=13)
    por_dia = defaultdict(dict)
    base_pagos = Pago.objects.filter(metodo_pago__in=METODOS_MP,
                                     fecha_pago__date__gte=corte_mp)
    for r in (base_pagos.filter(monto__gt=0)
              .annotate(d=TruncDate('fecha_pago')).values('d')
              .annotate(t=Sum('monto'), n=Count('id'))):
        por_dia[r['d']].update(sis=int(r['t'] or 0), sis_n=r['n'])
    for r in (base_pagos.filter(monto__lt=0)
              .annotate(d=TruncDate('fecha_pago')).values('d')
              .annotate(t=Sum('monto'), n=Count('id'))):
        por_dia[r['d']].update(dev=abs(int(r['t'] or 0)), dev_n=r['n'])
    for r in (MovimientoMP.objects.filter(fecha__date__gte=corte_mp)
              .exclude(sugerencia_motivo=MOTIVO_NO_ES_COBRO)
              .annotate(d=TruncDate('fecha')).values('d')
              .annotate(t=Sum('monto'), n=Count('id'))):
        por_dia[r['d']].update(mp=int(r['t'] or 0), mp_n=r['n'])

    verif_mp, v_sis, v_mp, v_dev = [], 0, 0, 0
    for d in sorted(por_dia):
        v = por_dia[d]
        sis, mp_t, dev_d = v.get('sis', 0), v.get('mp', 0), v.get('dev', 0)
        dif = mp_t - sis
        v_sis += sis
        v_mp += mp_t
        v_dev += dev_d
        verif_mp.append({
            'dia': d,
            'sistema': _clp(sis) if sis else '—', 'sistema_n': v.get('sis_n', 0),
            'dev': _clp(dev_d) if dev_d else '', 'dev_n': v.get('dev_n', 0),
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
        'verif_dev': _clp(v_dev) if v_dev else '',
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


def ventas_por_mes(anio, mes=None):
    """{date(año, mes, 1): vendido} con la MISMA definición del tablero.

    Importa que coincida: si esta página dijera «ventas» y el tablero otra
    cosa, el presupuesto como % estaría midiendo contra un número que Jorge no
    reconoce. Las giftcards y los descuentos quedan fuera igual que allá — un
    canje de giftcard no es plata nueva que entra este mes.
    """
    filtros = {'fecha_pago__year': anio}
    if mes:
        filtros['fecha_pago__month'] = mes
    ventas = defaultdict(int)
    for f in (Pago.objects.filter(**filtros)
              .exclude(metodo_pago__in=METODOS_EXCLUIDOS)
              .values('fecha_pago__year', 'fecha_pago__month')
              .annotate(t=Sum('monto'))):
        ventas[date(f['fecha_pago__year'], f['fecha_pago__month'], 1)] += \
            int(f['t'] or 0)
    return ventas


def ventas_por_familia(anio, mes=None):
    """{date(año, mes, 1): {'Masajes': X, 'Tinas': Y, …}} de ese período.

    OJO CON EL RELOJ: acá manda la fecha en que el servicio se PRESTA, no la
    del pago (que es la de `ventas_por_mes`). Para el contrato de las
    masajistas ese es el reloj correcto — el honorario nace cuando ella
    trabaja, no cuando el cliente transfiere. Las dos bases conviven en el
    mismo reporte a propósito, y la página lo declara.
    """
    from ventas.models import Cliente, ReservaServicio

    filtros = {'fecha_agendamiento__year': anio}
    if mes:
        filtros['fecha_agendamiento__month'] = mes
    por_mes = defaultdict(lambda: defaultdict(int))
    for rs in (ReservaServicio.objects.filter(**filtros)
               .select_related('servicio', 'servicio__categoria')):
        if not rs.servicio_id:
            continue
        cat = (rs.servicio.categoria.nombre
               if rs.servicio.categoria_id else '')
        familia = Cliente._mapear_categoria_a_familia(
            cat, getattr(rs.servicio, 'tipo_servicio', '') or '')
        # El precio guardado en la línea manda: es lo que se cobró ese día, y
        # el del catálogo pudo cambiar después.
        unitario = rs.precio_unitario_venta
        if unitario is None:
            unitario = rs.servicio.precio_base
        d = rs.fecha_agendamiento
        por_mes[date(d.year, d.month, 1)][familia] += \
            int(unitario or 0) * (rs.cantidad_personas or 1)
    return por_mes


def base_de_ventas(categoria, totales, por_familia):
    """Contra qué venta se mide el % de este ítem.

    Sin familia declarada, el total. Con familia, solo lo vendido en ella —
    el contrato de las masajistas es 40% de la venta de MASAJES, y medirlo
    contra el total se desarma en verano, cuando las tinas pesan más.
    """
    familia = (getattr(categoria, 'familia_ventas', '') or '').strip()
    if familia:
        return int((por_familia or {}).get(familia, 0))
    return int(totales)


def presupuesto_efectivo(categoria, vendido):
    """Cuánto puede gastar este ítem en un mes que vendió `vendido`.

    El % manda sobre el monto fijo: casi la mitad del gasto de Aremko se mueve
    con las ventas, y ahí un monto fijo se cumple solo en temporada baja —
    justo cuando entra menos plata (Jorge 2026-08-11).
    """
    pct = float(getattr(categoria, 'presupuesto_pct_ventas', 0) or 0)
    if pct > 0:
        return int(round(vendido * pct / 100.0))
    return int(categoria.presupuesto_mensual or 0)


def _presupuesto_de_fila(presupuestos, grupo, categoria=None):
    """El presupuesto de una categoría, o la suma del grupo si no se pide una.

    Un grupo sin ningún ítem presupuestado devuelve 0, que el reporte muestra
    como «—»: no es que sobre plata, es que nadie definió cuánto se piensa
    gastar ahí.
    """
    if categoria is not None:
        return int(presupuestos.get((grupo, categoria), 0))
    return sum(int(v) for (g, _), v in presupuestos.items() if g == grupo)


def _celda_presupuesto(presupuesto, gastado, pct_ventas=None):
    """Presupuesto, diferencia y si se excedió — listo para la plantilla.

    pct_ventas: None, o la tupla (porcentaje, familia) — la familia vacía
    significa «contra las ventas totales».
    """
    familia = ''
    if isinstance(pct_ventas, (tuple, list)):
        pct_ventas, familia = (list(pct_ventas) + [''])[:2]
    # float() a propósito: Decimal('20.00') formateado con 'g' conserva los
    # ceros, y en pantalla «20.00% de ventas» se lee peor que «20%».
    regla = (f'{float(pct_ventas):.10g}% de '
             f'{"venta de " + familia if familia else "ventas"}'
             ) if pct_ventas else ''
    if not presupuesto:
        # Sin monto no hay contra qué comparar, aunque la regla exista: un mes
        # que no vendió nada tiene un tope de $0, y marcar «excedido en todo lo
        # gastado» sería ruido. La regla igual se declara, para que se entienda
        # que el «—» no es falta de presupuesto sino falta de ventas.
        return {'txt': '—', 'dif': '', 'excedido': False, 'sin': True,
                'pct': '', 'regla': regla}
    resto = presupuesto - gastado
    return {
        'txt': _clp(presupuesto),
        'dif': ('−' + _clp(-resto)) if resto < 0 else _clp(resto),
        'excedido': resto < 0,
        'sin': False,
        'pct': f'{round(gastado * 100 / presupuesto)}%',
        # Con qué regla salió ese monto, para que no parezca escrito a mano.
        'regla': regla,
    }


def _tabla_matriz(datos, columnas, ids=None, enlace=None, presupuestos=None,
                  columnas_son_meses=False, pcts=None, presupuesto_por_col=None):
    """Arma las filas del plan de cuentas contra columnas arbitrarias.

    datos: {(grupo, categoría): {col: monto}} · columnas: claves ordenadas.
    ids: {(grupo, categoría): id} para enlazar la fila de categoría.
    enlace: f(grupo, cat_id, columna_o_None) → URL. Cada cifra con plata
    queda clicable hacia los movimientos que la componen.
    presupuestos: {(grupo, categoría): monto mensual} para comparar.
    columnas_son_meses: solo entonces cada celda se puede pintar contra el
    presupuesto. En el reporte del mes las columnas son CUENTAS, y comparar
    lo que salió de una cuenta contra el presupuesto del ítem entero daría
    rojos falsos.
    Misma agrupación del tablero: subtotal por grupo y debajo sus categorías
    solo si el grupo tiene más de una.
    """
    ids = ids or {}
    filas = []
    tot_col = {c: 0 for c in columnas}
    tot_general = 0
    tot_presupuesto = 0

    def _celda(valor, grupo, cat_id, col, tope=0):
        return {'txt': _clp(valor) if valor else '',
                'url': enlace(grupo, cat_id, col) if (enlace and valor) else '',
                'excede': bool(columnas_son_meses and tope and valor > tope)}

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
        pres_g = _presupuesto_de_fila(presupuestos, g) if presupuestos else 0
        tot_presupuesto += pres_g
        # Con % de ventas el tope cambia mes a mes, así que cada celda se pinta
        # contra el presupuesto DE SU columna, no contra uno solo.
        topes_g = [(_presupuesto_de_fila(presupuesto_por_col.get(c, {}), g)
                    if presupuesto_por_col else pres_g) for c in columnas]
        # La regla del grupo solo se muestra si TODAS sus categorías comparten
        # la misma. Con una sola categoría —el caso de Honorarios masajistas—
        # la fila del grupo ES el ítem, y sin esto la regla no se vería nunca.
        # Si adentro conviven reglas distintas, no se muestra ninguna.
        reglas_g = {(pcts or {}).get((g, cat)) for cat in cats_g}
        regla_g = reglas_g.pop() if len(reglas_g) == 1 else None
        filas.append({
            'es_grupo': True, 'nombre': g_nombre,
            'celdas': [_celda(v, g, None, c, t)
                       for v, c, t in zip(celdas_g, columnas, topes_g)],
            'total': _celda(total_g, g, None, None),
            'presupuesto': _celda_presupuesto(pres_g, total_g, regla_g)})
        if len(cats_g) > 1:
            for cat in cats_g:
                cat_id = ids.get((g, cat))
                celdas = [datos[(g, cat)].get(c, 0) for c in columnas]
                pres_c = (_presupuesto_de_fila(presupuestos, g, cat)
                          if presupuestos else 0)
                topes_c = [(_presupuesto_de_fila(presupuesto_por_col.get(c, {}),
                                                 g, cat)
                            if presupuesto_por_col else pres_c)
                           for c in columnas]
                filas.append({
                    'es_grupo': False, 'nombre': cat,
                    'celdas': [_celda(v, g, cat_id, c, t)
                               for v, c, t in zip(celdas, columnas, topes_c)],
                    'total': _celda(sum(celdas), g, cat_id, None),
                    'presupuesto': _celda_presupuesto(
                        pres_c, sum(celdas), (pcts or {}).get((g, cat)))})
    return (filas,
            [_clp(tot_col[c]) if tot_col[c] else '—' for c in columnas],
            _clp(tot_general),
            _celda_presupuesto(tot_presupuesto, tot_general))


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

    # Presupuestos (Jorge 2026-08-10). Un ítem presupuestado que este mes NO
    # gastó nada TIENE que aparecer igual: si solo mostráramos lo gastado, el
    # mes en que no se pagó la luz se vería como un mes sin ese ítem en vez de
    # como un mes por debajo del presupuesto.
    vendido = ventas_por_mes(ano, mes).get(date(ano, mes, 1), 0)
    familias = ventas_por_familia(ano, mes).get(date(ano, mes, 1), {})
    presupuestos, con_pct, hay_familia = {}, {}, False
    for c in CategoriaFinanciera.objects.filter(clase='gasto').exclude(
            presupuesto_mensual=0, presupuesto_pct_ventas=0):
        clave = (c.grupo or 'otros', c.nombre)
        presupuestos[clave] = presupuesto_efectivo(
            c, base_de_ventas(c, vendido, familias))
        if c.presupuesto_pct_ventas:
            con_pct[clave] = (c.presupuesto_pct_ventas, c.familia_ventas)
            hay_familia = hay_familia or bool(c.familia_ventas)
        ids.setdefault(clave, c.id)
        datos[clave]              # crea la fila vacía si no gastó nada

    # Solo las cuentas que generaron gastos este mes; la que más gasta primero.
    claves = sorted(tot_cuenta, key=lambda c: -tot_cuenta[c])
    filas, tot_columnas, tot_general, tot_presupuesto = _tabla_matriz(
        datos, claves, ids,
        lambda g, cid, cta: url_movimientos(
            grupo=g, cat_id=cid, ano=ano, mes=mes,
            cuenta_id=cuenta_ids.get(cta) if cta else None),
        presupuestos=presupuestos, pcts=con_pct)

    # Un mes a medio andar comparado contra el presupuesto del mes completo se
    # ve siempre «bien». Decirlo vale más que corregirlo con una regla de tres.
    en_curso = (ano, mes) == (hoy.year, hoy.month)
    dias_mes = calendar.monthrange(ano, mes)[1]

    return render(request, 'finanzas/gastos_mes.html', {
        'ano': ano, 'mes': mes, 'nombre_mes': MESES_ES[mes],
        'anos': list(range(INICIO_GASTOS.year, hoy.year + 1)),
        'meses_sel': [(i, MESES_ES[i]) for i in range(1, 13)],
        'cuentas': [{'corto': NOMBRE_CORTO_CUENTA.get(c, nombres[c]),
                     'largo': nombres[c]} for c in claves],
        'filas': filas,
        'tot_columnas': tot_columnas,
        'tot_general': tot_general,
        'tot_presupuesto': tot_presupuesto,
        'hay_presupuestos': bool(presupuestos),
        'hay_familia': hay_familia,
        'en_curso': en_curso,
        'dia_hoy': hoy.day if en_curso else dias_mes,
        'dias_mes': dias_mes,
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

    # El presupuesto es MENSUAL, así que en esta vista es la vara de cada
    # columna: sirve para ver de un vistazo en qué meses se pasó cada ítem.
    # Con % de ventas la vara es distinta en cada mes —ese es el punto—, así
    # que se calcula una por columna.
    ventas = ventas_por_mes(ano)
    familias_ano = ventas_por_familia(ano)
    cats_presupuestadas = list(
        CategoriaFinanciera.objects.filter(clase='gasto').exclude(
            presupuesto_mensual=0, presupuesto_pct_ventas=0))
    presupuestos, con_pct, por_mes_pres = {}, {}, {}
    for c in cats_presupuestadas:
        clave = (c.grupo or 'otros', c.nombre)
        presupuestos[clave] = int(c.presupuesto_mensual)
        if c.presupuesto_pct_ventas:
            con_pct[clave] = (c.presupuesto_pct_ventas, c.familia_ventas)
        ids.setdefault(clave, c.id)
        datos[clave]
    for m in meses_nums:
        vendido = ventas.get(date(ano, m, 1), 0)
        del_mes = familias_ano.get(date(ano, m, 1), {})
        por_mes_pres[m] = {
            (c.grupo or 'otros', c.nombre): presupuesto_efectivo(
                c, base_de_ventas(c, vendido, del_mes))
            for c in cats_presupuestadas}

    filas, tot_columnas, tot_general, _pres = _tabla_matriz(
        datos, meses_nums, ids,
        lambda g, cid, m: url_movimientos(grupo=g, cat_id=cid, ano=ano, mes=m),
        presupuestos=presupuestos, columnas_son_meses=True, pcts=con_pct,
        presupuesto_por_col=por_mes_pres)

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
        'hay_presupuestos': bool(presupuestos),
    })


NOMBRE_CUENTA_CARTOLA = {'bancoestado': 'BancoEstado Chequera Electrónica',
                         'scotiabank': 'Scotiabank',
                         'scotiabank_alda': 'Scotiabank Alda (personal)',
                         'cuentarut_jorge': 'CuentaRUT Jorge (personal)',
                         'tarjeta_alda_1': 'Tarjeta Alda 1 (Scotiabank)',
                         'tarjeta_alda_2': 'Tarjeta Alda 2 (Scotiabank)'}


def _es_imagen(magia):
    """¿Los primeros bytes son de una imagen? PNG, JPEG, WEBP o HEIC.

    Las capturas de iPhone son PNG; las fotos, HEIC. Se detecta por contenido
    igual que el resto de los formatos: el nombre del archivo miente seguido.
    """
    return (magia.startswith(b'\x89PNG')
            or magia.startswith(b'\xff\xd8\xff')          # JPEG
            or (magia[:4] == b'RIFF' and magia[8:12] == b'WEBP')
            or magia[4:8] == b'ftyp')                        # HEIC/HEIF


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

    from .services import (CUENTA_ALDA_NUMERO, TARJETAS_ALDA,
                           estado_fila_cartola, parsear_cartola_alda,
                           parsear_cartola_bancoestado,
                           parsear_cartola_scotiabank, parsear_tarjeta_alda,
                           registrar_filas_alda, registrar_filas_cartola,
                           registrar_filas_tarjeta)

    ctx = {'tarjetas': list(CuentaFinanciera.objects
                            .filter(clave__in=TARJETAS_ALDA)
                            .order_by('clave')),
           'tarjeta_sel': request.POST.get('tarjeta', '')}

    if request.method == 'POST' and request.POST.get('confirmar'):
        try:
            payload = signing.loads(request.POST.get('payload', ''), max_age=3600)
        except signing.BadSignature:
            ctx['error'] = ('La propuesta expiró o viene alterada — '
                            'sube el archivo de nuevo.')
        else:
            cuenta_clave = payload.get('cuenta', 'bancoestado')
            convertidos = 0
            if cuenta_clave in TARJETAS_ALDA:
                creados, saltados, calzados, sin_calce = \
                    registrar_filas_tarjeta(payload['filas'], cuenta_clave)
                ctx['resultado'] = {
                    'creados': creados, 'saltados': saltados,
                    'convertidos': calzados, 'sin_calce': sin_calce,
                    'cuenta': NOMBRE_CUENTA_CARTOLA.get(cuenta_clave,
                                                        cuenta_clave),
                    'cierres': [],
                }
                return render(request, 'finanzas/cargar_cartola.html', ctx)
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
        magia = archivo.read(12)
        archivo.seek(0)
        try:
            if _es_imagen(magia):
                # Jorge sube la captura ACÁ, que es la página con el nombre
                # obvio (2026-08-12). El lector vive en «pegar movimientos»
                # porque ahí está el circuito de revisión; se lee la imagen y
                # se lo manda para allá con el texto puesto, en vez de
                # devolverle un «no reconozco el archivo».
                from .vision import leer_capturas
                texto, dudosas, error_v = leer_capturas([archivo])
                if error_v:
                    raise ValueError(error_v)
                request.session['captura_texto'] = texto
                request.session['captura_dudosas'] = dudosas
                return redirect('finanzas:cargar_movimientos')
            if magia.startswith(b'PK'):            # zip → xlsx BancoEstado
                cuenta_clave = 'bancoestado'
                datos = parsear_cartola_bancoestado(archivo)
            elif magia.startswith(b'\xd0\xcf'):    # OLE2 → xls Scotiabank
                cuenta_clave = 'scotiabank'
                datos = parsear_cartola_scotiabank(archivo)
            elif magia.startswith(b'%PDF'):        # PDF → tarjeta de Alda
                # El PDF no dice a qué tarjeta pertenece (verificado
                # 2026-08-10): sin el selector, adivinar sería inventar.
                cuenta_clave = ctx['tarjeta_sel']
                if cuenta_clave not in TARJETAS_ALDA:
                    raise ValueError(
                        'Es un PDF de tarjeta: elige ARRIBA a cuál de las dos '
                        'tarjetas corresponde antes de subirlo — el archivo '
                        'no lo dice.')
                datos = parsear_tarjeta_alda(archivo, cuenta_clave)
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
                                 'de BancoEstado, el .xls de Scotiabank, el '
                                 'BSA.dat de la cuenta de Alda, el PDF de una '
                                 'de sus tarjetas — o una captura de pantalla '
                                 '(PNG/JPG) de la app del banco.')
        except ValueError as e:
            ctx['error'] = str(e)
        except Exception:
            ctx['error'] = ('No pude leer el archivo — ¿es el export del '
                            'portal del banco?')
        else:
            if cuenta_clave in TARJETAS_ALDA:
                # La tarjeta no tiene saldo encadenado ni cierres de mes: son
                # compras sueltas, así que lleva su propia vista previa.
                for f in datos['filas']:
                    if MovimientoFinanciero.objects.filter(
                            referencia=f['referencia']).exists():
                        f['estado'] = 'ya_existe'
                    elif date.fromisoformat(f['fecha']) < date(2026, 7, 1):
                        f['estado'] = 'fuera_cobertura'
                    else:
                        f['estado'] = 'nuevo'
                    f['clase'] = 'traspaso' if f['es_pago'] else 'gasto'
                    f['monto_fmt'] = _clp(f['cargo'] or f['abono'])
                    if f['es_pago']:
                        f['categoria'] = 'pago de la tarjeta'
                nuevas = [f for f in datos['filas'] if f['estado'] == 'nuevo']
                ctx.update({
                    'datos': datos, 'es_tarjeta': True,
                    'cuenta_nombre': NOMBRE_CUENTA_CARTOLA.get(cuenta_clave,
                                                               cuenta_clave),
                    'n_nuevas': len(nuevas),
                    'n_ya': len(datos['filas']) - len(nuevas),
                    'compras_fmt': _clp(datos['total_compras']),
                    'pagos_fmt': _clp(datos['total_pagos']),
                })
                if nuevas:
                    ctx['payload'] = signing.dumps({'cuenta': cuenta_clave,
                                                    'filas': nuevas})
                return render(request, 'finanzas/cargar_cartola.html', ctx)

            from .services import marcar_traspaso_puente
            nombres_cta = dict(CuentaFinanciera.objects.values_list(
                'clave', 'nombre'))
            for f in datos['filas']:
                f['estado'] = estado_fila_cartola(cuenta_clave, f)
                # Marca de presentación (no toca `clase` ni `categoria`: ese
                # dict viaja firmado a la escritura — ver la función).
                marcar_traspaso_puente(f, cuenta_clave, nombres_cta)
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

    # Llegó desde «Cargar cartola» con una captura ya leída: se recoge el texto
    # y se muestra acá, que es donde vive la revisión. Se saca de la sesión
    # (pop) para que un F5 no lo repita.
    if request.method == 'GET' and request.session.get('captura_texto'):
        ctx['texto'] = request.session.pop('captura_texto')
        ctx['dudosas'] = request.session.pop('captura_dudosas', [])
        ctx['leidas'] = len(ctx['texto'].splitlines())

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

    elif request.method == 'POST' and request.FILES.getlist('capturas'):
        # Captura del celular → texto para pegar. NO escribe movimientos: llena
        # el mismo cuadro y de ahí sigue el circuito de dos golpes de siempre.
        # Un modelo leyendo montos puede errarle a un dígito, y el lugar más
        # fácil para cazar eso es el texto, antes de que sea un movimiento.
        from .vision import leer_capturas, validar_capturas

        capturas = request.FILES.getlist('capturas')
        ok, error = validar_capturas(capturas)
        if not ok:
            ctx['error'] = error
        else:
            texto, dudosas, error = leer_capturas(capturas)
            ctx['error'] = error
            if texto:
                ctx['texto'] = ((ctx['texto'] + '\n' + texto).strip()
                                if ctx['texto'].strip() else texto)
                ctx['leidas'] = len(texto.splitlines())
            ctx['dudosas'] = dudosas

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


# Cuentas de Aremko con cartola: son las únicas contra las que se puede
# verificar un ingreso por transferencia. Las personales quedan fuera a
# propósito — sus abonos de clientes no se registran como ingreso.
CUENTAS_VERIFICABLES = ('bancoestado', 'scotiabank')
# Métodos de pago que dicen «esto llegó por transferencia a una cuenta que
# seguimos». Los de cuentas personales (bcialda, machjorge…) se informan
# aparte: no hay contra qué cruzarlos.
METODOS_TRANSFERENCIA = ('transferencia', 'bancoestado', 'scotiabank')
METODOS_TRANSFERENCIA_SIN_CARTOLA = (
    'cuentarut', 'scotiabankalda', 'bcialda', 'bicegoalda', 'andesalda',
    'machjorge', 'machalda')
VENTANA_CALCE_DIAS = 5     # decisión de Jorge 2026-08-10

CUENTAS_CON_CARTOLA = ('bancoestado', 'scotiabank', 'scotiabank_alda',
                       'cuentarut_jorge')
# Las tarjetas también se vigilan (Jorge 2026-08-10): alimentan los gastos y la
# cuenta corriente, y si Alda deja de mandar los PDF ese gasto desaparece del
# tablero sin que nadie note la ausencia. Solo se les mide el ATRASO.
CUENTAS_TARJETA = ('tarjeta_alda_1', 'tarjeta_alda_2')
# Una tarjeta pasa días sin una sola compra; con el umbral de 3 de las cuentas
# corrientes estaría siempre en rojo y la alarma dejaría de significar algo.
DIAS_ALERTA_TARJETA = 10
HUECO_SOSPECHOSO = 4      # días seguidos sin un solo movimiento


def _tramos_vacios(fechas, desde, hasta, minimo=HUECO_SOSPECHOSO):
    """Tramos de `minimo` días o más sin ningún movimiento, dentro del rango
    que la cartola dice cubrir. Un banco puede pasar un fin de semana quieto;
    una semana entera en blanco casi siempre es cartola que falta."""
    tramos, corrida = [], []
    d = desde
    while d <= hasta:
        if d in fechas:
            if len(corrida) >= minimo:
                tramos.append((corrida[0], corrida[-1], len(corrida)))
            corrida = []
        else:
            corrida.append(d)
        d += timedelta(days=1)
    if len(corrida) >= minimo:
        tramos.append((corrida[0], corrida[-1], len(corrida)))
    return tramos


def calzar_abonos_con_pagos(abonos, pagos, dias=VENTANA_CALCE_DIAS):
    """Empareja cada abono del banco con un pago del sistema del MISMO monto
    dentro de la ventana. Devuelve (pares, abonos_solos, pagos_solos).

    Uno a uno: cada pago se consume una sola vez. Función pura sobre listas
    de (fecha, monto, objeto) — así se puede probar sin base de datos.
    """
    libres = sorted(pagos, key=lambda p: p[0])
    usados = set()
    pares, solos = [], []
    for fecha, monto, obj in sorted(abonos, key=lambda a: a[0]):
        elegido = None
        for i, (pf, pm, po) in enumerate(libres):
            if i in usados or pm != monto:
                continue
            if abs((pf - fecha).days) <= dias:
                elegido = i
                break
        if elegido is None:
            solos.append((fecha, monto, obj))
        else:
            usados.add(elegido)
            pares.append(((fecha, monto, obj), libres[elegido]))
    sin_abono = [p for i, p in enumerate(libres) if i not in usados]
    return pares, solos, sin_abono


@user_passes_test(puede_ver_finanzas)
def verificar_transferencias(request):
    """El equivalente del panel de Mercado Pago para las transferencias
    (pedido de Jorge 2026-08-10).

    Compara los abonos de clientes que muestran las cartolas contra los pagos
    que el equipo registró con método de transferencia. Lo que no calza en un
    lado o en el otro es lo que hay que mirar.
    """
    hoy = date.today()
    desde = date(2026, 7, 1)

    # Hasta dónde se puede verificar: la cartola menos avanzada manda. Más
    # allá de esa fecha no hay con qué comparar, y decirlo importa tanto como
    # el número — si no, la falta de datos se lee como plata perdida.
    coberturas = {}
    for clave in CUENTAS_VERIFICABLES:
        ult = (MovimientoFinanciero.objects
               .filter(cuenta__clave=clave, fuente='captura')
               .aggregate(m=Max('fecha'))['m'])
        coberturas[clave] = ult
    con_datos = [f for f in coberturas.values() if f]
    hasta = min(con_datos) if con_datos else None

    ctx = {
        'desde': desde, 'hasta': hasta, 'ventana': VENTANA_CALCE_DIAS,
        'coberturas': [(NOMBRE_CORTO_CUENTA.get(c, c), coberturas[c])
                       for c in CUENTAS_VERIFICABLES],
    }
    if hasta is None:
        return render(request, 'finanzas/verificar_transferencias.html', ctx)

    abonos = [
        (m.fecha, int(m.monto), m) for m in
        MovimientoFinanciero.objects
        .filter(clase='ingreso', categoria__clave='transferencias_recibidas',
                cuenta__clave__in=CUENTAS_VERIFICABLES,
                fecha__gte=desde, fecha__lte=hasta)
        .select_related('cuenta').order_by('fecha')]

    from django.utils import timezone as _tz

    pagos_qs = (Pago.objects
                .filter(metodo_pago__in=METODOS_TRANSFERENCIA, monto__gt=0,
                        fecha_pago__date__gte=desde,
                        fecha_pago__date__lte=hasta)
                .select_related('venta_reserva', 'venta_reserva__cliente')
                .order_by('fecha_pago'))
    pagos = [(_tz.localtime(p.fecha_pago).date(), int(p.monto), p)
             for p in pagos_qs]

    pares, sin_pago, sin_abono = calzar_abonos_con_pagos(abonos, pagos)

    # Resumen por mes de los dos lados.
    por_mes = defaultdict(lambda: {'banco': 0, 'sistema': 0})
    for fecha, monto, _ in abonos:
        por_mes[date(fecha.year, fecha.month, 1)]['banco'] += monto
    for fecha, monto, _ in pagos:
        por_mes[date(fecha.year, fecha.month, 1)]['sistema'] += monto
    resumen = []
    for mes in sorted(por_mes, reverse=True):
        d = por_mes[mes]
        dif = d['banco'] - d['sistema']
        resumen.append({
            'mes': mes, 'banco': _clp(d['banco']), 'sistema': _clp(d['sistema']),
            'dif': (f'+{_clp(dif)}' if dif > 0 else f'−{_clp(-dif)}') if dif else '',
            'alerta': dif != 0,
        })

    otros = (Pago.objects
             .filter(metodo_pago__in=METODOS_TRANSFERENCIA_SIN_CARTOLA,
                     monto__gt=0, fecha_pago__date__gte=desde,
                     fecha_pago__date__lte=hasta)
             .aggregate(t=Sum('monto'), n=Count('id')))

    ctx.update({
        'resumen': resumen,
        'n_calzados': len(pares),
        'monto_calzado': _clp(sum(m for (_, m, _), _ in pares)),
        'sin_pago': [{'fecha': f, 'monto': _clp(m),
                      'cuenta': NOMBRE_CORTO_CUENTA.get(o.cuenta.clave,
                                                        o.cuenta.nombre),
                      'glosa': (o.descripcion or '')[:70]}
                     for f, m, o in sin_pago],
        'total_sin_pago': _clp(sum(m for _, m, _ in sin_pago)),
        'sin_abono': [{'fecha': f, 'monto': _clp(m), 'metodo': o.metodo_pago,
                       'reserva': o.venta_reserva_id,
                       'cliente': (getattr(getattr(o.venta_reserva, 'cliente',
                                                   None), 'nombre', '') or '')[:40]}
                      for f, m, o in sin_abono],
        'total_sin_abono': _clp(sum(m for _, m, _ in sin_abono)),
        'otros_n': otros['n'] or 0,
        'otros_monto': _clp(otros['t'] or 0),
    })
    return render(request, 'finanzas/verificar_transferencias.html', ctx)


@user_passes_test(puede_ver_finanzas)
def salud_fuentes(request):
    """¿Está entrando todo? (P-22, pedido de Jorge 2026-08-10)

    Dos preguntas: las cartolas ¿cubren el mes completo o hay saltos?, y las
    fuentes automáticas (MP, SumUp, correos) ¿siguen llegando? Un tablero que
    no se puede auditar a sí mismo no sirve para auditar nada.
    """
    hoy = date.today()
    desde = date(2026, 7, 1)

    # ── Cartolas: cobertura y huecos ────────────────────────────────────────
    vigiladas = CUENTAS_CON_CARTOLA + CUENTAS_TARJETA
    cuentas = {c.clave: c for c in
               CuentaFinanciera.objects.filter(clave__in=vigiladas)}
    anclas = set(SaldoMensual.objects
                 .filter(periodo=date(2026, 7, 1))
                 .values_list('cuenta__clave', flat=True))
    cartolas = []
    for clave in vigiladas:
        if clave not in cuentas:
            continue
        # Una tarjeta no es una cuenta corriente: pasa días sin una sola
        # compra, así que buscarle «saltos» o exigirle que cubra desde el 1
        # daría alarmas falsas. De ella solo interesa hace cuántos días que
        # nadie sube el PDF (criterio de Jorge 2026-08-10).
        es_tarjeta = clave in CUENTAS_TARJETA
        movs = (MovimientoFinanciero.objects
                .filter(cuenta__clave=clave, fecha__gte=desde)
                .values_list('fecha', flat=True))
        fechas = set(movs)
        if not fechas:
            cartolas.append({
                'nombre': NOMBRE_CORTO_CUENTA.get(clave, cuentas[clave].nombre),
                'vacia': True, 'ancla': clave in anclas,
                'es_tarjeta': es_tarjeta})
            continue
        primera, ultima = min(fechas), max(fechas)
        atraso = (hoy - ultima).days
        cartolas.append({
            'nombre': NOMBRE_CORTO_CUENTA.get(clave, cuentas[clave].nombre),
            'vacia': False,
            'es_tarjeta': es_tarjeta,
            # El hueco más fácil de no ver: la cartola no empieza donde
            # empieza el período. No es un «salto» (está antes del rango
            # cubierto) y por eso pasaba piola — BancoEstado partía el 14-07.
            'falta_inicio': (0 if es_tarjeta else
                             ((primera - desde).days if primera > desde else 0)),
            'inicio_esperado': desde,
            'primera': primera, 'ultima': ultima,
            'n_movs': len(movs), 'n_dias': len(fechas),
            'atraso': atraso,
            'atrasada': atraso >= (DIAS_ALERTA_TARJETA if es_tarjeta else 3),
            'ancla': clave in anclas,
            'tramos': [] if es_tarjeta else
                      [{'desde': a, 'hasta': b, 'dias': n}
                       for a, b, n in _tramos_vacios(fechas, primera, ultima)],
        })

    # ── Fuentes automáticas: ¿cuándo llegó el último dato? ──────────────────
    def _ultimo(**filtros):
        return (MovimientoFinanciero.objects.filter(**filtros)
                .aggregate(m=Max('fecha'))['m'])

    from django.utils import timezone as _tz

    mp_ultimo = MovimientoMP.objects.aggregate(m=Max('fecha'))['m']
    mp_ultimo_dia = _tz.localtime(mp_ultimo).date() if mp_ultimo else None
    corte14 = hoy - timedelta(days=13)
    dias_con_mp = set(MovimientoMP.objects
                      .filter(fecha__date__gte=corte14)
                      .annotate(d=TruncDate('fecha'))
                      .values_list('d', flat=True))
    sin_cobros = [d for d in (corte14 + timedelta(days=i) for i in range(14))
                  if d <= hoy and d not in dias_con_mp]

    fuentes = [
        {'nombre': 'Mercado Pago · cobros (API)',
         'ultimo': mp_ultimo_dia,
         'detalle': (f'{MovimientoMP.objects.filter(fecha__date__gte=corte14).count()}'
                     ' cobros en 14 días'),
         'tope': 2},
        {'nombre': 'Mercado Pago · comisiones',
         'ultimo': _ultimo(referencia__startswith='mp:fee:'),
         'detalle': f"{MovimientoFinanciero.objects.filter(referencia__startswith='mp:fee:').count()} registradas",
         'tope': 3},
        {'nombre': 'Mercado Pago · compras de Aremko',
         'ultimo': (MovimientoFinanciero.objects
                    .filter(referencia__startswith='mp:', clase='gasto')
                    .exclude(referencia__startswith='mp:fee:')
                    .aggregate(m=Max('fecha'))['m']),
         'detalle': 'gastos que Aremko pagó con Mercado Pago',
         'tope': 15},
        {'nombre': 'Correos de transferencia (IMAP)',
         'ultimo': _ultimo(referencia__startswith='correo:'),
         'detalle': f"{MovimientoFinanciero.objects.filter(referencia__startswith='correo:').count()} movimientos",
         'tope': 5},
        {'nombre': 'SumUp · comisiones (API)',
         'ultimo': _ultimo(referencia__startswith='sumup:fee:'),
         'detalle': f"{MovimientoFinanciero.objects.filter(referencia__startswith='sumup:fee:').count()} registradas",
         'tope': 5},
    ]
    for f in fuentes:
        f['dias'] = (hoy - f['ultimo']).days if f['ultimo'] else None
        f['alerta'] = f['ultimo'] is None or f['dias'] > f['tope']

    # ── Traspasos: el control que atrapa lo que nadie avisa ─────────────────
    agg = {r['sentido']: int(r['t'] or 0) for r in
           MovimientoFinanciero.objects.filter(clase='traspaso')
           .values('sentido').annotate(t=Sum('monto'))}
    descalce = agg.get('entra', 0) - agg.get('sale', 0)

    por_calzar = MovimientoFinanciero.objects.filter(
        categoria__clave='abono_aremko_por_calzar', clase='ingreso')
    sin_clasificar = MovimientoFinanciero.objects.filter(
        clase='gasto', categoria__grupo='otros', fecha__gte=desde)

    return render(request, 'finanzas/salud_fuentes.html', {
        'hoy': hoy, 'desde': desde,
        'cartolas': cartolas,
        'fuentes': fuentes,
        'traspasos_cuadran': descalce == 0,
        'descalce': _clp(abs(descalce)),
        'n_por_calzar': por_calzar.count(),
        'monto_por_calzar': _clp(sum(int(m.monto) for m in por_calzar)),
        'n_sin_clasificar': sin_clasificar.count(),
        'monto_sin_clasificar': _clp(
            sum(int(m.monto) for m in sin_clasificar)),
        'sin_cobros_mp': sin_cobros,
        'dias_alerta_tarjeta': DIAS_ALERTA_TARJETA,
    })


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
            # `clase__in`: además del gasto, se acepta una pierna de traspaso
            # HUÉRFANA (sin par) — es la pareja perdida de un abono, ver
            # candidatos_de_calce. Sin esto el botón daba «ya lo calzaron».
            retiro = MovimientoFinanciero.objects.get(
                pk=request.POST.get('retiro'), sentido='sale',
                clase__in=('gasto', 'traspaso'))
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


# ── Cuenta corriente con Aremko (pedido de Jorge 2026-08-10) ────────────────
# Jorge paga el seguro del auto de su bolsillo y Aremko se lo devuelve; Alda
# pone gastos de la empresa desde su cuenta y su tarjeta. Nadie estaba
# haciendo la resta. Las tarjetas de Alda entran acá porque una compra de
# Aremko con SU tarjeta también es plata que ella puso.
CUENTAS_POR_PERSONA = (
    ('Jorge', ('cuentarut_jorge',)),
    ('Alda', ('scotiabank_alda', 'tarjeta_alda_1', 'tarjeta_alda_2')),
)
# El grupo de lo que todavía no tiene dueño declarado (por clasificar, vale
# vista sin destino). No entra al saldo: adivinar acá es inventar una deuda.
GRUPO_SIN_DECIDIR = 'otros'


def saldo_cuenta_corriente(gastos_empresa, recibido_de_aremko):
    """Lo que Aremko debe: lo que la persona pagó por la empresa menos lo que
    Aremko ya le transfirió. Positivo = Aremko debe."""
    return gastos_empresa - recibido_de_aremko


@user_passes_test(puede_ver_finanzas)
def cuenta_corriente(request):
    from .reglas import GRUPOS_FAMILIA

    personas = []
    for nombre, claves in CUENTAS_POR_PERSONA:
        existentes = list(CuentaFinanciera.objects.filter(clave__in=claves)
                          .values_list('clave', flat=True))
        if not existentes:
            continue
        base = (MovimientoFinanciero.objects
                .filter(cuenta__clave__in=existentes)
                .select_related('cuenta', 'categoria'))

        # A favor de la persona: gastos del NEGOCIO pagados desde sus cuentas.
        de_aremko = (base.filter(clase='gasto')
                     .exclude(categoria__grupo__in=GRUPOS_FAMILIA)
                     .exclude(categoria__grupo=GRUPO_SIN_DECIDIR))
        # A favor de Aremko: lo que le mandó. Se excluyen los traspasos entre
        # las cuentas de la MISMA persona (su cuenta paga su tarjeta): esa
        # plata no viene de Aremko y contarla borraría deuda que sí existe.
        recibido = (base.filter(clase='traspaso', sentido='entra')
                    .exclude(traspaso_par__cuenta__clave__in=existentes))
        # Abonos que vinieron de Aremko pero no calzaron con ningún retiro:
        # son plata de Aremko igual, y dejarlos fuera inflaría la deuda.
        por_calzar = base.filter(clase='ingreso',
                                 categoria__clave='abono_aremko_por_calzar')

        total_gastos = sum(int(m.monto) for m in de_aremko)
        total_recibido = (sum(int(m.monto) for m in recibido)
                          + sum(int(m.monto) for m in por_calzar))
        saldo = saldo_cuenta_corriente(total_gastos, total_recibido)

        # Lo que NO entra al saldo, dicho en voz alta.
        retiros = sum(int(m.monto) for m in
                      base.filter(clase='gasto',
                                  categoria__grupo__in=GRUPOS_FAMILIA))
        sin_decidir = base.filter(clase='gasto',
                                  categoria__grupo=GRUPO_SIN_DECIDIR)
        propios = sum(int(m.monto) for m in base.filter(
            clase='ingreso', categoria__clave='abonos_personales'))

        # Detalle en orden de fecha, con saldo corrido.
        lineas = ([(m, 1) for m in de_aremko]
                  + [(m, -1) for m in list(recibido) + list(por_calzar)])
        detalle, corrido = [], 0
        for m, signo in sorted(lineas, key=lambda x: (x[0].fecha, x[0].id)):
            corrido += signo * int(m.monto)
            detalle.append({
                'fecha': m.fecha,
                'glosa': (m.descripcion or '')[:70],
                'cuenta': NOMBRE_CORTO_CUENTA.get(m.cuenta.clave,
                                                  m.cuenta.nombre),
                'categoria': m.categoria.nombre if m.categoria else 'Traspaso',
                'a_favor': _clp(m.monto) if signo > 0 else '',
                'devuelto': _clp(m.monto) if signo < 0 else '',
                'corrido': _clp(corrido),
            })
        detalle.reverse()

        personas.append({
            'nombre': nombre,
            'cuentas': ', '.join(NOMBRE_CORTO_CUENTA.get(c, c)
                                 for c in existentes),
            'gastos': _clp(total_gastos),
            'recibido': _clp(total_recibido),
            'saldo_abs': _clp(abs(saldo)),
            'debe_aremko': saldo > 0,
            'cuadrado': saldo == 0,
            'retiros': _clp(retiros),
            'sin_decidir': _clp(sum(int(m.monto) for m in sin_decidir)),
            'n_sin_decidir': sin_decidir.count(),
            'propios': _clp(propios),
            'detalle': detalle,
            'ultima': base.aggregate(m=Max('fecha'))['m'],
        })

    return render(request, 'finanzas/cuenta_corriente.html',
                  {'personas': personas, 'desde': date(2026, 7, 1)})
