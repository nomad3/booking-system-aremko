# -*- coding: utf-8 -*-
# Migración escrita a mano (NO con makemigrations) para agregar SOLO los 3 campos
# nuevos de ConfiguracionResumen, evitando el drift de AR-034 (ver
# 0126_ritualrio_publicacion, mismo criterio).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0126_ritualrio_publicacion'),
    ]

    operations = [
        migrations.AddField(
            model_name='configuracionresumen',
            name='nombre_beneficiario',
            field=models.CharField(blank=True, default='Aremko Hotel Spa Rut 76.485.192-7', help_text="Se copia solo, tal cual, al botón 'Copiar nombre' de la Ficha de Reserva.", max_length=200, verbose_name='Nombre del beneficiario (para copiar)'),
        ),
        migrations.AddField(
            model_name='configuracionresumen',
            name='numero_cuenta_transferencia',
            field=models.CharField(blank=True, default='Mercado Pago Cta Vista 1016006859', help_text="Se copia solo, tal cual, al botón 'Copiar cuenta' de la Ficha de Reserva.", max_length=200, verbose_name='Número de cuenta (para copiar)'),
        ),
        migrations.AddField(
            model_name='configuracionresumen',
            name='correo_confirmacion_pago',
            field=models.EmailField(blank=True, default='ventas@aremko.cl', help_text="Se copia solo, tal cual, al botón 'Copiar correo' de la Ficha de Reserva.", max_length=254, verbose_name='Correo para confirmar transferencia (para copiar)'),
        ),
    ]
