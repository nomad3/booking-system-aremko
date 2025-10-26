# -*- coding: utf-8 -*-
"""
Comando de diagnóstico para envío automático de emails
"""

from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import connection
from ventas.models import VentaReserva, CommunicationLog, CommunicationLimit
from ventas.services.communication_service import communication_service
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Diagnostica problemas de envío automático de emails'

    def add_arguments(self, parser):
        parser.add_argument(
            '--test-booking',
            type=int,
            help='ID de reserva para probar envío',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("🔍 DIAGNÓSTICO EMAIL AUTOMÁTICO"))
        
        # 1. Verificar configuración de email
        self.stdout.write("\n1️⃣ CONFIGURACIÓN EMAIL:")
        self.stdout.write(f"   EMAIL_BACKEND: {settings.EMAIL_BACKEND}")
        self.stdout.write(f"   EMAIL_HOST: {settings.EMAIL_HOST}")
        self.stdout.write(f"   EMAIL_PORT: {settings.EMAIL_PORT}")
        self.stdout.write(f"   EMAIL_USE_TLS: {settings.EMAIL_USE_TLS}")
        self.stdout.write(f"   EMAIL_HOST_USER: {'✅ Configurado' if settings.EMAIL_HOST_USER else '❌ NO configurado'}")
        self.stdout.write(f"   EMAIL_HOST_PASSWORD: {'✅ Configurado' if settings.EMAIL_HOST_PASSWORD else '❌ NO configurado'}")
        self.stdout.write(f"   DEFAULT_FROM_EMAIL: {settings.DEFAULT_FROM_EMAIL}")
        self.stdout.write(f"   VENTAS_FROM_EMAIL: {settings.VENTAS_FROM_EMAIL}")
        
        # 2. Verificar flags de comunicación
        self.stdout.write("\n2️⃣ FLAGS DE COMUNICACIÓN:")
        self.stdout.write(f"   COMMUNICATION_EMAIL_ENABLED: {settings.COMMUNICATION_EMAIL_ENABLED}")
        self.stdout.write(f"   COMMUNICATION_SMS_ENABLED: {settings.COMMUNICATION_SMS_ENABLED}")
        
        # 3. Verificar signals
        self.stdout.write("\n3️⃣ SIGNALS REGISTRADOS:")
        try:
            import ventas.services.communication_triggers
            self.stdout.write("   ✅ communication_triggers importado correctamente")
        except Exception as e:
            self.stdout.write(f"   ❌ Error importando triggers: {e}")
        
        # 4. Verificar última reserva
        self.stdout.write("\n4️⃣ ÚLTIMA RESERVA:")
        try:
            ultima_reserva = VentaReserva.objects.all().order_by('-id').first()
            if ultima_reserva:
                self.stdout.write(f"   ID: {ultima_reserva.id}")
                self.stdout.write(f"   Cliente: {ultima_reserva.cliente.nombre}")
                self.stdout.write(f"   Email: {ultima_reserva.cliente.email}")
                self.stdout.write(f"   Teléfono: {ultima_reserva.cliente.telefono}")
                self.stdout.write(f"   Fecha: {ultima_reserva.fecha_reserva}")
                
                # Verificar servicios asociados
                servicios = ultima_reserva.reservaservicios.all()
                self.stdout.write(f"   Servicios: {servicios.count()}")
                
            else:
                self.stdout.write("   ❌ No hay reservas en la BD")
        except Exception as e:
            self.stdout.write(f"   ❌ Error consultando reservas: {e}")
        
        # 5. Verificar logs de comunicación
        self.stdout.write("\n5️⃣ LOGS DE COMUNICACIÓN (últimos 10):")
        try:
            logs = CommunicationLog.objects.all().order_by('-created_at')[:10]
            if logs:
                for log in logs:
                    status_icon = "✅" if log.status == "SUCCESS" else "❌"
                    self.stdout.write(f"   {status_icon} {log.created_at.strftime('%d/%m %H:%M')} - {log.message_type} - {log.communication_type}")
            else:
                self.stdout.write("   📭 No hay logs de comunicación")
        except Exception as e:
            self.stdout.write(f"   ❌ Error consultando logs: {e}")
        
        # 6. Test de envío si se especifica booking
        if options['test_booking']:
            booking_id = options['test_booking']
            self.stdout.write(f"\n6️⃣ TEST DE ENVÍO - Reserva {booking_id}:")
            try:
                booking = VentaReserva.objects.get(id=booking_id)
                result = communication_service.send_booking_confirmation_dual(
                    booking_id=booking.id,
                    cliente_id=booking.cliente.id
                )
                
                if result['success']:
                    self.stdout.write("   ✅ Envío exitoso")
                    if result.get('email_result', {}).get('success'):
                        self.stdout.write("   📧 Email enviado")
                    if result.get('sms_result', {}).get('success'):
                        self.stdout.write("   📱 SMS enviado")
                else:
                    self.stdout.write(f"   ❌ Error: {result.get('reason', 'unknown')}")
                    
            except VentaReserva.DoesNotExist:
                self.stdout.write(f"   ❌ Reserva {booking_id} no existe")
            except Exception as e:
                self.stdout.write(f"   ❌ Error en test: {e}")
        
        # 7. Verificar conexión a BD
        self.stdout.write("\n7️⃣ CONEXIÓN BD:")
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM ventas_ventareserva")
                count = cursor.fetchone()[0]
                self.stdout.write(f"   ✅ {count} reservas en BD")
        except Exception as e:
            self.stdout.write(f"   ❌ Error BD: {e}")
        
        self.stdout.write(self.style.SUCCESS("\n🏁 DIAGNÓSTICO COMPLETADO"))
        
        # Recomendaciones
        self.stdout.write("\n💡 POSIBLES SOLUCIONES:")
        if settings.EMAIL_BACKEND == 'django.core.mail.backends.console.EmailBackend':
            self.stdout.write("   • Configurar EMAIL_HOST_USER y EMAIL_HOST_PASSWORD en producción")
        if not settings.COMMUNICATION_EMAIL_ENABLED:
            self.stdout.write("   • Activar COMMUNICATION_EMAIL_ENABLED=true")
        if not settings.EMAIL_HOST_USER:
            self.stdout.write("   • Verificar variable EMAIL_HOST_USER en Render")