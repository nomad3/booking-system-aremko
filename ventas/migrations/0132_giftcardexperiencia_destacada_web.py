# -*- coding: utf-8 -*-
"""Columna nueva con default: aditiva y sin ventana de corte.

Escrita a mano a propósito: `makemigrations ventas` arrastra el drift
AR-033/034 (quiere recrear ServiceHistory, CampaignEmailTemplate y compañía)
y eso en producción es exactamente lo que no queremos.

El backfill marca las 5 experiencias que la vitrina mostraba por la lista fija
de giftcard_views.py, para que la web se vea IGUAL después de migrar. Desde
ahí, la curaduría la maneja Jorge desde el admin.
"""
from django.db import migrations, models

IDS_INSIGNIA = ['tina_para_dos', 'pausa_junto_al_rio', 'noche_aguas_calientes',
                'ritual_del_rio', 'refugio_aremko']


def marcar_insignia(apps, schema_editor):
    GiftCardExperiencia = apps.get_model('ventas', 'GiftCardExperiencia')
    GiftCardExperiencia.objects.filter(
        id_experiencia__in=IDS_INSIGNIA).update(destacada_web=True)


def desmarcar(apps, schema_editor):
    GiftCardExperiencia = apps.get_model('ventas', 'GiftCardExperiencia')
    GiftCardExperiencia.objects.update(destacada_web=False)


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0131_masajeslandingconfig_video_recorrido'),
    ]

    operations = [
        migrations.AddField(
            model_name='giftcardexperiencia',
            name='destacada_web',
            field=models.BooleanField(
                db_index=True, default=False,
                help_text='Aparece en la vitrina de /giftcards/. Sin ninguna '
                          'marcada, la vitrina muestra todas las activas.',
                verbose_name='Destacada en la web'),
        ),
        migrations.RunPython(marcar_insignia, desmarcar),
    ]
