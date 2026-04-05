# Generated manually on 2026-04-05
# Sistema de comandas para clientes vía WhatsApp

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0081_comanda_fecha_entrega_objetivo'),
    ]

    operations = [
        # ========================================
        # TABLA: Producto - Campos para comandas de clientes
        # ========================================

        migrations.AddField(
            model_name='producto',
            name='comanda_cliente',
            field=models.BooleanField(
                default=False,
                verbose_name='Disponible para Comanda de Cliente',
                help_text='Si está marcado, el cliente puede ver y seleccionar este producto desde su link de comanda vía WhatsApp'
            ),
        ),

        migrations.AddField(
            model_name='producto',
            name='orden_comanda',
            field=models.IntegerField(
                default=0,
                verbose_name='Orden en Menú de Comanda',
                help_text='Orden de visualización en el menú de comandas para clientes (menor número = primero)'
            ),
        ),

        # Índice compuesto para búsquedas rápidas de productos disponibles
        migrations.AddIndex(
            model_name='producto',
            index=models.Index(
                fields=['comanda_cliente', 'orden_comanda'],
                name='producto_comanda_idx'
            ),
        ),

        # ========================================
        # TABLA: Comanda - Campos para sistema de clientes
        # ========================================

        migrations.AddField(
            model_name='comanda',
            name='token_acceso',
            field=models.CharField(
                max_length=64,
                unique=True,
                null=True,
                blank=True,
                db_index=True,
                verbose_name='Token de Acceso',
                help_text='Token único para acceso del cliente vía WhatsApp'
            ),
        ),

        migrations.AddField(
            model_name='comanda',
            name='creada_por_cliente',
            field=models.BooleanField(
                default=False,
                db_index=True,
                verbose_name='Creada por Cliente',
                help_text='Indica si la comanda fue creada por el cliente vía link de WhatsApp'
            ),
        ),

        migrations.AddField(
            model_name='comanda',
            name='fecha_vencimiento_link',
            field=models.DateTimeField(
                null=True,
                blank=True,
                verbose_name='Vencimiento del Link',
                help_text='Fecha límite para usar el link de comanda (24-48 horas típicamente)'
            ),
        ),

        migrations.AddField(
            model_name='comanda',
            name='flow_order_id',
            field=models.CharField(
                max_length=100,
                null=True,
                blank=True,
                verbose_name='Flow Order ID',
                help_text='ID de la orden en Flow'
            ),
        ),

        migrations.AddField(
            model_name='comanda',
            name='flow_token',
            field=models.CharField(
                max_length=255,
                null=True,
                blank=True,
                verbose_name='Flow Token',
                help_text='Token de pago de Flow'
            ),
        ),

        # Índice para búsquedas por token
        migrations.AddIndex(
            model_name='comanda',
            index=models.Index(
                fields=['token_acceso'],
                name='comanda_token_idx'
            ),
        ),

        # Índice para filtrar comandas de clientes
        migrations.AddIndex(
            model_name='comanda',
            index=models.Index(
                fields=['creada_por_cliente', 'estado'],
                name='comanda_cliente_estado_idx'
            ),
        ),
    ]
