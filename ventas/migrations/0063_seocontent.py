# Generated migration for SEOContent model

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0062_visualcampaign_visualcampaignrecipient_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='SEOContent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('meta_title', models.CharField(help_text='Título SEO (máx. 70 caracteres)', max_length=70)),
                ('meta_description', models.CharField(help_text='Meta descripción SEO (máx. 160 caracteres)', max_length=160)),
                ('contenido_principal', models.TextField(help_text='Texto principal de la categoría (180-300 palabras)')),
                ('subtitulo_principal', models.CharField(blank=True, help_text='Subtítulo descriptivo para la categoría', max_length=200)),
                ('beneficio_1_titulo', models.CharField(blank=True, max_length=100)),
                ('beneficio_1_descripcion', models.TextField(blank=True)),
                ('beneficio_2_titulo', models.CharField(blank=True, max_length=100)),
                ('beneficio_2_descripcion', models.TextField(blank=True)),
                ('beneficio_3_titulo', models.CharField(blank=True, max_length=100)),
                ('beneficio_3_descripcion', models.TextField(blank=True)),
                ('faq_1_pregunta', models.CharField(blank=True, max_length=200)),
                ('faq_1_respuesta', models.TextField(blank=True)),
                ('faq_2_pregunta', models.CharField(blank=True, max_length=200)),
                ('faq_2_respuesta', models.TextField(blank=True)),
                ('faq_3_pregunta', models.CharField(blank=True, max_length=200)),
                ('faq_3_respuesta', models.TextField(blank=True)),
                ('faq_4_pregunta', models.CharField(blank=True, max_length=200)),
                ('faq_4_respuesta', models.TextField(blank=True)),
                ('faq_5_pregunta', models.CharField(blank=True, max_length=200)),
                ('faq_5_respuesta', models.TextField(blank=True)),
                ('faq_6_pregunta', models.CharField(blank=True, max_length=200)),
                ('faq_6_respuesta', models.TextField(blank=True)),
                ('keywords', models.CharField(blank=True, help_text='Palabras clave separadas por comas', max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('categoria', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='seo_content', to='ventas.categoriaservicio')),
            ],
            options={
                'verbose_name': 'Contenido SEO',
                'verbose_name_plural': 'Contenidos SEO',
            },
        ),
    ]