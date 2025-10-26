# -*- coding: utf-8 -*-
"""
Comando para probar la integración con Mercado Pago Link
"""

from django.core.management.base import BaseCommand
from django.conf import settings
from ventas.models import VentaReserva, Cliente
from ventas.services.mercadopago_service import mercadopago_service


class Command(BaseCommand):
    help = "Prueba la integración con Mercado Pago Link"

    def add_arguments(self, parser):
        parser.add_argument('--booking-id', type=int, help='ID de la reserva para probar')
        parser.add_argument('--test-credentials', action='store_true', help='Probar solo las credenciales')

    def handle(self, *args, **options):
        booking_id = options.get('booking_id')
        test_credentials = options.get('test_credentials')
        
        self.stdout.write("🧪 Probando integración con Mercado Pago Link")
        self.stdout.write("=" * 50)
        
        # Verificar configuración
        self.stdout.write("\n1. Verificando configuración...")
        access_token = getattr(settings, 'MERCADOPAGO_ACCESS_TOKEN', None)
        sandbox = getattr(settings, 'MERCADOPAGO_SANDBOX', True)
        
        if not access_token:
            self.stdout.write(self.style.ERROR("❌ MERCADOPAGO_ACCESS_TOKEN no configurado"))
            return
        
        self.stdout.write(self.style.SUCCESS(f"✅ Access Token configurado"))
        self.stdout.write(f"   Modo: {'Sandbox' if sandbox else 'Producción'}")
        
        if test_credentials:
            self.stdout.write(self.style.SUCCESS("✅ Configuración básica OK"))
            return
        
        # Probar con reserva real
        if not booking_id:
            self.stdout.write(self.style.ERROR("❌ Debes proporcionar --booking-id"))
            return
        
        try:
            booking = VentaReserva.objects.get(id=booking_id)
            cliente = booking.cliente
            
            self.stdout.write(f"\n2. Probando con reserva {booking_id}...")
            self.stdout.write(f"   Cliente: {cliente.nombre} ({cliente.email})")
            self.stdout.write(f"   Total: ${booking.total}")
            
            # Crear link de pago
            self.stdout.write("\n3. Creando link de pago...")
            result = mercadopago_service.create_payment_link(
                reserva_id=booking_id,
                amount=float(booking.total),
                description=f"Reserva Aremko #{booking_id}",
                customer_email=cliente.email,
                customer_name=cliente.nombre
            )
            
            if result.get('success'):
                self.stdout.write(self.style.SUCCESS("✅ Link de pago creado exitosamente"))
                self.stdout.write(f"   Link: {result.get('payment_link')}")
                if result.get('sandbox_init_point'):
                    self.stdout.write(f"   Sandbox: {result.get('sandbox_init_point')}")
            else:
                self.stdout.write(self.style.ERROR(f"❌ Error creando link: {result.get('error')}"))
                if result.get('details'):
                    self.stdout.write(f"   Detalles: {result.get('details')}")
                
        except VentaReserva.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"❌ Reserva {booking_id} no encontrada"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error: {str(e)}"))
        
        self.stdout.write("\n" + "=" * 50)
        self.stdout.write("🏁 Prueba completada")