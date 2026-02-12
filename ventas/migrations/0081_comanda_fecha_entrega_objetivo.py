# Generated manually on 2026-02-12
# Agrega campo fecha_entrega_objetivo para programar entregas

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0080_comandas_system'),
    ]

    operations = [
        # ========================================
        # OPERACIÓN 1: Agregar campo fecha_entrega_objetivo
        # ========================================
        migrations.AddField(
            model_name='comanda',
            name='fecha_entrega_objetivo',
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name='Fecha/Hora Entrega Objetivo',
                help_text='Para cuándo se necesita este pedido. Si es vacío, es para ahora (inmediato).',
                db_index=True
            ),
        ),

        # ========================================
        # OPERACIÓN 2: Crear índice compuesto para Vista Cocina
        # ========================================
        migrations.AddIndex(
            model_name='comanda',
            index=models.Index(
                fields=['fecha_entrega_objetivo', 'estado'],
                name='comanda_entrega_obj_idx'
            ),
        ),
    ]
