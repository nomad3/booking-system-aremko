# -*- coding: utf-8 -*-
"""Las reglas que deciden qué merece interrumpir la mañana.

Todas son funciones PURAS: reciben datos ya leídos y devuelven alertas. Se
pueden probar sin base de datos ni red, que es la única forma de confiar en
un umbral.

El principio de diseño: si no hay nada fuera de rango, esta lista viene
VACÍA. Un correo que grita todos los días se deja de leer en una semana, y
entonces el día que grite de verdad tampoco se va a leer.
"""

# Bajo esta caja Jorge no duerme tranquilo (valor fijado por él, 2026-08-23).
UMBRAL_CAJA_DEFAULT = 15_000_000
# Una cartola sin cargar hace más de una semana deja el saldo desactualizado
# sin que nada lo diga. La deuda de datos se cobra sola.
TOPE_REZAGO_CARTOLA = 7
# Antes del día 7 del mes, dos días flojos mueven el porcentaje entero. Gritar
# ahí es ruido, no señal.
DIA_MINIMO_ALERTA_VENTAS = 7
CAIDA_VENTAS_PCT = -15
# Una campaña que gastó menos que esto en la ventana todavía no dice nada.
GASTO_MINIMO_CAMPANA = 20_000

ALTA, MEDIA = 'alta', 'media'


def _alerta(nivel, texto, accion=''):
    return {'nivel': nivel, 'texto': texto, 'accion': accion}


def alerta_caja_baja(total, umbral=UMBRAL_CAJA_DEFAULT):
    """La caja bajo el mínimo que el dueño fijó.

    Con total None (falta un ancla de saldo) NO se alerta: no sabemos cuánto
    hay, y una alarma falsa por un dato faltante enseña a ignorar la alarma.
    """
    if total is None or total >= umbral:
        return None
    falta = umbral - total
    return _alerta(
        ALTA,
        f'Caja en ${total:,.0f} — bajo tu mínimo de ${umbral:,.0f} '
        f'(faltan ${falta:,.0f})'.replace(',', '.'),
        'Revisar el flujo de caja y qué pagos vienen esta semana.')


def alertas_cartola_atrasada(cuentas, tope=TOPE_REZAGO_CARTOLA):
    """Cuentas cuya última cartola cargada quedó vieja.

    Es la alerta que se cobra sola la deuda de datos: sin cartola fresca, el
    saldo que muestra el resumen es de hace días aunque se vea de hoy.
    """
    salida = []
    for c in cuentas:
        rezago = c.get('dias_rezago')
        if rezago is None or rezago <= tope:
            continue
        if rezago >= 9999:
            salida.append(_alerta(
                ALTA, f'{c["nombre"]}: nunca se ha cargado una cartola',
                'Cargar cartola en Finanzas → Cargar cartola.'))
        else:
            salida.append(_alerta(
                MEDIA,
                f'{c["nombre"]}: cartola con {rezago} días de rezago '
                f'(última al {c["ultima_cartola"]:%d-%m})',
                'Cargar cartola en Finanzas → Cargar cartola.'))
    return salida


def alerta_publicaciones_pendientes(publicaciones):
    """Piezas de HOY que siguen sin publicarse.

    Se cuenta lo que el Telar dice que falta. Ojo: «publicada» en el Telar es
    lo que alguien marcó, no lo que se verificó en la plataforma — por eso el
    texto habla de la lista del día y no promete que estén arriba.
    """
    pendientes = [p for p in publicaciones if p.get('estado') != 'publicada']
    if not pendientes:
        return None
    detalle = ', '.join(
        f'{p.get("hora") or "sin hora"} {p.get("canal", "")}'.strip()
        for p in pendientes[:3])
    resto = f' y {len(pendientes) - 3} más' if len(pendientes) > 3 else ''
    return _alerta(
        MEDIA,
        f'{len(pendientes)} publicación(es) de hoy sin publicar: {detalle}{resto}',
        'Ver la cola del día en el Telar.')


def alerta_ventas_en_baja(comparativa, dia_del_mes,
                          dia_minimo=DIA_MINIMO_ALERTA_VENTAS,
                          umbral_pct=CAIDA_VENTAS_PCT):
    """Ventas del mes bastante bajo el mismo tramo del mes anterior.

    Solo desde el día `dia_minimo`: antes de eso el porcentaje se mueve entero
    con un par de días flojos y la alerta sería una moneda al aire.
    """
    if not comparativa or dia_del_mes < dia_minimo:
        return None
    pct = (comparativa.get('totales') or {}).get('facturado_pct_cambio')
    if not isinstance(pct, (int, float)) or pct > umbral_pct:
        return None
    return _alerta(
        ALTA,
        f'Ventas del mes {pct:.0f}% vs el mismo tramo del mes anterior',
        'Revisar qué familia cayó y si hay campañas apagadas.')


def alertas_campanas_sin_resultado(campanas, gasto_minimo=GASTO_MINIMO_CAMPANA):
    """Campañas activas que gastaron y no trajeron nada.

    El resultado se lee según el OBJETIVO de la campaña: una campaña de
    mensajes se mide en conversaciones iniciadas, no en clics al enlace.
    Medirla con la métrica equivocada da un veredicto equivocado (pasó con el
    reporte de Google que decía «pausar» mientras las ventas subían).

    Una campaña que no declara su métrica de resultado se OMITE: no alertar es
    mejor que alertar por no saber leerla.
    """
    salida = []
    for c in campanas or []:
        gasto = c.get('gasto') or 0
        resultados = c.get('resultados')
        if gasto < gasto_minimo or resultados is None:
            continue
        if resultados > 0:
            continue
        salida.append(_alerta(
            MEDIA,
            f'{c.get("plataforma", "")} · «{c.get("nombre", "sin nombre")}»: '
            f'${gasto:,.0f} y 0 {c.get("unidad", "resultados")} '
            f'en {c.get("dias", 7)} días'.replace(',', '.'),
            'Revisar el creativo o pausarla.'))
    return salida


def construir_alertas(*, caja_total, umbral_caja, cuentas, publicaciones,
                      comparativa, dia_del_mes, campanas):
    """Junta todas las reglas y ordena por gravedad.

    Devuelve una lista, vacía cuando todo está en rango — que es el caso que
    hace creíble a la lista cuando NO está vacía.
    """
    alertas = []
    for a in (alerta_caja_baja(caja_total, umbral_caja),
              alerta_publicaciones_pendientes(publicaciones),
              alerta_ventas_en_baja(comparativa, dia_del_mes)):
        if a:
            alertas.append(a)
    alertas.extend(alertas_cartola_atrasada(cuentas))
    alertas.extend(alertas_campanas_sin_resultado(campanas))
    return sorted(alertas, key=lambda a: 0 if a['nivel'] == ALTA else 1)
