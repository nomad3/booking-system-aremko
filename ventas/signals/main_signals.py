import logging
from django.db.models.signals import post_save, post_delete, m2m_changed, pre_save, pre_delete # Added pre_delete
from django.dispatch import receiver
from django.utils import timezone
from django.db import transaction
from django.db import models
from django.db.models import Sum, F, DecimalField
# Import all relevant models, including CRM ones
from ..models import (
    VentaReserva, Cliente, ReservaProducto, ReservaServicio, Pago, MovimientoCliente,
    DetalleCompra, Compra, Producto, Servicio, Activity, Lead
)
from django.contrib.auth.models import User, AnonymousUser  # Importa el modelo de usuario
from ..middleware import get_current_user  # Importa el middleware
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from ..calendar_utils import verificar_disponibilidad  # Import the verificar_disponibilidad function

logger = logging.getLogger(__name__)

# --- CRM Signals ---

@receiver(post_save, sender=Activity)
def update_lead_status_on_activity(sender, instance, created, **kwargs):
    """
    Updates Lead status to 'Contacted' when a relevant activity is logged
    for the first time for a 'New' lead.
    """
    if created and instance.related_lead:
        try:
            lead = instance.related_lead
            # Define which activities trigger the status change
            trigger_activities = ['Call', 'Email Sent', 'Meeting']
            if lead.status == 'New' and instance.activity_type in trigger_activities:
                lead.status = 'Contacted'
                lead.save(update_fields=['status']) # Update only the status field efficiently
        except Lead.DoesNotExist:
             logger.warning(f"Lead associated with Activity {instance.pk} does not exist.")
        except Exception as e:
            logger.error(f"Error in update_lead_status_on_activity signal for Activity {instance.pk}: {e}")


# --- Existing Signals ---

# Movimientos y auditoría (Temporarily Disabled)

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

# @receiver(post_save, sender=VentaReserva) # Temporarily disabled MovimientoCliente logging
# def registrar_movimiento_venta(sender, instance, created, **kwargs):
#     """Signal for tracking VentaReserva changes in admin panel"""
#     if created:
#         try:
#             with transaction.atomic():
#                 # Get the user from the request if available, default to None if invalid
#                 user = getattr(instance, '_current_user', None)
#                 if isinstance(user, AnonymousUser): # Explicitly check for AnonymousUser
#                     user = None
#
#                 # Ensure cliente exists
#                 if instance.cliente:
#                     MovimientoCliente.objects.create(
#                         cliente=instance.cliente,
#                         tipo_movimiento='pre_reserva',
#                         usuario=user, # Allow None if user context is lost
#                         fecha_movimiento=timezone.now(),
#                         comentarios=f"Pre-reserva automática - {instance.comentarios or ''}",
#                         venta_reserva=instance
#                     )
#         except Exception as e:
#             logger.error(f"Error in registrar_movimiento_venta signal for VentaReserva {instance.pk}: {e}")

# @receiver(pre_delete, sender=VentaReserva) # Temporarily disabled MovimientoCliente logging
# def registrar_movimiento_eliminacion_venta(sender, instance, **kwargs):
#     usuario = get_current_user()
#     # Ensure we always have a user, defaulting to system user
#     if not usuario or isinstance(usuario, AnonymousUser):
#         usuario = get_or_create_system_user()
#
#     # Check if cliente still exists before creating movement
#     # Accessing instance.cliente might fail if it was deleted cascade
#     try:
#         cliente_nombre = instance.cliente.nombre if instance.cliente else "Cliente Desconocido"
#         cliente_obj = instance.cliente # Keep the object if it exists
#     except ObjectDoesNotExist:
#         cliente_nombre = "Cliente Eliminado"
#         cliente_obj = None # Cannot link movement if client is gone
#
#     comentarios = f"Se ha eliminado la venta/reserva con ID {instance.id} del cliente {cliente_nombre}."
#
#     if cliente_obj: # Only create if we have a valid client reference
#         try:
#             MovimientoCliente.objects.create(
#                 cliente=cliente_obj,
#                 tipo_movimiento='Eliminación de Venta/Reserva',
#                 comentarios=comentarios,
#                 usuario=None, # Set user to None for deletion logs
#                 fecha_movimiento=timezone.now()
#             )
#         except Exception as e:
#             logger.error(f"Error creating movement log for deleting VentaReserva {instance.pk}: {e}") # Adjusted log message

# Clientes

# @receiver(post_save, sender=Cliente) # Temporarily disabled MovimientoCliente logging
# def registrar_movimiento_cliente(sender, instance, created, **kwargs):
#     """Signal for tracking Cliente changes in admin panel"""
#     if created:
#         try:
#             with transaction.atomic():
#                 # Get the user from the request if available, default to None if invalid
#                 user = getattr(instance, '_current_user', None)
#                 if isinstance(user, AnonymousUser):
#                     user = None
#
#                 MovimientoCliente.objects.create(
#                     cliente=instance,
#                     tipo_movimiento='creacion',
#                     usuario=user, # Allow None
#                     fecha_movimiento=timezone.now(),
#                     comentarios='Cliente creado automáticamente'
#                 )
#         except Exception as e:
#             logger.error(f"Error in registrar_movimiento_cliente signal for Cliente {instance.pk}: {e}")

# @receiver(pre_delete, sender=Cliente) # Temporarily disabled MovimientoCliente logging
# def registrar_movimiento_eliminacion_cliente(sender, instance, **kwargs):
#     # Logging before deletion is generally safer for audit trails.
#     usuario = get_current_user()
#     if not usuario or isinstance(usuario, AnonymousUser):
#         usuario = get_or_create_system_user()
#
#     descripcion = f"Se va a eliminar el cliente: {instance.nombre} (ID: {instance.pk})." # Adjusted message
#
#     # Create the log before the client is actually deleted
#     try:
#         MovimientoCliente.objects.create(
#             cliente=instance, # Instance still exists here
#             tipo_movimiento='Eliminación de Cliente',
#             comentarios=descripcion,
#             usuario=None, # Set user to None for deletion logs
#             fecha_movimiento=timezone.now()
#         )
#     except Exception as e:
#          logger.error(f"Failed to log pre-deletion movement for Cliente {instance.pk}: {e}")


# Productos

# @receiver(post_save, sender=ReservaProducto) # Temporarily disabled MovimientoCliente logging
# def registrar_movimiento_reserva_producto(sender, instance, created, **kwargs):
#     # Default to None if user context is unreliable
#     usuario = get_current_user()
#     if not usuario or isinstance(usuario, AnonymousUser):
#         usuario = None
#
#     try:
#         # Ensure related objects exist
#         venta_reserva = instance.venta_reserva
#         producto = instance.producto
#         cliente = venta_reserva.cliente
#
#         if cliente and producto:
#             tipo = 'Añadido Producto a Venta/Reserva' if created else 'Actualización de Producto en Venta/Reserva'
#             descripcion = f"Se ha {'añadido' if created else 'actualizado'} {instance.cantidad} x {producto.nombre} en la venta/reserva #{venta_reserva.id}."
#
#             MovimientoCliente.objects.create(
#                 cliente=cliente,
#                 tipo_movimiento=tipo,
#                 comentarios=descripcion,
#                 usuario=usuario,
#                 fecha_movimiento=timezone.now()
#             )
#     except ObjectDoesNotExist:
#         logger.warning(f"Could not log movement for ReservaProducto {instance.pk} due to missing related object (VentaReserva, Producto, or Cliente).")
#     except Exception as e:
#         logger.error(f"Error in registrar_movimiento_reserva_producto signal for ReservaProducto {instance.pk}: {e}")


# @receiver(pre_delete, sender=ReservaProducto) # Temporarily disabled MovimientoCliente logging
# def registrar_movimiento_eliminacion_producto(sender, instance, **kwargs):
#     usuario = get_current_user()
#     if not usuario or isinstance(usuario, AnonymousUser):
#         usuario = get_or_create_system_user()
#
#     try:
#         # Access related objects carefully, they might be gone soon
#         venta_reserva_id = instance.venta_reserva_id
#         producto_nombre = instance.producto.nombre if hasattr(instance, 'producto') and instance.producto else "Producto Desconocido"
#         cliente = instance.venta_reserva.cliente if hasattr(instance, 'venta_reserva') and instance.venta_reserva and hasattr(instance.venta_reserva, 'cliente') and instance.venta_reserva.cliente else None
#
#         if cliente:
#             descripcion = f"Se va a eliminar {instance.cantidad} x {producto_nombre} de la venta/reserva #{venta_reserva_id}." # Adjusted message
#             MovimientoCliente.objects.create(
#                 cliente=cliente,
#                 tipo_movimiento='Eliminación de Producto en Venta/Reserva',
#                 comentarios=descripcion,
#                 usuario=None, # Set user to None for deletion logs
#                 fecha_movimiento=timezone.now()
#             )
#     except ObjectDoesNotExist:
#          logger.warning(f"Could not log pre-deletion movement for ReservaProducto {instance.pk} due to missing related object.")
#     except Exception as e:
#         logger.error(f"Error logging pre-deletion movement for ReservaProducto {instance.pk}: {e}") # Adjusted log message


# Servicios

# @receiver(post_save, sender=ReservaServicio) # Temporarily disabled MovimientoCliente logging
# def registrar_movimiento_reserva_servicio(sender, instance, created, **kwargs):
#     if created:
#         # Default to None if user context is unreliable
#         user = getattr(instance, '_current_user', None)
#         if not user:
#             user = get_current_user()
#         if not user or isinstance(user, AnonymousUser):
#             user = None # Default to None
#
#         try:
#             # Ensure related objects exist
#             venta_reserva = instance.venta_reserva
#             servicio = instance.servicio
#             cliente = venta_reserva.cliente
#
#             if cliente and servicio:
#                 MovimientoCliente.objects.create(
#                     cliente=cliente,
#                     tipo_movimiento='Reserva de Servicio',
#                     comentarios=f'Se ha reservado el servicio {servicio.nombre}',
#                     usuario=user,
#                     venta_reserva=venta_reserva
#                 )
#         except ObjectDoesNotExist:
#             logger.warning(f"Could not log movement for ReservaServicio {instance.pk} due to missing related object (VentaReserva, Servicio, or Cliente).")
#         except Exception as e:
#             logger.error(f"Error in registrar_movimiento_reserva_servicio signal for ReservaServicio {instance.pk}: {e}")


# @receiver(pre_delete, sender=ReservaServicio) # Temporarily disabled MovimientoCliente logging
# def registrar_movimiento_eliminacion_servicio(sender, instance, **kwargs):
#     usuario = get_current_user()
#     if not usuario or isinstance(usuario, AnonymousUser):
#         usuario = get_or_create_system_user()
#
#     try:
#         venta_reserva_id = instance.venta_reserva_id
#         servicio_nombre = instance.servicio.nombre if hasattr(instance, 'servicio') and instance.servicio else "Servicio Desconocido"
#         cliente = instance.venta_reserva.cliente if hasattr(instance, 'venta_reserva') and instance.venta_reserva and hasattr(instance.venta_reserva, 'cliente') and instance.venta_reserva.cliente else None
#
#         if cliente:
#             descripcion = f"Se va a eliminar la reserva del servicio {servicio_nombre} de la venta/reserva #{venta_reserva_id}." # Adjusted message
#             MovimientoCliente.objects.create(
#                 cliente=cliente,
#                 tipo_movimiento='Eliminación de Servicio en Venta/Reserva',
#                 comentarios=descripcion,
#                 usuario=None, # Set user to None for deletion logs
#                 fecha_movimiento=timezone.now()
#             )
#     except ObjectDoesNotExist:
#         logger.warning(f"Could not log pre-deletion movement for ReservaServicio {instance.pk} due to missing related object.")
#     except Exception as e:
#         logger.error(f"Error logging pre-deletion movement for ReservaServicio {instance.pk}: {e}") # Adjusted log message


# Pagos

# @receiver(post_save, sender=Pago) # Temporarily disabled MovimientoCliente logging
# def registrar_movimiento_pago(sender, instance, created, **kwargs):
#     if created:
#         try:
#             # User should be set by pre_save signal 'set_pago_user'
#             user = instance.usuario
#             # Add fallback just in case pre_save failed or user became invalid
#             if not user:
#                  current_ctx_user = get_current_user()
#                  if not current_ctx_user or isinstance(current_ctx_user, AnonymousUser):
#                      user = None # Default to None if context is unreliable
#                  else:
#                      user = current_ctx_user # Use context user if valid
#
#             # Ensure related objects exist
#             venta_reserva = instance.venta_reserva
#             cliente = venta_reserva.cliente
#
#             if cliente: # Check if cliente exists
#                 MovimientoCliente.objects.create(
#                     cliente=cliente,
#                     tipo_movimiento='pago',
#                     usuario=user, # Use user from instance
#                     fecha_movimiento=timezone.now(),
#                     comentarios=f'Pago registrado - {instance.metodo_pago} - ${instance.monto}',
#                     venta_reserva=venta_reserva
#                 )
#         except ObjectDoesNotExist:
#              logger.warning(f"Could not log movement for Pago {instance.pk} due to missing related VentaReserva or Cliente.")
#         except Exception as e:
#             logger.error(f"Error in registrar_movimiento_pago signal for Pago {instance.pk}: {e}")

# @receiver(pre_delete, sender=Pago) # Temporarily disabled MovimientoCliente logging
# def registrar_movimiento_eliminacion_pago(sender, instance, **kwargs):
#     usuario = get_current_user()
#     if not usuario or isinstance(usuario, AnonymousUser):
#         usuario = get_or_create_system_user()
#
#     try:
#         # Check if related objects still exist
#         venta_reserva = instance.venta_reserva
#         cliente = venta_reserva.cliente if venta_reserva else None
#
#         if cliente: # Only log if client exists
#             descripcion = f"Se va a eliminar el pago de {instance.monto} de la venta/reserva #{venta_reserva.id}." # Adjusted message
#             MovimientoCliente.objects.create(
#                 cliente=cliente,
#                 tipo_movimiento='Eliminación de Pago',
#                 comentarios=descripcion,
#                 usuario=None, # Set user to None for deletion logs
#                 fecha_movimiento=timezone.now()
#             )
#
#         # Update balance if venta_reserva still exists
#         # This logic is potentially problematic in pre_delete as the state might change.
#         # Consider if balance update should happen elsewhere or be triggered differently.
#         # If kept, ensure it doesn't rely on the Pago instance existing after this signal.
#         # if venta_reserva:
#         #     try:
#         #         # Re-fetch to be safe? Or trust instance?
#         #         venta_reserva_obj = VentaReserva.objects.get(pk=venta_reserva.pk)
#         #         # How to reliably subtract the amount being deleted?
#         #         # Maybe VentaReserva.calcular_total() should be robust enough?
#         #         # Let's rely on calcular_total being called elsewhere after deletion.
#         #         pass # Removing direct balance manipulation from pre_delete
#         #     except VentaReserva.DoesNotExist:
#         #         logger.warning(f"VentaReserva {venta_reserva.pk} not found when attempting balance update during Pago {instance.pk} pre_delete.")
#         #     except Exception as e:
#         #          logger.error(f"Error attempting balance update during Pago {instance.pk} pre_delete: {e}")
#
#     except ObjectDoesNotExist:
#         logger.warning(f"Could not log pre-deletion movement for Pago {instance.pk} due to missing related VentaReserva or Cliente.")
#     except Exception as e:
#         logger.error(f"Error in registrar_movimiento_eliminacion_pago (pre_delete) signal for Pago {instance.pk}: {e}")

# @receiver(post_save, sender=Pago) # Temporarily disabled MovimientoCliente logging (Redundant with registrar_movimiento_pago)
# def crear_movimiento_cliente_pago(sender, instance, created, **kwargs):
#     if created:
#         MovimientoCliente.objects.create(
#             cliente=instance.venta_reserva.cliente,
#             tipo_movimiento='Pago',
#             comentarios=f'Pago #{instance.id} para Venta/Reserva #{instance.venta_reserva.id} - Monto: ${instance.monto}',
#             usuario=instance.usuario, # User should be set by pre_save signal
#             venta_reserva=instance.venta_reserva
#         )

# @receiver(post_delete, sender=Pago) # Temporarily disabled MovimientoCliente logging (Redundant with registrar_movimiento_eliminacion_pago)
# def crear_movimiento_cliente_pago_eliminado(sender, instance, **kwargs):
#     usuario = get_current_user()
#     # Ensure we always have a user, defaulting to system user
#     if not usuario or isinstance(usuario, AnonymousUser):
#         usuario = get_or_create_system_user()
#
#     # Check if related objects still exist
#     if hasattr(instance, 'venta_reserva') and instance.venta_reserva and instance.venta_reserva.cliente:
#         MovimientoCliente.objects.create(
#             cliente=instance.venta_reserva.cliente,
#             tipo_movimiento='Anulación de Pago',
#             comentarios=f'Anulación de Pago #{instance.id} para Venta/Reserva #{instance.venta_reserva.id} - Monto: ${instance.monto}',
#             usuario=usuario,
#             venta_reserva=instance.venta_reserva
#         )


# Signals for updating totals (Keep these active)

# Using pre_delete for total updates might be more reliable than post_delete
@receiver(post_delete, sender=ReservaProducto)
def actualizar_total_despues_eliminar_producto(sender, instance, **kwargs):
    try:
        # Guardar referencia a venta_reserva antes de que pueda perderse
        venta_reserva = instance.venta_reserva
        if venta_reserva:
            # Calcular total DESPUÉS de que el producto fue eliminado
            venta_reserva.calcular_total()
    except ObjectDoesNotExist:
        logger.warning(f"VentaReserva not found when updating total after ReservaProducto {instance.pk} deletion.")
    except Exception as e:
            logger.error(f"Error updating total after ReservaProducto {instance.pk} deletion: {e}")

@receiver(post_delete, sender=ReservaServicio) # Keep this signal for total updates
def actualizar_total_despues_eliminar_servicio(sender, instance, **kwargs):
    try:
        # Guardar referencia a venta_reserva antes de que pueda perderse
        venta_reserva = instance.venta_reserva
        if venta_reserva:
            # Calcular total DESPUÉS de que el servicio fue eliminado
            venta_reserva.calcular_total()
    except ObjectDoesNotExist:
        logger.warning(f"VentaReserva not found when updating total after ReservaServicio {instance.pk} deletion.")
    except Exception as e:
            logger.error(f"Error updating total after ReservaServicio {instance.pk} deletion: {e}")

# post_save for adding/updating items should still trigger total calculation
@receiver(post_save, sender=ReservaServicio) # Keep this signal for total updates
def actualizar_total_al_guardar_servicio(sender, instance, created, raw, using, update_fields, **kwargs):
    try:
        if instance.venta_reserva and not raw: # Avoid recalculating during fixture loading
             instance.venta_reserva.calcular_total()
    except ObjectDoesNotExist:
        logger.warning(f"VentaReserva not found when updating total after ReservaServicio {instance.pk} save.")
    except Exception as e:
            logger.error(f"Error updating total after ReservaServicio {instance.pk} save: {e}")

@receiver(post_save, sender=ReservaProducto) # Keep this signal for total updates
def actualizar_total_al_guardar_producto(sender, instance, created, raw, using, update_fields, **kwargs):
    try:
        if instance.venta_reserva and not raw: # Avoid recalculating during fixture loading
             instance.venta_reserva.calcular_total()
    except ObjectDoesNotExist:
        logger.warning(f"VentaReserva not found when updating total after ReservaProducto {instance.pk} save.")
    except Exception as e:
        logger.error(f"Error updating total after ReservaProducto {instance.pk} save: {e}")


# Inventory Update Signals (Keep these active)

@receiver(post_save, sender=ReservaProducto) # Keep this signal for inventory updates
def actualizar_inventario(sender, instance, created, **kwargs):
    try:
        producto = instance.producto
        if producto:
            if created:
                with transaction.atomic():
                    producto.reducir_inventario(instance.cantidad)
            else:
                cantidad_anterior = getattr(instance, '_cantidad_anterior', 0)
                diferencia = instance.cantidad - cantidad_anterior
                if diferencia != 0:
                    with transaction.atomic():
                        # Re-fetch product inside transaction for safety
                        prod_atomic = Producto.objects.select_for_update().get(pk=producto.pk)
                        if diferencia > 0:
                            prod_atomic.reducir_inventario(diferencia)
                        else:
                            prod_atomic.incrementar_inventario(-diferencia)
    except ObjectDoesNotExist:
        logger.warning(f"Producto not found when updating inventory for ReservaProducto {instance.pk}.")
    except Exception as e:
        logger.error(f"Error updating inventory in actualizar_inventario signal for ReservaProducto {instance.pk}: {e}")

# Keep m2m disabled for now due to complexity/potential issues
# @receiver(m2m_changed, sender=VentaReserva.productos.through) # Keep commented out
# def actualizar_inventario_m2m(sender, instance, action, pk_set, **kwargs):
#     pass

@receiver(pre_save, sender=ReservaProducto) # Keep this signal for inventory updates
def guardar_cantidad_anterior(sender, instance, **kwargs):
    if instance.pk:
        try:
            instance._cantidad_anterior = ReservaProducto.objects.get(pk=instance.pk).cantidad
        except ReservaProducto.DoesNotExist:
            instance._cantidad_anterior = 0
    else:
        instance._cantidad_anterior = 0

@receiver(pre_save, sender=ReservaProducto)
def congelar_precio_producto(sender, instance, **kwargs):
    """
    Congela el precio del producto al momento de agregarlo a la reserva.
    Si es un nuevo producto (no tiene pk) y no tiene precio_unitario_venta,
    copia el precio_base actual del producto.
    """
    # Solo congelar precio si es nuevo y no tiene precio ya asignado
    if not instance.pk and not instance.precio_unitario_venta:
        if instance.producto:
            instance.precio_unitario_venta = instance.producto.precio_base
            logger.debug(f"Precio congelado para ReservaProducto: ${instance.precio_unitario_venta}")

@receiver(pre_save, sender=ReservaServicio)
def congelar_precio_servicio(sender, instance, **kwargs):
    """
    Congela el precio del servicio al momento de agregarlo a la reserva.
    Si es un nuevo servicio (no tiene pk) y no tiene precio_unitario_venta,
    copia el precio_base actual del servicio.
    """
    # Solo congelar precio si es nuevo y no tiene precio ya asignado
    if not instance.pk and not instance.precio_unitario_venta:
        if instance.servicio:
            instance.precio_unitario_venta = instance.servicio.precio_base
            logger.debug(f"Precio congelado para ReservaServicio: ${instance.precio_unitario_venta}")

@receiver(post_delete, sender=ReservaProducto) # Keep this signal for inventory updates
def restaurar_inventario_al_eliminar_producto(sender, instance, **kwargs):
    try:
        producto = instance.producto
        if producto:
            with transaction.atomic():
                # Re-fetch product to be safe and lock
                producto_obj = Producto.objects.select_for_update().get(pk=producto.pk)
                producto_obj.incrementar_inventario(instance.cantidad)
    except ObjectDoesNotExist:
        logger.warning(f"Producto not found when restoring inventory for deleted ReservaProducto {instance.pk}.")
    except Exception as e:
        logger.error(f"Error restoring inventory for deleted ReservaProducto {instance.pk}: {e}")


# Compra/DetalleCompra Signals (Keep these active)

@receiver(post_save, sender=DetalleCompra)
@receiver(post_delete, sender=DetalleCompra)
def update_compra_total(sender, instance, **kwargs):
    try:
        compra = instance.compra
        if compra:
            total_detalles = compra.detalles.aggregate(
                total=Sum(F('precio_unitario') * F('cantidad'), output_field=DecimalField())
            )['total'] or 0
            Compra.objects.filter(pk=compra.pk).update(total=total_detalles)
            logger.debug(f"Actualizando Compra ID {compra.pk}: Total Detalles = {total_detalles}")
    except ObjectDoesNotExist:
         logger.warning(f"Compra not found when updating total after DetalleCompra {instance.pk} change.")
    except Exception as e:
        logger.error(f"Error updating Compra total after DetalleCompra {instance.pk} change: {e}")


# Pago User Signal (Keep this active)

@receiver(pre_save, sender=Pago)
def set_pago_user(sender, instance, **kwargs):
    # Only set user if it's a new instance and user is not already set
    if not instance.pk and not instance.usuario:
        usuario = get_current_user()
        # Ensure we always have a user, defaulting to system user
        if not usuario or isinstance(usuario, AnonymousUser):
            usuario = get_or_create_system_user()
        instance.usuario = usuario

# Availability Signal (Keep this active)

@receiver(pre_save, sender=ReservaServicio)
def validar_disponibilidad_admin(sender, instance, **kwargs):
    # Check if servicio exists before accessing attributes
    if hasattr(instance, 'servicio') and instance.servicio:
        try:
            # Pass the instance itself to verificar_disponibilidad to exclude it from checks if it exists
            if not verificar_disponibilidad(
                servicio=instance.servicio,
                fecha_propuesta=instance.fecha_agendamiento,
                hora_propuesta=instance.hora_inicio,
                cantidad_personas=instance.cantidad_personas,
                reserva_actual=instance, # Pass the current instance to exclude itself
                proveedor_asignado=instance.proveedor_asignado # Pass the provider being assigned
            ):
                # Customize error message if provider is the issue
                error_msg = f"Slot {instance.hora_inicio} no disponible para {instance.servicio.nombre}"
                if instance.servicio.tipo_servicio == 'masaje' and instance.proveedor_asignado:
                    error_msg += f" con el proveedor {instance.proveedor_asignado.nombre}"
                raise ValidationError(error_msg)
        except ObjectDoesNotExist:
             logger.warning(f"Related object (Servicio?) missing during availability check for ReservaServicio {instance.pk}.")
             # raise ValidationError("Servicio relacionado no encontrado.") # Optionally raise error
        except Exception as e:
             logger.error(f"Error during availability check for ReservaServicio {instance.pk}: {e}")
             # raise ValidationError("Error inesperado al verificar disponibilidad.") # Optionally raise error


# --- Premio/Tramo Signals ---

@receiver(post_save, sender=VentaReserva)
def actualizar_tramo_y_premios_on_pago(sender, instance, created, raw, using, update_fields, **kwargs):
    """
    Signal que detecta cuando una VentaReserva es pagada y actualiza el tramo del cliente.
    Genera premios automáticamente solo para hitos (tramos 5, 10, 15, 20).

    NOTA: El premio de bienvenida ahora se genera con delay de 3 días después del check-in
    mediante el comando: python manage.py procesar_premios_bienvenida
    """
    # Skip if fixture loading
    if raw:
        return

    # Solo procesar si está pagado o parcialmente pagado
    if instance.estado_pago not in ['pagado', 'parcial']:
        return

    # Asegurar que tiene cliente
    if not instance.cliente:
        return

    try:
        from ventas.services.tramo_service import TramoService

        with transaction.atomic():
            # Actualizar tramo del cliente SOLO para registro, SIN generar premios
            # Los premios (tanto de bienvenida como de hito) se generan 3 días después del check-in
            resultado = TramoService.actualizar_tramo_cliente(instance.cliente, generar_premio_inmediato=False)

            logger.info(
                f"Tramo actualizado para cliente {instance.cliente.id}: "
                f"Tramo {resultado['tramo_anterior']} → {resultado['tramo_actual']}, "
                f"Gasto: ${resultado['gasto_total']:,.0f}"
            )

            # PREMIOS DESACTIVADOS AQUÍ (tanto de bienvenida como de hito)
            # TODOS los premios se generan mediante comando de gestión 3 días después del check-in
            # Ver: python manage.py procesar_premios_bienvenida

            if resultado.get('hito_alcanzado'):
                logger.info(
                    f"¡Hito alcanzado! Cliente {instance.cliente.id} llegó al Tramo {resultado['tramo_actual']}. "
                    f"Premio se generará automáticamente 3 días después del check-in."
                )

    except Exception as e:
        # Log error but don't break the sale process
        logger.error(
            f"Error actualizando tramo/premios para VentaReserva {instance.id}, "
            f"Cliente {instance.cliente.id}: {e}",
            exc_info=True
        )

# ----------------------------------------------------------------------
# Signal to keep NewsletterSubscriber in sync with Cliente email changes
# ----------------------------------------------------------------------

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

@receiver(pre_save, sender='ventas.Cliente')
def cache_previous_email(sender, instance, **kwargs):
    """Store the previous email before the Cliente is saved so we can detect removals."""
    if not instance.pk:
        instance._old_email = None
        return
    try:
        old = sender.objects.get(pk=instance.pk)
        instance._old_email = (old.email or '').strip().lower()
    except sender.DoesNotExist:
        instance._old_email = None

@receiver(post_save, sender='ventas.Cliente')
def sync_newsletter_subscriber(sender, instance, created, **kwargs):
    """Create or update a NewsletterSubscriber when a Cliente is saved.

    - If the Cliente has a non‑empty email, ensure a subscriber exists and is active.
    - If the email is cleared, deactivate the existing subscriber (if any).
    """
    # Lazy import to avoid circular imports
    try:
        from ..models import NewsletterSubscriber
    except Exception as e:
        logger.error(f"Unable to import NewsletterSubscriber: {e}")
        return

    current_email = (instance.email or '').strip().lower()

    # Email removed → deactivate previous subscriber
    if not current_email:
        old_email = getattr(instance, "_old_email", None)
        if old_email:
            try:
                sub = NewsletterSubscriber.objects.filter(email=old_email).first()
                if sub and sub.is_active:
                    sub.is_active = False
                    sub.save()
                    logger.info(
                        f"Desactivado NewsletterSubscriber {old_email} porque Cliente {instance.pk} quitó su email."
                    )
            except Exception as e:
                logger.error(f"Error desactivando suscriptor {old_email}: {e}")
        return

    # Email present → create or reactivate subscriber
    try:
        nombre_completo = (instance.nombre or '').strip()
        parts = nombre_completo.split(' ', 1)
        first_name_val = parts[0]
        last_name_val = parts[1] if len(parts) > 1 else ''

        subscriber, created_sub = NewsletterSubscriber.objects.get_or_create(
            email=current_email,
            defaults={
                "first_name": first_name_val,
                "last_name": last_name_val,
                "subscribed_at": timezone.now(),
                "source": "Sync via signal (Cliente saved)",
            },
        )
        if not subscriber.is_active:
            subscriber.is_active = True
            subscriber.save()
            logger.info(
                f"Reactivado NewsletterSubscriber {current_email} por actualización de Cliente {instance.pk}."
            )
    except Exception as e:
        logger.error(f"Error creando/actualizando suscriptor {current_email}: {e}")
