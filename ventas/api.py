from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.db import transaction
from django.contrib.auth.models import User
from django.utils import timezone
from .models import VentaReserva, Cliente, Servicio, Producto, ReservaServicio, ReservaProducto, MovimientoCliente
from decimal import Decimal

@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def create_prebooking(request):
    try:
        with transaction.atomic():
            data = request.data
            
            # Get or create cliente
            cliente, created = Cliente.objects.get_or_create(
                telefono=data['telefono'],
                defaults={'nombre': data['nombre_cliente']}
            )

            # Create VentaReserva
            venta_reserva = VentaReserva.objects.create(
                cliente=cliente,
                fecha_reserva=data['fecha_reserva'],
                estado_reserva='pendiente',
                estado_pago='pendiente',
                comentarios=data.get('comentarios', '')
            )

            # Add services
            for servicio_data in data['servicios']:
                servicio = Servicio.objects.get(id=servicio_data['servicio_id'])
                venta_reserva.agregar_servicio(
                    servicio=servicio,
                    fecha_agendamiento=servicio_data['fecha_agendamiento'],
                    cantidad_personas=servicio_data.get('cantidad_personas', 1)
                )

            # Calculate initial total before discount
            venta_reserva.calcular_total()

            # Handle discount if provided
            if data.get('discount_code'):
                # Here you might want to validate the discount code
                # and calculate the discount amount based on your business rules
                if data['discount_code'] == 'AREMKO15':
                    discount_amount = venta_reserva.total * Decimal('0.15')  # 15% discount
                    venta_reserva.registrar_pago(
                        monto=discount_amount,
                        metodo_pago='descuento'
                    )

            # Create MovimientoCliente for the pre-booking
            MovimientoCliente.objects.create(
                cliente=cliente,
                tipo_movimiento='pre_reserva',
                usuario=None,
                comentarios=f"Pre-reserva automática - {data.get('comentarios', '')}",
                venta_reserva=venta_reserva
            )

            return Response({
                'status': 'success',
                'message': 'Pre-booking created successfully',
                'venta_reserva_id': venta_reserva.id,
                'total': float(venta_reserva.total),
                'discount_applied': float(discount_amount) if data.get('discount_code') else 0
            }, status=status.HTTP_201_CREATED)

    except Servicio.DoesNotExist:
        return Response({
            'status': 'error',
            'message': 'Invalid service ID'
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({
            'status': 'error',
            'message': str(e),
            'traceback': traceback.format_exc()
        }, status=status.HTTP_400_BAD_REQUEST) 