# H-060: agrega SOLO el campo nuevo reserva_existente_id. Escrita a mano (no con
# makemigrations sin revisar) porque el autodetector arrastra ruido cosmético no
# relacionado (RenameIndex + AlterField por diffs de help_text vs la migración 0009,
# sin cambio real de esquema) — se aísla acá el único cambio real que se quiere aplicar.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('whatsapp_agent', '0009_propuestareserva_campos_h028'),
    ]

    operations = [
        migrations.AddField(
            model_name='propuestareserva',
            name='reserva_existente_id',
            field=models.IntegerField(
                blank=True, null=True,
                help_text='VentaReserva.id a la que se AGREGA (no se crea una nueva) si está seteado',
            ),
        ),
    ]
