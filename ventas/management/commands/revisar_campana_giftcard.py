# -*- coding: utf-8 -*-
"""
Comando para revisar el estado de la campaña de giftcard
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from ventas.models import MailParaEnviar
import pytz


class Command(BaseCommand):
    help = "Revisa el estado actual de la campaña de giftcard"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("📊 ESTADO DE LA CAMPAÑA GIFTCARD"))
        
        # 1. Verificar hora actual
        chile_tz = pytz.timezone('America/Santiago')
        now_chile = timezone.now().astimezone(chile_tz)
        hour = now_chile.hour
        
        self.stdout.write(f"\n🕐 HORA ACTUAL (Chile): {now_chile.strftime('%Y-%m-%d %H:%M:%S')}")
        
        if 8 <= hour < 18:
            self.stdout.write(f"   ✅ Dentro del horario de envío (8:00-18:00)")
        else:
            self.stdout.write(f"   ⏰ Fuera del horario de envío (8:00-18:00)")
        
        # 2. Estadísticas de emails
        self.stdout.write(f"\n📧 ESTADÍSTICAS DE EMAILS:")
        
        # Total de emails en la campaña
        total_emails = MailParaEnviar.objects.filter(
            asunto__icontains='giftcard'
        ).count()
        
        # Emails pendientes
        emails_pendientes = MailParaEnviar.objects.filter(
            estado='PENDIENTE',
            asunto__icontains='giftcard'
        ).count()
        
        # Emails enviados
        emails_enviados = MailParaEnviar.objects.filter(
            estado='ENVIADO',
            asunto__icontains='giftcard'
        ).count()
        
        # Emails fallidos
        emails_fallidos = MailParaEnviar.objects.filter(
            estado='FALLIDO',
            asunto__icontains='giftcard'
        ).count()
        
        self.stdout.write(f"   📊 Total emails campaña: {total_emails}")
        self.stdout.write(f"   ⏳ Pendientes: {emails_pendientes}")
        self.stdout.write(f"   ✅ Enviados: {emails_enviados}")
        self.stdout.write(f"   ❌ Fallidos: {emails_fallidos}")
        
        # Progreso
        if total_emails > 0:
            progreso = (emails_enviados / total_emails) * 100
            self.stdout.write(f"   📈 Progreso: {progreso:.1f}%")
        
        # 3. Últimos 10 emails enviados
        self.stdout.write(f"\n📤 ÚLTIMOS 10 EMAILS ENVIADOS:")
        ultimos_enviados = MailParaEnviar.objects.filter(
            estado='ENVIADO',
            asunto__icontains='giftcard'
        ).order_by('-fecha_envio')[:10]
        
        if ultimos_enviados:
            for email in ultimos_enviados:
                fecha_envio = email.fecha_envio.astimezone(chile_tz) if email.fecha_envio else "N/A"
                self.stdout.write(f"   ✅ {email.email} - {email.nombre} - {fecha_envio}")
        else:
            self.stdout.write(f"   📭 No hay emails enviados aún")
        
        # 4. Próximos 5 emails pendientes
        self.stdout.write(f"\n⏳ PRÓXIMOS 5 EMAILS PENDIENTES:")
        proximos_pendientes = MailParaEnviar.objects.filter(
            estado='PENDIENTE',
            asunto__icontains='giftcard'
        ).order_by('prioridad', 'creado_en')[:5]
        
        if proximos_pendientes:
            for email in proximos_pendientes:
                self.stdout.write(f"   ⏳ {email.email} - {email.nombre} - Prioridad: {email.prioridad}")
        else:
            self.stdout.write(f"   ✅ No hay emails pendientes")
        
        # 5. Emails fallidos (si los hay)
        if emails_fallidos > 0:
            self.stdout.write(f"\n❌ EMAILS FALLIDOS:")
            fallidos = MailParaEnviar.objects.filter(
                estado='FALLIDO',
                asunto__icontains='giftcard'
            ).order_by('-fecha_envio')[:5]
            
            for email in fallidos:
                observaciones = email.observaciones or "Sin detalles"
                self.stdout.write(f"   ❌ {email.email} - {email.nombre} - Error: {observaciones}")
        
        # 6. Recomendaciones
        self.stdout.write(f"\n💡 RECOMENDACIONES:")
        
        if emails_pendientes == 0:
            self.stdout.write(f"   🎉 ¡Campaña completada! Todos los emails han sido procesados.")
        elif emails_pendientes > 0 and 8 <= hour < 18:
            self.stdout.write(f"   ⚡ La campaña está activa. Se enviarán 2 emails cada 6 minutos.")
            tiempo_restante = (emails_pendientes / 2) * 6  # minutos
            horas = tiempo_restante // 60
            minutos = tiempo_restante % 60
            self.stdout.write(f"   ⏱️  Tiempo estimado restante: {int(horas)}h {int(minutos)}m")
        elif emails_pendientes > 0 and (hour < 8 or hour >= 18):
            self.stdout.write(f"   ⏰ Los emails se reanudarán mañana a las 8:00 AM.")
        
        if emails_fallidos > 0:
            self.stdout.write(f"   ⚠️  Revisar emails fallidos para reenvío manual.")
        
        self.stdout.write(f"\n✅ Revisión completada")