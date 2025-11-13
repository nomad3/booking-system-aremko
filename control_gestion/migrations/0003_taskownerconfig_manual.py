# Generated manually to avoid index renaming issues
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('control_gestion', '0002_tasktemplate_empleadodisponibilidad'),
    ]

    operations = [
        migrations.CreateModel(
            name='TaskOwnerConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipo_tarea', models.CharField(choices=[
                    ('preparacion_servicio', 'Preparación de Servicio (1h antes)'),
                    ('vaciado_tina', 'Vaciado de Tina (después del servicio)'),
                    ('apertura_am', 'Apertura AM - Limpieza'),
                    ('reporte_diario', 'Reporte Diario'),
                    ('monitoreo', 'Monitoreo General'),
                    ('mantencion', 'Mantención y Reparaciones'),
                    ('alimentacion', 'Alimentación de Animales'),
                    ('otros', 'Otros (por defecto)')
                ], max_length=32, unique=True, verbose_name='Tipo de Tarea', help_text='Tipo de tarea automática a configurar')),
                ('asignar_a_grupo', models.CharField(blank=True, max_length=50, verbose_name='Asignar a Grupo', help_text='Nombre del grupo (ej: OPERACIONES, RECEPCION, COMERCIAL)')),
                ('activo', models.BooleanField(default=True, verbose_name='Activo', help_text='Si está inactivo, usará comportamiento por defecto del sistema')),
                ('notas', models.TextField(blank=True, verbose_name='Notas', help_text='Notas internas sobre esta configuración')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Fecha de creación')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Última actualización')),
                ('asignar_a_usuario', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='task_owner_configs',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Asignar a Usuario',
                    help_text='Usuario específico (tiene prioridad sobre grupo)'
                )),
                ('usuario_fallback', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='task_owner_fallback_configs',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Usuario Fallback',
                    help_text='Usuario a usar si no se encuentra el usuario/grupo configurado'
                )),
            ],
            options={
                'verbose_name': 'Configuración de Responsable',
                'verbose_name_plural': 'Configuraciones de Responsables',
                'ordering': ['tipo_tarea'],
            },
        ),
    ]
