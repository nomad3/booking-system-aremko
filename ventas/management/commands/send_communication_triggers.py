# -*- coding: utf-8 -*-
"""
Management command para ejecutar triggers de comunicación
Uso: python manage.py send_communication_triggers --type [reminders|surveys|birthdays|reactivation|vip|all]
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
import logging

from ventas.services.communication_triggers import (
    schedule_booking_reminders,
    schedule_satisfaction_surveys, 
    schedule_birthday_messages,
    schedule_reactivation_campaigns,
    schedule_vip_newsletters,
    test_communication_system
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Ejecuta triggers automáticos de comunicación'

    def add_arguments(self, parser):
        parser.add_argument(
            '--type',
            type=str,
            default='all',
            choices=['reminders', 'surveys', 'birthdays', 'reactivation', 'vip', 'test', 'all'],
            help='Tipo de comunicación a enviar'
        )
        
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Ejecutar en modo simulación (no envía mensajes reales)'
        )
        
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Mostrar información detallada'
        )

    def handle(self, *args, **options):
        start_time = timezone.now()
        
        if options['verbose']:
            logger.setLevel(logging.DEBUG)
            
        self.stdout.write(
            self.style.SUCCESS(
                f"🚀 Iniciando triggers de comunicación - {start_time.strftime('%Y-%m-%d %H:%M:%S')}"
            )
        )
        
        if options['dry_run']:
            self.stdout.write(
                self.style.WARNING("⚠️  MODO SIMULACIÓN ACTIVADO - No se enviarán mensajes reales")
            )
        
        trigger_type = options['type']
        
        try:
            if trigger_type == 'test':
                self._run_system_test()
            elif trigger_type == 'reminders':
                self._run_booking_reminders()
            elif trigger_type == 'surveys':
                self._run_satisfaction_surveys()
            elif trigger_type == 'birthdays':
                self._run_birthday_messages()
            elif trigger_type == 'reactivation':
                self._run_reactivation_campaigns()
            elif trigger_type == 'vip':
                self._run_vip_newsletters()
            elif trigger_type == 'all':
                self._run_all_triggers()
            else:
                raise CommandError(f"Tipo de trigger inválido: {trigger_type}")
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Error ejecutando triggers: {str(e)}")
            )
            raise CommandError(f"Error en ejecución: {str(e)}")
        
        end_time = timezone.now()
        duration = (end_time - start_time).total_seconds()
        
        self.stdout.write(
            self.style.SUCCESS(
                f"✅ Triggers completados exitosamente en {duration:.2f} segundos"
            )
        )

    def _run_system_test(self):
        """Ejecuta prueba completa del sistema"""
        self.stdout.write("🧪 Ejecutando prueba del sistema de comunicación...")
        
        success = test_communication_system()
        
        if success:
            self.stdout.write(self.style.SUCCESS("✅ Sistema funcionando correctamente"))
        else:
            self.stdout.write(self.style.ERROR("❌ Se encontraron problemas en el sistema"))
            raise CommandError("Prueba del sistema falló")

    def _run_booking_reminders(self):
        """Ejecuta recordatorios de reservas"""
        self.stdout.write("📅 Enviando recordatorios de reservas...")
        
        try:
            schedule_booking_reminders()
            self.stdout.write(self.style.SUCCESS("✅ Recordatorios procesados"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error en recordatorios: {str(e)}"))
            raise

    def _run_satisfaction_surveys(self):
        """Ejecuta encuestas de satisfacción"""
        self.stdout.write("📊 Enviando encuestas de satisfacción...")
        
        try:
            schedule_satisfaction_surveys()
            self.stdout.write(self.style.SUCCESS("✅ Encuestas procesadas"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error en encuestas: {str(e)}"))
            raise

    def _run_birthday_messages(self):
        """Ejecuta mensajes de cumpleaños"""
        self.stdout.write("🎂 Enviando mensajes de cumpleaños...")
        
        try:
            schedule_birthday_messages()
            self.stdout.write(self.style.SUCCESS("✅ Mensajes de cumpleaños procesados"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error en cumpleaños: {str(e)}"))
            raise

    def _run_reactivation_campaigns(self):
        """Ejecuta campañas de reactivación"""
        self.stdout.write("🔄 Enviando campañas de reactivación...")
        
        try:
            schedule_reactivation_campaigns()
            self.stdout.write(self.style.SUCCESS("✅ Campañas de reactivación procesadas"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error en reactivación: {str(e)}"))
            raise

    def _run_vip_newsletters(self):
        """Ejecuta newsletters VIP"""
        self.stdout.write("👑 Enviando newsletters VIP...")
        
        try:
            schedule_vip_newsletters()
            self.stdout.write(self.style.SUCCESS("✅ Newsletters VIP procesados"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error en newsletters VIP: {str(e)}"))
            raise

    def _run_all_triggers(self):
        """Ejecuta todos los triggers en secuencia"""
        self.stdout.write("🎯 Ejecutando todos los triggers...")
        
        triggers = [
            ("📅 Recordatorios", self._run_booking_reminders),
            ("📊 Encuestas", self._run_satisfaction_surveys),
            ("🎂 Cumpleaños", self._run_birthday_messages),
            ("🔄 Reactivación", self._run_reactivation_campaigns),
            ("👑 VIP", self._run_vip_newsletters),
        ]
        
        for name, trigger_func in triggers:
            try:
                self.stdout.write(f"Ejecutando {name}...")
                trigger_func()
            except Exception as e:
                self.stdout.write(
                    self.style.WARNING(f"⚠️  Error en {name}: {str(e)}")
                )
                # Continuar con los demás triggers aunque uno falle
                continue