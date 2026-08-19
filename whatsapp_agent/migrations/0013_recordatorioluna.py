# -*- coding: utf-8 -*-
"""Tabla nueva y aislada (H-109): bitácora de recordatorios de Luna.

Escrita a mano —como todas en este repo— porque `makemigrations` arrastra el
drift de AR-033/034 y pide input interactivo por cambios preexistentes.
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('whatsapp_agent', '0012_temaconversacion_v2'),
    ]

    operations = [
        migrations.CreateModel(
            name='RecordatorioLuna',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True,
                                        serialize=False, verbose_name='ID')),
                ('tipo', models.CharField(db_index=True, max_length=30, choices=[
                    ('cotizacion_lista', 'Cotización enviada y sin respuesta'),
                    ('cotizacion_por_vencer', 'Cotización a punto de expirar'),
                    ('pago_pendiente', 'Reserva aprobada sin pago'),
                ])),
                ('phone', models.CharField(db_index=True, max_length=20)),
                ('reserva_id', models.IntegerField(
                    blank=True, null=True,
                    help_text='VentaReserva.id (solo tipo pago_pendiente)')),
                ('texto', models.TextField(help_text='El mensaje EXACTO que se envía.')),
                ('estado', models.CharField(db_index=True, default='pendiente_envio',
                                            max_length=20, choices=[
                    ('pendiente_envio', 'Pendiente de envío'),
                    ('enviado', 'Enviado'),
                    ('fallido', 'Fallido'),
                ])),
                ('error', models.CharField(blank=True, max_length=200)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('enviado_at', models.DateTimeField(blank=True, null=True)),
                ('propuesta', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='recordatorios',
                    to='whatsapp_agent.propuestareserva')),
            ],
            options={
                'verbose_name': 'Recordatorio de Luna',
                'verbose_name_plural': 'Recordatorios de Luna',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='recordatorioluna',
            index=models.Index(fields=['estado', 'created_at'],
                               name='idx_recordatorio_estado'),
        ),
    ]
