"""Modelo PendingReservation: reserva tentativa antes de confirmacion Flow.

Evita que se creen VentaReserva fantasma cuando el cliente abandona el pago Flow.
Solo se materializa la VentaReserva cuando el webhook de Flow confirma el pago.
Para transferencia se mantiene el flujo actual (creacion inmediata).

Migracion manual en Render (regla del proyecto).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0087_review'),
    ]

    operations = [
        migrations.CreateModel(
            name='PendingReservation',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cart_data', models.JSONField(help_text='Snapshot del carrito: servicios, giftcards, totales, descuentos')),
                ('metodo_pago', models.CharField(default='flow', max_length=20)),
                ('monto', models.IntegerField(help_text='Total en CLP al momento del checkout')),
                ('flow_token', models.CharField(blank=True, db_index=True, max_length=100)),
                ('flow_url', models.URLField(blank=True, max_length=500)),
                ('estado', models.CharField(
                    choices=[
                        ('iniciado', 'Iniciado (esperando pago Flow)'),
                        ('confirmado', 'Confirmado (VentaReserva creada)'),
                        ('rechazado', 'Rechazado por Flow'),
                        ('cancelado', 'Cancelado por usuario'),
                        ('expirado', 'Expirado por timeout'),
                        ('slot_perdido', 'Slot tomado mientras se pagaba (requiere reembolso manual)'),
                    ],
                    db_index=True,
                    default='iniciado',
                    max_length=20,
                )),
                ('notas', models.TextField(blank=True, help_text='Mensajes de error o notas operativas')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('expires_at', models.DateTimeField(db_index=True)),
                ('cliente', models.ForeignKey(
                    on_delete=models.deletion.CASCADE,
                    related_name='pending_reservations',
                    to='ventas.cliente',
                )),
                ('venta_reserva', models.OneToOneField(
                    blank=True, null=True,
                    on_delete=models.deletion.SET_NULL,
                    related_name='pending_origin',
                    to='ventas.ventareserva',
                )),
            ],
            options={
                'verbose_name': 'Reserva pendiente (pre-pago Flow)',
                'verbose_name_plural': 'Reservas pendientes (pre-pago Flow)',
                'ordering': ['-created_at'],
            },
        ),
    ]
