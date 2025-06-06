# Generated by Django 4.2 on 2025-04-07 04:34

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0038_remove_servicio_proveedor_servicio_proveedores'),
    ]

    operations = [
        migrations.AddField(
            model_name='reservaservicio',
            name='proveedor_asignado',
            field=models.ForeignKey(blank=True, help_text='Proveedor específico asignado para esta reserva (ej. masajista).', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reservas_asignadas', to='ventas.proveedor'),
        ),
    ]
