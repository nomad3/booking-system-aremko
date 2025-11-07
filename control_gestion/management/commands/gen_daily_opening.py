"""
Comando: Generar tareas rutinarias de apertura/operación/cierre

Este comando debe ejecutarse diariamente (excepto martes) para crear
tareas rutinarias operativas del spa.

Uso:
    python manage.py gen_daily_opening

    # Con opciones:
    python manage.py gen_daily_opening --dry-run  # Solo simular
    python manage.py gen_daily_opening --force     # Forzar incluso si ya existen

Cron recomendado:
    0 9 * * * cd /path/to/proyecto && python manage.py gen_daily_opening
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model
from control_gestion.models import Task, Swimlane, TaskState, TaskSource, TaskTemplate
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


class Command(BaseCommand):
    help = "Genera tareas rutinarias de apertura/monitoreo/cierre (excepto martes - día de mantención mayor)"

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simular sin crear tareas (solo mostrar)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Forzar creación incluso si ya existen tareas del día'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        force = options['force']
        
        today = timezone.localdate()
        
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("🏢 GENERACIÓN DE TAREAS RUTINARIAS DIARIAS"))
        self.stdout.write("=" * 80 + "\n")
        
        self.stdout.write(f"📅 Fecha: {today.strftime('%A, %d de %B %Y')}")
        
        es_martes = today.weekday() == 1  # 0=lunes, 1=martes
        
        if es_martes:
            self.stdout.write(self.style.WARNING(
                "\n⚠️  MARTES detectado - Día de MANTENCIONES MAYORES"
            ))
            self.stdout.write(
                "   Se generan SOLO tareas especiales de martes (mantenciones profundas)\n"
            )
        
        # Verificar si ya existen tareas rutinarias hoy
        tareas_hoy = Task.objects.filter(
            created_at__date=today,
            source=TaskSource.RUTINA
        ).count()
        
        if tareas_hoy > 0 and not force:
            self.stdout.write(self.style.WARNING(
                f"\n⚠️  Ya existen {tareas_hoy} tareas rutinarias creadas hoy."
            ))
            self.stdout.write(
                "   Usa --force para crear de todas formas.\n"
            )
            return
        
        if dry_run:
            self.stdout.write(self.style.WARNING("\n⚠️  MODO DRY-RUN: No se crearán tareas\n"))
        
        # Obtener plantillas activas que aplican para hoy
        plantillas = TaskTemplate.objects.filter(activa=True)
        
        self.stdout.write(f"\n📋 Total plantillas configuradas: {plantillas.count()}")
        
        # Filtrar las que aplican hoy
        plantillas_hoy = [p for p in plantillas if p.aplica_hoy()]
        
        if not plantillas_hoy:
            self.stdout.write(self.style.WARNING(
                "\n⚠️  No hay plantillas configuradas para hoy"
            ))
            self.stdout.write(
                "   Configura plantillas en: Admin → Plantillas de Tareas Recurrentes\n"
            )
            return
        
        self.stdout.write(f"✅ Plantillas para hoy: {len(plantillas_hoy)}")
        
        if es_martes:
            martes_count = sum(1 for p in plantillas_hoy if p.solo_martes)
            self.stdout.write(f"   (Solo tareas de martes: {martes_count})\n")
        
        # Generar tareas
        self.stdout.write("\n" + "─" * 80)
        self.stdout.write("📝 TAREAS A CREAR DESDE PLANTILLAS:")
        self.stdout.write("─" * 80 + "\n")
        
        created_count = 0
        
        for template in plantillas_hoy:
            self.stdout.write(
                f"  • [{template.get_swimlane_display()}] {template.title_template}"
            )
            
            # Mostrar a quién se asignará
            if template.asignar_a_usuario:
                asignado = template.asignar_a_usuario.username
            elif template.asignar_a_grupo:
                user = User.objects.filter(groups__name=template.asignar_a_grupo).first()
                asignado = user.username if user else f"Grupo {template.asignar_a_grupo} (sin usuarios)"
            else:
                asignado = "Sin asignar"
            
            self.stdout.write(f"    Responsable: {asignado}")
            
            if not dry_run:
                task = template.generar_tarea(fecha=today)
                if task:
                    created_count += 1
                    self.stdout.write(self.style.SUCCESS("      ✅ Creada"))
                else:
                    self.stdout.write(self.style.WARNING("      ⚠️ No se pudo crear"))
            else:
                self.stdout.write("      [DRY-RUN]")
            
            self.stdout.write("")
        
        # Resumen final
        self.stdout.write("=" * 80)
        if not dry_run:
            self.stdout.write(self.style.SUCCESS(
                f"✅ {created_count} tareas rutinarias creadas exitosamente"
            ))
        else:
            self.stdout.write(self.style.WARNING(
                "⚠️  MODO DRY-RUN: No se crearon tareas"
            ))
        self.stdout.write("=" * 80 + "\n")
        
        # Notas importantes
        self.stdout.write(self.style.WARNING("📌 NOTAS IMPORTANTES:"))
        self.stdout.write("   • Este comando debe ejecutarse diariamente (excepto martes)")
        self.stdout.write("   • Martes = día de mantenciones mayores (sin rutinas)")
        self.stdout.write("   • Recomendado: Configurar en cron a las 09:00 AM")
        self.stdout.write("   • Cron: 0 9 * * * python manage.py gen_daily_opening\n")

