# -*- coding: utf-8 -*-
# Migración escrita a mano (criterio drift-safe de la app):
# - BoletaElectronica.pago pasa a nullable (las boletas del set de pruebas de
#   certificación no nacen de un pago real) + campo caso_set.
# - ConfiguracionFacturacion: fecha/número de resolución para la carátula del
#   sobre de envío al SII.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('facturacion', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='boletaelectronica',
            name='pago',
            field=models.OneToOneField(blank=True, null=True,
                                       on_delete=django.db.models.deletion.PROTECT,
                                       related_name='boleta_electronica',
                                       to='ventas.pago'),
        ),
        migrations.AddField(
            model_name='boletaelectronica',
            name='caso_set',
            field=models.CharField(blank=True, db_index=True, default='',
                                   help_text='Solo certificación: CASO-N del set de pruebas del SII.',
                                   max_length=12),
        ),
        migrations.AddField(
            model_name='configuracionfacturacion',
            name='fecha_resolucion',
            field=models.DateField(blank=True, null=True,
                                   help_text='Fecha de resolución que autoriza a emitir (cert: fecha de postulación).'),
        ),
        migrations.AddField(
            model_name='configuracionfacturacion',
            name='numero_resolucion',
            field=models.PositiveIntegerField(default=0,
                                              help_text='Número de resolución (0 en certificación).'),
        ),
    ]
