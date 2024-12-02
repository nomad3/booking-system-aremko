from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import VentaReserva, Cliente, Servicio, ReservaServicio, Producto, ReservaProducto
from django.utils import timezone
from django.db import transaction

@api_view(['POST'])
def create_prebooking(request):
    try:
        with transaction.atomic():
            data = request.data
            
            # Validate required fields
            if not data.get('telefono') or not data.get('nombre_cliente'):
                return Response({
                    'status': 'error',
                    'message': 'Nombre y teléfono son campos obligatorios'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Create or get client without email
            cliente, created = Cliente.objects.get_or_create(
                telefono=data.get('telefono'),
                defaults={
                    'nombre': data.get('nombre_cliente')
                }
            )

            # Create the main booking
            venta_reserva = VentaReserva.objects.create(
                cliente=cliente,
                fecha_reserva=data.get('fecha_reserva'),
                estado_reserva='PENDIENTE',
                estado_pago='PENDIENTE',
                comentarios=data.get('comentarios', 'Pre-reserva creada por agente virtual'),
                cobrado=False
            )

            total_venta = 0
            
            # Add services and create ReservaServicio entries
            if 'servicios' in data:
                for servicio_data in data['servicios']:
                    try:
                        servicio = Servicio.objects.get(id=servicio_data['servicio_id'])
                        cantidad_personas = servicio_data.get('cantidad_personas', 1)
                        
                        # Calculate values
                        precio_unitario = servicio.precio_base
                        valor_total = precio_unitario * cantidad_personas
                        total_venta += valor_total

                        # Create ReservaServicio
                        ReservaServicio.objects.create(
                            venta_reserva=venta_reserva,
                            servicio=servicio,
                            cantidad_personas=cantidad_personas,
                            fecha_agendamiento=servicio_data.get('fecha_agendamiento'),
                            precio_unitario=precio_unitario,
                            valor_total=valor_total
                        )
                    except Servicio.DoesNotExist:
                        raise ValueError(f"Servicio con ID {servicio_data['servicio_id']} no encontrado")

            # Apply discount if provided
            discount_code = data.get('discount_code')
            if discount_code:
                try:
                    producto_descuento = Producto.objects.get(codigo=discount_code, tipo='DESCUENTO')
                    # Create ReservaProducto for the discount
                    ReservaProducto.objects.create(
                        venta_reserva=venta_reserva,
                        producto=producto_descuento,
                        cantidad=1,
                        precio_unitario=producto_descuento.precio_base,
                        valor_total=producto_descuento.precio_base  # Assuming precio_base is negative for discounts
                    )
                    total_venta += producto_descuento.precio_base  # Add the negative value to total
                except Producto.DoesNotExist:
                    raise ValueError('Código de descuento no válido')

            # Update the total in VentaReserva
            venta_reserva.total = total_venta
            venta_reserva.save()

            return Response({
                'status': 'success',
                'message': 'Pre-reserva creada exitosamente',
                'reserva_id': venta_reserva.id,
                'total': total_venta,
                'cliente_id': cliente.id
            }, status=status.HTTP_201_CREATED)

    except Exception as e:
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_400_BAD_REQUEST) 