from rest_framework import viewsets
from rest_framework.response import Response
from django.db.models import Sum, Q, Count, F
from django.contrib.auth.decorators import user_passes_test
import csv
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse # Import reverse
from datetime import datetime, timedelta
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from .models import Proveedor, CategoriaProducto, Producto, VentaReserva, ReservaProducto, Cliente, Pago, CategoriaServicio, Servicio, ReservaServicio, MovimientoCliente, Compra, DetalleCompra, Categoria, HomepageSettings
from .signals import get_or_create_system_user
from .calendar_utils import verificar_disponibilidad
from django.utils.timezone import make_aware
from django.utils.dateparse import parse_date
from django.db import models
from django.db.models.signals import pre_save # Import pre_save
from django.db.models import Q, Sum
from django.db import transaction
from rest_framework.exceptions import ValidationError
from django.contrib.auth.models import User
from .serializers import (
    ProveedorSerializer,
    CategoriaProductoSerializer,
    ProductoSerializer,
    VentaReservaSerializer,
    ClienteSerializer,
    PagoSerializer,
    ReservaProductoSerializer,
    ServicioSerializer,
    ReservaServicioSerializer,
    CategoriaServicioSerializer,
    VentaReservaSerializer
)
import xlwt
from django.core.paginator import Paginator
from openpyxl import load_workbook
from django.contrib import messages
from itertools import islice
from django.views.decorators.csrf import csrf_protect, csrf_exempt
import traceback # Import traceback for detailed error logging
import os
import json
import hmac
import hashlib
import requests # Make sure 'requests' is in requirements.txt

# This file is intentionally left almost empty after refactoring.
# Views have been moved to the ventas/views/ directory.
# Imports might need cleanup depending on final usage.

def homepage(request):
    servicios = Servicio.objects.filter(activo=True).order_by('categoria__nombre', 'nombre')
    categorias = Categoria.objects.all().order_by('nombre')

    # Fetch homepage settings
    homepage_settings = HomepageSettings.objects.first() # Get the single instance
    hero_image_url = None
    if homepage_settings and homepage_settings.hero_background_image:
        hero_image_url = homepage_settings.hero_background_image.url

    context = {
        'servicios': servicios,
        'categorias': categorias,
        'hero_image_url': hero_image_url, # Pass URL to context
        # ... other context variables ...
    }
    return render(request, 'ventas/homepage.html', context)

