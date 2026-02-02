"""
Comando de Django para diagnosticar la agenda operativa
Uso: python manage.py diagnose_agenda [reserva_id]
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, timedelta
from ventas.models import VentaReserva, ReservaServicio, ReservaProducto


class Command(BaseCommand):
    help = 'Diagnostica problemas con la agenda operativa'

    def add_arguments(self, parser):
        parser.add_argument(
            'reserva_id',
            nargs='?',
            type=int,
            help='ID de reserva específica para analizar'
        )

    def handle(self, *args, **options):
        self.stdout.write("\n" + "="*60)
        self.stdout.write(self.style.SUCCESS("DIAGNÓSTICO DE AGENDA OPERATIVA"))
        self.stdout.write("="*60)

        # Obtener hora actual
        ahora = timezone.localtime(timezone.now())
        hoy = ahora.date()
        hora_actual = ahora.time()

        self.stdout.write(f"\n📅 Fecha HOY: {hoy.strftime('%d/%m/%Y')}")
        self.stdout.write(f"⏰ Hora actual (Chile): {hora_actual.strftime('%H:%M:%S')}")
        self.stdout.write("-" * 60)

        # 1. Buscar servicios de hoy
        self.stdout.write("\n1️⃣ SERVICIOS DE HOY (no cancelados, no descuentos):")
        self.stdout.write("-" * 40)

        servicios_hoy = ReservaServicio.objects.filter(
            fecha_agendamiento=hoy,
            venta_reserva__isnull=False
        ).exclude(
            venta_reserva__estado_reserva='cancelada'
        ).exclude(
            servicio__nombre__icontains='descuento'
        ).select_related('servicio', 'venta_reserva__cliente').order_by('hora_inicio')

        self.stdout.write(f"Total servicios encontrados: {servicios_hoy.count()}")

        if servicios_hoy.count() == 0:
            self.stdout.write(self.style.ERROR("❌ No hay servicios para hoy"))
            return

        # 2. Mostrar servicios pendientes o en curso
        self.stdout.write("\n2️⃣ SERVICIOS PENDIENTES O EN CURSO:")
        self.stdout.write("-" * 40)

        servicios_visibles = []
        for servicio in servicios_hoy[:5]:  # Mostrar solo primeros 5
            try:
                if not servicio.hora_inicio:
                    continue

                servicio_hora = datetime.strptime(servicio.hora_inicio, '%H:%M').time()

                # Calcular hora fin
                hora_fin = None
                if servicio.servicio and hasattr(servicio.servicio, 'duracion') and servicio.servicio.duracion:
                    hora_inicio_dt = datetime.combine(hoy, servicio_hora)
                    hora_fin_dt = hora_inicio_dt + timedelta(minutes=int(servicio.servicio.duracion))
                    hora_fin = hora_fin_dt.time()

                # Verificar si es visible
                es_futuro = servicio_hora >= hora_actual
                en_curso = False
                if hora_fin:
                    en_curso = servicio_hora < hora_actual and hora_fin > hora_actual

                if es_futuro or en_curso:
                    servicios_visibles.append(servicio)
                    estado = "EN CURSO 🟢" if en_curso else "PENDIENTE ⏳"
                    self.stdout.write(f"  {servicio.hora_inicio} - {servicio.servicio.nombre if servicio.servicio else 'N/A'}")
                    self.stdout.write(f"        Cliente: {servicio.venta_reserva.cliente.nombre if servicio.venta_reserva.cliente else 'N/A'}")
                    self.stdout.write(f"        Reserva: #{servicio.venta_reserva.id}")
                    self.stdout.write(f"        Estado: {estado}")

                    # DIAGNÓSTICO DE PRODUCTOS
                    self.stdout.write(self.style.WARNING("\n        📦 PRODUCTOS DE ESTA RESERVA:"))
                    productos = ReservaProducto.objects.filter(
                        venta_reserva=servicio.venta_reserva
                    ).select_related('producto')

                    productos_normales = 0
                    productos_descuento = 0

                    for producto in productos:
                        if not producto.producto:
                            continue

                        nombre = str(producto.producto.nombre or "").strip()
                        precio = float(producto.producto.precio_base or 0)

                        es_descuento = any([
                            'descuento' in nombre.lower(),
                            'discount' in nombre.lower(),
                            'dto' in nombre.lower(),
                            precio < 0,
                            nombre.startswith('-'),
                        ])

                        if es_descuento:
                            productos_descuento += 1
                            self.stdout.write(f"           🚫 DESCUENTO: {producto.cantidad}x {nombre}")
                        else:
                            productos_normales += 1
                            self.stdout.write(self.style.SUCCESS(f"           ✅ NORMAL: {producto.cantidad}x {nombre}"))

                    self.stdout.write(f"        Total normales que deberían aparecer: {productos_normales}")
                    self.stdout.write(f"        Total descuentos filtrados: {productos_descuento}\n")

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  ❌ Error procesando servicio: {e}"))

        self.stdout.write(f"\nTotal servicios visibles: {len(servicios_visibles)}")

        # 3. Búsqueda específica si se proporciona reserva_id
        reserva_id = options.get('reserva_id')
        if reserva_id:
            self.stdout.write(f"\n3️⃣ ANÁLISIS ESPECÍFICO - RESERVA #{reserva_id}")
            self.stdout.write("-" * 40)

            try:
                reserva = VentaReserva.objects.get(id=reserva_id)

                # Servicios de esta reserva hoy
                servicios_reserva = ReservaServicio.objects.filter(
                    venta_reserva=reserva,
                    fecha_agendamiento=hoy
                ).exclude(
                    servicio__nombre__icontains='descuento'
                )

                self.stdout.write(f"Cliente: {reserva.cliente.nombre if reserva.cliente else 'N/A'}")
                self.stdout.write(f"Servicios hoy: {servicios_reserva.count()}")
                for srv in servicios_reserva:
                    self.stdout.write(f"  - {srv.hora_inicio}: {srv.servicio.nombre if srv.servicio else 'N/A'}")

                # Productos
                productos = ReservaProducto.objects.filter(venta_reserva=reserva).select_related('producto')
                self.stdout.write(f"\nProductos totales: {productos.count()}")

                for prod in productos:
                    if prod.producto:
                        nombre = prod.producto.nombre
                        precio = prod.producto.precio_base
                        es_descuento = any([
                            'descuento' in nombre.lower(),
                            precio < 0
                        ])
                        if es_descuento:
                            self.stdout.write(f"  🚫 DESCUENTO: {prod.cantidad}x {nombre} (${precio:,.0f})")
                        else:
                            self.stdout.write(self.style.SUCCESS(f"  ✅ NORMAL: {prod.cantidad}x {nombre} (${precio:,.0f})"))
                            self.stdout.write(f"     Fecha entrega: {prod.fecha_entrega or 'Sin fecha'}")

            except VentaReserva.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"❌ Reserva #{reserva_id} no encontrada"))

        self.stdout.write("\n" + "="*60)
        self.stdout.write(self.style.SUCCESS("FIN DEL DIAGNÓSTICO"))
        self.stdout.write("="*60)