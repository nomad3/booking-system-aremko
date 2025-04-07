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
