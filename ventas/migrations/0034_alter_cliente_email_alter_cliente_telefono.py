# Generated by Django 4.2 on 2025-04-03 16:56

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0032_remove_categoriaservicio_imagen_url_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='cliente',
            name='email',
            field=models.EmailField(blank=True, max_length=254, null=True),
        ),
        migrations.AlterField(
            model_name='cliente',
            name='telefono',
            field=models.CharField(help_text='Número de teléfono único (formato internacional preferido)', max_length=20, unique=True),
        ),
    ]
