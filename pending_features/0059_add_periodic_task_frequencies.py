# Generated manually for periodic task frequencies

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('control_gestion', '0058_premio_tramo_hito'),
    ]

    operations = [
        migrations.AddField(
            model_name='tasktemplate',
            name='frecuencia',
            field=models.CharField(
                choices=[
                    ('DIARIA', 'Diaria (ciertos días de semana)'),
                    ('SEMANAL', 'Semanal (cada N semanas)'),
                    ('MENSUAL', 'Mensual (cierto día del mes)'),
                    ('TRIMESTRAL', 'Trimestral (cada 3 meses)'),
                    ('SEMESTRAL', 'Semestral (cada 6 meses)'),
                    ('ANUAL', 'Anual (una vez al año)')
                ],
                default='DIARIA',
                help_text='Con qué frecuencia se repite esta tarea',
                max_length=12,
                verbose_name='Frecuencia'
            ),
        ),
        migrations.AddField(
            model_name='tasktemplate',
            name='dia_del_mes',
            field=models.PositiveIntegerField(
                blank=True,
                help_text='Para frecuencias MENSUAL/TRIMESTRAL/SEMESTRAL/ANUAL: día del mes (1-31, 0 = último día)',
                null=True,
                verbose_name='Día del mes'
            ),
        ),
        migrations.AddField(
            model_name='tasktemplate',
            name='mes_inicio',
            field=models.PositiveIntegerField(
                blank=True,
                choices=[
                    (1, 'Enero'), (2, 'Febrero'), (3, 'Marzo'),
                    (4, 'Abril'), (5, 'Mayo'), (6, 'Junio'),
                    (7, 'Julio'), (8, 'Agosto'), (9, 'Septiembre'),
                    (10, 'Octubre'), (11, 'Noviembre'), (12, 'Diciembre')
                ],
                help_text='Para TRIMESTRAL/SEMESTRAL/ANUAL: mes en que comienza el ciclo',
                null=True,
                verbose_name='Mes de inicio'
            ),
        ),
        migrations.AddField(
            model_name='tasktemplate',
            name='ultima_generacion',
            field=models.DateField(
                blank=True,
                help_text='Fecha en que se generó la última tarea (control interno)',
                null=True,
                verbose_name='Última generación'
            ),
        ),
        migrations.AlterField(
            model_name='tasktemplate',
            name='dias_activa',
            field=models.JSONField(
                default=list,
                help_text='Solo para frecuencia DIARIA: [0,1,2,3,4] = Lun-Vie, [1] = Solo martes',
                verbose_name='Días activa'
            ),
        ),
    ]
