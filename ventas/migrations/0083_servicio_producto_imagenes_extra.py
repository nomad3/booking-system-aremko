from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0082_comandas_cliente_whatsapp'),
    ]

    operations = [
        migrations.AddField(
            model_name='servicio',
            name='imagen_2',
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to='servicios/',
                help_text='Segunda imagen del servicio (opcional, aparece en el carousel de la card).',
            ),
        ),
        migrations.AddField(
            model_name='servicio',
            name='imagen_3',
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to='servicios/',
                help_text='Tercera imagen del servicio (opcional, aparece en el carousel de la card).',
            ),
        ),
        migrations.AlterField(
            model_name='servicio',
            name='imagen',
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to='servicios/',
                help_text='Imagen principal del servicio.',
            ),
        ),
        migrations.AddField(
            model_name='producto',
            name='imagen_2',
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to='productos/',
                verbose_name='Imagen 2',
                help_text='Segunda foto del producto (opcional, aparece en el carousel)',
            ),
        ),
        migrations.AddField(
            model_name='producto',
            name='imagen_3',
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to='productos/',
                verbose_name='Imagen 3',
                help_text='Tercera foto del producto (opcional, aparece en el carousel)',
            ),
        ),
        migrations.AlterField(
            model_name='producto',
            name='imagen',
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to='productos/',
                verbose_name='Imagen',
                help_text='Foto principal del producto para el catálogo web',
            ),
        ),
    ]
