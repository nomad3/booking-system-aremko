# Generated manually on 2026-02-12
# Sistema de Comandas - Gestión de pedidos para reservas

from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0079_optimize_cliente_indexes'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ========================================
        # OPERACIÓN 1: Crear tabla Comanda
        # ========================================
        migrations.CreateModel(
            name='Comanda',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fecha_solicitud', models.DateTimeField(auto_now_add=True, verbose_name='Fecha y Hora de Solicitud')),
                ('hora_solicitud', models.TimeField(auto_now_add=True, verbose_name='Hora de Solicitud')),
                ('estado', models.CharField(
                    max_length=20,
                    choices=[
                        ('pendiente', 'Pendiente'),
                        ('procesando', 'En Proceso'),
                        ('entregada', 'Entregada'),
                        ('cancelada', 'Cancelada')
                    ],
                    default='pendiente',
                    db_index=True,
                    verbose_name='Estado'
                )),
                ('notas_generales', models.TextField(
                    blank=True,
                    null=True,
                    verbose_name='Notas Generales',
                    help_text='Indicaciones especiales para toda la comanda'
                )),
                ('fecha_inicio_proceso', models.DateTimeField(blank=True, null=True, verbose_name='Inicio de Proceso')),
                ('fecha_entrega', models.DateTimeField(blank=True, null=True, verbose_name='Fecha de Entrega')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),

                # Foreign Keys
                ('venta_reserva', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='comandas',
                    to='ventas.ventareserva',
                    verbose_name='Reserva'
                )),
                ('usuario_solicita', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='comandas_solicitadas',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Usuario que Solicita'
                )),
                ('usuario_procesa', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='comandas_procesadas',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Usuario que Procesa'
                )),
            ],
            options={
                'verbose_name': 'Comanda',
                'verbose_name_plural': 'Comandas',
                'ordering': ['-fecha_solicitud'],
            },
        ),

        # ========================================
        # OPERACIÓN 2: Crear tabla DetalleComanda
        # ========================================
        migrations.CreateModel(
            name='DetalleComanda',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cantidad', models.PositiveIntegerField(default=1, verbose_name='Cantidad')),
                ('especificaciones', models.TextField(
                    blank=True,
                    null=True,
                    verbose_name='Especificaciones',
                    help_text='Ej: Sabor frutilla, sin azúcar, con endulzante, bien frío, etc.'
                )),
                ('precio_unitario', models.DecimalField(decimal_places=0, max_digits=10, verbose_name='Precio Unitario')),

                # Foreign Keys
                ('comanda', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='detalles',
                    to='ventas.comanda',
                    verbose_name='Comanda'
                )),
                ('producto', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    to='ventas.producto',
                    verbose_name='Producto'
                )),
            ],
            options={
                'verbose_name': 'Detalle de Comanda',
                'verbose_name_plural': 'Detalles de Comanda',
                'ordering': ['id'],
            },
        ),

        # ========================================
        # OPERACIÓN 3: Crear índices para performance
        # ========================================
        migrations.AddIndex(
            model_name='comanda',
            index=models.Index(
                fields=['estado', '-fecha_solicitud'],
                name='comanda_estado_fecha_idx'
            ),
        ),
        migrations.AddIndex(
            model_name='comanda',
            index=models.Index(
                fields=['venta_reserva', 'estado'],
                name='comanda_reserva_estado_idx'
            ),
        ),
    ]
