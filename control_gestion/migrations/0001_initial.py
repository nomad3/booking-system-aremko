# Generated manually for control_gestion app

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CustomerSegment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='Nombre del segmento: ORO, PLATA, Tramo N, etc.', max_length=30, unique=True, verbose_name='Nombre')),
                ('min_spend', models.PositiveIntegerField(help_text='Gasto mínimo en CLP para este segmento', verbose_name='Gasto mínimo')),
                ('max_spend', models.PositiveIntegerField(blank=True, help_text='Gasto máximo en CLP (null = sin límite)', null=True, verbose_name='Gasto máximo')),
                ('benefit', models.CharField(help_text='Descripción del beneficio del segmento', max_length=120, verbose_name='Beneficio')),
            ],
            options={
                'verbose_name': 'Segmento de Cliente',
                'verbose_name_plural': 'Segmentos de Clientes',
                'ordering': ['min_spend'],
            },
        ),
        migrations.CreateModel(
            name='DailyReport',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(help_text='Fecha del reporte', verbose_name='Fecha')),
                ('generated_at', models.DateTimeField(auto_now_add=True, verbose_name='Generado el')),
                ('summary', models.TextField(help_text='Resumen generado por IA del día', verbose_name='Resumen')),
            ],
            options={
                'verbose_name': 'Reporte Diario',
                'verbose_name_plural': 'Reportes Diarios',
                'ordering': ['-date'],
            },
        ),
        migrations.CreateModel(
            name='Task',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(help_text='Título corto y descriptivo de la tarea', max_length=160, verbose_name='Título')),
                ('description', models.TextField(help_text='Descripción detallada de la tarea', verbose_name='Descripción')),
                ('swimlane', models.CharField(choices=[('COM', 'Comercial'), ('CS', 'Atención Cliente'), ('OPS', 'Operación'), ('RX', 'Recepción'), ('SUP', 'Marketing y Supervisión')], help_text='Área responsable de la tarea', max_length=3, verbose_name='Área')),
                ('state', models.CharField(choices=[('BACKLOG', 'Backlog'), ('IN_PROGRESS', 'En curso'), ('BLOCKED', 'Bloqueada'), ('DONE', 'Hecha')], default='BACKLOG', max_length=12, verbose_name='Estado')),
                ('source', models.CharField(choices=[('IDEA', 'Idea'), ('INCIDENTE', 'Incidente'), ('SOLICITUD', 'Solicitud Cliente'), ('RUTINA', 'Rutina'), ('SISTEMA', 'Sistema')], default='RUTINA', max_length=12, verbose_name='Origen')),
                ('priority', models.CharField(choices=[('NORMAL', 'Normal'), ('ALTA', 'Alta (Cliente en sitio)')], default='NORMAL', max_length=8, verbose_name='Prioridad')),
                ('queue_position', models.PositiveIntegerField(db_index=True, default=1, help_text='Orden en la cola de tareas del swimlane', verbose_name='Posición en cola')),
                ('promise_due_at', models.DateTimeField(blank=True, help_text='Fecha/hora comprometida para completar la tarea', null=True, verbose_name='Promesa de entrega')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Fecha creación')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Última actualización')),
                ('reservation_id', models.CharField(blank=True, help_text='Identificador de la reserva relacionada (sin ForeignKey)', max_length=40, verbose_name='ID Reserva')),
                ('customer_phone_last9', models.CharField(blank=True, help_text='Últimos 9 dígitos del teléfono del cliente (sin +56)', max_length=9, verbose_name='Teléfono cliente (últimos 9)')),
                ('location_ref', models.CharField(blank=True, choices=[('RECEPCION', 'Recepción'), ('CAFETERIA', 'Cafetería'), ('TINA_1', 'Tina 1'), ('TINA_2', 'Tina 2'), ('TINA_3', 'Tina 3'), ('TINA_4', 'Tina 4'), ('TINA_5', 'Tina 5'), ('TINA_6', 'Tina 6'), ('TINA_7', 'Tina 7'), ('TINA_8', 'Tina 8'), ('SALA_1', 'Sala 1'), ('SALA_2', 'Sala 2'), ('SALA_3', 'Sala 3'), ('CAB_1', 'Cabaña 1'), ('CAB_2', 'Cabaña 2'), ('CAB_3', 'Cabaña 3'), ('CAB_4', 'Cabaña 4'), ('CAB_5', 'Cabaña 5')], help_text='Ubicación física relacionada con la tarea', max_length=16, verbose_name='Ubicación')),
                ('service_type', models.CharField(blank=True, help_text='Tipo: TINA_SIMPLE, TINA_HIDRO, MASAJE, CABANA, F&B', max_length=32, verbose_name='Tipo de servicio')),
                ('segment_tag', models.CharField(blank=True, help_text='Segmento del cliente: BRONCE/PLATA/ORO/DIAMANTE o Tramo N', max_length=30, verbose_name='Segmento/Tramo')),
                ('media', models.FileField(blank=True, help_text='Foto, documento o evidencia relacionada', null=True, upload_to='task_media/', verbose_name='Archivo adjunto')),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='created_tasks', to=settings.AUTH_USER_MODEL, verbose_name='Creado por')),
                ('owner', models.ForeignKey(help_text='Persona asignada a la tarea', on_delete=django.db.models.deletion.PROTECT, related_name='owned_tasks', to=settings.AUTH_USER_MODEL, verbose_name='Responsable')),
            ],
            options={
                'verbose_name': 'Tarea',
                'verbose_name_plural': 'Tareas',
                'ordering': ['swimlane', 'queue_position', 'created_at'],
            },
        ),
        migrations.CreateModel(
            name='TaskLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('when', models.DateTimeField(auto_now_add=True, verbose_name='Cuándo')),
                ('action', models.CharField(help_text='CREATED/UPDATED/STARTED/BLOCKED/UNBLOCKED/REORDERED/DONE/COMMENT/PROMISE_MOVED/QA_RESULT', max_length=50, verbose_name='Acción')),
                ('note', models.TextField(blank=True, help_text='Detalles adicionales de la acción', verbose_name='Nota')),
                ('actor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL, verbose_name='Quién')),
                ('task', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='logs', to='control_gestion.task', verbose_name='Tarea')),
            ],
            options={
                'verbose_name': 'Log de Tarea',
                'verbose_name_plural': 'Logs de Tareas',
                'ordering': ['-when'],
            },
        ),
        migrations.CreateModel(
            name='ChecklistItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('text', models.CharField(help_text='Descripción del ítem del checklist', max_length=180, verbose_name='Texto')),
                ('done', models.BooleanField(default=False, verbose_name='Completado')),
                ('task', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='checklist', to='control_gestion.task', verbose_name='Tarea')),
            ],
            options={
                'verbose_name': 'Item de Checklist',
                'verbose_name_plural': 'Items de Checklist',
                'ordering': ['id'],
            },
        ),
        migrations.AddIndex(
            model_name='dailyreport',
            index=models.Index(fields=['-date'], name='control_ges_date_2d4e9f_idx'),
        ),
        migrations.AddIndex(
            model_name='task',
            index=models.Index(fields=['swimlane', 'queue_position'], name='control_ges_swimlan_8c5f8e_idx'),
        ),
        migrations.AddIndex(
            model_name='task',
            index=models.Index(fields=['owner', 'state'], name='control_ges_owner_i_9a2d5c_idx'),
        ),
        migrations.AddIndex(
            model_name='task',
            index=models.Index(fields=['state', 'promise_due_at'], name='control_ges_state_0f3a1b_idx'),
        ),
        migrations.AddIndex(
            model_name='tasklog',
            index=models.Index(fields=['task', '-when'], name='control_ges_task_id_4e7b2a_idx'),
        ),
    ]

