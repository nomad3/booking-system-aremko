# Generated manually to fix ServicioBloqueo model fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0098_ajustar_verbose_names_resenas'),  # Ajusta esto a tu última migración
    ]

    operations = [
        # Primero, hacer las columnas mezcladas opcionales si no lo son
        migrations.AlterField(
            model_name='serviciobloqueo',
            name='fecha',
            field=models.DateField(null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='serviciobloqueo',
            name='hora_slot',
            field=models.CharField(max_length=5, null=True, blank=True),
        ),

        # Luego, eliminar los campos que no deberían estar en ServicioBloqueo
        migrations.RemoveField(
            model_name='serviciobloqueo',
            name='fecha',
        ),
        migrations.RemoveField(
            model_name='serviciobloqueo',
            name='hora_slot',
        ),

        # Eliminar campos de timestamp si existen erróneamente
        migrations.RemoveField(
            model_name='serviciobloqueo',
            name='created_at',
        ),
        migrations.RemoveField(
            model_name='serviciobloqueo',
            name='updated_at',
        ),
    ]