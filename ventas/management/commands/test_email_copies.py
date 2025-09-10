# -*- coding: utf-8 -*-
"""
Comando para probar que las copias de email se envían correctamente
"""

from django.core.management.base import BaseCommand
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from ventas.models import VentaReserva, Cliente
from ventas.services.communication_service import communication_service


class Command(BaseCommand):
    help = "Prueba el envío de emails con copias a aremkospa@gmail.com y ventas@aremko.cl"

    def add_arguments(self, parser):
        parser.add_argument('--booking-id', type=int, help='ID de la reserva para probar')
        parser.add_argument('--test-type', choices=['confirmation', 'reminder', 'payment'], 
                          default='confirmation', help='Tipo de email a probar')

    def handle(self, *args, **options):
        booking_id = options.get('booking_id')
        test_type = options.get('test_type')
        
        if not booking_id:
            self.stdout.write(self.style.ERROR('❌ Debes proporcionar --booking-id'))
            return

        try:
            booking = VentaReserva.objects.get(id=booking_id)
            cliente = booking.cliente
            
            self.stdout.write(f"🧪 Probando email de {test_type} para reserva {booking_id}")
            self.stdout.write(f"👤 Cliente: {cliente.nombre} ({cliente.email})")
            
            # Probar envío de email según el tipo
            if test_type == 'confirmation':
                result = communication_service._send_confirmation_email(
                    cliente, booking, 'Servicio de Prueba', '01/01/2024', '10:00'
                )
            elif test_type == 'reminder':
                result = communication_service._send_reminder_email(cliente, booking)
            elif test_type == 'payment':
                result = communication_service._send_payment_email(cliente, booking)
            
            if result.get('success'):
                self.stdout.write(self.style.SUCCESS('✅ Email enviado correctamente'))
                self.stdout.write('📧 Copias enviadas a:')
                self.stdout.write('   - aremkospa@gmail.com')
                self.stdout.write('   - ventas@aremko.cl')
            else:
                self.stdout.write(self.style.ERROR(f'❌ Error enviando email: {result.get("error", "unknown")}'))
                
        except VentaReserva.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'❌ Reserva {booking_id} no encontrada'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Error: {str(e)}'))