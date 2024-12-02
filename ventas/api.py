from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.db import transaction
from .models import VentaReserva, Cliente, Servicio

@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])  # Allow anonymous access
def create_prebooking(request):
    try:
        with transaction.atomic():
            data = request.data
            
            # Create or get cliente
            cliente, created = Cliente.objects.get_or_create(
                telefono=data['telefono'],
                defaults={'nombre': data['nombre_cliente']}
            )

            # Create pre-booking
            pre_booking = VentaReserva.objects.create(
                cliente=cliente,
                fecha_reserva=data['fecha_reserva'],
                estado='pre_reserva',  # Or whatever status you use for pre-bookings
                comentarios=data.get('comentarios', ''),
                discount_code=data.get('discount_code')
            )

            # Add services
            for servicio_data in data['servicios']:
                servicio = Servicio.objects.get(id=servicio_data['servicio_id'])
                pre_booking.servicios.create(
                    servicio=servicio,
                    cantidad_personas=servicio_data['cantidad_personas'],
                    fecha_agendamiento=servicio_data['fecha_agendamiento']
                )

            return Response({
                'status': 'success',
                'message': 'Pre-booking created successfully',
                'pre_booking_id': pre_booking.id
            }, status=status.HTTP_201_CREATED)

    except Exception as e:
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_400_BAD_REQUEST) 