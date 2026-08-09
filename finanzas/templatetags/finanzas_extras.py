# -*- coding: utf-8 -*-
from django import template

register = template.Library()


@register.filter
def puede_finanzas(user):
    """True si el usuario puede ver las páginas de finanzas (grupo colaborador)."""
    try:
        return user.groups.filter(name='Finanzas colaborador').exists()
    except Exception:
        return False
