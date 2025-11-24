# -*- coding: utf-8 -*-
"""
Comando para diagnosticar por qué no se envió email para una reserva
"""

from django.core.management.base import BaseCommand
from ventas.models import VentaReserva, ReservaServicio, CommunicationLog, Cliente, ClientPreferences
from ventas.services.communication_service import communication_service


class Command(BaseCommand):
    help = 'Diagnostica por qué no se envió email para una reserva'

    def add_arguments(self, parser):
        parser.add_argument('booking_id', type=int, help='ID de la reserva a diagnosticar')

    def handle(self, *args, **options):
        booking_id = options['booking_id']

        self.stdout.write("=" * 80)
        self.stdout.write(f"🔍 DIAGNOSTICANDO RESERVA #{booking_id}")
        self.stdout.write("=" * 80)
        self.stdout.write("")

        # 1. Verificar que la reserva existe
        try:
            booking = VentaReserva.objects.get(id=booking_id)
            self.stdout.write(self.style.SUCCESS(f"✅ Reserva encontrada: #{booking.id}"))
            self.stdout.write(f"   Cliente: {booking.cliente.nombre}")
            self.stdout.write(f"   Email: {booking.cliente.email}")
            self.stdout.write(f"   Teléfono: {booking.cliente.telefono}")
            self.stdout.write(f"   Fecha creación: {booking.fecha_reserva}")
            self.stdout.write("")
        except VentaReserva.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"❌ Reserva #{booking_id} no encontrada"))
            return

        # 2. Verificar servicios asociados
        servicios = ReservaServicio.objects.filter(venta_reserva=booking)
        if servicios.exists():
            self.stdout.write(self.style.SUCCESS(f"✅ Servicios asociados: {servicios.count()}"))
            for rs in servicios:
                self.stdout.write(f"   - {rs.servicio.nombre} ({rs.fecha_agendamiento} {rs.hora_inicio})")
        else:
            self.stdout.write(self.style.WARNING("⚠️  NO hay servicios asociados a esta reserva"))
            self.stdout.write("   Esto puede evitar que se envíe el email de confirmación")
        self.stdout.write("")

        # 3. Verificar logs de comunicación
        logs = CommunicationLog.objects.filter(booking_id=booking_id)
        if logs.exists():
            self.stdout.write(self.style.SUCCESS(f"✅ Logs de comunicación: {logs.count()}"))
            for log in logs:
                status_icon = "✅" if log.status == "SENT" else "❌"
                self.stdout.write(f"   {status_icon} {log.communication_type} - {log.message_type}")
                self.stdout.write(f"      Estado: {log.status}")
                self.stdout.write(f"      Destino: {log.destination}")
                self.stdout.write(f"      Fecha: {log.created_at}")
        else:
            self.stdout.write(self.style.WARNING("⚠️  NO se encontraron logs de comunicación"))
            self.stdout.write("   El email nunca fue intentado")
        self.stdout.write("")

        # 4. Verificar preferencias del cliente
        cliente = booking.cliente
        try:
            prefs = ClientPreferences.objects.get(cliente=cliente)
            self.stdout.write("📋 Preferencias del cliente:")
            self.stdout.write(f"   SMS: {'✅ Acepta' if prefs.accepts_sms else '❌ NO acepta'}")
            self.stdout.write(f"   Email: {'✅ Acepta' if prefs.accepts_email else '❌ NO acepta'}")
            self.stdout.write(f"   Confirmaciones: {'✅ Acepta' if prefs.accepts_booking_confirmations else '❌ NO acepta'}")
        except ClientPreferences.DoesNotExist:
            self.stdout.write(self.style.SUCCESS("✅ Sin preferencias registradas (acepta todo por defecto)"))
        self.stdout.write("")

        # 5. Intentar enviar ahora
        self.stdout.write("=" * 80)
        self.stdout.write("🚀 INTENTANDO ENVIAR EMAIL AHORA")
        self.stdout.write("=" * 80)
        self.stdout.write("")

        if not servicios.exists():
            self.stdout.write(self.style.WARNING("⚠️  No se puede enviar: faltan servicios asociados"))
            self.stdout.write("   Agrega al menos un servicio a la reserva primero")
            return

        result = communication_service.send_booking_confirmation_dual(
            booking_id=booking_id,
            cliente_id=cliente.id
        )

        self.stdout.write("")
        if result and result.get('success'):
            self.stdout.write(self.style.SUCCESS("✅ EMAIL ENVIADO EXITOSAMENTE"))
            email_result = result.get('email_result') or {}
            sms_result = result.get('sms_result') or {}

            if email_result.get('success'):
                self.stdout.write(f"   📧 Email enviado a: {cliente.email}")
            if sms_result.get('success'):
                self.stdout.write(f"   📱 SMS enviado a: {cliente.telefono}")
        else:
            self.stdout.write(self.style.ERROR("❌ ERROR AL ENVIAR"))
            if result:
                self.stdout.write(f"   Razón: {result.get('reason', 'unknown')}")
                if 'error' in result:
                    self.stdout.write(f"   Error: {result['error']}")
            else:
                self.stdout.write("   No se recibió respuesta del servicio")

        self.stdout.write("")
