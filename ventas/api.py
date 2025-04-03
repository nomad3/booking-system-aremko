from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.db import transaction
from django.contrib.auth.models import User
from django.utils import timezone
from .models import VentaReserva, Cliente, Servicio, Producto, ReservaServicio, ReservaProducto, MovimientoCliente, Pago
from decimal import Decimal
import traceback
import logging
from datetime import datetime
from django.utils.dateparse import parse_datetime
from django.shortcuts import get_object_or_404
from .serializers import ClienteSerializer

logger = logging.getLogger(__name__)

@csrf_exempt
@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def create_prebooking(request):
    try:
        with transaction.atomic():
            data = request.data
            
            # Get or create cliente
            cliente = Cliente.objects.get_or_create(
                telefono=data['telefono'],
                defaults={'nombre': data['nombre_cliente']}
            )[0]

            # Create VentaReserva
            venta_reserva = VentaReserva.objects.create(
                cliente=cliente,
                fecha_reserva=parse_datetime(data['fecha_reserva']),
                estado_reserva='pendiente',
                estado_pago='pendiente',
                comentarios=data.get('comentarios', '')
            )

            # Add services and calculate total
            for servicio_data in data['servicios']:
                servicio = Servicio.objects.get(id=servicio_data['servicio_id'])
                fecha_agendamiento = parse_datetime(servicio_data['fecha_agendamiento'])
                venta_reserva.agregar_servicio(
                    servicio=servicio,
                    fecha_agendamiento=fecha_agendamiento,
                    cantidad_personas=servicio_data.get('cantidad_personas', 1)
                )

            venta_reserva.calcular_total()

            # Handle discount
            discount_amount = Decimal('0')
            if data.get('discount_code') == 'AREMKO15':
                discount_amount = venta_reserva.total * Decimal('0.15')
                # Create Pago with user context
                pago = Pago(
                    venta_reserva=venta_reserva,
                    monto=discount_amount,
                    metodo_pago='descuento'
                )
                pago._current_user = request.user  # Add user context
                pago.save()  # This will trigger the signal with user context

            return Response({
                'status': 'success',
                'message': 'Pre-booking created successfully',
                'venta_reserva_id': venta_reserva.id,
                'total': float(venta_reserva.total),
                'discount_applied': float(discount_amount)
            }, status=status.HTTP_201_CREATED)

    except Exception as e:
        return Response({
            'status': 'error',
            'message': str(e),
            'traceback': traceback.format_exc()
        }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([AllowAny])
def get_cliente(request, telefono=None):
    """
    Obtiene un cliente por su teléfono o lista todos los clientes
    """
    try:
        if telefono:
            # Buscar todos los clientes con ese teléfono
            clientes = Cliente.objects.filter(telefono=telefono)
            if not clientes.exists():
                return Response({
                    'status': 'error',
                    'message': 'No se encontró ningún cliente con ese teléfono'
                }, status=status.HTTP_404_NOT_FOUND)
            
            serializer = ClienteSerializer(clientes, many=True)
            return Response({
                'status': 'success',
                'count': clientes.count(),
                'data': serializer.data
            })
        else:
            clientes = Cliente.objects.all()
            serializer = ClienteSerializer(clientes, many=True)
            return Response({
                'status': 'success',
                'count': clientes.count(),
                'data': serializer.data
            })
    except Exception as e:
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([AllowAny])
def create_cliente(request):
    """
    Crea un nuevo cliente
    """
    try:
        serializer = ClienteSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({
                'status': 'success',
                'message': 'Cliente creado exitosamente',
                'data': serializer.data
            }, status=status.HTTP_201_CREATED)
        return Response({
            'status': 'error',
            'message': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['PUT'])
@permission_classes([AllowAny])
def update_cliente(request, telefono):
    """
    Actualiza un cliente existente
    """
    try:
        # Debug: Imprimir información de la solicitud
        print("Método:", request.method)
        print("Headers:", request.headers)
        print("Datos recibidos:", request.data)
        print("Teléfono:", telefono)

        # Buscar el cliente
        cliente = Cliente.objects.filter(telefono=telefono).first()
        
        if not cliente:
            return Response({
                'status': 'error',
                'message': f'No se encontró el cliente con teléfono {telefono}',
                'telefono_buscado': telefono
            }, status=status.HTTP_404_NOT_FOUND)

        # Validar que hay datos para actualizar
        if not request.data:
            return Response({
                'status': 'error',
                'message': 'No se recibieron datos para actualizar'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Actualizar solo los campos proporcionados
        if 'email' in request.data:
            cliente.email = request.data['email']
        if 'ciudad' in request.data:
            cliente.ciudad = request.data['ciudad']
        
        # Guardar cambios
        cliente.save()
        
        # Serializar y devolver respuesta
        serializer = ClienteSerializer(cliente)
        return Response({
            'status': 'success',
            'message': 'Cliente actualizado exitosamente',
            'data': serializer.data
        }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({
            'status': 'error',
            'message': str(e),
            'trace': traceback.format_exc(),
            'received_data': request.data,
            'content_type': request.content_type
        })

@api_view(['GET'])
@permission_classes([AllowAny]) # Allow access without authentication for this specific task
def get_client_by_phone(request):
    """
    Fetches client data based on the provided phone number.
    """
    telefono = request.GET.get('telefono', None)
    
    if not telefono:
        return Response({'error': 'Phone number parameter is required.'}, status=status.HTTP_400_BAD_REQUEST)

    # Basic cleaning - remove common non-digit characters
    # Consider using phonenumbers library here for more robust parsing/validation if needed
    cleaned_telefono = ''.join(filter(str.isdigit, telefono))
    
    # Add '+' if it's likely an international number but missing the prefix
    # This is a basic heuristic, might need refinement based on expected input formats
    if len(cleaned_telefono) > 9 and not telefono.startswith('+'):
         # Attempt to guess country code if needed, or assume a default like +56 for Chile
         # For simplicity, let's assume '+' was just missing
         formatted_telefono = '+' + cleaned_telefono
    else:
         formatted_telefono = telefono # Use original if it already has '+' or is short

    try:
        # Try finding client with the potentially formatted number or original input
        cliente = Cliente.objects.filter(Q(telefono=formatted_telefono) | Q(telefono=telefono)).first() 
        
        if cliente:
            serializer = ClienteSerializer(cliente)
            return Response({'cliente': serializer.data})
        else:
            return Response({'cliente': None}, status=status.HTTP_404_NOT_FOUND)
            
    except Exception as e:
        logger.error(f"Error fetching client by phone {telefono}: {e}")
        return Response({'error': 'An error occurred while fetching client data.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
