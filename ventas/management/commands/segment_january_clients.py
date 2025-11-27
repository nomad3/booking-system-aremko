# -*- coding: utf-8 -*-
"""
Comando para segmentar clientes que visitaron en un mes/año específico
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, date
from ventas.models import Cliente, VentaReserva, ReservaServicio
from django.db import models
from django.db.models import Q, Count, Sum
import calendar


class Command(BaseCommand):
    help = "Identifica y segmenta clientes que visitaron en un mes/año específico"

    def add_arguments(self, parser):
        parser.add_argument('--year', type=int, default=2025, help='Año a analizar (default: 2025)')
        parser.add_argument('--month', type=int, default=1, help='Mes a analizar (1-12, default: 1)')
        parser.add_argument('--export-csv', action='store_true', help='Exportar lista a CSV')
        parser.add_argument('--create-campaign', action='store_true', help='Crear campaña automáticamente')
        parser.add_argument('--giftcard-amount', type=int, default=15000, help='Monto de la giftcard (default: 15000)')

    def handle(self, *args, **options):
        year = options.get('year', 2025)
        month = options.get('month', 1)
        giftcard_amount = options.get('giftcard_amount', 15000)
        
        # Validar mes
        if month < 1 or month > 12:
            self.stdout.write(self.style.ERROR("❌ El mes debe estar entre 1 y 12"))
            return
        
        # Obtener nombre del mes
        month_name = calendar.month_name[month]
        
        self.stdout.write(f"🔍 Buscando clientes que visitaron en {month_name} {year}...")
        
        # Definir rango del mes/año
        month_start = date(year, month, 1)
        # Obtener el último día del mes
        last_day = calendar.monthrange(year, month)[1]
        month_end = date(year, month, last_day)
        
        # Buscar clientes que tuvieron reservas en el mes/año especificado
        clientes_mes = Cliente.objects.filter(
            ventareserva__reservaservicios__fecha_agendamiento__range=(month_start, month_end)
        ).annotate(
            num_visitas_mes=Count('ventareserva__reservaservicios', 
                                filter=Q(ventareserva__reservaservicios__fecha_agendamiento__range=(month_start, month_end))),
            gasto_mes=Sum('ventareserva__total', 
                        filter=Q(ventareserva__reservaservicios__fecha_agendamiento__range=(month_start, month_end))),
            ultima_visita_mes=models.Max('ventareserva__reservaservicios__fecha_agendamiento',
                                       filter=Q(ventareserva__reservaservicios__fecha_agendamiento__range=(month_start, month_end)))
        ).distinct()
        
        # Filtrar solo clientes con email válido
        clientes_con_email = clientes_mes.filter(
            email__isnull=False,
            email__gt=''
        ).exclude(email='')
        
        self.stdout.write(f"📊 Estadísticas de {month_name} {year}:")
        self.stdout.write(f"   Total clientes que visitaron: {clientes_mes.count()}")
        self.stdout.write(f"   Clientes con email válido: {clientes_con_email.count()}")
        
        if clientes_con_email.count() > 0:
            gasto_promedio = clientes_con_email.aggregate(
                avg_gasto=models.Avg('gasto_mes')
            )['avg_gasto'] or 0
            
            self.stdout.write(f"   Gasto promedio en {month_name}: ${gasto_promedio:,.0f}")
            
            # Mostrar top 10 clientes
            self.stdout.write(f"\n🏆 Top 10 clientes de {month_name} {year}:")
            top_clientes = clientes_con_email.order_by('-gasto_mes')[:10]
            
            for i, cliente in enumerate(top_clientes, 1):
                self.stdout.write(f"   {i:2d}. {cliente.nombre} - ${cliente.gasto_mes or 0:,.0f} - {cliente.email}")
        
        # Exportar CSV si se solicita
        if options.get('export_csv'):
            self.export_to_csv(clientes_con_email, month_name, year)
        
        # Crear campaña si se solicita
        if options.get('create_campaign'):
            self.create_campaign(clientes_con_email, month_name, year, giftcard_amount)
        
        self.stdout.write(f"\n✅ Segmentación completada: {clientes_con_email.count()} clientes listos para campaña")

    def export_to_csv(self, clientes, month_name, year):
        """Exporta la lista de clientes a CSV"""
        import csv
        from django.http import HttpResponse
        
        filename = f"clientes_{month_name.lower()}_{year}.csv"
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        writer = csv.writer(response)
        writer.writerow(['Nombre', 'Email', 'Teléfono', f'Visitas {month_name}', f'Gasto {month_name}', 'Última Visita'])
        
        for cliente in clientes:
            writer.writerow([
                cliente.nombre,
                cliente.email,
                cliente.telefono,
                cliente.num_visitas_mes,
                cliente.gasto_mes or 0,
                cliente.ultima_visita_mes.strftime('%d/%m/%Y') if cliente.ultima_visita_mes else ''
            ])
        
        # Guardar archivo localmente
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            f.write(response.content.decode('utf-8'))
        
        self.stdout.write(f"📄 CSV exportado: {filename}")

    def create_campaign(self, clientes, month_name, year, giftcard_amount):
        """Crea una campaña automáticamente"""
        from ventas.models import Campaign
        
        # Crear campaña
        campaign_name = f"Giftcard Septiembre - Clientes {month_name} {year}"
        campaign, created = Campaign.objects.get_or_create(
            name=campaign_name,
            defaults={
                'description': f'Campaña especial para clientes que visitaron en {month_name} {year}, ofreciendo giftcard de ${giftcard_amount:,} para usar en septiembre',
                'status': 'Planning',
                'goal': f'Reactivar clientes de {month_name} con oferta especial de giftcard',
                'email_subject_template': f'🎁 ¡Tu giftcard de ${giftcard_amount:,} te espera en Aremko!',
                'email_body_template': self.get_email_template(giftcard_amount),
                'target_min_visits': 1,  # Al menos 1 visita en el mes
                'target_min_spend': 0    # Sin restricción de gasto mínimo
            }
        )
        
        if created:
            self.stdout.write(f"✅ Campaña creada: {campaign.name}")
        else:
            self.stdout.write(f"ℹ️ Campaña ya existe: {campaign.name}")
        
        return campaign

    def get_email_template(self, giftcard_amount=15000):
        """Retorna la plantilla de email para la campaña"""
        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Giftcard Especial - Aremko Hotel Spa</title>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
        .content {{ background: #f8f9fa; padding: 30px; border-radius: 0 0 10px 10px; }}
        .giftcard {{ background: #fff; border: 3px dashed #28a745; padding: 20px; margin: 20px 0; text-align: center; border-radius: 10px; }}
        .giftcard-amount {{ font-size: 2.5em; font-weight: bold; color: #28a745; }}
        .cta-button {{ background: #28a745; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; display: inline-block; margin: 20px 0; font-weight: bold; }}
        .footer {{ margin-top: 40px; padding-top: 30px; border-top: 2px solid #e0e0e0; text-align: center; color: #666; font-size: 13px; line-height: 1.6; }}
        .highlight {{ background: #fff3cd; padding: 15px; border-left: 4px solid #ffc107; margin: 20px 0; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🏨 Aremko Hotel Spa</h1>
            <h2>¡Hola {nombre_cliente}!</h2>
        </div>
        
        <div class="content">
            <p>Esperamos que hayas disfrutado tu visita en enero. ¡Tenemos una sorpresa especial para ti!</p>
            
            <div class="giftcard">
                <h3>🎁 Tu Giftcard Especial</h3>
                <div class="giftcard-amount">${giftcard_amount:,}</div>
                <p><strong>Para usar durante todo septiembre 2025</strong></p>
            </div>
            
            <div class="highlight">
                <h4>✨ ¿Cómo funciona?</h4>
                <ul>
                    <li>Válida para cualquier servicio de nuestro spa</li>
                    <li>Se puede combinar con otras promociones</li>
                    <li>No tiene restricciones de horario</li>
                    <li>Válida solo durante septiembre 2025</li>
                </ul>
            </div>
            
            <p>Para reclamar tu giftcard, simplemente:</p>
            <ol>
                <li>Reserva tu cita para septiembre</li>
                <li>Menciona "Giftcard Enero 2025" al hacer tu reserva</li>
                <li>¡Disfruta de $15.000 de descuento!</li>
            </ol>
            
            <div style="text-align: center;">
                <a href="https://www.aremko.cl" class="cta-button">
                    🗓️ Reservar Ahora
                </a>
            </div>
            
            <p><strong>Servicios disponibles:</strong></p>
            <ul>
                <li>💆‍♀️ Masajes relajantes y descontracturantes</li>
                <li>🛁 Tina Tronador con vista al lago</li>
                <li>🏠 Cabañas privadas</li>
                <li>🧘‍♀️ Tratamientos de bienestar</li>
            </ul>
            
            <p>¡No dejes pasar esta oportunidad especial! Tu bienestar nos importa y queremos verte de vuelta.</p>
            
            <p>Con cariño,<br>
            <strong>El equipo de Aremko Hotel Spa</strong></p>
        </div>
        
        <!-- Footer Legal Compliant con SendGrid -->
        <div class="footer">
            <p style="margin: 10px 0;">
                <strong>Aremko Spa</strong><br>
                Rio Pescado Km 4<br>
                Puerto Varas, Región de Los Lagos<br>
                Chile
            </p>
            <p style="margin: 15px 0;">
                📞 +56 9 5790 2525 | 📧 ventas@aremko.cl
            </p>
            <p style="margin: 15px 0; font-size: 12px;">
                Estás recibiendo este correo porque eres cliente de Aremko o te suscribiste a nuestro boletín.
            </p>
            <p style="margin: 15px 0;">
                <a href="https://www.aremko.cl/privacy-policy/" style="color: #667eea; text-decoration: none; margin: 0 10px;">Política de Privacidad</a> | 
                <a href="https://www.aremko.cl/unsubscribe/{email}/" style="color: #667eea; text-decoration: none; margin: 0 10px;">Darse de baja</a>
            </p>
        </div>
    </div>
</body>
</html>
"""