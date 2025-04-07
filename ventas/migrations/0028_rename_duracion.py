from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ('ventas', '0027_allow_null_usuario'),  # Última migración válida
    ]

    operations = [
        migrations.RenameField(
            model_name='servicio',
            old_name='duracion',
            new_name='old_duracion',
        ),
    ] 