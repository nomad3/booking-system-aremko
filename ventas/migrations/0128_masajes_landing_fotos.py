# -*- coding: utf-8 -*-
# Migración escrita a mano (NO con makemigrations) para crear SOLO la tabla del
# singleton de fotos de la landing de masajes, evitando el drift de AR-034
# (mismo criterio que 0126/0127).
import cloudinary_storage.storage
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0127_pago_campos_para_copiar'),
    ]

    operations = [
        migrations.CreateModel(
            name='MasajesLandingConfig',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('video_hero', models.FileField(blank=True, help_text="EL VIDEO ESTRELLA: plano secuencia del recorrido (recepción → pasarelas → domos → mirador), 15-25 seg ya cortado, CON el audio del río. mp4 <5MB (comprimir antes). Si está vacío, el hero se muestra sin video.", max_length=255, null=True, storage=cloudinary_storage.storage.VideoMediaCloudinaryStorage(), upload_to='masajes_landing/')),
                ('foto_recepcion', models.ImageField(blank=True, help_text='Estación 1 — La recepción: el mesón de madera / el espacio que huele rico.', null=True, upload_to='masajes_landing/')),
                ('foto_camino', models.ImageField(blank=True, help_text='Estación 2 — El camino a los domos: pasarela de madera entre el bosque.', null=True, upload_to='masajes_landing/')),
                ('foto_sala_espera', models.ImageField(blank=True, help_text='Estación 3 — El domo de espera: los sillones de a dos con la mesa entre medio.', null=True, upload_to='masajes_landing/')),
                ('foto_domo_masaje', models.ImageField(blank=True, help_text='Estación 4 — Domo Sol o Luna: las DOS camillas listas, la madera, la luz tibia.', null=True, upload_to='masajes_landing/')),
                ('foto_masaje_pareja', models.ImageField(blank=True, help_text='Estación 5 — El masaje en pareja: las dos camillas en uso (manos, sin rostros).', null=True, upload_to='masajes_landing/')),
                ('foto_infusion', models.ImageField(blank=True, help_text='Estación 6 — La Infusión de la Masajista: manos sirviendo, vapor, hierbas a la vista. LA FOTO MÁS IMPORTANTE (también aparece en su sección propia).', null=True, upload_to='masajes_landing/')),
            ],
            options={
                'verbose_name': 'Landing Masajes (5 Sentidos)',
                'verbose_name_plural': 'Landing Masajes (5 Sentidos)',
            },
        ),
    ]
