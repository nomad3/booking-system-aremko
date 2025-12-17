"""
Vista simplificada de calendario matriz para debugging
"""
from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponse
from datetime import date

def staff_required(view_func):
    """Decorador para requerir que el usuario sea staff"""
    decorated_view = user_passes_test(lambda u: u.is_staff)(view_func)
    return login_required(decorated_view)


@staff_required
def calendario_matriz_simple(request):
    """
    Vista simplificada del calendario matriz para verificar que funcione.
    """
    # Datos mínimos para renderizar
    context = {
        'fecha_seleccionada': date.today(),
        'fecha_str': date.today().strftime('%Y-%m-%d'),
        'categoria_seleccionada': {'nombre': 'Tinas Calientes', 'id': 1},
        'categoria_id': 1,
        'categorias': [],
        'matriz': {},
        'slots_horarios': ['10:00 - 12:00', '12:00 - 14:00', '14:00 - 16:00'],
        'recursos': ['Tina 1', 'Tina 2', 'Tina 3'],
        'resumen': {
            'total_slots': 9,
            'ocupados': 0,
            'disponibles': 9,
            'porcentaje_ocupacion': 0
        },
    }

    # Intentar renderizar el template
    try:
        return render(request, 'ventas/calendario_matriz.html', context)
    except Exception as e:
        # Si falla, devolver error detallado
        return HttpResponse(f"Error renderizando template: {str(e)}", status=500)