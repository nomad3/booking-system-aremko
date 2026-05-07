"""Servicio para materializar VentaReserva + ReservaServicio + GiftCards desde un carrito.

Reutilizado por:
- checkout_views.complete_checkout (cuando metodo_pago='transferencia')
- flow_views.flow_confirmation (cuando Flow confirma el pago)

Centraliza la logica para evitar drift entre los dos puntos de creacion.
"""
from datetime import datetime, timedelta
import traceback

from django.db import transaction
from django.db.models.signals import pre_save
from django.utils import timezone

from ..models import (
    Cliente,
    GiftCard,
    ReservaServicio,
    Servicio,
    ServicioBloqueo,
    ServicioSlotBloqueo,
    VentaReserva,
)
from ..signals import validar_disponibilidad_admin


class SlotUnavailableError(Exception):
    """Lanzada cuando un slot del carrito ya no esta disponible."""

    def __init__(self, slots):
        self.slots = slots
        super().__init__(', '.join(slots))


def validar_disponibilidad_carrito(cart_data):
    """Revisa que todos los slots del carrito sigan disponibles.

    Devuelve la lista de slots no disponibles (vacia si todo OK).
    """
    unavailable = []
    for servicio_item in cart_data.get('servicios', []):
        servicio_id = servicio_item.get('id')
        if not servicio_id:
            continue
        try:
            servicio_obj = Servicio.objects.get(id=servicio_id)
        except Servicio.DoesNotExist:
            unavailable.append(f"Servicio {servicio_id} ya no existe")
            continue

        try:
            fecha = datetime.strptime(servicio_item['fecha'], '%Y-%m-%d').date()
        except (KeyError, ValueError):
            unavailable.append(f"Fecha invalida para {servicio_obj.nombre}")
            continue

        hora = servicio_item.get('hora')

        if ServicioBloqueo.servicio_bloqueado_en_fecha(servicio_id, fecha):
            unavailable.append(
                f"{servicio_obj.nombre} no esta disponible en {fecha.strftime('%d/%m/%Y')} (fuera de servicio)"
            )
            continue

        if ServicioSlotBloqueo.slot_bloqueado(servicio_id, fecha, hora):
            unavailable.append(
                f"Slot {hora} para {servicio_obj.nombre} en {fecha.strftime('%d/%m/%Y')} no esta disponible"
            )
            continue

        if ReservaServicio.objects.filter(
            servicio=servicio_obj,
            fecha_agendamiento=fecha,
            hora_inicio=hora,
        ).exists():
            unavailable.append(f"Slot {hora} no disponible para {servicio_obj.nombre}")

    return unavailable


def _crear_cliente_destinatario(giftcard_item):
    """Crea o encuentra el Cliente destinatario de una GiftCard."""
    destinatario_telefono = giftcard_item.get('destinatario_telefono', '')
    destinatario_email = giftcard_item.get('destinatario_email', '')
    destinatario_nombre = giftcard_item.get('destinatario_nombre', 'Destinatario')

    if not destinatario_telefono and not destinatario_email:
        return None

    try:
        if destinatario_telefono:
            tel = destinatario_telefono.replace(' ', '').replace('-', '')
            if not tel.startswith('+'):
                if tel.startswith('9'):
                    tel = '+56' + tel
                elif tel.startswith('56'):
                    tel = '+' + tel
            cliente_destinatario, _created = Cliente.objects.get_or_create(
                telefono=tel,
                defaults={'nombre': destinatario_nombre, 'email': destinatario_email},
            )
            return cliente_destinatario

        if destinatario_email:
            try:
                return Cliente.objects.get(email=destinatario_email)
            except Cliente.DoesNotExist:
                return None
            except Cliente.MultipleObjectsReturned:
                return Cliente.objects.filter(email=destinatario_email).first()
    except Exception as e:
        print(f"Error creando cliente destinatario: {e}")
        traceback.print_exc()

    return None


def materializar_venta_desde_carrito(cliente, cart_data, comprador_form_data=None, revalidar=True):
    """Crea VentaReserva + ReservaServicio + GiftCards a partir del cliente y cart_data.

    Args:
        cliente: instancia de Cliente (comprador).
        cart_data: dict con keys 'servicios', 'giftcards', 'total', 'descuentos', 'total_descuentos'.
        comprador_form_data: dict opcional con datos del form (nombre, email, telefono) para snapshot en GiftCard.
        revalidar: si True (default), valida disponibilidad de slots antes de crear.

    Returns:
        VentaReserva creada.

    Raises:
        SlotUnavailableError si un slot ya no esta disponible.
    """
    if revalidar:
        unavailable = validar_disponibilidad_carrito(cart_data)
        if unavailable:
            raise SlotUnavailableError(unavailable)

    comprador_form_data = comprador_form_data or {}
    nombre = comprador_form_data.get('nombre', cliente.nombre)
    email = comprador_form_data.get('email', cliente.email or '')
    telefono = comprador_form_data.get('telefono', cliente.telefono or '')

    with transaction.atomic():
        signal_disconnected = False
        try:
            pre_save.disconnect(validar_disponibilidad_admin, sender=ReservaServicio)
            signal_disconnected = True

            venta = VentaReserva.objects.create(
                cliente=cliente,
                total=cart_data.get('total', 0),
                estado_pago='pendiente',
                estado_reserva='pendiente',
                fecha_reserva=timezone.now(),
            )

            for servicio_item in cart_data.get('servicios', []):
                servicio_id = servicio_item.get('id')
                if not servicio_id:
                    continue
                servicio_obj = Servicio.objects.get(id=servicio_id)
                fecha = datetime.strptime(servicio_item['fecha'], '%Y-%m-%d').date()
                ReservaServicio.objects.create(
                    venta_reserva=venta,
                    servicio=servicio_obj,
                    fecha_agendamiento=fecha,
                    hora_inicio=servicio_item['hora'],
                    cantidad_personas=servicio_item['cantidad_personas'],
                    precio_unitario_venta=servicio_obj.precio_base,
                )

            total_descuentos = cart_data.get('total_descuentos', 0)
            if total_descuentos and total_descuentos > 0:
                try:
                    servicio_descuento = Servicio.objects.get(
                        nombre__icontains='descuento', precio_base=-1
                    )
                    fecha_descuento = datetime.strptime(
                        cart_data['servicios'][0]['fecha'], '%Y-%m-%d'
                    ).date()
                    ReservaServicio.objects.create(
                        venta_reserva=venta,
                        servicio=servicio_descuento,
                        fecha_agendamiento=fecha_descuento,
                        hora_inicio='00:00',
                        cantidad_personas=int(total_descuentos),
                    )
                except Servicio.DoesNotExist:
                    print('Servicio de descuento no encontrado (nombre__icontains=descuento, precio_base=-1)')
                except Exception as e:
                    print(f"Error aplicando descuento pack: {e}")

            for giftcard_item in cart_data.get('giftcards', []):
                cliente_destinatario = _crear_cliente_destinatario(giftcard_item)
                fecha_vencimiento = timezone.now().date() + timedelta(days=365)
                GiftCard.objects.create(
                    monto_inicial=giftcard_item['precio'],
                    monto_disponible=giftcard_item['precio'],
                    fecha_emision=timezone.now().date(),
                    fecha_vencimiento=fecha_vencimiento,
                    estado='por_cobrar',
                    cliente_comprador=cliente,
                    cliente_destinatario=cliente_destinatario,
                    venta_reserva=venta,
                    comprador_nombre=nombre,
                    comprador_email=email,
                    comprador_telefono=telefono,
                    destinatario_nombre=giftcard_item.get('destinatario_nombre', ''),
                    destinatario_email=giftcard_item.get('destinatario_email', ''),
                    destinatario_telefono=giftcard_item.get('destinatario_telefono', ''),
                    tipo_mensaje=giftcard_item.get('tipo_mensaje', ''),
                    mensaje_personalizado=giftcard_item.get('mensaje_seleccionado', ''),
                    servicio_asociado=giftcard_item.get('experiencia_id', ''),
                )

            venta.calcular_total()
            return venta
        finally:
            if signal_disconnected:
                pre_save.connect(validar_disponibilidad_admin, sender=ReservaServicio)
