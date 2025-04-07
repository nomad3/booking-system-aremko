import decimal # Import decimal for PagoViewSet validation
from django.http import JsonResponse # Add JsonResponse
from django.shortcuts import get_object_or_404 # Add get_object_or_404
from django.views.decorators.http import require_GET # To ensure only GET requests
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from ..models import ( # Relative imports
    Proveedor, CategoriaProducto, Producto, VentaReserva, Cliente, Pago,
    Servicio, ReservaProducto, ReservaServicio, CategoriaServicio
)
# Import Cliente model directly for the new view
from ..models import Cliente
from ..serializers import ( # Relative imports
    ProveedorSerializer, CategoriaProductoSerializer, ProductoSerializer,
    VentaReservaSerializer, ClienteSerializer, PagoSerializer,
    ReservaProductoSerializer, ServicioSerializer, ReservaServicioSerializer,
    CategoriaServicioSerializer
)
from ..utils import verificar_disponibilidad # Relative import

class ProveedorViewSet(viewsets.ModelViewSet):
    queryset = Proveedor.objects.all()
    serializer_class = ProveedorSerializer


class CategoriaProductoViewSet(viewsets.ModelViewSet):
    queryset = CategoriaProducto.objects.all()
    serializer_class = CategoriaProductoSerializer


class ProductoViewSet(viewsets.ModelViewSet):
    queryset = Producto.objects.all()
    serializer_class = ProductoSerializer


class ServicioViewSet(viewsets.ModelViewSet):
    queryset = Servicio.objects.all()
    serializer_class = ServicioSerializer


class CategoriaServicioViewSet(viewsets.ModelViewSet):
    queryset = CategoriaServicio.objects.all()
    serializer_class = CategoriaServicioSerializer


class ClienteViewSet(viewsets.ModelViewSet):
    queryset = Cliente.objects.all()
    serializer_class = ClienteSerializer


class ReservaProductoViewSet(viewsets.ModelViewSet):
    queryset = ReservaProducto.objects.all()
    serializer_class = ReservaProductoSerializer


class ReservaServicioViewSet(viewsets.ModelViewSet):
    queryset = ReservaServicio.objects.all()
    serializer_class = ReservaServicioSerializer

class VentaReservaViewSet(viewsets.ModelViewSet):
    queryset = VentaReserva.objects.all()
    serializer_class = VentaReservaSerializer

    def get_queryset(self):
        """
        Filtra las reservas por cliente, servicio, o fecha.
        """
        queryset = super().get_queryset()

        # Filtros por cliente, servicio y fecha
        cliente_id = self.request.query_params.get('cliente')
        servicio_id = self.request.query_params.get('servicio')
        fecha_inicio = self.request.query_params.get('fecha_inicio')
        fecha_fin = self.request.query_params.get('fecha_fin')

        # Filtrar por cliente
        if cliente_id:
            queryset = queryset.filter(cliente_id=cliente_id)

        # Filtrar por servicio (assuming services are linked via ReservaServicio)
        if servicio_id:
            # This filter might need adjustment based on how services are linked.
            # If VentaReserva has a direct M2M to Servicio:
            # queryset = queryset.filter(servicios__id=servicio_id)
            # If linked via ReservaServicio:
            queryset = queryset.filter(reservaservicios__servicio_id=servicio_id).distinct()


        # Filtrar por rango de fechas
        if fecha_inicio and fecha_fin:
            queryset = queryset.filter(fecha_reserva__range=[fecha_inicio, fecha_fin])
        elif fecha_inicio:
            queryset = queryset.filter(fecha_reserva__gte=fecha_inicio)
        elif fecha_fin:
            queryset = queryset.filter(fecha_reserva__lte=fecha_fin)

        return queryset

    def create(self, request, *args, **kwargs):
        data = request.data
        cliente_id = data.get('cliente')
        # Assuming 'productos' and 'servicios' are lists of dicts in the request data
        productos_data = data.get('productos', [])
        servicios_data = data.get('servicios', [])

        if not cliente_id:
             raise ValidationError("El campo 'cliente' es requerido.")

        # Envolver en una transacción atómica
        with transaction.atomic():
            # Crear la venta/reserva
            # Ensure cliente exists
            cliente = get_object_or_404(Cliente, pk=cliente_id)
            venta_reserva = VentaReserva.objects.create(cliente=cliente, fecha_reserva=timezone.now())

            # Procesar los productos
            for producto_data in productos_data:
                producto_id = producto_data.get('producto')
                cantidad = producto_data.get('cantidad')
                if not producto_id or cantidad is None:
                    raise ValidationError("Datos de producto incompletos (se requiere 'producto' y 'cantidad').")

                producto = get_object_or_404(Producto, id=producto_id)

                # Verificar si hay inventario suficiente
                if producto.cantidad_disponible < cantidad:
                    raise ValidationError(f"No hay suficiente inventario para el producto {producto.nombre}.")

                # Reducir inventario y agregar producto a la reserva
                # Consider moving inventory logic to a signal or service
                producto.cantidad_disponible -= cantidad
                producto.save()
                ReservaProducto.objects.create(
                    venta_reserva=venta_reserva,
                    producto=producto,
                    cantidad=cantidad,
                    precio_unitario=producto.precio_base # Store price at time of reservation
                )

            # Procesar los servicios
            for servicio_data in servicios_data:
                servicio_id = servicio_data.get('servicio')
                fecha_agendamiento_str = servicio_data.get('fecha_agendamiento')
                hora_inicio_str = servicio_data.get('hora_inicio') # Assuming time is passed
                cantidad_personas = servicio_data.get('cantidad_personas', 1)

                if not servicio_id or not fecha_agendamiento_str or not hora_inicio_str:
                    raise ValidationError("Datos de servicio incompletos (se requiere 'servicio', 'fecha_agendamiento', 'hora_inicio').")

                servicio = get_object_or_404(Servicio, id=servicio_id)
                try:
                    fecha_agendamiento = datetime.strptime(fecha_agendamiento_str, '%Y-%m-%d').date()
                    # Assuming hora_inicio_str is HH:MM
                    hora_inicio = datetime.strptime(hora_inicio_str, '%H:%M').time()
                except ValueError:
                    raise ValidationError("Formato de fecha u hora inválido. Use YYYY-MM-DD y HH:MM.")


                # Verificar disponibilidad del servicio (using the utility function)
                # Note: verificar_disponibilidad might need adjustment if it expects datetimes
                if not verificar_disponibilidad(servicio, fecha_agendamiento, hora_inicio): # Adjust call if needed
                    raise ValidationError(f"El servicio {servicio.nombre} no está disponible en la fecha {fecha_agendamiento_str} a las {hora_inicio_str}.")

                # Agregar el servicio a la reserva
                ReservaServicio.objects.create(
                    venta_reserva=venta_reserva,
                    servicio=servicio,
                    fecha_agendamiento=fecha_agendamiento,
                    hora_inicio=hora_inicio,
                    cantidad_personas=cantidad_personas,
                    precio_unitario=servicio.precio_base # Store price at time of reservation
                )

            # Guardar la reserva y calcular el total
            venta_reserva.calcular_total() # This method should save the instance

        # Serializar la respuesta con los datos actualizados
        serializer = self.get_serializer(venta_reserva)
        return Response(serializer.data, status=201) # Use 201 Created status

    def update(self, request, *args, **kwargs):
        # Update logic can be complex: replacing all items, adding/removing specific items?
        # This example assumes replacing items, which might not be ideal.
        # Consider dedicated endpoints for adding/removing items or a more granular update approach.
        instance = self.get_object()
        data = request.data

        productos_data = data.get('productos', [])
        servicios_data = data.get('servicios', [])

        with transaction.atomic():
            # --- Handle potential updates to related items ---
            # Option 1: Clear existing and add new (simple but destructive)
            # instance.reservaproductos.all().delete() # Need to handle inventory restoration
            # instance.reservaservicios.all().delete()

            # Option 2: More complex diffing logic (better but harder)
            # ... compare existing items with data, add/update/delete as needed ...

            # --- For simplicity, let's assume adding items (adjust as needed) ---

            # Procesar los productos actualizados
            for producto_data in productos_data:
                # Similar logic as in create, potentially checking if item exists first
                producto_id = producto_data.get('producto')
                cantidad = producto_data.get('cantidad')
                if not producto_id or cantidad is None: continue # Skip incomplete

                producto = get_object_or_404(Producto, id=producto_id)
                # Check inventory, update/create ReservaProducto, adjust inventory...

            # Procesar los servicios actualizados
            for servicio_data in servicios_data:
                 # Similar logic as in create, potentially checking if item exists first
                servicio_id = servicio_data.get('servicio')
                fecha_agendamiento_str = servicio_data.get('fecha_agendamiento')
                hora_inicio_str = servicio_data.get('hora_inicio')
                if not servicio_id or not fecha_agendamiento_str or not hora_inicio_str: continue # Skip incomplete

                servicio = get_object_or_404(Servicio, id=servicio_id)
                # Parse dates/times, check availability, update/create ReservaServicio...


            # Recalculate total after modifications
            instance.calcular_total() # Should save

        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class PagoViewSet(viewsets.ModelViewSet):
    queryset = Pago.objects.all()
    serializer_class = PagoSerializer

    def create(self, request, *args, **kwargs):
        # Consider adding validation and ensuring user permissions if needed
        data = request.data
        venta_reserva_id = data.get('venta_reserva')
        monto = data.get('monto')
        metodo_pago = data.get('metodo_pago')
        usuario = request.user # Associate payment with logged-in user

        if not venta_reserva_id or monto is None or not metodo_pago:
             raise ValidationError("Se requieren 'venta_reserva', 'monto' y 'metodo_pago'.")

        venta_reserva = get_object_or_404(VentaReserva, id=venta_reserva_id)

        # Basic validation
        try:
            monto_decimal = decimal.Decimal(monto)
            if monto_decimal <= 0:
                 raise ValidationError("El monto debe ser positivo.")
        except (TypeError, decimal.InvalidOperation):
             raise ValidationError("Monto inválido.")


        with transaction.atomic():
            pago = Pago.objects.create(
                venta_reserva=venta_reserva,
                monto=monto_decimal,
                metodo_pago=metodo_pago,
                fecha_pago=timezone.now(),
                usuario=usuario if usuario.is_authenticated else None # Handle anonymous if applicable
            )

            # Signal should handle updating VentaReserva status, but refresh to be sure
            venta_reserva.refresh_from_db()

        serializer = self.get_serializer(pago)
        return Response(serializer.data, status=201) # Use 201 Created


# --- New API View for Client Lookup ---
@require_GET # Only allow GET requests for this endpoint
def get_client_details_by_phone(request):
    """
    API endpoint to fetch client details based on phone number.
    Expects 'telefono' as a GET parameter.
    """
    phone_number = request.GET.get('telefono', None)

    if not phone_number:
        return JsonResponse({'error': 'Parámetro "telefono" es requerido.'}, status=400)

    # Basic cleaning/normalization (should match logic used elsewhere, e.g., checkout)
    cleaned_telefono = ''.join(filter(str.isdigit, phone_number))
    if len(cleaned_telefono) > 9 and not phone_number.startswith('+'):
         formatted_telefono = '+' + cleaned_telefono
    else:
         formatted_telefono = phone_number # Use original if already formatted or short

    try:
        # Use the potentially cleaned/formatted number for lookup
        cliente = Cliente.objects.get(telefono=formatted_telefono)
        data = {
            'found': True,
            'nombre': cliente.nombre,
            'email': cliente.email or '', # Return empty string if null
            'documento_identidad': cliente.documento_identidad or '' # Return empty string if null
        }
        return JsonResponse(data)
    except Cliente.DoesNotExist:
        return JsonResponse({'found': False})
    except Exception as e:
        # Log the error for debugging
        print(f"Error in get_client_details_by_phone: {e}")
        return JsonResponse({'error': 'Error interno del servidor'}, status=500)
