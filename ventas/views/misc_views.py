from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from ..models import Cliente, Servicio, Producto, MovimientoCliente # Relative imports
# This view might be redundant if VentaReserva is created via checkout/admin.
# from ..forms import VentaReservaForm # Removed import

def inicio_sistema_view(request):
    """
    Vista que renderiza la página de inicio del sistema con enlaces a los recursos importantes.
    """
    return render(request, 'ventas/inicio_sistema.html')

# Removed the add_venta_reserva view as it seems unused and caused an ImportError.
# If this view is needed, VentaReservaForm must be created in forms.py
# and the view logic potentially updated.
