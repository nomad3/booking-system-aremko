"""
0114_refugio_garantia
======================

Agrega 2 campos al singleton RefugioConfig para mostrar una línea
sutil debajo del subtítulo del precio en la landing /refugio/:

    garantia_texto: "Respaldado por la Garantía Aremko" (editable)
    garantia_url:   "/garantia/" por default (página /garantia/ ya
                    existe en el sitio, registrada como name='garantia')

Brief Jorge / agente aremko-cli 2026-05-27 PM. Objetivo: agregar
confianza al lead que duda en gastar $270K, sin que parezca un
argumento de venta fuerte. Por eso es línea pequeña (0.85rem),
color gris medio, link sutil. NO compite con el botón CTA.

Si Jorge en el futuro deja `garantia_texto` vacío desde admin,
la línea no se renderiza. Si deja `garantia_url` vacío pero hay
texto, se muestra como texto plano (sin link).

Migración trivial: AddField × 2 con defaults que pueblan el
singleton existente. Sin RunPython necesario.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0113_refugio_paquete_3d_2n'),
    ]

    operations = [
        migrations.AddField(
            model_name='refugioconfig',
            name='garantia_texto',
            field=models.CharField(
                blank=True,
                default='Respaldado por la Garantía Aremko',
                help_text="Línea pequeña debajo de 'por 2 personas, todo incluido'. Si está vacío, no se muestra.",
                max_length=200,
                verbose_name='Garantía · texto sutil pie del precio',
            ),
        ),
        migrations.AddField(
            model_name='refugioconfig',
            name='garantia_url',
            field=models.CharField(
                blank=True,
                default='/garantia/',
                help_text='Path relativo (ej. /garantia/) o URL absoluta. Si está vacío, el texto se muestra sin link.',
                max_length=300,
                verbose_name='Garantía · URL del link',
            ),
        ),
    ]
