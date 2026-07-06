# -*- coding: utf-8 -*-
# Migración escrita a mano (NO con makemigrations sobre ventas) — mismo criterio
# drift-safe de 0127/0128/0129: CreateModel puro en la app aislada conciliacion.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('conciliacion', '0001_initial'),
        ('ventas', '0129_giftcard_experiencia_galeria'),
    ]

    operations = [
        migrations.CreateModel(
            name='MovimientoMP',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('mp_payment_id', models.CharField(db_index=True, help_text='ID del pago en Mercado Pago (no se importa dos veces).', max_length=40, unique=True)),
                ('fecha', models.DateTimeField(db_index=True, help_text='Fecha de aprobación del pago en MP.')),
                ('monto', models.DecimalField(decimal_places=0, max_digits=10)),
                ('tipo', models.CharField(blank=True, default='', help_text='operation_type/payment_type (ej. account_fund/bank_transfer).', max_length=60)),
                ('glosa', models.CharField(blank=True, default='', help_text='description del pago — a veces trae el nombre del cliente.', max_length=255)),
                ('transaction_id', models.CharField(blank=True, default='', help_text='ID bancario único (CCA…). Referencia de idempotencia al aplicar.', max_length=80)),
                ('payer_email', models.CharField(blank=True, default='', help_text='Email del pagador (útil en pagos MP→MP y tarjeta; en transferencias bancarias viene la propia cuenta).', max_length=254)),
                ('external_reference', models.CharField(blank=True, default='', help_text='Si viene (link generado por reserva), el match es directo.', max_length=64)),
                ('estado', models.CharField(choices=[('sugerido', 'Con sugerencia (confirmar)'), ('revisar', 'Revisar a mano'), ('aplicado', 'Aplicado a reserva'), ('ignorado', 'Ignorado')], db_index=True, default='revisar', max_length=20)),
                ('sugerencia_motivo', models.CharField(blank=True, default='', max_length=255)),
                ('raw', models.JSONField(blank=True, default=dict)),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('actualizado_en', models.DateTimeField(auto_now=True)),
                ('sugerencia', models.ForeignKey(blank=True, help_text='Reserva que propone el matcher (editable antes de aplicar).', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='mp_sugerencias', to='ventas.ventareserva')),
                ('reserva_aplicada', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='mp_movimientos', to='ventas.ventareserva')),
            ],
            options={
                'db_table': 'conciliacion_movimientomp',
                'verbose_name': 'Movimiento Mercado Pago',
                'verbose_name_plural': 'Movimientos Mercado Pago',
                'ordering': ['-fecha'],
            },
        ),
    ]
