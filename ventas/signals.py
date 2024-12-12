import logging
from django.db.models.signals import post_save, post_delete, m2m_changed, pre_save
from django.dispatch import receiver
from django.utils import timezone
from django.db import transaction
from django.db import models
from django.db.models import Sum, F, DecimalField 
from .models import VentaReserva, Cliente, ReservaProducto, ReservaServicio, Pago, MovimientoCliente, DetalleCompra, Compra
from django.contrib.auth.models import User, AnonymousUser  # Importa el modelo de usuario
from .middleware import get_current_user  # Importa el middleware
from django.contrib.auth import get_user_model

# Movimientos y auditoría

def get_or_create_system_user():
    """Helper function to get or create the system user"""
    system_user, _ = User.objects.get_or_create(
        username='system',
        defaults={
            'is_active': True,
            'is_staff': True,
            'email': 'system@example.com',
            'first_name': 'System',
            'last_name': 'User'
        }
    )
    return system_user

@receiver(post_save, sender=VentaReserva)
def registrar_movimiento_venta(sender, instance, created, **kwargs):
    """Signal for tracking VentaReserva changes in admin panel"""
    if created:
        try:
            with transaction.atomic():
                # Get the user from the request if available
                user = getattr(instance, '_current_user', None)
                
                MovimientoCliente.objects.create(
                    cliente=instance.cliente,
                    tipo_movimiento='pre_reserva',
                    usuario=user,
                    fecha_movimiento=timezone.now(),
                    comentarios=f"Pre-reserva automática - {instance.comentarios or ''}",
                    venta_reserva=instance
                )
        except Exception as e:
            print(f"Error in registrar_movimiento_venta: {e}")

@receiver(post_delete, sender=VentaReserva)
def registrar_movimiento_eliminacion_venta(sender, instance, **kwargs):
    usuario = get_current_user()
    descripcion = f"Se ha eliminado la venta/reserva con ID {instance.id} del cliente {instance.cliente.nombre}."
    
    MovimientoCliente.objects.create(
        cliente=instance.cliente,
        tipo_movimiento='Eliminación de Venta/Reserva',
        descripcion=descripcion,
        usuario=usuario,
        fecha_movimiento=timezone.now()
    )

# Clientes

@receiver(post_save, sender=Cliente)
def registrar_movimiento_cliente(sender, instance, created, **kwargs):
    """Signal for tracking Cliente changes in admin panel"""
    if created:
        try:
            with transaction.atomic():
                # Get the user from the request if available
                user = getattr(instance, '_current_user', None)
                
                MovimientoCliente.objects.create(
                    cliente=instance,
                    tipo_movimiento='creacion',
                    usuario=user,
                    fecha_movimiento=timezone.now(),
                    comentarios='Cliente creado automáticamente'
                )
        except Exception as e:
            print(f"Error in registrar_movimiento_cliente: {e}")

@receiver(post_delete, sender=Cliente)
def registrar_movimiento_eliminacion_cliente(sender, instance, **kwargs):
    usuario = get_current_user()
    descripcion = f"Se ha eliminado el cliente: {instance.nombre}."
    
    MovimientoCliente.objects.create(
        cliente=instance,
        tipo_movimiento='Eliminación de Cliente',
        descripcion=descripcion,
        usuario=usuario,
        fecha_movimiento=timezone.now()
    )

# Productos

@receiver(post_save, sender=ReservaProducto)
def registrar_movimiento_reserva_producto(sender, instance, created, **kwargs):
    usuario = get_current_user()
    tipo = 'Añadido Producto a Venta/Reserva' if created else 'Actualización de Producto en Venta/Reserva'
    descripcion = f"Se ha {'añadido' if created else 'actualizado'} {instance.cantidad} x {instance.producto.nombre} en la venta/reserva #{instance.venta_reserva.id}."
    
    MovimientoCliente.objects.create(
        cliente=instance.venta_reserva.cliente,
        tipo_movimiento=tipo,
        descripcion=descripcion,
        usuario=usuario,
        fecha_movimiento=timezone.now()
    )

@receiver(post_delete, sender=ReservaProducto)
def registrar_movimiento_eliminacion_producto(sender, instance, **kwargs):
    usuario = get_current_user()
    descripcion = f"Se ha eliminado {instance.cantidad} x {instance.producto.nombre} de la venta/reserva #{instance.venta_reserva.id}."
    
    MovimientoCliente.objects.create(
        cliente=instance.venta_reserva.cliente,
        tipo_movimiento='Eliminación de Producto en Venta/Reserva',
        descripcion=descripcion,
        usuario=usuario,
        fecha_movimiento=timezone.now()
    )

# Servicios

@receiver(post_save, sender=ReservaServicio)
def registrar_movimiento_reserva_servicio(sender, instance, created, **kwargs):
    usuario = get_current_user()
    tipo = 'Añadido Servicio a Venta/Reserva' if created else 'Actualización de Servicio en Venta/Reserva'
    descripcion = f"Se ha {'reservado' if created else 'actualizado'} el servicio {instance.servicio.nombre} para el {instance.fecha_agendamiento} en la venta/reserva #{instance.venta_reserva.id}."
    
    MovimientoCliente.objects.create(
        cliente=instance.venta_reserva.cliente,
        tipo_movimiento=tipo,
        descripcion=descripcion,
        usuario=usuario,
        fecha_movimiento=timezone.now()
    )

@receiver(post_delete, sender=ReservaServicio)
def registrar_movimiento_eliminacion_servicio(sender, instance, **kwargs):
    usuario = get_current_user()
    descripcion = f"Se ha eliminado la reserva del servicio {instance.servicio.nombre} de la venta/reserva #{instance.venta_reserva.id}."
    
    MovimientoCliente.objects.create(
        cliente=instance.venta_reserva.cliente,
        tipo_movimiento='Eliminación de Servicio en Venta/Reserva',
        descripcion=descripcion,
        usuario=usuario,
        fecha_movimiento=timezone.now()
    )

# Pagos

@receiver(post_save, sender=Pago)
def registrar_movimiento_pago(sender, instance, created, **kwargs):
    if created:
        try:
            with transaction.atomic():
                # Get user from instance or use None
                user = getattr(instance, '_current_user', None)
                
                MovimientoCliente.objects.create(
                    cliente=instance.venta_reserva.cliente,
                    tipo_movimiento='pago',
                    usuario=user,
                    fecha_movimiento=timezone.now(),
                    comentarios=f'Pago registrado - {instance.metodo_pago} - ${instance.monto}',
                    venta_reserva=instance.venta_reserva
                )
        except Exception as e:
            print(f"Error in registrar_movimiento_pago: {e}")

   # NO necesitas actualizar el saldo aquí. Ya se hace en el save() de Pago.

@receiver(post_delete, sender=Pago)
def registrar_movimiento_eliminacion_pago(sender, instance, **kwargs):
    usuario = get_current_user()
    descripcion = f"Se ha eliminado el pago de {instance.monto} de la venta/reserva #{instance.venta_reserva.id}."
    
    MovimientoCliente.objects.create(
        cliente=instance.venta_reserva.cliente,
        tipo_movimiento='Eliminación de Pago',
        descripcion=descripcion,
        usuario=usuario,
        fecha_movimiento=timezone.now()
    )

    # Restar el pago eliminado y actualizar el saldo pendiente
    instance.venta_reserva.pagado -= instance.monto
    instance.venta_reserva.actualizar_saldo()
    instance.venta_reserva.calcular_total()  # Recalcular el total

@receiver(post_delete, sender=ReservaProducto)
def actualizar_total_al_eliminar_producto(sender, instance, **kwargs):
    instance.venta_reserva.calcular_total()

@receiver(post_delete, sender=ReservaServicio)
def actualizar_total_al_eliminar_servicio(sender, instance, **kwargs):
    instance.venta_reserva.calcular_total()

@receiver(post_save, sender=ReservaServicio)
def actualizar_total_al_guardar_servicio(sender, instance, created, raw, using, update_fields, **kwargs):  # Agrega raw y using
    if created:
        instance.venta_reserva.calcular_total()
    elif not raw:  # Verifica que no sea una creación raw
        try:
            anterior_reserva_servicio = ReservaServicio.objects.using(using).get(pk=instance.pk)
            if anterior_reserva_servicio.cantidad_personas != instance.cantidad_personas or anterior_reserva_servicio.servicio != instance.servicio:
                instance.venta_reserva.calcular_total()
        except ReservaServicio.DoesNotExist:
            pass  # La instancia no existía antes, probablemente creada a través del inline

@receiver(post_save, sender=ReservaProducto)
@receiver(post_save, sender=ReservaServicio)
def actualizar_total_venta_reserva(sender, instance, created, **kwargs):
    instance.venta_reserva.actualizar_total()
    instance.venta_reserva.save() # Guardar los cambios del total

@receiver(post_save, sender=ReservaProducto)
def actualizar_inventario(sender, instance, created, **kwargs):
    if created:
        with transaction.atomic():
            instance.producto.reducir_inventario(instance.cantidad)
    else:
        cantidad_anterior = getattr(instance, '_cantidad_anterior', 0)
        diferencia = instance.cantidad - cantidad_anterior
        with transaction.atomic():
            if diferencia > 0:
                instance.producto.reducir_inventario(diferencia)
            elif diferencia < 0:
                # Since diferencia is negative, subtracting it will add back to the inventory
                instance.producto.cantidad_disponible -= diferencia
                instance.producto.save()

@receiver(m2m_changed, sender=VentaReserva.productos.through)
def actualizar_inventario_m2m(sender, instance, action, **kwargs):
    if action == 'post_add':
        for pk in kwargs['pk_set']:
            producto = Producto.objects.get(pk=pk)
            cantidad = ReservaProducto.objects.get(venta_reserva=instance, producto=producto).cantidad
            producto.reducir_inventario(cantidad)
    elif action == 'post_remove':  # Restaurar inventario al eliminar productos
        for pk in kwargs['pk_set']:
            producto = Producto.objects.get(pk=pk)
            cantidad = ReservaProducto.objects.filter(venta_reserva=instance, producto=producto).first().cantidad
            producto.cantidad_disponible += cantidad
            producto.save()
    elif action == 'post_clear':  # Restaurar inventario al borrar todos los productos
        for reserva_producto in ReservaProducto.objects.filter(venta_reserva=instance):
            reserva_producto.producto.cantidad_disponible += reserva_producto.cantidad
            reserva_producto.producto.save()

@receiver(pre_save, sender=ReservaProducto)
def guardar_cantidad_anterior(sender, instance, **kwargs):
    if instance.pk:
        try:
            instance._cantidad_anterior = ReservaProducto.objects.get(pk=instance.pk).cantidad
        except ReservaProducto.DoesNotExist:
            instance._cantidad_anterior = 0
    else:
        instance._cantidad_anterior = 0

@receiver(post_delete, sender=ReservaProducto)
def restaurar_inventario_al_eliminar_producto(sender, instance, **kwargs):
    with transaction.atomic():
        instance.producto.cantidad_disponible += instance.cantidad
        instance.producto.save()


logger = logging.getLogger(__name__)

@receiver(post_save, sender=DetalleCompra)
@receiver(post_delete, sender=DetalleCompra)
def update_compra_total(sender, instance, **kwargs):
    compra = instance.compra
    if compra:
        total_detalles = compra.detalles.aggregate(
            total=Sum(F('precio_unitario') * F('cantidad'), output_field=DecimalField())
        )['total'] or 0
        Compra.objects.filter(pk=compra.pk).update(total=total_detalles)
        logger.debug(f"Actualizando Compra ID {compra.pk}: Total Detalles = {total_detalles}")

@receiver(post_save, sender=Pago)
def crear_movimiento_cliente_pago(sender, instance, created, **kwargs):
    if created:
        MovimientoCliente.objects.create(
            cliente=instance.venta_reserva.cliente,
            monto=instance.monto,
            tipo_movimiento='Pago',
            comentarios=f'Pago #{instance.id} para Venta/Reserva #{instance.venta_reserva.id}',  # Cambiado de 'descripcion' a 'comentarios'
            usuario=instance.usuario
        )

@receiver(post_delete, sender=Pago)
def crear_movimiento_cliente_pago_eliminado(sender, instance, **kwargs):
    MovimientoCliente.objects.create(
        cliente=instance.venta_reserva.cliente,
        monto=-instance.monto,
        tipo_movimiento='Anulación de Pago',
        comentarios=f'Anulación de Pago #{instance.id} para Venta/Reserva #{instance.venta_reserva.id}',  # Cambiado de 'descripcion' a 'comentarios'
        usuario=get_current_user() or get_or_create_system_user()
    )