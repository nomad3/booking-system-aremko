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
from control_gestion.models import Task, Swimlane, TaskState, TaskSource
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
        
        # Verificar si es martes (día de mantención mayor)
        if today.weekday() == 1:  # 0=lunes, 1=martes
            self.stdout.write(self.style.WARNING(
                "\n⚠️  MARTES detectado - Día de MANTENCIONES MAYORES"
            ))
            self.stdout.write(
                "   Las rutinas diarias NO se generan los martes."
            )
            self.stdout.write(
                "   El equipo se enfoca en mantenciones profundas y especiales.\n"
            )
            return
        
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
        
        # Obtener usuarios por grupo
        ops = User.objects.filter(groups__name="OPERACIONES").first()
        rx = User.objects.filter(groups__name="RECEPCION").first()
        
        if not ops:
            ops = User.objects.first()
            self.stdout.write(self.style.WARNING(
                "⚠️  Grupo 'OPERACIONES' no encontrado. Usando primer usuario."
            ))
        
        if not rx:
            rx = User.objects.first()
            self.stdout.write(self.style.WARNING(
                "⚠️  Grupo 'RECEPCION' no encontrado. Usando primer usuario."
            ))
        
        # Lista de tareas rutinarias a crear
        tareas_rutinarias = [
            {
                "title": "Apertura AM – limpieza y preparación tinas/salas",
                "description": (
                    "Rutina de apertura diaria:\n"
                    "• Sanitizar todas las tinas\n"
                    "• Llenar tinas según reservas del día\n"
                    "• Verificar temperatura (tinas y salas)\n"
                    "• Revisar niveles de estanques\n"
                    "• Verificar químicos y cloro\n"
                    "• Encender sistemas de calefacción"
                ),
                "swimlane": Swimlane.OPERACION,
                "owner": ops,
                "queue_position": 1
            },
            {
                "title": "Monitoreo °C 16–22h (cada hora)",
                "description": (
                    "Registro de temperatura cada hora:\n"
                    "• Medir temperatura a las 16:00, 17:00, 18:00, 19:00, 20:00, 21:00, 22:00\n"
                    "• Registrar en planilla de control\n"
                    "• Ajustar calefacción si es necesario\n"
                    "• Alertar si alguna tina está fuera de rango (36-38°C)"
                ),
                "swimlane": Swimlane.OPERACION,
                "owner": ops,
                "queue_position": 2
            },
            {
                "title": "Cierre PM – lavar filtros y apagar sistemas",
                "description": (
                    "Rutina de cierre diaria:\n"
                    "• Lavar filtros de bombas\n"
                    "• Apagar sistemas de calefacción\n"
                    "• Vaciar tinas según protocolo\n"
                    "• Verificar que todas las áreas estén cerradas\n"
                    "• Registrar observaciones del día"
                ),
                "swimlane": Swimlane.OPERACION,
                "owner": ops,
                "queue_position": 3
            },
            {
                "title": "Recepción lista 15:30 – limpieza/insumos/café",
                "description": (
                    "Preparación de recepción antes de horario de atención:\n"
                    "• Limpieza completa de recepción\n"
                    "• Verificar baños limpios\n"
                    "• Preparar cafetería (café, agua, insumos)\n"
                    "• Revisar stock de toallas\n"
                    "• Verificar sistema de reservas funcionando\n"
                    "• Lista antes de 15:30"
                ),
                "swimlane": Swimlane.RECEPCION,
                "owner": rx,
                "queue_position": 1
            },
        ]
        
        # Crear tareas
        self.stdout.write("\n" + "─" * 80)
        self.stdout.write("📝 TAREAS A CREAR:")
        self.stdout.write("─" * 80 + "\n")
        
        created_count = 0
        
        for tarea_data in tareas_rutinarias:
            self.stdout.write(
                f"  • [{tarea_data['swimlane']}] {tarea_data['title']}"
            )
            self.stdout.write(
                f"    Responsable: {tarea_data['owner'].username if tarea_data['owner'] else 'Sin asignar'}"
            )
            
            if not dry_run:
                Task.objects.create(
                    title=tarea_data['title'],
                    description=tarea_data['description'],
                    swimlane=tarea_data['swimlane'],
                    owner=tarea_data['owner'],
                    created_by=tarea_data['owner'],
                    state=TaskState.BACKLOG,
                    queue_position=tarea_data['queue_position'],
                    source=TaskSource.RUTINA
                )
                created_count += 1
                self.stdout.write(self.style.SUCCESS("      ✅ Creada"))
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

