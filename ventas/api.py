from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db import transaction
from django.contrib.auth.models import User
from django.utils import timezone
from .models import VentaReserva, Cliente, Servicio, Producto, ReservaServicio, ReservaProducto, MovimientoCliente
from decimal import Decimal
import traceback
import logging
from datetime import datetime
from django.utils.dateparse import parse_datetime

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

            # Create VentaReserva without usuario
            venta_reserva = VentaReserva.objects.create(
                cliente=cliente,
                fecha_reserva=parse_datetime(data['fecha_reserva']),
                estado_reserva='pendiente',
                estado_pago='pendiente',
                comentarios=data.get('comentarios', '')
            )

            # Add services
            for servicio_data in data['servicios']:
                servicio = Servicio.objects.get(id=servicio_data['servicio_id'])
                fecha_agendamiento = parse_datetime(servicio_data['fecha_agendamiento'])
                venta_reserva.agregar_servicio(
                    servicio=servicio,
                    fecha_agendamiento=fecha_agendamiento,
                    cantidad_personas=servicio_data.get('cantidad_personas', 1)
                )

            # Calculate initial total before discount
            venta_reserva.calcular_total()

            # Handle discount if provided
            discount_amount = Decimal('0')
            if data.get('discount_code'):
                if data['discount_code'] == 'AREMKO15':
                    discount_amount = venta_reserva.total * Decimal('0.15')
                    venta_reserva.registrar_pago(
                        monto=discount_amount,
                        metodo_pago='descuento'
                    )

            # Create MovimientoCliente with the authenticated user
            MovimientoCliente.objects.create(
                cliente=cliente,
                tipo_movimiento='pre_reserva',
                usuario=request.user,
                fecha_movimiento=timezone.now(),
                comentarios=f"Pre-reserva automática - {data.get('comentarios', '')}",
                venta_reserva=venta_reserva
            )

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