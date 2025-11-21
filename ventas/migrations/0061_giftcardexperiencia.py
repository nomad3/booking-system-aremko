# Generated manually for GiftCardExperiencia model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0060_add_giftcard_wizard_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='GiftCardExperiencia',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('id_experiencia', models.CharField(help_text="ID único de la experiencia (ej: 'tinas', 'masaje_relajacion')", max_length=50, unique=True)),
                ('categoria', models.CharField(choices=[('tinas', 'Tinas y Hidromasajes'), ('masajes', 'Masajes'), ('faciales', 'Faciales'), ('packs', 'Packs Spa'), ('valor', 'Tarjetas de Valor')], db_index=True, max_length=20)),
                ('nombre', models.CharField(max_length=200)),
                ('descripcion', models.CharField(help_text='Descripción corta para menú', max_length=500)),
                ('descripcion_giftcard', models.TextField(help_text='Descripción detallada para la gift card')),
                ('imagen', models.ImageField(help_text='Imagen de la experiencia (recomendado: 800x600px)', upload_to='giftcards/experiencias/')),
                ('monto_fijo', models.IntegerField(blank=True, help_text='Monto fijo si la experiencia tiene un precio único (ej: $50.000)', null=True)),
                ('montos_sugeridos', models.JSONField(blank=True, default=list, help_text='Lista de montos sugeridos para tarjetas de valor [30000, 50000, 75000]')),
                ('activo', models.BooleanField(default=True, help_text='Si está inactivo, no aparece en el wizard')),
                ('orden', models.IntegerField(default=0, help_text='Orden de aparición en la lista (menor = primero)')),
                ('creado', models.DateTimeField(auto_now_add=True)),
                ('modificado', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Experiencia Gift Card',
                'verbose_name_plural': 'Experiencias Gift Cards',
                'ordering': ['categoria', 'orden', 'nombre'],
                'indexes': [
                    models.Index(fields=['categoria', 'activo'], name='ventas_gift_categor_idx'),
                    models.Index(fields=['activo', 'orden'], name='ventas_gift_activo_idx'),
                ],
            },
        ),
    ]
