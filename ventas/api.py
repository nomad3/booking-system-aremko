from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.db import transaction
from django.contrib.auth.models import User
from django.utils import timezone
from .models import VentaReserva, Cliente, Servicio, Producto, ReservaServicio, ReservaProducto, MovimientoCliente

@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def create_prebooking(request):
    try:
        with transaction.atomic():
            data = request.data
            current_time = timezone.now()
            
            # Get or create cliente
            cliente, created = Cliente.objects.get_or_create(
                telefono=data['telefono'],
                defaults={'nombre': data['nombre_cliente']}
            )

            # Create VentaReserva without user
            venta_reserva = VentaReserva.objects.create(
                cliente=cliente,
                fecha_reserva=data['fecha_reserva'],
                estado='pre_reserva',
                comentarios=data.get('comentarios', ''),
                usuario=None  # Set to None for now
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
                discount_product, _ = Producto.objects.get_or_create(
                    codigo=data['discount_code'],
                    defaults={
                        'nombre': f"Descuento {data['discount_code']}",
                        'precio': 0,
                        'tipo': 'descuento'
                    }
                )
                
                ReservaProducto.objects.create(
                    venta_reserva=venta_reserva,
                    producto=discount_product,
                    cantidad=1,
                    precio_unitario=0
                )

            # Create MovimientoCliente with fecha_movimiento
            MovimientoCliente.objects.create(
                cliente=cliente,
                tipo_movimiento='pre_reserva',
                usuario=None,  # Set to None
                comentarios=f"Pre-reserva automática - {data.get('comentarios', '')}",
                venta_reserva=venta_reserva,
                fecha_movimiento=current_time  # Add the current time
            )

            return Response({
                'status': 'success',
                'message': 'Pre-booking created successfully',
                'venta_reserva_id': venta_reserva.id,
                'fecha_movimiento': current_time.isoformat()
            }, status=status.HTTP_201_CREATED)

    except Servicio.DoesNotExist:
        return Response({
            'status': 'error',
            'message': 'Invalid service ID'
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        import traceback
        return Response({
            'status': 'error',
            'message': str(e),
            'traceback': traceback.format_exc()  # Include traceback for debugging
        }, status=status.HTTP_400_BAD_REQUEST) 