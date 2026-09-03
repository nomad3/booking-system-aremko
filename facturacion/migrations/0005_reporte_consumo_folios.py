# Escrita a mano: makemigrations se queda esperando una pregunta interactiva
# por drift pendiente de OTRA app. Acá solo se crea la tabla nueva.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('facturacion', '0004_decision_sin_boleta'),
    ]

    operations = [
        migrations.CreateModel(
            name='ReporteConsumoFolios',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True,
                                        serialize=False, verbose_name='ID')),
                ('ambiente', models.CharField(db_index=True, max_length=20)),
                ('fecha', models.DateField(db_index=True)),
                ('secuencia', models.PositiveSmallIntegerField(default=1)),
                ('cantidad_folios', models.PositiveIntegerField(default=0)),
                ('monto_total', models.DecimalField(decimal_places=0, default=0,
                                                     max_digits=12)),
                ('xml', models.TextField(blank=True, default='')),
                ('valido', models.BooleanField(default=False)),
                ('error_validacion', models.TextField(blank=True, default='')),
                ('generado_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Reporte de consumo de folios (RCOF)',
                'verbose_name_plural': 'Reportes de consumo de folios (RCOF)',
                'ordering': ['-fecha'],
            },
        ),
        migrations.AddConstraint(
            model_name='reporteconsumofolios',
            constraint=models.UniqueConstraint(
                fields=['ambiente', 'fecha', 'secuencia'], name='unique_rcof_dia'),
        ),
    ]
