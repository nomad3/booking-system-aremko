# Generated manually for safe migration
# Adds web publishing fields to Producto model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0065_seocontent'),
    ]

    operations = [
        migrations.AddField(
            model_name='producto',
            name='publicado_web',
            field=models.BooleanField(default=False, help_text='Marcar para mostrar este producto en el catálogo web público', verbose_name='Publicado en Web'),
        ),
        migrations.AddField(
            model_name='producto',
            name='descripcion_web',
            field=models.TextField(blank=True, help_text='Descripción detallada del producto para mostrar en la web (ingredientes, preparación, etc.)', null=True, verbose_name='Descripción Web'),
        ),
        migrations.AddField(
            model_name='producto',
            name='imagen',
            field=models.ImageField(blank=True, help_text='Foto del producto para el catálogo web', null=True, upload_to='productos/', verbose_name='Imagen'),
        ),
        migrations.AddField(
            model_name='producto',
            name='orden',
            field=models.IntegerField(default=0, help_text='Orden de visualización en el catálogo (menor número = primero)', verbose_name='Orden'),
        ),
        migrations.AlterModelOptions(
            name='producto',
            options={'ordering': ['orden', 'nombre'], 'verbose_name': 'Producto', 'verbose_name_plural': 'Productos'},
        ),
    ]
