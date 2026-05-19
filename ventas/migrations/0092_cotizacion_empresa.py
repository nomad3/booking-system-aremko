"""Modelos CotizacionFormal + CotizacionItem + extensión ConfiguracionResumen.

Permite generar cotizaciones formales numeradas (desde 321) para empresas
sin tener que crear una VentaReserva. La cotización lista servicios y
productos con cantidades y precios pero NO tiene fechas — al aceptarse,
se coordinan las fechas manualmente y eventualmente se crea VentaReserva.

Migración manual en Render (regla del proyecto).
"""
from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0091_ga4snapshot_searchconsolesnapshot'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CotizacionFormal',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('estado', models.CharField(
                    choices=[
                        ('borrador', 'Borrador'),
                        ('enviada', 'Enviada'),
                        ('aceptada', 'Aceptada'),
                        ('rechazada', 'Rechazada'),
                        ('expirada', 'Expirada'),
                    ],
                    db_index=True, default='borrador', max_length=20,
                )),
                ('fecha_emision', models.DateField(auto_now_add=True, db_index=True)),
                ('validez_dias', models.PositiveIntegerField(
                    default=30,
                    help_text='Días de validez de la cotización desde la emisión',
                )),
                ('empresa_razon_social', models.CharField(max_length=200)),
                ('empresa_rut', models.CharField(blank=True, max_length=20)),
                ('empresa_giro', models.CharField(blank=True, help_text='Giro comercial (opcional)', max_length=200)),
                ('contacto_nombre', models.CharField(max_length=120)),
                ('contacto_email', models.EmailField(blank=True, max_length=254)),
                ('contacto_telefono', models.CharField(blank=True, max_length=20)),
                ('frase_beneficios', models.TextField(
                    blank=True,
                    help_text='Si vacío, usa la frase global desde ConfiguracionResumen.cotizacion_frase_beneficios.',
                )),
                ('notas', models.TextField(blank=True, help_text='Notas internas, no visibles para el cliente.')),
                ('fecha_envio', models.DateTimeField(blank=True, null=True)),
                ('fecha_aceptacion', models.DateTimeField(blank=True, null=True)),
                ('motivo_rechazo', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='cotizaciones_creadas',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'Cotización Formal (documento)',
                'verbose_name_plural': 'Cotizaciones Formales (documentos)',
                'ordering': ['-fecha_emision', '-id'],
                'indexes': [
                    models.Index(fields=['-fecha_emision'], name='ventas_cotform_femis_idx'),
                    models.Index(fields=['estado', '-fecha_emision'], name='ventas_cotform_est_idx'),
                ],
            },
        ),
        migrations.CreateModel(
            name='CotizacionItem',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('descripcion_custom', models.CharField(
                    blank=True,
                    help_text='Para items que no están en el catálogo (servicio/producto a medida).',
                    max_length=200,
                )),
                ('cantidad', models.PositiveIntegerField(default=1)),
                ('precio_unitario', models.DecimalField(
                    decimal_places=0, max_digits=10,
                    help_text='Snapshot del precio al momento de cotizar (CLP, sin decimales).',
                )),
                ('orden', models.PositiveIntegerField(default=0, help_text='Orden de aparición en el documento')),
                ('cotizacion', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='items',
                    to='ventas.cotizacionformal',
                )),
                ('producto', models.ForeignKey(
                    blank=True, null=True,
                    help_text='Si es un producto del catálogo.',
                    on_delete=django.db.models.deletion.SET_NULL,
                    to='ventas.producto',
                )),
                ('servicio', models.ForeignKey(
                    blank=True, null=True,
                    help_text='Si es un servicio del catálogo.',
                    on_delete=django.db.models.deletion.SET_NULL,
                    to='ventas.servicio',
                )),
            ],
            options={
                'verbose_name': 'Ítem de cotización',
                'verbose_name_plural': 'Ítems de cotización',
                'ordering': ['orden', 'id'],
            },
        ),
        migrations.AddField(
            model_name='configuracionresumen',
            name='cotizacion_frase_beneficios',
            field=models.TextField(
                blank=True,
                help_text=(
                    'Frase formal sobre beneficios para el equipo/grupo. Aparece debajo de la tabla '
                    'de servicios en el documento de cotización. Si se deja vacío, se usa el default '
                    'del código. Cada cotización puede sobrescribir esta frase individualmente.'
                ),
                verbose_name='Cotización: frase de beneficios para el grupo',
            ),
        ),
        migrations.AddField(
            model_name='configuracionresumen',
            name='cotizacion_terminos',
            field=models.TextField(
                blank=True,
                help_text='Términos legales/operativos. Validez, forma de pago, etc.',
                verbose_name='Cotización: términos y condiciones',
            ),
        ),
        migrations.AddField(
            model_name='configuracionresumen',
            name='cotizacion_cierre',
            field=models.TextField(
                blank=True,
                help_text="Firma de cierre del documento (ej: 'Cordialmente, Equipo Aremko...').",
                verbose_name='Cotización: cierre formal',
            ),
        ),
    ]
