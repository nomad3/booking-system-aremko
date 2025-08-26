# -*- coding: utf-8 -*-
"""
Management command para crear plantillas SMS predefinidas
Uso: python manage.py create_default_sms_templates
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from ventas.models import SMSTemplate


class Command(BaseCommand):
    help = 'Crea plantillas SMS predefinidas para diferentes tipos de comunicación'

    def handle(self, *args, **options):
        self.stdout.write("📱 Creando plantillas SMS predefinidas...")
        
        templates = [
            {
                'name': 'Confirmación Reserva Estándar',
                'message_type': 'BOOKING_CONFIRMATION',
                'content': '✅ ¡Reserva confirmada! Te esperamos el {fecha} a las {hora} para {servicio}. ¡Nos emociona verte! - Aremko',
                'max_uses_per_client_per_day': 3,
                'max_uses_per_client_per_month': 10
            },
            {
                'name': 'Recordatorio Cita 24h',
                'message_type': 'BOOKING_REMINDER',
                'content': '🔔 Recordatorio: Mañana {fecha} a las {hora} tienes tu cita para {servicio}. ¡Te esperamos! - Aremko',
                'max_uses_per_client_per_day': 2,
                'max_uses_per_client_per_month': 8
            },
            {
                'name': 'Cumpleaños Especial',
                'message_type': 'BIRTHDAY',
                'content': '🎉 ¡Feliz cumpleaños {nombre}! En tu día especial queremos desearte lo mejor. ¡Tienes un 20% de descuento esperándote! - Aremko',
                'max_uses_per_client_per_day': 1,
                'max_uses_per_client_per_month': 1
            },
            {
                'name': 'Cumpleaños VIP',
                'message_type': 'BIRTHDAY',
                'content': '👑🎂 ¡Feliz cumpleaños {nombre}! Como cliente VIP, tienes una sorpresa especial esperándote. ¡Ven a celebrar con nosotros! - Aremko',
                'max_uses_per_client_per_day': 1,
                'max_uses_per_client_per_month': 1
            },
            {
                'name': 'Encuesta Satisfacción',
                'message_type': 'SATISFACTION_SURVEY',
                'content': '⭐ Hola {nombre}, ¿cómo fue tu experiencia con {servicio}? Tu opinión nos ayuda a mejorar. Compártela aquí: {link} - Aremko',
                'max_uses_per_client_per_day': 1,
                'max_uses_per_client_per_month': 3
            },
            {
                'name': 'Promoción Especial',
                'message_type': 'PROMOTIONAL',
                'content': '🎯 ¡Oferta especial para ti {nombre}! {descuento} en {servicio}. Válido hasta {fecha_limite}. Reserva: {link} - Aremko',
                'max_uses_per_client_per_day': 1,
                'max_uses_per_client_per_month': 2
            },
            {
                'name': 'Reactivación Cliente',
                'message_type': 'REACTIVATION',
                'content': '💙 Te extrañamos {nombre}. Como gesto especial, tienes 25% OFF en tu próxima visita. ¡Vuelve cuando gustes! - Aremko',
                'max_uses_per_client_per_day': 1,
                'max_uses_per_client_per_month': 1
            }
        ]
        
        created_count = 0
        updated_count = 0
        
        for template_data in templates:
            template, created = SMSTemplate.objects.get_or_create(
                name=template_data['name'],
                message_type=template_data['message_type'],
                defaults={
                    'content': template_data['content'],
                    'is_active': True,
                    'requires_approval': False,
                    'max_uses_per_client_per_day': template_data['max_uses_per_client_per_day'],
                    'max_uses_per_client_per_month': template_data['max_uses_per_client_per_month']
                }
            )
            
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f"✅ Creada: {template.name}")
                )
            else:
                # Actualizar contenido si es diferente
                if template.content != template_data['content']:
                    template.content = template_data['content']
                    template.max_uses_per_client_per_day = template_data['max_uses_per_client_per_day']
                    template.max_uses_per_client_per_month = template_data['max_uses_per_client_per_month']
                    template.save()
                    updated_count += 1
                    self.stdout.write(
                        self.style.WARNING(f"🔄 Actualizada: {template.name}")
                    )
                else:
                    self.stdout.write(
                        self.style.HTTP_INFO(f"ℹ️  Ya existe: {template.name}")
                    )
        
        self.stdout.write("\n" + "="*50)
        self.stdout.write(
            self.style.SUCCESS(
                f"🎉 Proceso completado:\n"
                f"   📱 {created_count} plantillas creadas\n"
                f"   🔄 {updated_count} plantillas actualizadas\n"
                f"   📋 {SMSTemplate.objects.count()} plantillas totales"
            )
        )
        
        # Mostrar guía de uso
        self.stdout.write("\n" + "="*50)
        self.stdout.write(self.style.HTTP_INFO("📖 GUÍA DE USO DE VARIABLES:"))
        self.stdout.write("""
Variables disponibles en plantillas:
• {nombre} - Nombre del cliente
• {apellido} - Apellido del cliente  
• {telefono} - Teléfono del cliente
• {servicio} - Nombre del servicio reservado
• {fecha} - Fecha de la reserva (DD/MM/YYYY)
• {hora} - Hora de la reserva (HH:MM)
• {link} - Enlace personalizado (para encuestas, reservas, etc.)
• {descuento} - Descripción del descuento ofrecido
• {fecha_limite} - Fecha límite de la promoción

Ejemplos de uso:
✅ Correcto: "Hola {nombre}, tu cita es el {fecha}"
❌ Incorrecto: "Hola [nombre], tu cita es el [fecha]"

Para editar plantillas:
1. Ve al Admin de Django → Plantillas SMS
2. Selecciona la plantilla a editar
3. Modifica el contenido usando las variables
4. Guarda los cambios
        """)
        
        self.stdout.write("\n" + "="*50)
        self.stdout.write(
            self.style.SUCCESS("✅ ¡Plantillas SMS listas para usar!")
        )