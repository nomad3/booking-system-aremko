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
