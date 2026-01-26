"""
Comando para diagnosticar por qué una reserva no tiene descuentos aplicados
y opcionalmente aplicarlos.

Uso:
    python manage.py diagnosticar_descuentos_reserva <reserva_id>
    python manage.py diagnosticar_descuentos_reserva <reserva_id> --aplicar
"""

from django.core.management.base import BaseCommand
from ventas.models import VentaReserva, Pago, PackDescuento, Servicio
from ventas.services.pack_descuento_service import PackDescuentoService
from datetime import datetime


class Command(BaseCommand):
    help = 'Diagnostica por qué una reserva no tiene descuentos y permite aplicarlos'

    def add_arguments(self, parser):
        parser.add_argument('reserva_id', type=int, help='ID de la reserva a diagnosticar')
        parser.add_argument(
            '--aplicar',
            action='store_true',
            help='Aplicar el descuento automáticamente si califica'
        )

    def handle(self, *args, **options):
        reserva_id = options['reserva_id']
        aplicar_descuento = options['aplicar']

        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(f"🔍 DIAGNÓSTICO DE DESCUENTOS - Reserva #{reserva_id}")
        self.stdout.write("=" * 80 + "\n")

        try:
            reserva = VentaReserva.objects.get(id=reserva_id)
        except VentaReserva.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"❌ Reserva #{reserva_id} no encontrada"))
            return

        # Información básica de la reserva
        self.stdout.write(f"Cliente: {reserva.cliente.nombre}")
        self.stdout.write(f"Estado: {reserva.estado_reserva}")
        self.stdout.write(f"Fecha creación: {reserva.fecha_reserva.strftime('%d/%m/%Y %H:%M')}")
        self.stdout.write(f"Total actual: ${reserva.total:,.0f}\n")

        # Listar servicios
        servicios_reserva = reserva.reservaservicios.all().select_related('servicio')

        self.stdout.write("📋 SERVICIOS EN LA RESERVA:")
        self.stdout.write("-" * 80)

        total_servicios = 0
        for rs in servicios_reserva:
            # Skip si es el servicio de descuento
            if 'descuento' in rs.servicio.nombre.lower() and rs.servicio.precio_base == -1:
                descuento_actual = rs.cantidad_personas
                self.stdout.write(self.style.WARNING(
                    f"  [DESCUENTO APLICADO] ${descuento_actual:,.0f}"
                ))
                continue

            precio = rs.precio_unitario_venta or rs.servicio.precio_base
            personas = rs.cantidad_personas or 1
            subtotal = precio * personas

            total_servicios += subtotal

            self.stdout.write(
                f"  • {rs.servicio.nombre} ({rs.servicio.tipo_servicio})\n"
                f"    Fecha: {rs.fecha_agendamiento.strftime('%d/%m/%Y')} - {rs.hora_inicio} hrs\n"
                f"    Personas: {personas}\n"
                f"    Precio unitario: ${precio:,.0f}\n"
                f"    Subtotal: ${subtotal:,.0f}"
            )

        self.stdout.write(f"\nTOTAL SERVICIOS: ${total_servicios:,.0f}\n")

        # Verificar descuentos ya aplicados
        descuentos_existentes = reserva.pagos.filter(metodo_pago='descuento')
        total_descuentos_existentes = sum(d.monto for d in descuentos_existentes)

        if total_descuentos_existentes > 0:
            self.stdout.write(self.style.WARNING(
                f"⚠️ Ya tiene descuentos aplicados: ${total_descuentos_existentes:,.0f}"
            ))
            for desc in descuentos_existentes:
                self.stdout.write(f"  - ${desc.monto:,.0f} ({desc.fecha_pago})")
            self.stdout.write("")

        # Convertir reserva a formato de carrito para verificar packs
        cart_items = []
        for rs in servicios_reserva:
            # Skip servicios de descuento
            if 'descuento' in rs.servicio.nombre.lower() and rs.servicio.precio_base == -1:
                continue

            cart_items.append({
                'id': rs.servicio.id,
                'nombre': rs.servicio.nombre,
                'precio': float(rs.precio_unitario_venta or rs.servicio.precio_base),
                'fecha': rs.fecha_agendamiento.strftime('%Y-%m-%d'),
                'hora': rs.hora_inicio or '00:00',
                'cantidad_personas': rs.cantidad_personas or 1,
                'tipo_servicio': rs.servicio.tipo_servicio,
                'subtotal': float((rs.precio_unitario_venta or rs.servicio.precio_base) * (rs.cantidad_personas or 1))
            })

        self.stdout.write("🎁 ANALIZANDO PACKS DE DESCUENTO APLICABLES:")
        self.stdout.write("-" * 80)

        # Detectar packs aplicables
        packs_aplicables = PackDescuentoService.detectar_packs_aplicables(cart_items)

        if not packs_aplicables:
            self.stdout.write(self.style.SUCCESS("✅ No hay packs de descuento aplicables para esta reserva"))
            self.stdout.write("\nPosibles razones:")
            self.stdout.write("  - No cumple con las condiciones de ningún pack activo")
            self.stdout.write("  - Los servicios no están en las fechas/días válidos del pack")
            self.stdout.write("  - No alcanza el número mínimo de personas/servicios requeridos")
            return

        # Mostrar packs aplicables
        total_descuento_disponible = 0
        for pack_info in packs_aplicables:
            pack = pack_info['pack']
            descuento = pack_info['descuento']
            total_descuento_disponible += descuento

            self.stdout.write(self.style.SUCCESS(
                f"\n✅ PACK APLICABLE: {pack.nombre}"
            ))
            self.stdout.write(f"   Descuento: ${descuento:,.0f}")
            self.stdout.write(f"   Descripción: {pack.descripcion}")
            if pack_info.get('descripcion_aplicacion'):
                self.stdout.write(f"   {pack_info['descripcion_aplicacion']}")

        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(f"💰 RESUMEN FINAL:")
        self.stdout.write(f"   Subtotal servicios: ${total_servicios:,.0f}")
        if total_descuentos_existentes > 0:
            self.stdout.write(f"   Descuentos ya aplicados: -${total_descuentos_existentes:,.0f}")
        self.stdout.write(f"   Descuentos disponibles: -${total_descuento_disponible:,.0f}")
        total_final = total_servicios - total_descuento_disponible
        self.stdout.write(f"   TOTAL FINAL: ${total_final:,.0f}")
        self.stdout.write("=" * 80 + "\n")

        # Aplicar descuento si se solicitó
        if aplicar_descuento:
            if total_descuentos_existentes > 0:
                self.stdout.write(self.style.WARNING(
                    "⚠️ No se aplicó el descuento porque ya tiene descuentos registrados."
                ))
                self.stdout.write("   Elimínelos primero si desea aplicar el nuevo descuento.\n")
                return

            self.stdout.write(self.style.SUCCESS("🚀 APLICANDO DESCUENTO..."))

            # Crear registro de Pago con el descuento
            from django.utils import timezone

            pago_descuento = Pago.objects.create(
                venta_reserva=reserva,
                metodo_pago='descuento',
                monto=total_descuento_disponible,
                fecha_pago=timezone.now()
            )

            self.stdout.write(self.style.SUCCESS(
                f"✅ Descuento de ${total_descuento_disponible:,.0f} aplicado correctamente"
            ))

            # Recalcular total de la reserva
            reserva.calcular_total()
            reserva.save()

            self.stdout.write(f"✅ Total de reserva actualizado: ${reserva.total:,.0f}\n")

        else:
            self.stdout.write(self.style.WARNING(
                "ℹ️ Para aplicar el descuento, ejecute:\n"
                f"   python manage.py diagnosticar_descuentos_reserva {reserva_id} --aplicar\n"
            ))
