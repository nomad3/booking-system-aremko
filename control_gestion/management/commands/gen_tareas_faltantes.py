"""
Comando: Generar solo las tareas faltantes del día

Este comando revisa qué plantillas aplican para hoy y genera solo
las tareas que aún no existen, evitando duplicados.

Uso:
    python manage.py gen_tareas_faltantes
    python manage.py gen_tareas_faltantes --dry-run  # Solo simular
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from control_gestion.models_templates import TaskTemplate
from control_gestion.models import Task


class Command(BaseCommand):
    help = 'Genera solo las tareas faltantes del día (sin duplicar)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simular sin crear tareas (solo mostrar)'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        today = timezone.localdate()

        self.stdout.write("\n" + "="*80)
        self.stdout.write(self.style.SUCCESS(f"🔍 BUSCANDO TAREAS FALTANTES PARA HOY: {today.strftime('%d/%m/%Y')}"))
        self.stdout.write("="*80 + "\n")

        if dry_run:
            self.stdout.write(self.style.WARNING("🔍 MODO SIMULACIÓN (--dry-run)\n"))

        # Obtener todas las plantillas activas
        plantillas = TaskTemplate.objects.filter(activa=True)
        self.stdout.write(f"Total plantillas activas: {plantillas.count()}\n")

        tareas_creadas = 0
        tareas_existentes = 0
        no_aplican = 0

        for plantilla in plantillas:
            if plantilla.aplica_hoy():
                self.stdout.write(self.style.SUCCESS(f"✅ {plantilla.title_template}"))
                self.stdout.write(f"   Frecuencia: {plantilla.frecuencia or 'DIARIA (legacy)'}")
                self.stdout.write(f"   Días: {plantilla.get_dias_str()}")

                # Verificar si ya existe una tarea de esta plantilla hoy
                # Buscamos por título similar y fecha de creación
                titulo_base = plantilla.title_template.split('{')[0].strip()[:30]

                existe = Task.objects.filter(
                    title__icontains=titulo_base,
                    created_at__date=today,
                    source='RUTINA'
                ).exists()

                if existe:
                    self.stdout.write(self.style.WARNING("   ⏭️  Ya existe tarea de esta plantilla hoy"))
                    tareas_existentes += 1
                else:
                    if not dry_run:
                        # Generar tarea
                        tarea = plantilla.generar_tarea()
                        if tarea:
                            self.stdout.write(self.style.SUCCESS(f"   🎉 Tarea creada: ID={tarea.id}, Título: {tarea.title}"))
                            tareas_creadas += 1
                        else:
                            self.stdout.write(self.style.ERROR("   ⚠️  No se pudo crear"))
                    else:
                        self.stdout.write(self.style.SUCCESS("   🔍 Se crearía esta tarea"))
                        tareas_creadas += 1

                self.stdout.write("")  # Línea en blanco

            else:
                self.stdout.write(f"⏭️  {plantilla.title_template}")
                self.stdout.write(f"   No aplica hoy ({plantilla.get_dias_str()})")
                self.stdout.write("")  # Línea en blanco
                no_aplican += 1

        # Resumen
        self.stdout.write("\n" + "="*80)
        self.stdout.write(self.style.SUCCESS("RESUMEN:"))
        self.stdout.write("="*80)

        if dry_run:
            self.stdout.write(f"  🔍 Tareas que se crearían: {tareas_creadas}")
        else:
            self.stdout.write(f"  ✅ Tareas creadas: {tareas_creadas}")

        self.stdout.write(f"  ⏭️  Tareas que ya existían: {tareas_existentes}")
        self.stdout.write(f"  ❌ Plantillas que no aplican hoy: {no_aplican}")
        self.stdout.write("="*80 + "\n")

        if dry_run:
            self.stdout.write(self.style.WARNING("Para crear las tareas, ejecuta sin --dry-run:\n"))
            self.stdout.write(self.style.WARNING("python manage.py gen_tareas_faltantes\n"))
