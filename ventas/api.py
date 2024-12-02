from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.db import transaction
from django.contrib.auth.models import User
from .models import VentaReserva, Cliente, Servicio, Producto, ReservaServicio, ReservaProducto, MovimientoCliente

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

            # Get system user
            system_user, _ = User.objects.get_or_create(
                username='system',
                defaults={
                    'is_active': True,
                    'is_staff': True,
                    'email': 'system@example.com'
                }
            )

            # Create VentaReserva
            venta_reserva = VentaReserva.objects.create(
                cliente=cliente,
                fecha_reserva=data['fecha_reserva'],
                estado='pre_reserva',
                comentarios=data.get('comentarios', ''),
                usuario=system_user
            )

            # Add services
            for servicio_data in data['servicios']:
                servicio = Servicio.objects.get(id=servicio_data['servicio_id'])
                ReservaServicio.objects.create(
                    venta_reserva=venta_reserva,
                    servicio=servicio,
                    cantidad_personas=servicio_data['cantidad_personas'],
                    fecha_agendamiento=servicio_data['fecha_agendamiento']
                )

            # Add discount code as product if provided
            if data.get('discount_code'):
                # Get or create discount product
                discount_product, _ = Producto.objects.get_or_create(
                    codigo=data['discount_code'],
                    defaults={
                        'nombre': f"Descuento {data['discount_code']}",
                        'precio': 0,
                        'tipo': 'descuento'
                    }
                )
                
                # Create ReservaProducto for discount
                ReservaProducto.objects.create(
                    venta_reserva=venta_reserva,
                    producto=discount_product,
                    cantidad=1,
                    precio_unitario=0
                )

            # Create MovimientoCliente with system user
            MovimientoCliente.objects.create(
                cliente=cliente,
                tipo_movimiento='pre_reserva',
                usuario=system_user,
                comentarios=f"Pre-reserva automática - {data.get('comentarios', '')}",
                venta_reserva=venta_reserva
            )

            return Response({
                'status': 'success',
                'message': 'Pre-booking created successfully',
                'venta_reserva_id': venta_reserva.id
            }, status=status.HTTP_201_CREATED)

    except Servicio.DoesNotExist:
        return Response({
            'status': 'error',
            'message': 'Invalid service ID'
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_400_BAD_REQUEST) 