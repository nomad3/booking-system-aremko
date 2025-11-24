# -*- coding: utf-8 -*-
"""
Comando para inicializar el template de email por defecto
"""

from django.core.management.base import BaseCommand
from ventas.models import CampaignEmailTemplate


class Command(BaseCommand):
    help = 'Inicializa el template de email por defecto para campañas'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=== INICIALIZANDO TEMPLATE DE EMAIL ==='))

        # Contenido del template proporcionado por el usuario
        subject = "¡Hola {nombre_cliente}, tenemos una buena noticia que darte desde Aremko"

        body = '''<div style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
      <h2 style="color: #417690;">¡Hola {nombre_cliente}!</h2>

      <p>Espero que te encuentres muy bien. Nos llena de alegría recordar las visitas a nuestro spa. Cada visita tuya nos ha
   permitido conocerte mejor y saber lo que más te hace feliz.</p>

      <p>En consecuencia, queremos sorprenderte con la siguiente propuesta:</p>

      <div style="background-color: #f0f8ff; padding: 20px; border-left: 4px solid #417690; margin: 20px 0;">
          <h3 style="margin-top: 0; color: #417690;">✨ Invitación exclusiva para ti</h3>
          <p><strong>Alojamiento de cortesía</strong> al reservar nuestro paquete, solo cancela:</p>
          <ul>
              <li>Desayuno</li>
              <li>Tinas de agua caliente</li>
              <li>Masajes</li>
          </ul>
          <p>Una experiencia limitada que creamos para nuestros clientes más especiales, como tú.</p>
      </div>

      <p><strong>📱 Reservar por WhatsApp:</strong> <a href="https://wa.me/56957902525" style="color:
  #417690;">+56957902525</a></p>

      <p><em>Estos beneficios son válidos durante todo el mes de noviembre de 2025.</em> Aprovecha esta oportunidad para
  regalarte el descanso que tanto necesitas antes de que termine el año.</p>

      <p>Sabes que para nosotros no eres un cliente más; <strong>eres parte de la familia Aremko</strong>. Nos encantaría
  volver a verte pronto disfrutando y relajándote como en tus visitas anteriores.</p>

      <p>Con cariño,<br>
      <strong>El equipo de Aremko</strong><br>
      Aguas Calientes & Spa Puerto Varas, Chile</p>
  </div>'''

        # Buscar si ya existe un template por defecto
        default_template = CampaignEmailTemplate.objects.filter(is_default=True).first()

        if default_template:
            # Actualizar el existente
            default_template.subject_template = subject
            default_template.body_template = body
            default_template.name = "Template Por Defecto - Promoción Aremko"
            default_template.description = "Template con formato HTML profesional para campañas de promoción"
            default_template.save()

            self.stdout.write(self.style.SUCCESS(f'✅ Template "{default_template.name}" actualizado exitosamente'))
        else:
            # Crear uno nuevo
            template = CampaignEmailTemplate.objects.create(
                name="Template Por Defecto - Promoción Aremko",
                description="Template con formato HTML profesional para campañas de promoción",
                subject_template=subject,
                body_template=body,
                is_default=True,
                is_active=True
            )

            self.stdout.write(self.style.SUCCESS(f'✅ Template "{template.name}" creado exitosamente'))

        self.stdout.write('')
        self.stdout.write('📝 Variables disponibles en el template:')
        self.stdout.write('   - {nombre_cliente}: Primer nombre del cliente')
        self.stdout.write('   - {gasto_total}: Gasto total histórico del cliente')
        self.stdout.write('')
        self.stdout.write('🎨 Puedes editar este template desde:')
        self.stdout.write('   Admin → Ventas → Templates de Email')
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=== TEMPLATE INICIALIZADO CORRECTAMENTE ==='))
