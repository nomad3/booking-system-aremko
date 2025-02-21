from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
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
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def get_cliente(request, telefono=None):
    """
    Obtiene un cliente por su teléfono o lista todos los clientes
    """
    try:
        if telefono:
            cliente = get_object_or_404(Cliente, telefono=telefono)
            serializer = ClienteSerializer(cliente)
            return Response(serializer.data)
        else:
            clientes = Cliente.objects.all()
            serializer = ClienteSerializer(clientes, many=True)
            return Response(serializer.data)
    except Exception as e:
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
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
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def update_cliente(request, telefono):
    """
    Actualiza un cliente existente
    """
    try:
        cliente = get_object_or_404(Cliente, telefono=telefono)
        serializer = ClienteSerializer(cliente, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({
                'status': 'success',
                'message': 'Cliente actualizado exitosamente',
                'data': serializer.data
            })
        return Response({
            'status': 'error',
            'message': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_400_BAD_REQUEST) 