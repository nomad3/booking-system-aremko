from django.db import migrations, models

def convert_duracion(apps, schema_editor):
    Servicio = apps.get_model('ventas', 'Servicio')
    for servicio in Servicio.objects.all():
        # Convierte la duración de intervalo a minutos
        if servicio.duracion:
            servicio.duracion_minutos = servicio.duracion.total_seconds() // 60
            servicio.save()

class Migration(migrations.Migration):
    dependencies = [
        ('ventas', '0028_reservaservicio_hora_inicio_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='servicio',
            name='duracion_minutos',
            field=models.PositiveIntegerField(default=60, help_text="Duración en minutos"),
        ),
        migrations.RunPython(convert_duracion),
        migrations.RemoveField(
            model_name='servicio',
            name='duracion',
        ),
        migrations.RenameField(
            model_name='servicio',
            old_name='duracion_minutos',
            new_name='duracion',
        ),
    ]
