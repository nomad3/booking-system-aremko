# Generated for task templates and employee availability

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('control_gestion', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='TaskTemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title_template', models.CharField(help_text="Puede usar {fecha}, {dia} en el título", max_length=160, verbose_name='Título plantilla')),
                ('description', models.TextField(help_text='Descripción completa de la tarea recurrente', verbose_name='Descripción')),
                ('swimlane', models.CharField(choices=[('COM', 'Comercial'), ('CS', 'Atención Cliente'), ('OPS', 'Operación'), ('RX', 'Recepción'), ('SUP', 'Marketing y Supervisión')], max_length=3, verbose_name='Área')),
                ('priority', models.CharField(choices=[('NORMAL', 'Normal'), ('ALTA', 'Alta (Cliente en sitio)')], default='NORMAL', max_length=8, verbose_name='Prioridad')),
                ('queue_position', models.PositiveIntegerField(default=1, verbose_name='Posición en cola')),
                ('dias_activa', models.JSONField(default=list, help_text='Lista de días de semana: [0,1,2,3,4] = Lun-Vie, [1] = Solo martes', verbose_name='Días activa')),
                ('asignar_a_grupo', models.CharField(blank=True, help_text='Nombre del grupo (OPERACIONES, RECEPCION, etc.)', max_length=50, verbose_name='Asignar a grupo')),
                ('activa', models.BooleanField(default=True, help_text='Si está inactiva, no se generará', verbose_name='Activa')),
                ('solo_martes', models.BooleanField(default=False, help_text='Tarea especial de mantención que solo se genera los martes', verbose_name='Solo martes')),
                ('asignar_a_usuario', models.ForeignKey(blank=True, help_text='Si se especifica, ignora el grupo', null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, verbose_name='Asignar a usuario específico')),
            ],
            options={
                'verbose_name': 'Plantilla de Tarea Recurrente',
                'verbose_name_plural': 'Plantillas de Tareas Recurrentes',
                'ordering': ['swimlane', 'queue_position'],
            },
        ),
        migrations.CreateModel(
            name='EmpleadoDisponibilidad',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('dias_trabajo', models.JSONField(default=list, help_text='Lista de días: [0,1,2,3,4] = Lun-Vie', verbose_name='Días que trabaja')),
                ('notas', models.TextField(blank=True, help_text="Ej: 'Martes solo medio día', 'Fines de semana a veces'", verbose_name='Notas')),
                ('empleado', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='disponibilidad', to=settings.AUTH_USER_MODEL, verbose_name='Empleado')),
            ],
            options={
                'verbose_name': 'Disponibilidad de Empleado',
                'verbose_name_plural': 'Disponibilidad de Empleados',
            },
        ),
    ]

