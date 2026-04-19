from django import template

register = template.Library()

@register.filter
def formato_clp(value):
    try:
        value = float(value)
        formatted = "{:,.0f}".format(value).replace(",", ".")
        return f"${formatted}"
    except (ValueError, TypeError):
        return value

@register.filter
def duration_in_hours(minutes):
    """Converts duration from minutes to a readable hour/minute format."""
    try:
        minutes = int(minutes)
        if minutes < 60:
            return f"{minutes} minutos"
        else:
            hours = minutes / 60
            # Use .1f for one decimal place, then replace .0 if it's a whole number
            hours_str = "{:.1f}".format(hours).replace('.0', '')
            return f"{hours_str} hora{'s' if hours > 1 else ''}"
    except (ValueError, TypeError, AttributeError):
        return "" # Return empty string if input is invalid


@register.filter
def filter_reserva_web(servicios, value):
    """Filtra una lista de servicios por el campo permite_reserva_web."""
    try:
        target = bool(value)
        return [s for s in servicios if bool(getattr(s, 'permite_reserva_web', False)) == target]
    except (TypeError, AttributeError):
        return []


# Nombres de tinas que tienen hidromasaje (derivado por nombre, sin tocar BD)
TINAS_HIDROMASAJE = {'llaima', 'villarrica', 'puntiagudo', 'puyehue'}


@register.filter
def filter_hidromasaje(servicios, value):
    """Separa tinas por hidromasaje basándose en el nombre. value=1 (con) / 0 (sin)."""
    try:
        target = bool(value)
        result = []
        for s in servicios:
            nombre = (getattr(s, 'nombre', '') or '').lower()
            has_jets = any(n in nombre for n in TINAS_HIDROMASAJE)
            if has_jets == target:
                result.append(s)
        return result
    except (TypeError, AttributeError):
        return []


@register.filter
def multiply(value, arg):
    """Multiplica value × arg. Devuelve 0 si falla."""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0


@register.filter
def order_by_capacity(servicios):
    """Ordena servicios de menor a mayor capacidad_maxima."""
    try:
        return sorted(servicios, key=lambda s: getattr(s, 'capacidad_maxima', 0) or 0)
    except (TypeError, AttributeError):
        return list(servicios) if servicios else []
