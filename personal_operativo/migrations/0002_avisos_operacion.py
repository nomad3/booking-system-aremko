# -*- coding: utf-8 -*-
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('personal_operativo', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='personaloperativo',
            name='recibe_avisos_operacion',
            field=models.BooleanField(default=False, help_text='📥 Recibe por WhatsApp los avisos de tareas de Recepción/Operación apenas se generan (el "recepcionista de turno"). Marca esto en quien esté cubriendo recepción.'),
        ),
        migrations.CreateModel(
            name='NotificacionStaff',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('telefono', models.CharField(db_index=True, help_text='Destinatario (E.164).', max_length=20)),
                ('texto', models.TextField()),
                ('estado', models.CharField(choices=[('pendiente', 'Pendiente'), ('enviada', 'Enviada'), ('fallida', 'Fallida'), ('descartada', 'Descartada')], db_index=True, default='pendiente', max_length=12)),
                ('origen', models.CharField(blank=True, default='', help_text='Ej: task_creada, task_vencida.', max_length=40)),
                ('ref_tipo', models.CharField(blank=True, default='', max_length=20)),
                ('ref_id', models.CharField(blank=True, default='', max_length=40)),
                ('dedup_key', models.CharField(help_text='Evita duplicados (ej. task_creada:123:5).', max_length=120, unique=True)),
                ('intentos', models.PositiveIntegerField(default=0)),
                ('error', models.TextField(blank=True, default='')),
                ('creada', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('enviada_at', models.DateTimeField(blank=True, null=True)),
            ],
            options={
                'verbose_name': 'Notificación a staff',
                'verbose_name_plural': 'Notificaciones a staff (Luna Interna)',
                'ordering': ['-creada'],
            },
        ),
        migrations.AddIndex(
            model_name='notificacionstaff',
            index=models.Index(fields=['estado', 'creada'], name='personal_op_estado_aa3c5e_idx'),
        ),
    ]
