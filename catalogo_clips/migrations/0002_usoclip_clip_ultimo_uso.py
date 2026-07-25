# H-072: registro de uso de clips (cimiento anti-repetición Fase 2) + campo
# desnormalizado en Clip. Drift-safe: depende SOLO de catalogo_clips.0001
# (misma app) — cero deps cruzadas de migración.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalogo_clips', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='clip',
            name='ultimo_uso',
            field=models.DateField(blank=True, db_index=True, null=True,
                                   help_text='Última vez que se usó en una historia (desnormalizado; H-072). '
                                             'Lo usa el auto-pick anti-repetición de Fase 2.'),
        ),
        migrations.CreateModel(
            name='UsoClip',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fecha', models.DateField(db_index=True)),
                ('publicacion_id', models.PositiveIntegerField(
                    blank=True, db_index=True, null=True,
                    help_text='ID de marketing_briefs.PublicacionPlanificada (referencia suave).')),
                ('canal', models.CharField(blank=True, default='', max_length=40)),
                ('creado', models.DateTimeField(auto_now_add=True)),
                ('clip', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                           related_name='usos', to='catalogo_clips.clip')),
            ],
            options={
                'verbose_name': 'Uso de clip',
                'verbose_name_plural': 'Usos de clips',
                'ordering': ['-fecha', '-id'],
            },
        ),
    ]
