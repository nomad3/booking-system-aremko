# Migración inicial de la app AISLADA catalogo_clips (H-070).
# Escrita a mano, drift-safe: sin dependencias cruzadas (no toca AR-033/AR-034).

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Clip',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('archivo', models.CharField(db_index=True, help_text='Nombre original del archivo (referencia; clave de upsert).', max_length=255, unique=True)),
                ('imagen', models.ImageField(blank=True, help_text='Solo la imagen optimizada (el master pesado NO se sube).', null=True, upload_to='catalogo_clips/')),
                ('cloud_url', models.URLField(blank=True, help_text='URL Cloudinary de la imagen optimizada (q_auto,f_auto,w_1440).', max_length=500)),
                ('tipo', models.CharField(choices=[('foto', 'Foto'), ('video', 'Video')], default='foto', max_length=10)),
                ('area', models.CharField(choices=[('tina', 'Tina'), ('masaje', 'Masaje'), ('cabaña', 'Cabaña'), ('entorno', 'Entorno'), ('detalle', 'Detalle'), ('aereo', 'Aéreo'), ('recepcion', 'Recepción'), ('entorno_region', 'Entorno región')], db_index=True, max_length=20)),
                ('nombre_comercial', models.CharField(blank=True, help_text='Nombre de la tina/cabaña/espacio (vacío si hay duda).', max_length=100)),
                ('momento', models.CharField(choices=[('dia', 'Día'), ('atardecer', 'Atardecer'), ('noche', 'Noche'), ('indistinto', 'Indistinto')], default='indistinto', max_length=12)),
                ('estacion', models.CharField(choices=[('invierno', 'Invierno'), ('verano', 'Verano'), ('indistinto', 'Indistinto')], default='indistinto', max_length=12)),
                ('vapor', models.CharField(choices=[('no', 'No'), ('sí', 'Sí'), ('sí (IA)', 'Sí (IA)')], default='no', max_length=8)),
                ('decoracion', models.CharField(blank=True, choices=[('con', 'Con decoración'), ('sin', 'Sin decoración'), ('', '—')], default='', max_length=4)),
                ('personas', models.BooleanField(default=False)),
                ('permiso', models.CharField(choices=[('libre', 'Libre'), ('revisar_derechos', 'Revisar derechos')], default='libre', max_length=20)),
                ('calidad', models.CharField(choices=[('alta', 'Alta'), ('media', 'Media')], default='media', max_length=6)),
                ('keeper', models.BooleanField(db_index=True, default=False, help_text='Hero: sin personas, nítida, distinta, no duplicado.')),
                ('descripcion', models.CharField(blank=True, max_length=300)),
                ('orientacion', models.CharField(blank=True, max_length=12)),
                ('estado', models.CharField(choices=[('ok', 'OK'), ('revisar', 'Revisar'), ('descartado', 'Descartado')], db_index=True, default='ok', max_length=12)),
                ('fuente', models.CharField(blank=True, default='disco', help_text='disco | chatgpt | ingesta_api | ...', max_length=30)),
                ('nota', models.TextField(blank=True)),
                ('origen', models.CharField(blank=True, help_text='Variantes / master de origen.', max_length=120)),
                ('etiquetas', models.JSONField(blank=True, default=list)),
                ('apto_para', models.JSONField(blank=True, default=list)),
                ('atributos', models.JSONField(blank=True, default=dict)),
                ('creado', models.DateTimeField(auto_now_add=True)),
                ('actualizado', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Clip del catálogo',
                'verbose_name_plural': 'Catálogo de clips',
                'ordering': ['-actualizado'],
            },
        ),
        migrations.AddIndex(
            model_name='clip',
            index=models.Index(fields=['area', 'keeper'], name='catalogo_cl_area_keeper_idx'),
        ),
        migrations.AddIndex(
            model_name='clip',
            index=models.Index(fields=['estado', 'tipo'], name='catalogo_cl_estado_tipo_idx'),
        ),
    ]
