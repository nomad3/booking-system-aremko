"""
Repunte de chocolates del configurador romántico (camino seguro, jul-2026).

QUÉ HACE (idempotente, SOLO reprecia — no crea ni borra nada):
  · Reprecia el Servicio "Caja de chocolates" (con que se COBRA en el
    configurador) al precio del Producto real "Caja Chocolate" (id 42), para que
    el cliente pague el valor correcto ($16.000, no $15.000).

QUÉ NO HACE:
  · NO desactiva el servicio: en el camino seguro sigue siendo el vehículo de
    cobro. El INVENTARIO real lo mueve una comanda en la fecha de la visita
    (ventas/services/ambientacion_bebidas.py::asegurar_comanda_chocolates), que se
    dispara sola al crear la reserva con chocolates.

Uso (Shell de Render):
    python manage.py repuntar_chocolates
"""
from django.core.management.base import BaseCommand

from ventas.models import Producto, Servicio
from ventas.services.ambientacion_bebidas import (
    CHOCOLATES_ID, NOMBRE_SERVICIO_CHOCOLATES, NOMBRE_CAT_AMBIENTACION,
)

FALLBACK_PRECIO = 16000


class Command(BaseCommand):
    help = 'Reprecia el servicio de chocolates del configurador al precio del Producto real (id 42)'

    def handle(self, *args, **options):
        self.stdout.write('🍫 Repunte de chocolates — reprecio del servicio de cobro al Producto real')

        # 1) Precio objetivo = el del Producto real (fuente de verdad). Fallback defensivo.
        producto = Producto.objects.filter(id=CHOCOLATES_ID).first()
        if producto and producto.precio_base and int(producto.precio_base) > 0:
            precio_objetivo = int(producto.precio_base)
            self.stdout.write(
                f'  Producto id {CHOCOLATES_ID} "{producto.nombre}": '
                f'${precio_objetivo:,}  stock={producto.cantidad_disponible}')
        else:
            precio_objetivo = FALLBACK_PRECIO
            self.stdout.write(self.style.WARNING(
                f'  Producto id {CHOCOLATES_ID} no encontrado o sin precio; '
                f'uso fallback ${FALLBACK_PRECIO:,}'))

        # 2) Servicio de cobro (el que ve el configurador).
        servicio = Servicio.objects.filter(
            categoria__nombre__iexact=NOMBRE_CAT_AMBIENTACION,
            nombre__iexact=NOMBRE_SERVICIO_CHOCOLATES,
        ).first()
        if not servicio:
            self.stdout.write(self.style.ERROR(
                f'  Servicio "{NOMBRE_SERVICIO_CHOCOLATES}" (cat. {NOMBRE_CAT_AMBIENTACION}) '
                f'no encontrado. Nada que repreciar.'))
            return

        antes = int(servicio.precio_base)
        if antes == precio_objetivo:
            self.stdout.write(self.style.SUCCESS(
                f'  Servicio id {servicio.id} ya está en ${precio_objetivo:,}. '
                f'Sin cambios (idempotente).'))
            return

        servicio.precio_base = precio_objetivo
        servicio.save(update_fields=['precio_base'])
        self.stdout.write(self.style.SUCCESS(
            f'  Servicio id {servicio.id} "{servicio.nombre}": '
            f'${antes:,} → ${precio_objetivo:,}  ✅'))
