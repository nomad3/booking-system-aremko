# Escrita a mano: makemigrations se queda esperando una pregunta interactiva
# por drift pendiente de OTRA app. Acá solo se agrega el campo nuevo.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('facturacion', '0005_reporte_consumo_folios'),
    ]

    operations = [
        migrations.AddField(
            model_name='configuracionfacturacion',
            name='unidad_sii',
            field=models.CharField(
                blank=True, default='', max_length=60,
                help_text='Unidad del SII que va en el recuadro rojo de la boleta impresa '
                          '(ej. «PUERTO MONTT»). Si se deja vacío se usa la comuna. Es un '
                          'dato tributario: confírmalo con el contador antes de imprimir.'),
        ),
    ]
