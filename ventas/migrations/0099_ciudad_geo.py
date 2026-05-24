"""
Migración: Etapa Geo.2.a — Modelo Ciudad + 3 campos en Cliente.

Crea:
  - Modelo Ciudad (catálogo con aliases + región geográfica)
  - Cliente.ciudad_normalizada (FK SET_NULL → Ciudad)
  - Cliente.region_geografica (default='sin_clasificar', indexed)
  - Cliente.ciudad_normalizada_manual (BooleanField default=False)

Sin data backfill. Las 3 columnas nuevas en Cliente tienen defaults
seguros que no requieren rewrite de filas existentes.

El seed inicial de Ciudades viene en la migración 0100 separada.
La normalización efectiva (asignar ciudad_normalizada a cada Cliente)
la hace el comando normalizar_ciudades_clientes en una corrida manual.
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0098_seed_scripts_extra'),
    ]

    operations = [
        # ====================================================================
        # 1. Modelo Ciudad
        # ====================================================================
        migrations.CreateModel(
            name='Ciudad',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre_canonico', models.CharField(
                    max_length=100, unique=True, db_index=True,
                    help_text="Nombre 'oficial' que se muestra (ej. 'Puerto Varas').",
                )),
                ('aliases', models.TextField(
                    blank=True,
                    help_text=(
                        'Aliases en minúscula separados por |. Ej: '
                        "'puerto varas|pto varas|pto. varas|p. varas'. Lookup es "
                        'case-insensitive y trim-aware.'
                    ),
                )),
                ('region_geografica', models.CharField(
                    max_length=20,
                    db_index=True,
                    choices=[
                        ('sur', 'Sur (≤120 km Puerto Varas)'),
                        ('nacional', 'Resto de Chile'),
                        ('extranjero', 'Extranjero'),
                    ],
                )),
                ('pais', models.CharField(max_length=50, default='Chile')),
                ('activo', models.BooleanField(default=True)),
                ('creado', models.DateTimeField(auto_now_add=True)),
                ('modificado', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Ciudad',
                'verbose_name_plural': 'Ciudades',
                'ordering': ['region_geografica', 'nombre_canonico'],
            },
        ),
        migrations.AddIndex(
            model_name='ciudad',
            index=models.Index(
                fields=['region_geografica', 'activo'],
                name='idx_ciudad_region_activo',
            ),
        ),

        # ====================================================================
        # 2. Campos nuevos en Cliente
        # ====================================================================
        migrations.AddField(
            model_name='cliente',
            name='ciudad_normalizada',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.SET_NULL,
                null=True, blank=True,
                related_name='clientes',
                to='ventas.ciudad',
                help_text="Mapeo del texto libre 'ciudad' a una Ciudad canónica.",
            ),
        ),
        migrations.AddField(
            model_name='cliente',
            name='region_geografica',
            field=models.CharField(
                max_length=20,
                default='sin_clasificar',
                db_index=True,
                choices=[
                    ('sur', 'Sur (≤120 km)'),
                    ('nacional', 'Resto de Chile'),
                    ('extranjero', 'Extranjero'),
                    ('sin_clasificar', 'Sin clasificar'),
                ],
                help_text='Categoría geográfica derivada. Define el tipo de mensaje WhatsApp.',
            ),
        ),
        migrations.AddField(
            model_name='cliente',
            name='ciudad_normalizada_manual',
            field=models.BooleanField(
                default=False,
                help_text=(
                    'True si el admin editó ciudad_normalizada/region_geografica '
                    'manualmente. El comando normalizar_ciudades_clientes RESPETA '
                    'estas ediciones y no las sobrescribe.'
                ),
            ),
        ),
    ]
