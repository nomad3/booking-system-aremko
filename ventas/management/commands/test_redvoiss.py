# -*- coding: utf-8 -*-
"""
Management command para probar la integración con Redvoiss
Uso: python manage.py test_redvoiss [--send-test-sms]
"""

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
import logging

from ventas.services.redvoiss_service import redvoiss_service
from ventas.models import Cliente

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Prueba la integración con la API de Redvoiss'

    def add_arguments(self, parser):
        parser.add_argument(
            '--send-test-sms',
            action='store_true',
            help='Enviar SMS de prueba real (requiere credenciales válidas)'
        )
        
        parser.add_argument(
            '--phone',
            type=str,
            help='Número de teléfono para SMS de prueba (formato: +56912345678)'
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS("🧪 Iniciando pruebas de integración con Redvoiss")
        )
        
        # 1. Verificar configuración
        self._check_configuration()
        
        # 2. Probar conexión
        self._test_connection()
        
        # 3. Probar envío SMS si se solicita
        if options['send_test_sms']:
            phone = options.get('phone')
            self._test_sms_sending(phone)
        
        self.stdout.write(
            self.style.SUCCESS("✅ Pruebas completadas exitosamente")
        )

    def _check_configuration(self):
        """Verifica que la configuración esté completa"""
        self.stdout.write("1️⃣ Verificando configuración...")
        
        config_items = {
            'REDVOISS_API_URL': getattr(settings, 'REDVOISS_API_URL', None),
            'REDVOISS_USERNAME': getattr(settings, 'REDVOISS_USERNAME', None),
            'REDVOISS_PASSWORD': getattr(settings, 'REDVOISS_PASSWORD', None),
        }
        
        for key, value in config_items.items():
            if value:
                if 'PASSWORD' in key:
                    display_value = '*' * len(value) if value else 'No configurado'
                else:
                    display_value = value
                self.stdout.write(f"   ✅ {key}: {display_value}")
            else:
                self.stdout.write(f"   ❌ {key}: No configurado")
                raise CommandError(f"Variable de entorno {key} no configurada")
        
        # Verificar límites
        limits = {
            'SMS_DAILY_LIMIT_PER_CLIENT': getattr(settings, 'SMS_DAILY_LIMIT_PER_CLIENT', 2),
            'SMS_MONTHLY_LIMIT_PER_CLIENT': getattr(settings, 'SMS_MONTHLY_LIMIT_PER_CLIENT', 8),
            'EMAIL_WEEKLY_LIMIT_PER_CLIENT': getattr(settings, 'EMAIL_WEEKLY_LIMIT_PER_CLIENT', 1),
        }
        
        self.stdout.write("   📊 Límites configurados:")
        for key, value in limits.items():
            self.stdout.write(f"      {key}: {value}")

    def _test_connection(self):
        """Prueba la conexión con Redvoiss"""
        self.stdout.write("2️⃣ Probando conexión con Redvoiss...")
        
        try:
            result = redvoiss_service.greet()
            
            if result['success']:
                self.stdout.write(
                    self.style.SUCCESS(f"   ✅ Conexión exitosa: {result['message']}")
                )
            else:
                self.stdout.write(
                    self.style.ERROR(f"   ❌ Error de conexión: {result['message']}")
                )
                raise CommandError("No se puede conectar con Redvoiss")
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"   ❌ Error inesperado: {str(e)}")
            )
            raise CommandError(f"Error probando conexión: {str(e)}")

    def _test_sms_sending(self, phone=None):
        """Prueba el envío real de SMS"""
        self.stdout.write("3️⃣ Probando envío de SMS...")
        
        # Determinar número de destino
        if phone:
            destination = phone
        else:
            # Buscar el primer cliente con teléfono
            cliente = Cliente.objects.filter(telefono__isnull=False).first()
            if cliente:
                destination = cliente.telefono
                self.stdout.write(f"   📱 Usando teléfono del cliente: {cliente.nombre} - {destination}")
            else:
                raise CommandError("No se encontró un número de teléfono válido. Use --phone para especificar uno.")
        
        # Validar formato
        if not destination.startswith('+56'):
            self.stdout.write(
                self.style.WARNING(f"   ⚠️  Número {destination} no tiene formato internacional, intentando corregir...")
            )
        
        # Mensaje de prueba
        test_message = f"🧪 SMS de prueba desde Aremko - {timezone.now().strftime('%H:%M')}"
        
        try:
            result = redvoiss_service.send_sms(
                destination=destination,
                message=test_message,
                bulk_name="Prueba Aremko"
            )
            
            if result['success']:
                self.stdout.write(
                    self.style.SUCCESS(f"   ✅ SMS enviado exitosamente!")
                )
                self.stdout.write(f"      📱 Destino: {result['destination']}")
                self.stdout.write(f"      🆔 Batch ID: {result['batch_id']}")
                self.stdout.write(f"      💬 Mensaje: {result['message']}")
                
                # Verificar estado después de unos segundos
                self._check_sms_status(result['batch_id'])
                
            else:
                self.stdout.write(
                    self.style.ERROR(f"   ❌ Error enviando SMS: {result['error']}")
                )
                raise CommandError("Falló el envío de SMS de prueba")
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"   ❌ Error inesperado enviando SMS: {str(e)}")
            )
            raise CommandError(f"Error en envío de SMS: {str(e)}")

    def _check_sms_status(self, batch_id):
        """Verifica el estado del SMS enviado"""
        import time
        
        self.stdout.write("4️⃣ Verificando estado del SMS...")
        
        # Esperar unos segundos para que el SMS se procese
        self.stdout.write("   ⏳ Esperando 10 segundos para verificar estado...")
        time.sleep(10)
        
        try:
            result = redvoiss_service.check_batch_status(batch_id)
            
            if result['success']:
                self.stdout.write(
                    self.style.SUCCESS("   ✅ Estado verificado exitosamente:")
                )
                
                for message in result['messages']:
                    status = message.get('message', 'UNKNOWN')
                    destination = message.get('destination', 'N/A')
                    msg_cod = message.get('msgCod', 'N/A')
                    
                    if status == 'RECIBIDO':
                        style = self.style.SUCCESS
                        icon = "📱✅"
                    elif status == 'ENVIADO':
                        style = self.style.WARNING
                        icon = "📤"
                    elif status == 'PENDIENTE':
                        style = self.style.HTTP_INFO
                        icon = "⏳"
                    else:
                        style = self.style.ERROR
                        icon = "❌"
                    
                    self.stdout.write(
                        style(f"      {icon} {destination}: {status} (ID: {msg_cod})")
                    )
            else:
                self.stdout.write(
                    self.style.WARNING(f"   ⚠️  No se pudo verificar estado: {result['error']}")
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f"   ⚠️  Error verificando estado: {str(e)}")
            )
        
        # Información sobre estados
        self.stdout.write("\n📋 Estados posibles:")
        self.stdout.write("   • PENDIENTE: No enviado aún")
        self.stdout.write("   • ENVIADO: Enviado a la red, esperando confirmación")
        self.stdout.write("   • RECIBIDO: Entregado al dispositivo del usuario")
        self.stdout.write("   • FALLIDO: No se pudo entregar")
        
        self.stdout.write(
            self.style.HTTP_INFO("\n💡 Los estados pueden cambiar hasta 24h después del envío")
        )