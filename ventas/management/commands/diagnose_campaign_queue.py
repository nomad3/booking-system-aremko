# -*- coding: utf-8 -*-
"""
Management command para diagnosticar el estado de la cola de campañas
Uso: python manage.py diagnose_campaign_queue
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.cache import cache
from datetime import timedelta

from ventas.models import CommunicationLog, Contact, Company

class Command(BaseCommand):
    help = 'Diagnostica el estado actual de la cola de campañas de email'

    def handle(self, *args, **options):
        """
        Genera un reporte completo del estado de la campaña
        """
        self.stdout.write("=== DIAGNÓSTICO DE CAMPAÑA DRIP ===\n")
        
        # 1. Estado general de la cola
        self.stdout.write("1. ESTADO DE LA COLA:")
        pending_count = CommunicationLog.objects.filter(
            status='PENDING',
            communication_type='EMAIL',
            message_type='PROMOTIONAL'
        ).count()
        
        sent_count = CommunicationLog.objects.filter(
            status='SENT',
            communication_type='EMAIL',
            message_type='PROMOTIONAL'
        ).count()
        
        failed_count = CommunicationLog.objects.filter(
            status='FAILED',
            communication_type='EMAIL',
            message_type='PROMOTIONAL'
        ).count()
        
        self.stdout.write(f"   - Pendientes: {pending_count}")
        self.stdout.write(f"   - Enviados: {sent_count}")
        self.stdout.write(f"   - Fallidos: {failed_count}")
        self.stdout.write(f"   - Total: {pending_count + sent_count + failed_count}\n")
        
        # 2. Contactos y empresas
        self.stdout.write("2. DATOS BASE:")
        total_contacts = Contact.objects.count()
        total_companies = Company.objects.count()
        
        self.stdout.write(f"   - Total contactos: {total_contacts}")
        self.stdout.write(f"   - Total empresas: {total_companies}\n")
        
        # 3. Actividad reciente
        self.stdout.write("3. ACTIVIDAD RECIENTE (últimas 24 horas):")
        yesterday = timezone.now() - timedelta(hours=24)
        
        recent_sent = CommunicationLog.objects.filter(
            status='SENT',
            communication_type='EMAIL',
            message_type='PROMOTIONAL',
            sent_at__gte=yesterday
        ).count()
        
        recent_failed = CommunicationLog.objects.filter(
            status='FAILED',
            communication_type='EMAIL',
            message_type='PROMOTIONAL',
            updated_at__gte=yesterday
        ).count()
        
        self.stdout.write(f"   - Enviados (24h): {recent_sent}")
        self.stdout.write(f"   - Fallidos (24h): {recent_failed}\n")
        
        # 4. Últimos logs
        self.stdout.write("4. ÚLTIMOS 10 LOGS:")
        latest_logs = CommunicationLog.objects.filter(
            communication_type='EMAIL',
            message_type='PROMOTIONAL'
        ).order_by('-created_at')[:10]
        
        for log in latest_logs:
            created_str = log.created_at.strftime("%Y-%m-%d %H:%M")
            sent_str = log.sent_at.strftime("%H:%M") if log.sent_at else "N/A"
            self.stdout.write(f"   - {created_str} | {log.status} | {log.destination} | Enviado: {sent_str}")
        
        # 5. Estado del cache
        self.stdout.write("\n5. ESTADO DEL CACHE:")
        progress_data = cache.get('campaign_progress')
        if progress_data:
            self.stdout.write(f"   - Cache encontrado:")
            self.stdout.write(f"     * Total: {progress_data.get('total', 'N/A')}")
            self.stdout.write(f"     * Enviados: {progress_data.get('sent', 'N/A')}")
            self.stdout.write(f"     * Pendientes: {progress_data.get('pending', 'N/A')}")
            self.stdout.write(f"     * Porcentaje: {progress_data.get('percentage', 'N/A')}%")
            self.stdout.write(f"     * Última actualización: {progress_data.get('last_updated', 'N/A')}")
        else:
            self.stdout.write("   - No hay datos en cache")
        
        # 6. Próximo email a enviar
        self.stdout.write("\n6. PRÓXIMO EMAIL:")
        next_email = CommunicationLog.objects.filter(
            status='PENDING',
            communication_type='EMAIL',
            message_type='PROMOTIONAL'
        ).order_by('created_at').first()
        
        if next_email:
            self.stdout.write(f"   - Destino: {next_email.destination}")
            self.stdout.write(f"   - Asunto: {next_email.subject}")
            self.stdout.write(f"   - Creado: {next_email.created_at.strftime('%Y-%m-%d %H:%M')}")
        else:
            self.stdout.write("   - No hay emails pendientes")
        
        self.stdout.write("\n=== FIN DEL DIAGNÓSTICO ===")