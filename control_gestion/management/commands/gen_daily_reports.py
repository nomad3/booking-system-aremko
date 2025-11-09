"""
Comando: Generar reporte diario con resumen IA

Este comando debe ejecutarse 2 veces al día (09:00 y 18:00) para generar
reportes del equipo con resumen generado por IA.

Uso:
    python manage.py gen_daily_reports

    # Con opciones:
    python manage.py gen_daily_reports --momento=matutino  # 09:00 AM
    python manage.py gen_daily_reports --momento=vespertino  # 18:00 PM

Cron recomendado:
    5 9 * * * cd /path/to/proyecto && python manage.py gen_daily_reports --momento=matutino
    0 18 * * * cd /path/to/proyecto && python manage.py gen_daily_reports --momento=vespertino
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from control_gestion.models import Task, TaskState, DailyReport, Swimlane
from control_gestion import ai
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Genera reporte diario con redacción IA (para enviar a WhatsApp/Email)"

    def add_arguments(self, parser):
        parser.add_argument(
            '--momento',
            type=str,
            choices=['matutino', 'vespertino'],
            default='vespertino',
            help='Momento del día: matutino (09:00) o vespertino (18:00)'
        )

    def handle(self, *args, **options):
        momento = options['momento']
        today = timezone.localdate()
        
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS(
            f"📊 REPORTE DIARIO - {momento.upper()}"
        ))
        self.stdout.write("=" * 80 + "\n")
        
        self.stdout.write(f"📅 Fecha: {today.strftime('%A, %d de %B %Y')}")
        self.stdout.write(f"🕐 Momento: {momento}\n")
        
        # Recolectar estadísticas del día
        self.stdout.write("─" * 80)
        self.stdout.write("📈 RECOLECTANDO ESTADÍSTICAS")
        self.stdout.write("─" * 80 + "\n")
        
        # Tareas completadas hoy
        done_today = Task.objects.filter(
            state=TaskState.DONE,
            updated_at__date=today
        ).count()
        
        # Tareas en curso (cualquier fecha, estado actual)
        in_progress = Task.objects.filter(state=TaskState.IN_PROGRESS).count()
        
        # Tareas bloqueadas (cualquier fecha, estado actual)
        blocked = Task.objects.filter(state=TaskState.BLOCKED).count()
        
        # Tareas pendientes (cualquier fecha, estado actual)
        backlog = Task.objects.filter(state=TaskState.BACKLOG).count()
        
        # Por área (swimlane)
        por_area = {}
        for lane in [
            Swimlane.COMERCIAL,
            Swimlane.ATENCION,
            Swimlane.OPERACION,
            Swimlane.RECEPCION,
            Swimlane.SUPERVISION,
            Swimlane.MUCAMA
        ]:
            por_area[lane] = {
                "nombre": dict(Swimlane.choices)[lane],
                "hechas": Task.objects.filter(
                    state=TaskState.DONE,
                    updated_at__date=today,
                    swimlane=lane
                ).count(),
                "pendientes": Task.objects.exclude(state=TaskState.DONE).filter(
                    swimlane=lane
                ).count(),
            }
        
        # Mostrar estadísticas
        self.stdout.write(f"  ✅ Completadas hoy: {done_today}")
        self.stdout.write(f"  ⏳ En curso: {in_progress}")
        self.stdout.write(f"  🚫 Bloqueadas: {blocked}")
        self.stdout.write(f"  📋 Pendientes: {backlog}")
        
        self.stdout.write(f"\n  📊 Por área:")
        for lane_key, data in por_area.items():
            if data['hechas'] > 0 or data['pendientes'] > 0:
                self.stdout.write(
                    f"     • {data['nombre']}: "
                    f"{data['hechas']} hechas, {data['pendientes']} pendientes"
                )
        
        # Preparar datos para IA
        stats = {
            "fecha": str(today),
            "momento": momento,
            "hechas": done_today,
            "en_curso": in_progress,
            "bloqueadas": blocked,
            "pendientes": backlog,
            "por_area": {
                data['nombre']: {
                    "hechas": data['hechas'],
                    "pendientes": data['pendientes']
                }
                for lane_key, data in por_area.items()
            }
        }
        
        # Generar resumen con IA
        self.stdout.write("\n" + "─" * 80)
        self.stdout.write("🤖 GENERANDO RESUMEN CON IA")
        self.stdout.write("─" * 80 + "\n")
        
        try:
            summary = ai.summarize_day(stats)
            
            # Guardar reporte
            report = DailyReport.objects.create(
                date=today,
                summary=summary
            )
            
            self.stdout.write(self.style.SUCCESS("✅ Resumen generado con IA\n"))
            
            # Mostrar resumen
            self.stdout.write("─" * 80)
            self.stdout.write("📄 RESUMEN:")
            self.stdout.write("─" * 80 + "\n")
            self.stdout.write(summary)
            self.stdout.write("\n" + "─" * 80 + "\n")
            
            # Información del reporte
            self.stdout.write(f"💾 Reporte guardado con ID: {report.id}")
            self.stdout.write(f"📅 Fecha: {report.date}")
            self.stdout.write(f"🕐 Generado: {report.generated_at.strftime('%H:%M:%S')}")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(
                f"❌ Error generando resumen IA: {str(e)}"
            ))
            logger.error(f"Error en gen_daily_reports: {str(e)}", exc_info=True)
        
        # Resumen final
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("✅ Reporte diario generado"))
        self.stdout.write("=" * 80 + "\n")
        
        # Integración con n8n/WhatsApp
        self.stdout.write(self.style.WARNING("📌 PRÓXIMOS PASOS:"))
        self.stdout.write("   • Integrar con n8n para envío automático por WhatsApp")
        self.stdout.write("   • Configurar workflow de n8n para leer DailyReport")
        self.stdout.write(f"   • API endpoint: /admin/control_gestion/dailyreport/{report.id if 'report' in locals() else 'X'}/\n")

