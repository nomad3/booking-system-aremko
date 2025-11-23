# -*- coding: utf-8 -*-
"""
Script para crear una campaña de email de prueba con clientes seleccionados
"""

from django.core.management.base import BaseCommand
from ventas.models import EmailCampaign, EmailRecipient, Cliente
from django.utils import timezone


class Command(BaseCommand):
    help = 'Crea una campaña de email de prueba con 2 clientes'

    def add_arguments(self, parser):
        parser.add_argument(
            '--cliente-ids',
            type=str,
            required=True,
            help='IDs de clientes separados por coma (ej: 1,2)'
        )
        parser.add_argument(
            '--nombre-campana',
            type=str,
            default='Prueba Segmento $500k',
            help='Nombre de la campaña'
        )

    def handle(self, *args, **options):
        cliente_ids_str = options['cliente_ids']
        nombre_campana = options['nombre_campana']
        
        # Parsear IDs
        try:
            cliente_ids = [int(id.strip()) for id in cliente_ids_str.split(',')]
        except ValueError:
            self.stdout.write(self.style.ERROR('❌ IDs de clientes inválidos'))
            return
        
        # Verificar que los clientes existan
        clientes = Cliente.objects.filter(id__in=cliente_ids)
        if clientes.count() != len(cliente_ids):
            self.stdout.write(self.style.ERROR(f'❌ Algunos clientes no fueron encontrados'))
            return
        
        self.stdout.write(f'✅ Encontrados {clientes.count()} clientes:')
        for cliente in clientes:
            self.stdout.write(f'   - {cliente.nombre} ({cliente.email})')
        
        # Leer template HTML
        import os
        from django.conf import settings
        
        template_path = os.path.join(
            settings.BASE_DIR,
            'ventas/templates/email/campaign_template_example.html'
        )
        
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                body_template = f.read()
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f'❌ Template no encontrado: {template_path}'))
            return
        
        # Crear EmailCampaign
        campaign = EmailCampaign.objects.create(
            name=nombre_campana,
            subject_template='Hola {nombre_cliente}, tenemos una oferta especial para ti',
            body_template_html=body_template,
            status='draft',
            schedule_config={
                "start_time": "08:00",
                "end_time": "21:00",
                "batch_size": 2,
                "interval_minutes": 1,
                "ai_enabled": False
            },
            ai_variation_enabled=False,
            created_by=None  # Puedes pasar el usuario si quieres
        )
        
        self.stdout.write(self.style.SUCCESS(f'✅ Campaña creada: {campaign.name} (ID: {campaign.id})'))
        
        # Crear EmailRecipients
        for cliente in clientes:
            # Calcular gasto total del cliente
            from django.db.models import Sum
            gasto_total = cliente.ventareserva_set.aggregate(
                total=Sum('total')
            )['total'] or 0
            
            # Personalizar subject y body
            subject = campaign.subject_template.replace('{nombre_cliente}', cliente.nombre)
            body = campaign.body_template_html.replace('{nombre_cliente}', cliente.nombre)
            body = body.replace('{gasto_total}', f'{gasto_total:,.0f}')
            
            recipient = EmailRecipient.objects.create(
                campaign=campaign,
                email=cliente.email,
                name=cliente.nombre,
                personalized_subject=subject,
                personalized_body=body,
                client_total_spend=gasto_total,
                client_visit_count=cliente.ventareserva_set.count(),
                client_last_visit=cliente.ventareserva_set.order_by('-fecha_reserva').first().fecha_reserva if cliente.ventareserva_set.exists() else None,
                client_city=cliente.ciudad or 'N/A',
                status='pending',
                send_enabled=True,
                priority=1
            )
            
            self.stdout.write(f'   ✅ Destinatario creado: {recipient.email}')
        
        self.stdout.write(self.style.SUCCESS(f'\n🎉 Campaña lista para envío!'))
        self.stdout.write(f'\n📋 Próximos pasos:')
        self.stdout.write(f'   1. Revisa la campaña en: /admin/ventas/emailcampaign/{campaign.id}/change/')
        self.stdout.write(f'   2. Revisa los destinatarios en: /admin/ventas/emailrecipient/?campaign__id__exact={campaign.id}')
        self.stdout.write(f'   3. Cambia el estado a "ready" cuando estés listo')
        self.stdout.write(f'   4. Ejecuta: python manage.py enviar_campana_email --campaign-id {campaign.id} --dry-run')
        self.stdout.write(f'   5. Si todo se ve bien, ejecuta sin --dry-run')
