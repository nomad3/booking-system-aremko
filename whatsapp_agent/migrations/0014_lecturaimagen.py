# -*- coding: utf-8 -*-
"""Tabla nueva y aislada (P-52, 25-09-2026): lo que el lector vio en cada foto.

Escrita a mano —como todas en este repo— porque `makemigrations` arrastra el
drift de AR-033/034 (quería además alterar campos de PropuestaReserva y los id
de otras tablas). Solo crea la tabla; no toca nada existente.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('whatsapp_agent', '0013_recordatorioluna'),
    ]

    operations = [
        migrations.CreateModel(
            name='LecturaImagen',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('wa_message_id', models.CharField(db_index=True, max_length=128, unique=True)),
                ('phone', models.CharField(db_index=True, max_length=20)),
                ('tipo', models.CharField(choices=[('giftcard_aremko', 'Gift card de Aremko'), ('voucher_antiguo', 'Voucher antiguo (R ####)'), ('comprobante', 'Comprobante de pago'), ('otro', 'Otra imagen')], max_length=20)),
                ('codigo', models.CharField(blank=True, help_text='Tal como lo leyó el modelo.', max_length=40)),
                ('giftcard_id', models.IntegerField(blank=True, help_text='La gift card con que calzó.', null=True)),
                ('forma', models.CharField(blank=True, help_text='Cómo calzó: exacto, o_por_cero, tolerancia, comienzo.', max_length=20)),
                ('voucher', models.IntegerField(blank=True, help_text='Número de reserva de un voucher R ####.', null=True)),
                ('resumen', models.CharField(blank=True, help_text='Lo que ven Luna y Deborah.', max_length=200)),
                ('modelo', models.CharField(blank=True, max_length=120)),
                ('tokens', models.PositiveIntegerField(default=0)),
                ('latency_ms', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Lectura de imagen',
                'verbose_name_plural': 'Lecturas de imágenes',
                'ordering': ['-created_at'],
            },
        ),
    ]
