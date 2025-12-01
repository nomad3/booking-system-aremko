# -*- coding: utf-8 -*-
"""
Comando para enviar campaña de lanzamiento de Gift Cards Digitales.

Envía emails a todos los suscriptores activos de NewsletterSubscriber
en lotes pequeños (25 cada 15 minutos) para evitar problemas de spam.

Uso:
    # Modo prueba (no envía realmente)
    python manage.py enviar_campana_giftcard_digital --dry-run
    
    # Enviar solo a un email de prueba
    python manage.py enviar_campana_giftcard_digital --test-email tu@email.com
    
    # Envío real a todos
    python manage.py enviar_campana_giftcard_digital
    
    # Envío a primeros 100 (para probar)
    python manage.py enviar_campana_giftcard_digital --limit 100
"""

import time
import logging
from django.core.management.base import BaseCommand
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone
from django.conf import settings
from ventas.models import NewsletterSubscriber, CommunicationLog

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Envía campaña de lanzamiento de Gift Cards Digitales a suscriptores activos'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Modo prueba (muestra lo que haría pero no envía emails)',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=25,
            help='Número de emails por lote (default: 25)',
        )
        parser.add_argument(
            '--batch-delay',
            type=int,
            default=900,  # 15 minutos en segundos
            help='Segundos de espera entre lotes (default: 900 = 15 min)',
        )
        parser.add_argument(
            '--test-email',
            type=str,
            help='Enviar solo a este email (para pruebas)',
        )
        parser.add_argument(
            '--limit',
            type=int,
            help='Límite de emails a enviar (para pruebas)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        batch_size = options['batch_size']
        batch_delay = options['batch_delay']
        test_email = options['test_email']
        limit = options['limit']

        # Banner inicial
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('📧 CAMPAÑA: LANZAMIENTO GIFT CARDS DIGITALES'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('⚠️  MODO PRUEBA (DRY RUN) - No se enviarán emails'))
        
        # 1. Filtrar destinatarios
        if test_email:
            suscriptores = NewsletterSubscriber.objects.filter(
                email=test_email,
                is_active=True
            )
            self.stdout.write(f"🎯 Modo prueba: enviando solo a {test_email}")
        else:
            suscriptores = NewsletterSubscriber.objects.filter(
                is_active=True
            ).order_by('id')
            
            if limit:
                suscriptores = suscriptores[:limit]
                self.stdout.write(f"⚠️  Límite aplicado: solo primeros {limit} suscriptores")
        
        total = suscriptores.count()
        
        if total == 0:
            self.stdout.write(self.style.ERROR('❌ No hay suscriptores activos para enviar'))
            return
        
        self.stdout.write(f"\n📊 Total de destinatarios: {total}")
        self.stdout.write(f"📦 Tamaño de lote: {batch_size} emails")
        self.stdout.write(f"⏱️  Delay entre lotes: {batch_delay // 60} minutos\n")
        
        # Estimación de tiempo
        total_batches = (total + batch_size - 1) // batch_size
        estimated_minutes = (total_batches - 1) * (batch_delay // 60)
        self.stdout.write(f"⏰ Tiempo estimado: ~{estimated_minutes} minutos ({estimated_minutes // 60}h {estimated_minutes % 60}m)\n")
        
        if not dry_run and not test_email:
            confirm = input(f"¿Confirmas envío a {total} suscriptores? (yes/no): ")
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.WARNING('❌ Envío cancelado'))
                return
        
        # 2. Enviar en lotes
        sent_count = 0
        error_count = 0
        batch_number = 1
        
        for i, sub in enumerate(suscriptores):
            try:
                # Renderizar email personalizado
                html_content = render_to_string(
                    'emails/giftcard_digital_launch.html',
                    {
                        'nombre': sub.first_name or 'Cliente Aremko',
                        'email': sub.email,
                    }
                )
                
                if not dry_run:
                    # Enviar email
                    email = EmailMultiAlternatives(
                        subject='🎁 Nuevas Gift Cards Digitales Aremko',
                        body='Este email requiere visualización HTML.',
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        to=[sub.email],
                    )
                    email.attach_alternative(html_content, "text/html")
                    email.send()
                    
                    # Registrar en CommunicationLog
                    CommunicationLog.objects.create(
                        cliente_id=None,  # NewsletterSubscriber puede no estar vinculado a Cliente
                        communication_type='EMAIL',
                        message_type='PROMOTIONAL',
                        subject='🎁 Nuevas Gift Cards Digitales Aremko',
                        content=html_content[:500],  # Primeros 500 chars
                        destination=sub.email,
                        status='SENT',
                        sent_at=timezone.now(),
                    )
                    
                    sent_count += 1
                else:
                    # En dry-run solo contamos
                    sent_count += 1
                
                # Mostrar progreso
                if (i + 1) % 10 == 0 or (i + 1) == total:
                    self.stdout.write(
                        f"  📨 Procesados: {i + 1}/{total} "
                        f"(✅ {sent_count} | ❌ {error_count})"
                    )
                
                # Rate limiting por lote
                if (i + 1) % batch_size == 0 and (i + 1) < total:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"\n✅ Lote {batch_number} completado ({batch_size} emails)"
                        )
                    )
                    batch_number += 1
                    
                    if not dry_run:
                        minutes = batch_delay // 60
                        self.stdout.write(
                            self.style.WARNING(
                                f"⏸️  Esperando {minutes} minutos antes del próximo lote..."
                            )
                        )
                        time.sleep(batch_delay)
                    else:
                        self.stdout.write("⏸️  (En dry-run no se espera)\n")
            
            except Exception as e:
                error_count += 1
                logger.error(f"Error enviando a {sub.email}: {e}")
                self.stdout.write(
                    self.style.ERROR(f"  ❌ Error enviando a {sub.email}: {str(e)}")
                )
        
        # Resumen final
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS('✅ CAMPAÑA COMPLETADA'))
        self.stdout.write('=' * 60)
        self.stdout.write(f"📊 Total procesados: {sent_count + error_count}")
        self.stdout.write(self.style.SUCCESS(f"✅ Enviados exitosamente: {sent_count}"))
        if error_count > 0:
            self.stdout.write(self.style.ERROR(f"❌ Errores: {error_count}"))
        self.stdout.write('=' * 60)
