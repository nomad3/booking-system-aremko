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
    Servicio, ReservaProducto, ReservaServicio, CategoriaServicio, Region, Comuna
)
# Import Cliente and Servicio models directly for the new views
from ..models import Cliente, Servicio, Proveedor
from ..serializers import ( # Relative imports
    ProveedorSerializer, CategoriaProductoSerializer, ProductoSerializer,
    VentaReservaSerializer, ClienteSerializer, PagoSerializer,
    ReservaProductoSerializer, ServicioSerializer, ReservaServicioSerializer,
    CategoriaServicioSerializer, RegionSerializer, ComunaSerializer
)
from ..calendar_utils import verificar_disponibilidad # Relative import
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated # Or custom permission
from rest_framework import status
from ..models import Campaign, Contact, Activity, CampaignInteraction # Import CRM models including Interaction
from .. import communication_utils # Import communication utils
from django.conf import settings # To get placeholder API key
from django.utils.dateparse import parse_datetime # For parsing timestamp if provided

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
        # Log the error for debugging
        print(f"Error in get_client_details_by_phone: {e}")
        return JsonResponse({'error': 'Error interno del servidor'}, status=500)

# Removed get_service_providers view as it's no longer needed for admin JS


# --- API Endpoints for Remarketing & Automation ---

# Placeholder for API Key Authentication (Replace with a proper method)
def is_valid_api_key(request):
    provided_key = request.headers.get('X-API-KEY')
    expected_key = getattr(settings, 'AUTOMATION_API_KEY', None) # Get key from settings
    if not expected_key or not provided_key:
        return False
    return provided_key == expected_key

@api_view(['GET'])
# @permission_classes([IsAuthenticated]) # Or a custom permission class
def get_campaign_targets(request, campaign_id):
    """
    API endpoint to get a list of target Cliente IDs for a specific campaign
    based on its defined criteria (min_visits, min_spend).
    Requires authentication (e.g., API Key in header).
    """
    # --- Authentication (Placeholder - Replace with robust method) ---
    if not is_valid_api_key(request):
         return Response({"error": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED)
    # --- End Authentication ---

    campaign = get_object_or_404(Campaign, pk=campaign_id)
    target_clientes_qs = campaign.get_target_clientes()

    # Serialize the required client data for n8n
    target_data = []
    for cliente in target_clientes_qs:
        target_data.append({
            'id': cliente.id,
            'nombre': cliente.nombre,
            'email': cliente.email,
            'telefono': cliente.telefono,
            # Add any other fields n8n might need for personalization
        })

    return Response({'campaign_id': campaign.id, 'targets': target_data})

@api_view(['GET'])
# @permission_classes([IsAuthenticated]) # Or a custom permission class
def get_campaign_details(request, campaign_id):
    """
    API endpoint to get details for a specific campaign, including templates.
    Requires authentication (e.g., API Key in header).
    """
    # --- Authentication (Placeholder - Replace with robust method) ---
    if not is_valid_api_key(request):
         return Response({"error": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED)
    # --- End Authentication ---

    campaign = get_object_or_404(Campaign, pk=campaign_id)

    data = {
        'id': campaign.id,
        'name': campaign.name,
        'status': campaign.status,
        'goal': campaign.goal,
        'email_subject_template': campaign.email_subject_template,
        'email_body_template': campaign.email_body_template,
        'sms_template': campaign.sms_template,
        'whatsapp_template': campaign.whatsapp_template,
        # Add other campaign fields if needed by n8n
    }
    return Response(data)


@api_view(['POST'])
# @permission_classes([IsAuthenticated]) # Or a custom permission class
def log_external_activity(request):
    """
    API endpoint for external tools (like n8n) to log a communication activity.
    Expects data like:
    {
        "contact_identifier_type": "email" or "phone",
        "contact_identifier": "user@example.com" or "+123456789",
        "campaign_id": 123,
        "activity_type": "SMS Sent", # Or "WhatsApp Sent", "Call Attempted", etc.
        "subject": "Subject of the communication",
        "notes": "Optional notes about the interaction."
    }
    Requires authentication (e.g., API Key in header).
    """
    # --- Authentication (Placeholder - Replace with robust method) ---
    if not is_valid_api_key(request):
         return Response({"error": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED)
    # --- End Authentication ---

    data = request.data
    identifier_type = data.get('contact_identifier_type')
    identifier = data.get('contact_identifier')
    campaign_id = data.get('campaign_id')
    activity_type = data.get('activity_type')
    subject = data.get('subject')
    notes = data.get('notes', '')

    if not all([identifier_type, identifier, campaign_id, activity_type, subject]):
        return Response({"error": "Missing required fields: contact_identifier_type, contact_identifier, campaign_id, activity_type, subject"}, status=status.HTTP_400_BAD_REQUEST)

    # Find Contact based on identifier
    contact = None
    try:
        if identifier_type == 'email':
            contact = Contact.objects.get(email=identifier)
        elif identifier_type == 'phone':
            # Add potential phone number cleaning/normalization if needed here
            contact = Contact.objects.get(phone=identifier)
        else:
            return Response({"error": "Invalid contact_identifier_type. Use 'email' or 'phone'."}, status=status.HTTP_400_BAD_REQUEST)
    except Contact.DoesNotExist:
        # Optionally create a Contact/Lead here if desired, or just fail
        logger.warning(f"Contact not found for identifier {identifier_type}={identifier} during external activity logging.")
        return Response({"error": f"Contact not found for {identifier_type} '{identifier}'."}, status=status.HTTP_404_NOT_FOUND)
    except Contact.MultipleObjectsReturned:
         logger.error(f"Multiple contacts found for identifier {identifier_type}={identifier}. Cannot log activity.")
         return Response({"error": f"Multiple contacts found for {identifier_type} '{identifier}'. Ambiguous."}, status=status.HTTP_400_BAD_REQUEST)


    # Find Campaign
    campaign = get_object_or_404(Campaign, pk=campaign_id)

    # Log the activity using the utility function (without sending anything from here)
    activity = communication_utils.log_communication_activity(
        contact=contact,
        campaign=campaign,
        activity_type=activity_type,
        subject=subject,
        notes=f"(Logged via API) {notes}",
        created_by=None # Activity logged by the system/automation
    )

    if activity:
        return Response({"success": True, "activity_id": activity.id}, status=status.HTTP_201_CREATED)
    else:
        return Response({"error": "Failed to log activity."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
# @permission_classes([IsAuthenticated]) # Or a custom permission class
def log_campaign_interaction(request):
    """
    API endpoint for external systems (email platforms, SMS gateways, n8n)
    to log customer interactions related to a campaign.
    Expects data like:
    {
        "contact_identifier_type": "email" or "phone",
        "contact_identifier": "user@example.com" or "+123456789",
        "campaign_id": 123,
        "interaction_type": "EMAIL_OPEN", # e.g., EMAIL_OPEN, EMAIL_CLICK, SMS_REPLY
        "timestamp": "2024-04-15T10:30:00Z", # Optional ISO 8601 format
        "details": { ... } # Optional JSON object (e.g., {"clicked_url": "..."})
        "activity_id": 456 # Optional: ID of the original Activity that led to this interaction
    }
    Requires authentication (e.g., API Key in header).
    """
    # --- Authentication (Placeholder - Replace with robust method) ---
    if not is_valid_api_key(request):
         return Response({"error": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED)
    # --- End Authentication ---

    data = request.data
    identifier_type = data.get('contact_identifier_type')
    identifier = data.get('contact_identifier')
    campaign_id = data.get('campaign_id')
    interaction_type = data.get('interaction_type')
    timestamp_str = data.get('timestamp') # Optional timestamp
    details = data.get('details') # Optional details
    activity_id = data.get('activity_id') # Optional originating activity

    if not all([identifier_type, identifier, campaign_id, interaction_type]):
        return Response({"error": "Missing required fields: contact_identifier_type, contact_identifier, campaign_id, interaction_type"}, status=status.HTTP_400_BAD_REQUEST)

    # Validate interaction_type
    valid_interaction_types = [choice[0] for choice in CampaignInteraction.INTERACTION_TYPES]
    if interaction_type not in valid_interaction_types:
         return Response({"error": f"Invalid interaction_type. Valid types are: {', '.join(valid_interaction_types)}"}, status=status.HTTP_400_BAD_REQUEST)

    # Find Contact
    contact = None
    try:
        if identifier_type == 'email':
            contact = Contact.objects.get(email=identifier)
        elif identifier_type == 'phone':
            contact = Contact.objects.get(phone=identifier) # Add normalization if needed
        else:
            return Response({"error": "Invalid contact_identifier_type. Use 'email' or 'phone'."}, status=status.HTTP_400_BAD_REQUEST)
    except Contact.DoesNotExist:
        logger.warning(f"Contact not found for identifier {identifier_type}={identifier} during interaction logging.")
        return Response({"error": f"Contact not found for {identifier_type} '{identifier}'."}, status=status.HTTP_404_NOT_FOUND)
    except Contact.MultipleObjectsReturned:
         logger.error(f"Multiple contacts found for identifier {identifier_type}={identifier}. Cannot log interaction.")
         return Response({"error": f"Multiple contacts found for {identifier_type} '{identifier}'. Ambiguous."}, status=status.HTTP_400_BAD_REQUEST)

    # Find Campaign
    campaign = get_object_or_404(Campaign, pk=campaign_id)

    # Find original Activity if ID provided
    activity = None
    if activity_id:
        try:
            activity = Activity.objects.get(pk=activity_id)
        except Activity.DoesNotExist:
             logger.warning(f"Originating Activity ID {activity_id} not found when logging interaction.")
             # Decide whether to proceed without linking or return an error

    # Parse timestamp or use current time
    timestamp = timezone.now()
    if timestamp_str:
        parsed_time = parse_datetime(timestamp_str)
        if parsed_time:
            timestamp = parsed_time
        else:
             logger.warning(f"Could not parse provided timestamp '{timestamp_str}'. Using current time.")


    # Create the interaction record
    try:
        interaction = CampaignInteraction.objects.create(
            contact=contact,
            campaign=campaign,
            activity=activity, # Link to original activity if found
            interaction_type=interaction_type,
            timestamp=timestamp,
            details=details # Store extra JSON data if provided
        )

        # --- Optional: Trigger n8n Webhook ---
        # If you want n8n to react immediately to interactions, you could
        # make an HTTP POST request to a specific n8n webhook URL here.
        # Example (requires 'requests' library and n8n webhook URL in settings):
        # n8n_webhook_url = getattr(settings, 'N8N_INTERACTION_WEBHOOK_URL', None)
        # if n8n_webhook_url:
        #     try:
        #         interaction_data = { # Send relevant data to n8n
        #             "interaction_id": interaction.id,
        #             "contact_id": contact.id,
        #             "campaign_id": campaign.id,
        #             "interaction_type": interaction.interaction_type,
        #             "timestamp": interaction.timestamp.isoformat(),
        #             "details": interaction.details
        #         }
        #         # Consider running this asynchronously (e.g., with Celery) to avoid blocking the API response
        #         response = requests.post(n8n_webhook_url, json=interaction_data, timeout=5)
        #         response.raise_for_status() # Raise an exception for bad status codes
        #         logger.info(f"Successfully triggered n8n webhook for interaction {interaction.id}")
        #     except requests.exceptions.RequestException as e:
        #         logger.error(f"Failed to trigger n8n webhook for interaction {interaction.id}: {e}")
        # --- End Optional n8n Trigger ---


        return Response({"success": True, "interaction_id": interaction.id}, status=status.HTTP_201_CREATED)
    except Exception as e:
        logger.error(f"Error creating CampaignInteraction for contact {contact.id}, campaign {campaign.id}: {e}")
        return Response({"error": "Failed to log interaction."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# ============================================
# VIEWSETS PARA REGIÓN Y COMUNA
# ============================================

class RegionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet de solo lectura para Regiones.
    
    Endpoints:
    - GET /api/regiones/ - Lista todas las regiones
    - GET /api/regiones/{id}/ - Detalle de una región
    """
    queryset = Region.objects.all().order_by('orden')
    serializer_class = RegionSerializer
    permission_classes = [AllowAny]  # Permitir acceso público


class ComunaViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet de solo lectura para Comunas.
    
    Endpoints:
    - GET /api/comunas/ - Lista todas las comunas
    - GET /api/comunas/{id}/ - Detalle de una comuna
    - GET /api/comunas/?region={region_id} - Filtra comunas por región
    
    Query params:
    - region: ID de la región para filtrar comunas
    """
    queryset = Comuna.objects.all().select_related('region').order_by('region__orden', 'nombre')
    serializer_class = ComunaSerializer
    permission_classes = [AllowAny]  # Permitir acceso público
    
    def get_queryset(self):
        """
        Filtra comunas por región si se proporciona el parámetro 'region'.
        """
        queryset = super().get_queryset()
        region_id = self.request.query_params.get('region', None)
        
        if region_id is not None:
            queryset = queryset.filter(region_id=region_id)
        
        return queryset
