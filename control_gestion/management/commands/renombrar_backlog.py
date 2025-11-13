#!/usr/bin/env python
"""
Comando para actualizar el nombre de estado 'Backlog' a 'Por Ejecutar'

Este comando NO cambia el valor interno del estado (sigue siendo "BACKLOG"),
solo actualiza la etiqueta visual que se muestra a los usuarios.

El cambio ya se hizo en models.py:
    BACKLOG = "BACKLOG", "Por Ejecutar"  # antes era "Backlog"

Este script es informativo y verifica que el cambio funcione correctamente.

Uso:
    python manage.py renombrar_backlog
"""

from django.core.management.base import BaseCommand
from control_gestion.models import Task, TaskState


class Command(BaseCommand):
    help = 'Verifica el cambio de "Backlog" a "Por Ejecutar" en el sistema'

    def handle(self, *args, **options):
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("✏️  VERIFICACIÓN: Cambio de 'Backlog' a 'Por Ejecutar'"))
        self.stdout.write("=" * 80 + "\n")

        # Contar tareas en estado BACKLOG
        tareas_backlog = Task.objects.filter(state=TaskState.BACKLOG)
        total = tareas_backlog.count()

        self.stdout.write(f"📊 Total de tareas en estado BACKLOG: {total}\n")

        if total == 0:
            self.stdout.write(self.style.WARNING(
                "ℹ️  No hay tareas en estado BACKLOG actualmente.\n"
            ))
        else:
            self.stdout.write("📋 Mostrando primeras 10 tareas:\n")
            for tarea in tareas_backlog[:10]:
                # Obtener el label del estado
                estado_label = tarea.get_state_display()

                self.stdout.write(
                    f"  • #{tarea.id} - {tarea.title[:50]} - Estado: {estado_label}"
                )

        # Verificar el cambio en el modelo
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write("🔍 VERIFICACIÓN DEL MODELO:\n")

        # Obtener el label del estado BACKLOG
        backlog_label = TaskState.BACKLOG.label

        self.stdout.write(f"Estado interno (valor en BD): '{TaskState.BACKLOG.value}'")
        self.stdout.write(f"Etiqueta visible (label):     '{backlog_label}'")

        if backlog_label == "Por Ejecutar":
            self.stdout.write(self.style.SUCCESS("\n✅ CORRECTO: El label es 'Por Ejecutar'"))
        elif backlog_label == "Backlog":
            self.stdout.write(self.style.ERROR("\n❌ ERROR: El label sigue siendo 'Backlog'"))
            self.stdout.write(self.style.WARNING(
                "   Verifica que el archivo models.py tenga:\n"
                "   BACKLOG = \"BACKLOG\", \"Por Ejecutar\""
            ))
        else:
            self.stdout.write(self.style.WARNING(f"\n⚠️  INESPERADO: El label es '{backlog_label}'"))

        self.stdout.write("\n" + "=" * 80)
        self.stdout.write("📝 EXPLICACIÓN TÉCNICA:\n")
        self.stdout.write("""
Django TextChoices usa dos valores:
1. VALOR (en base de datos): "BACKLOG" - NO cambia, es el identificador interno
2. LABEL (interfaz de usuario): "Por Ejecutar" - Es lo que ven los usuarios

Cambio realizado en models.py línea 29:
    ANTES: BACKLOG = "BACKLOG", "Backlog"
    AHORA: BACKLOG = "BACKLOG", "Por Ejecutar"

NO se requiere migración de base de datos porque el valor interno no cambió.
Solo cambió la etiqueta visual que Django muestra en:
- Django Admin
- Templates que usan {{ tarea.get_state_display }}
- Formularios y selectores de estado
""")

        self.stdout.write("=" * 80)
        self.stdout.write(self.style.SUCCESS("\n✅ Verificación completada\n"))

        # Mostrar siguiente paso
        self.stdout.write(self.style.WARNING("📌 PRÓXIMO PASO:"))
        self.stdout.write("   1. Hacer redeploy en Render")
        self.stdout.write("   2. Verificar en la interfaz web que se muestra 'Por Ejecutar'")
        self.stdout.write("   3. Las tareas existentes mostrarán automáticamente el nuevo nombre\n")
