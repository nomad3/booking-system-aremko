# -*- coding: utf-8 -*-
"""Tabla nueva para la sincronización con Booking/Airbnb (H-106 Fase 1).

Es una tabla NUEVA, no una columna en una existente: mientras no se corra la
migración, lo único que falla es la URL del .ics —que todavía no está pegada en
ninguna parte—. El resto del sitio no la consulta. Eso la hace distinta del
susto de esta mañana con `destacada_web`, donde el código nuevo leía una
columna de una tabla que TODO el sitio consulta.

Escrita a mano: `makemigrations ventas` arrastra el drift AR-033/034.
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0134_producto_venta_meson'),
    ]

    operations = [
        migrations.CreateModel(
            name='CalendarioCabana',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True,
                                        serialize=False, verbose_name='ID')),
                ('token', models.CharField(
                    db_index=True, editable=False,
                    help_text='Secreto de la URL del .ics. Se genera solo.',
                    max_length=48, unique=True)),
                ('activo', models.BooleanField(
                    db_index=True, default=True,
                    help_text='Si se desmarca, la URL deja de responder. '
                              'Desmarcá solo si querés cortar la sincronización: '
                              'mientras esté conectada en Booking, cortarla hace '
                              'que ellos vean la cabaña libre.')),
                ('url_booking', models.URLField(
                    blank=True, max_length=500,
                    help_text='La que entrega Booking en «Calendario y precios → '
                              'Sincronizar calendarios». Se lee para bloquear acá '
                              'lo que se vende allá (Fase 2).',
                    verbose_name='URL iCal de Booking')),
                ('url_airbnb', models.URLField(
                    blank=True, max_length=500,
                    help_text='La de «Conectar con otro sitio web» del anuncio '
                              '(Fase 2).',
                    verbose_name='URL iCal de Airbnb')),
                ('ultima_lectura_ok', models.DateTimeField(
                    blank=True, null=True,
                    help_text='Cuándo se leyeron con éxito las URLs de arriba '
                              '(Fase 2).',
                    verbose_name='Última lectura de las OTAs')),
                ('creado', models.DateTimeField(auto_now_add=True)),
                ('modificado', models.DateTimeField(auto_now=True)),
                ('servicio', models.OneToOneField(
                    limit_choices_to={'tipo_servicio': 'cabana'},
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='calendario_externo', to='ventas.servicio',
                    verbose_name='Cabaña')),
            ],
            options={
                'verbose_name': 'Calendario externo de cabaña',
                'verbose_name_plural': 'Calendarios externos (Booking / Airbnb)',
                'ordering': ['servicio__nombre'],
            },
        ),
    ]
