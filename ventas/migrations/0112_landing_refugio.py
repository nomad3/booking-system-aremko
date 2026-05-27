"""
0112_landing_refugio
=====================

Crea las 3 tablas que soportan la landing pública /refugio/:

    - RefugioConfig: singleton con textos editables (hero, paquete,
      precio CLP, SEO meta) — patrón HomepageConfig vía django-solo.
    - RefugioImagen: galería ordenable de la sección "Galería" de la
      landing (admin sube fotos hasta el lanzamiento 15-jun-2026).
    - RefugioLead: leads del formulario público con tracking UTM
      completo (source/medium/campaign/content/term + referer + IP)
      y workflow simple (nuevo → contactado → cotizado → reservado).

Contexto:
    Brief Jorge 2026-05-27 PM. Lanzamiento previsto 15-jun-2026.
    Decisión: modelo dedicado RefugioLead (no reusar Lead B2B) para
    no contaminar el embudo de empresas y poder tener campos
    específicos (fecha_tentativa, num_personas).

Migración trivial: 3 CreateModel + 3 índices sobre RefugioLead.
Sin data migration ni dependencias cruzadas con otros modelos.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0111_plantillas_genericas_en_riesgo_n_sc'),
    ]

    operations = [
        migrations.CreateModel(
            name='RefugioConfig',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('hero_title', models.CharField(default='Refugio Aremko', max_length=200, verbose_name='Título Hero')),
                ('hero_subtitle', models.CharField(default='Una pausa de 24 horas para reconectar contigo', max_length=300, verbose_name='Subtítulo Hero')),
                ('hero_cta_text', models.CharField(default='Reserva tu Refugio', max_length=60, verbose_name='Texto botón principal Hero')),
                ('precio_clp', models.PositiveIntegerField(default=270000, help_text='Precio total del paquete Refugio en pesos chilenos.', verbose_name='Precio (CLP)')),
                ('paquete_titulo', models.CharField(default='Tu Refugio Incluye', max_length=120, verbose_name='Título sección paquete')),
                ('paquete_incluye', models.TextField(
                    default='Alojamiento 1 noche en cabaña\nTina caliente privada\nMasaje relajante 60 min por persona\nDesayuno de campo\nLate check-out 14:00',
                    help_text='Una línea por ítem. Se renderizan como bullets en la landing.',
                    verbose_name="Lista 'Qué incluye' (una línea por item)",
                )),
                ('fecha_limite_oferta', models.DateField(blank=True, null=True, help_text='Si se completa, se muestra como urgencia en la landing.', verbose_name='Fecha límite oferta')),
                ('cupo_disponible_texto', models.CharField(blank=True, default='Cupos limitados', max_length=120, verbose_name='Texto urgencia/escasez')),
                ('por_que_titulo', models.CharField(default='¿Por qué Aremko?', max_length=200, verbose_name="Título sección 'Por qué'")),
                ('por_que_texto', models.TextField(
                    default='Llevamos años cuidando a quienes buscan desconectar. Tinajas calientes con vista al sur, masajes terapéuticos y un entorno pensado para que recuperes el ritmo.',
                    verbose_name="Texto 'Por qué Aremko'",
                )),
                ('cta_final_titulo', models.CharField(default='Reserva tu Refugio', max_length=200, verbose_name='Título CTA final')),
                ('cta_final_subtitulo', models.CharField(default='Te contactamos dentro de 24 horas para coordinar tu fecha.', max_length=300, verbose_name='Subtítulo CTA final')),
                ('seo_title', models.CharField(default='Refugio Aremko · Pausa de 24h en Puerto Varas', max_length=70, verbose_name='SEO Title')),
                ('seo_description', models.CharField(
                    default='Pasa una noche en Aremko Spa: cabaña, tina caliente, masaje y desayuno por $270.000. Reserva tu Refugio en Puerto Varas.',
                    max_length=200,
                    verbose_name='SEO Meta Description',
                )),
                ('og_image', models.ImageField(blank=True, null=True, upload_to='refugio/', verbose_name='Imagen Open Graph (1200x630)')),
                ('activo', models.BooleanField(default=True, help_text='Si está desactivada, la URL /refugio/ devuelve 404.', verbose_name='Landing activa')),
            ],
            options={
                'verbose_name': 'Configuración Landing Refugio',
                'verbose_name_plural': 'Configuración Landing Refugio',
            },
        ),
        migrations.CreateModel(
            name='RefugioImagen',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('imagen', models.ImageField(upload_to='refugio/galeria/', verbose_name='Imagen')),
                ('alt_text', models.CharField(blank=True, help_text='Descripción para lectores de pantalla y SEO.', max_length=200, verbose_name='Alt text (SEO/accesibilidad)')),
                ('orden', models.PositiveIntegerField(default=10, help_text='Menor número = aparece primero.', verbose_name='Orden')),
                ('activa', models.BooleanField(default=True, verbose_name='Activa')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Imagen Refugio',
                'verbose_name_plural': 'Galería Refugio',
                'ordering': ['orden', 'id'],
            },
        ),
        migrations.CreateModel(
            name='RefugioLead',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=120, verbose_name='Nombre')),
                ('email', models.EmailField(max_length=254, verbose_name='Email')),
                ('telefono', models.CharField(blank=True, help_text='Idealmente con +56. Si viene sin prefijo se acepta igual.', max_length=30, verbose_name='Teléfono')),
                ('fecha_tentativa', models.DateField(blank=True, null=True, verbose_name='Fecha tentativa')),
                ('num_personas', models.PositiveSmallIntegerField(default=2, verbose_name='Número de personas')),
                ('mensaje', models.TextField(blank=True, verbose_name='Mensaje libre')),
                ('utm_source', models.CharField(blank=True, max_length=120, verbose_name='utm_source')),
                ('utm_medium', models.CharField(blank=True, max_length=120, verbose_name='utm_medium')),
                ('utm_campaign', models.CharField(blank=True, max_length=120, verbose_name='utm_campaign')),
                ('utm_content', models.CharField(blank=True, max_length=120, verbose_name='utm_content')),
                ('utm_term', models.CharField(blank=True, max_length=120, verbose_name='utm_term')),
                ('referer', models.CharField(blank=True, max_length=500, verbose_name='Referer')),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True, verbose_name='IP')),
                ('user_agent', models.CharField(blank=True, max_length=500, verbose_name='User-Agent')),
                ('status', models.CharField(
                    choices=[
                        ('nuevo', 'Nuevo'),
                        ('contactado', 'Contactado'),
                        ('cotizado', 'Cotizado'),
                        ('reservado', 'Reservado'),
                        ('descartado', 'Descartado'),
                    ],
                    default='nuevo',
                    max_length=20,
                    verbose_name='Estado',
                )),
                ('notas_internas', models.TextField(blank=True, help_text='Notas del equipo de ventas. No se muestran al cliente.', verbose_name='Notas internas')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Recibido')),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Lead Refugio',
                'verbose_name_plural': 'Leads Refugio',
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['-created_at'], name='idx_refugiolead_created'),
                    models.Index(fields=['status', '-created_at'], name='idx_refugiolead_status'),
                    models.Index(fields=['utm_campaign'], name='idx_refugiolead_utm_camp'),
                ],
            },
        ),
    ]
