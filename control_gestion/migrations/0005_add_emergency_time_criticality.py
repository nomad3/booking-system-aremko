# Generated manually
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('control_gestion', '0004_add_time_criticality'),
    ]

    operations = [
        migrations.AlterField(
            model_name='task',
            name='time_criticality',
            field=models.CharField(
                choices=[
                    ('EMERGENCY', 'Emergencia - Ejecución inmediata'),
                    ('CRITICAL', 'Crítica - Hora exacta'),
                    ('SCHEDULED', 'Programada - Rango horario'),
                    ('FLEXIBLE', 'Flexible - Durante el día')
                ],
                default='FLEXIBLE',
                help_text='Define la urgencia temporal: EMERGENCY=inmediata, CRITICAL=hora exacta, FLEXIBLE=durante el día',
                max_length=12,
                verbose_name='Criticidad Temporal'
            ),
        ),
    ]