# -*- coding: utf-8 -*-
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PersonalOperativo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=120)),
                ('telefono', models.CharField(db_index=True, help_text='Número del trabajador en formato E.164 (+56...). Es la LLAVE de la whitelist: el número desde el que escribe al WhatsApp de Aremko.', max_length=20, unique=True)),
                ('rol', models.CharField(choices=[('jefatura', 'Jefatura / Administración'), ('recepcion', 'Recepción'), ('masajista', 'Masajista'), ('mantencion', 'Mantención'), ('otro', 'Otro')], default='otro', max_length=20)),
                ('turno', models.CharField(blank=True, choices=[('manana', 'Mañana'), ('tarde', 'Tarde'), ('completo', 'Completo / Variable')], default='completo', max_length=12)),
                ('responde_auto', models.BooleanField(default=False, help_text='⚙️ INTERRUPTOR DE AUTONOMÍA: si está activo, Luna le responde AUTOMÁTICAMENTE (sin pasar por la aprobación de Deborah). Solo para staff de confianza.')),
                ('activo', models.BooleanField(default=True)),
                ('notas', models.TextField(blank=True, default='')),
                ('creado', models.DateTimeField(auto_now_add=True)),
                ('actualizado', models.DateTimeField(auto_now=True)),
                ('usuario', models.ForeignKey(blank=True, help_text='Usuario del sistema (para resolver sus tareas y rol). Si es masajista, desde el usuario se llega a su Proveedor (usuario.proveedor).', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='personal_operativo', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Personal operativo',
                'verbose_name_plural': 'Personal Operativo (Luna Interna)',
                'ordering': ['nombre'],
            },
        ),
    ]
