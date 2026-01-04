# -*- coding: utf-8 -*-
"""
Management command para verificar el estado de las campañas de email
"""

from django.core.management.base import BaseCommand
from ventas.models import EmailCampaign, EmailRecipient
from django.db.models import Count, Q


class Command(BaseCommand):
    help = 'Verifica el estado actual de las campañas de email'

    def handle(self, *args, **options):
        self.stdout.write("=" * 80)
        self.stdout.write(self.style.SUCCESS("📊 ESTADO ACTUAL DE CAMPAÑAS DE EMAIL"))
        self.stdout.write("=" * 80)

        # Obtener todas las campañas
        campanas = EmailCampaign.objects.all().order_by('-created_at')

        if not campanas.exists():
            self.stdout.write("\n⚠️ No hay campañas creadas")
            return

        for campana in campanas:
            self.stdout.write(f"\n📧 Campaña: {campana.name}")
            self.stdout.write(f"   ID: {campana.id}")
            self.stdout.write(f"   Estado: {campana.get_status_display()}")
            self.stdout.write(f"   Creada: {campana.created_at.strftime('%Y-%m-%d %H:%M')}")

            # Estadísticas de recipients
            recipients_stats = campana.recipients.aggregate(
                total=Count('id'),
                pending=Count('id', filter=Q(status='pending')),
                sent=Count('id', filter=Q(status='sent')),
                failed=Count('id', filter=Q(status='failed')),
                disabled=Count('id', filter=Q(send_enabled=False))
            )

            total = recipients_stats['total']
            pending = recipients_stats['pending']
            sent = recipients_stats['sent']
            failed = recipients_stats['failed']
            disabled = recipients_stats['disabled']

            self.stdout.write(f"\n   📊 Destinatarios:")
            self.stdout.write(f"      Total: {total}")
            self.stdout.write(f"      ✅ Enviados: {sent} ({(sent/total*100) if total > 0 else 0:.1f}%)")
            self.stdout.write(f"      ⏳ Pendientes: {pending} ({(pending/total*100) if total > 0 else 0:.1f}%)")
            self.stdout.write(f"      ❌ Fallidos: {failed}")
            self.stdout.write(f"      🚫 Deshabilitados: {disabled}")

            # Configuración de envío
            if campana.schedule_config:
                batch_size = campana.schedule_config.get('batch_size', 5)
                interval = campana.schedule_config.get('interval_minutes', 6)
                start_time = campana.schedule_config.get('start_time', '08:00')
                end_time = campana.schedule_config.get('end_time', '21:00')

                self.stdout.write(f"\n   ⚙️ Configuración:")
                self.stdout.write(f"      Lote: {batch_size} emails")
                self.stdout.write(f"      Intervalo: {interval} minutos")
                self.stdout.write(f"      Horario: {start_time} - {end_time}")

            # Estimación de tiempo restante
            if pending > 0 and campana.schedule_config:
                batch_size = campana.schedule_config.get('batch_size', 5)
                interval = campana.schedule_config.get('interval_minutes', 6)

                lotes_restantes = (pending + batch_size - 1) // batch_size  # Round up
                minutos_restantes = lotes_restantes * interval
                horas_restantes = minutos_restantes / 60

                self.stdout.write(f"\n   ⏱️ Estimación:")
                self.stdout.write(f"      Lotes restantes: {lotes_restantes}")
                self.stdout.write(f"      Tiempo estimado: ~{horas_restantes:.1f} horas ({minutos_restantes:.0f} min)")

                if campana.status == 'sending':
                    self.stdout.write(self.style.SUCCESS(f"\n   ✅ El cron job continuará enviando automáticamente"))
                elif campana.status == 'ready':
                    self.stdout.write(self.style.WARNING(f"\n   ⚠️ Campaña lista pero no iniciada. El cron la iniciará en el próximo ciclo"))
                elif campana.status == 'paused':
                    self.stdout.write(self.style.WARNING(f"\n   ⏸️ Campaña pausada. Cambiar estado a 'ready' o 'sending' para reanudar"))

        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("🔄 CRON JOB"))
        self.stdout.write("=" * 80)

        # Verificar campañas que el cron procesará
        campanas_activas = EmailCampaign.objects.filter(status__in=['ready', 'sending'])
        count = campanas_activas.count()

        if count > 0:
            self.stdout.write(self.style.SUCCESS(f"\n✅ El cron job procesará {count} campaña(s) en el próximo ciclo (cada 5 min)"))
            for camp in campanas_activas:
                pending_count = camp.recipients.filter(status='pending', send_enabled=True).count()
                self.stdout.write(f"   • {camp.name}: {pending_count} emails pendientes")
        else:
            self.stdout.write(self.style.WARNING(f"\n⚠️ No hay campañas activas (status='ready' o 'sending')"))
            self.stdout.write(f"   El cron job esperará hasta que haya campañas activas")

        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("📝 PRÓXIMOS PASOS"))
        self.stdout.write("=" * 80)
        self.stdout.write("\n1. Monitorear logs de Render:")
        self.stdout.write("   Buscar: '✅ Cron enviar_campanas_email iniciado'")
        self.stdout.write("\n2. Ver progreso en Django Admin:")
        self.stdout.write("   /admin/ventas/emailcampaign/")
        self.stdout.write("\n3. Si necesitas pausar:")
        self.stdout.write("   Cambiar estado de campaña a 'paused'")
        self.stdout.write("\n4. Si quieres acelerar:")
        self.stdout.write("   Reducir 'interval_minutes' en schedule_config")
        self.stdout.write("")
