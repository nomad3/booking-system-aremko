"""Reglas de la gift card compartidas por la tarjeta móvil y el lector de fotos.

Nació en la tarjeta (canje, 24-09-2026) y se mudó acá el 25-09 cuando el lector
de fotos de Luna (P-52 paso 3) necesitó exactamente las mismas: cómo se limpia
y se compara un código, qué significa «pagada», y el estado en palabras.
"""
from __future__ import annotations

import re

from django.utils import timezone

# Largo de los códigos que genera GiftCard.generar_codigo_unico().
LARGO_CODIGO = 12


def pesos(n):
    return f'${int(n or 0):,}'.replace(',', '.')


def codigo_limpio(texto):
    """Los códigos son 12 letras y números en mayúscula; el cliente los dicta
    con espacios, guiones o en minúscula."""
    return re.sub(r'[^0-9A-Za-z]', '', texto or '').upper()


# Letras y números que se confunden al leer o dictar un código: los códigos
# mezclan las 26 letras con los 10 dígitos, y la fuente de la carta dibuja la O
# igual que el cero (prueba del 24-09-2026: «OGEFH03K7B2J» empieza con la LETRA
# O y en el PDF y en la tarjeta se ve como un cero). Para buscar, se compara
# todo en una forma donde O=0 e I=1.
PARES_AMBIGUOS = (('O', '0'), ('I', '1'))


def forma_canonica(codigo):
    for letra, numero in PARES_AMBIGUOS:
        codigo = codigo.replace(letra, numero)
    return codigo


def codigo_canonico_sql():
    from django.db.models import Value
    from django.db.models.functions import Replace, Upper

    expr = Upper('codigo')
    for letra, numero in PARES_AMBIGUOS:
        expr = Replace(expr, Value(letra), Value(numero))
    return expr


def _distinto(a, b):
    """Cuántas posiciones difieren entre dos códigos del mismo largo."""
    return sum(1 for x, y in zip(a, b) if x != y)


def caracteres_distintos(texto, codigo):
    """Cuántos caracteres de lo escrito no calzan con el código (O por 0 e I
    por 1 no cuentan: son la misma tecla para quien lee)."""
    return _distinto(forma_canonica(codigo_limpio(texto)), forma_canonica(codigo_limpio(codigo)))


def buscar_por_codigo(texto, base=None, limite=6):
    """Las gift cards que calzan con un código dictado, copiado o leído de una foto.

    Devuelve (lista, forma), donde forma dice cómo calzó: 'exacto',
    'o_por_cero' (O=0, I=1), 'tolerancia' (1 o 2 caracteres distintos, SOLO si
    hay una sola candidata así de cerca: los códigos son al azar y la segunda
    más parecida queda a 9 o más), 'comienzo' (el cliente dio una parte) o ''.

    La tolerancia nació de un caso real (20-09-2026): quien regaló un Refugio
    copió el código a mano en una tarjeta de cumpleaños y la letra manuscrita
    confundió un carácter; era la gift card 471.
    """
    from ventas.models import GiftCard

    codigo = codigo_limpio(texto)
    if len(codigo) < 6:
        return [], ''
    base = base if base is not None else GiftCard.objects.all()
    exacta = base.filter(codigo__iexact=codigo).first()
    if exacta:
        return [exacta], 'exacto'
    canon = forma_canonica(codigo)
    con_canon = base.annotate(canon=codigo_canonico_sql())
    iguales = list(con_canon.filter(canon=canon)[:limite])
    if iguales:
        return iguales, 'o_por_cero'
    if len(codigo) == LARGO_CODIGO:
        cercanas = sorted(
            (_distinto(canon, forma_canonica((c or '').upper())), pk)
            for pk, c in GiftCard.objects.values_list('pk', 'codigo')
            if len(c or '') == LARGO_CODIGO)
        if cercanas and cercanas[0][0] <= 2 and (
                len(cercanas) == 1 or cercanas[1][0] >= cercanas[0][0] + 2):
            elegida = base.filter(pk=cercanas[0][1]).first()
            if elegida:
                return [elegida], 'tolerancia'
        return [], ''
    comienzo = list(con_canon.filter(canon__startswith=canon).order_by('-id')[:limite])
    return comienzo, ('comienzo' if comienzo else '')


# Los vouchers de antes del sistema de gift cards («Nro Voucher: R 5602»): el
# número es el de la RESERVA donde se registró la venta o la cortesía, y se
# canjeaban cambiándole la fecha a esa misma reserva (visto el 25-09-2026 en
# fotos reales: cortesías del Día del Carabinero y una venta a mano de 2025).
_VOUCHER = re.compile(r'^\s*R\s*[-#.]?\s*(\d{3,5})\s*$', re.IGNORECASE)


def numero_de_voucher(texto):
    """El número de reserva de un voucher antiguo («R 5602» → 5602), o None."""
    m = _VOUCHER.match(texto or '')
    return int(m.group(1)) if m else None


def compra_sin_pagar(gc):
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
    no sirve para esto (ver compra_sin_pagar): se deriva del saldo, el
    vencimiento y la venta donde se compró."""
    hoy = hoy or timezone.localdate()
    saldo = int(gc.monto_disponible or 0)
    if gc.fecha_vencimiento and gc.fecha_vencimiento < hoy:
        return 'Vencida'
    if saldo <= 0:
        return 'Usada'
    if compra_sin_pagar(gc):
        return 'Por cobrar'
    if saldo < int(gc.monto_inicial or 0):
        return f'Le quedan {pesos(saldo)}'
    return 'Lista para usar'


