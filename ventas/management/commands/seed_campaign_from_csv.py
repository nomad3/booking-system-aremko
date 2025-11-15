# -*- coding: utf-8 -*-
"""
Management command para sembrar una campaña de emails desde un archivo CSV
Uso: python manage.py seed_campaign_from_csv --csv-file path/to/file.csv --subject "Asunto del email" --template-file path/to/template.html
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.template.loader import render_to_string
from django.template import Template, Context
from django.core.cache import cache
import csv
import os
import logging

from ventas.models import CommunicationLog, Cliente, Contact, Company

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Siembra una campaña de emails desde un archivo CSV'

    def add_arguments(self, parser):
        parser.add_argument(
            '--csv-file',
            type=str,
            required=True,
            help='Ruta al archivo CSV con los contactos'
        )
        parser.add_argument(
            '--subject',
            type=str,
            required=True,
            help='Asunto del email'
        )
        parser.add_argument(
            '--template-file',
            type=str,
            help='Ruta al archivo HTML de plantilla (opcional)'
        )
        parser.add_argument(
            '--email-body',
            type=str,
            help='Cuerpo del email en HTML (alternativa a template-file)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Ejecutar en modo simulación (no crea registros reales)'
        )

    def handle(self, *args, **options):
        """
        Procesa el CSV y crea CommunicationLog para cada contacto
        """
        csv_file = options['csv_file']
        subject = options['subject']
        template_file = options.get('template_file')
        email_body = options.get('email_body')
        dry_run = options['dry_run']

        # Validar que el archivo CSV existe
        if not os.path.exists(csv_file):
            raise CommandError(f'El archivo CSV no existe: {csv_file}')

        # Validar que tenemos un template o body
        if not template_file and not email_body:
            raise CommandError('Debe proporcionar --template-file o --email-body')

        # Cargar template
        if template_file:
            if not os.path.exists(template_file):
                raise CommandError(f'El archivo de template no existe: {template_file}')
            with open(template_file, 'r', encoding='utf-8') as f:
                email_body = f.read()

        # Procesar CSV
        created_count = 0
        error_count = 0
        
        if dry_run:
            self.stdout.write("🔍 MODO SIMULACIÓN - No se crearán registros reales")

        with open(csv_file, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            
            # Validar columnas requeridas
            required_columns = ['email', 'nombre']
            missing_columns = set(required_columns) - set(reader.fieldnames)
            if missing_columns:
                raise CommandError(f'El CSV debe contener las columnas: {", ".join(missing_columns)}')

            for row_num, row in enumerate(reader, 1):
                try:
                    email = row['email'].strip()
                    nombre = row['nombre'].strip()
                    empresa = row.get('empresa', '').strip()
                    
                    if not email or not nombre:
                        self.stdout.write(f"⚠️  Fila {row_num}: Email o nombre vacío - omitiendo")
                        error_count += 1
                        continue

                    # Buscar o crear cliente
                    cliente = self.get_or_create_cliente(email, nombre, empresa)
                    
                    if not cliente:
                        self.stdout.write(f"⚠️  Fila {row_num}: No se pudo crear cliente para {email}")
                        error_count += 1
                        continue

                    # Personalizar email
                    personalized_content = self.personalize_email(email_body, {
                        'nombre': nombre,
                        'empresa': empresa,
                        'email': email
                    })

                    # Crear CommunicationLog
                    if not dry_run:
                        comm_log = CommunicationLog.objects.create(
                            cliente=cliente,
                            communication_type='EMAIL',
                            message_type='PROMOTIONAL',
                            subject=subject,
                            content=personalized_content,
                            destination=email,
                            status='PENDING',
                            triggered_by='seed_campaign_from_csv'
                        )
                        created_count += 1
                    else:
                        created_count += 1
                        
                    if row_num % 100 == 0:
                        self.stdout.write(f"📧 Procesadas {row_num} filas...")

                except Exception as e:
                    self.stdout.write(f"❌ Error en fila {row_num}: {str(e)}")
                    error_count += 1

        # Resumen
        self.stdout.write("\n=== RESUMEN ===")
        self.stdout.write(f"✅ Emails creados: {created_count}")
        self.stdout.write(f"❌ Errores: {error_count}")
        
        if not dry_run:
            # Actualizar cache de progreso
            self.update_progress_cache()
            self.stdout.write(f"📊 Cache de progreso actualizado")

    def get_or_create_cliente(self, email, nombre, empresa):
        """
        Busca o crea un cliente basado en el email
        """
        try:
            # Buscar cliente existente por email
            cliente = Cliente.objects.filter(email=email).first()
            
            if cliente:
                return cliente
            
            # Crear nuevo cliente
            cliente = Cliente.objects.create(
                email=email,
                nombre=nombre,
                # Puedes agregar más campos según tu modelo
            )
            return cliente
            
        except Exception as e:
            logger.error(f"Error creando cliente {email}: {str(e)}")
            return None

    def personalize_email(self, template_content, context):
        """
        Personaliza el contenido del email con variables del contexto
        """
        try:
            template = Template(template_content)
            return template.render(Context(context))
        except Exception as e:
            logger.error(f"Error personalizando email: {str(e)}")
            return template_content

    def update_progress_cache(self):
        """
        Actualiza el progreso de la campaña en cache
        """
        try:
            total_pending = CommunicationLog.objects.filter(
                status='PENDING',
                communication_type='EMAIL',
                message_type='PROMOTIONAL'
            ).count()
            
            total_sent = CommunicationLog.objects.filter(
                status='SENT',
                communication_type='EMAIL',
                message_type='PROMOTIONAL'
            ).count()
            
            total_failed = CommunicationLog.objects.filter(
                status='FAILED',
                communication_type='EMAIL',
                message_type='PROMOTIONAL'
            ).count()
            
            total_emails = total_pending + total_sent + total_failed
            
            progress_data = {
                'total': total_emails,
                'sent': total_sent,
                'pending': total_pending,
                'failed': total_failed,
                'percentage': round((total_sent / total_emails * 100), 2) if total_emails > 0 else 0,
                'last_updated': timezone.now().isoformat()
            }
            
            cache.set('campaign_progress', progress_data, 3600)
            
        except Exception as e:
            logger.error(f"Error actualizando progreso en cache: {str(e)}")