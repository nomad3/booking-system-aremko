# Segmentos (Historia 1, Historia 2…) con foto + revisión propia por historia.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('marketing_briefs', '0005_publicacionplanificada_hora_sugerida'),
    ]

    operations = [
        migrations.AddField(
            model_name='publicacionplanificada',
            name='segmentos',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='Sub-piezas visuales con revisión propia (Historia 1, Historia 2, …). '
                          'Solo para stories: cada segmento son 2+ historias distintas, cada una '
                          'con su foto y su veredicto. Cada item: {indice, titulo, texto, '
                          'material_urls, material_meta, revision_veredicto, revision_json, '
                          'revision_resumen, revision_at}. Vacío en piezas de una sola imagen.',
            ),
        ),
    ]
