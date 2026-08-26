# -*- coding: utf-8 -*-
"""Formato de plata para el panel.

No se usa `intcomma` porque respeta la configuración regional de Django y
acá salía «$511 000» con espacio, que no es como se escribe un monto en
Chile. Se reusa el MISMO formateador del correo para que el panel y el correo
no muestren el mismo número de dos maneras distintas.
"""
from django import template

from ..render import clp as _clp

register = template.Library()


@register.filter(name='clp')
def clp(valor):
    if valor is None or valor == '':
        return '—'
    try:
        return _clp(valor)
    except (TypeError, ValueError):
        return '—'
