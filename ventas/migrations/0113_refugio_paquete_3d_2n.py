"""
0113_refugio_paquete_3d_2n
===========================

CORRECCIÓN URGENTE del contenido de la landing /refugio/.

El paquete real (confirmado por Jorge 2026-05-27 PM) es:
    - 3 días / 2 noches en cabaña
    - 1 masaje en pareja (una sesión, en simultáneo)
    - 2 sesiones de tinas en pareja (una por tarde)
    - La segunda noche es cortesía Aremko
    - NO incluye desayuno
    - NO incluye late check-out (mecánica distinta con 2 noches)
    - Cupos: 5 cabañas
    - Restricción fechas: mes 1 sin restricción, mes 2+ solo dom-jueves
    - Cancelación: 48h antes sin costo

La migración 0112 dejó el singleton con el paquete equivocado (24h, 1
noche, desayuno, late check-out). Esta migración:

    1. Agrega 5 campos nuevos a RefugioConfig:
       duracion_texto, restricciones_fechas_texto, cancelacion_texto,
       para_quien_texto, como_llegar_texto
    2. Agrega ciudad_origen a RefugioLead
    3. RunPython: pisa los valores del singleton existente con los
       nuevos defaults correctos (hero_title, hero_subtitle,
       paquete_incluye, cupo_disponible_texto, seo_title, seo_description
       y los 5 campos nuevos).

La data migration es IDEMPOTENTE: corre update sobre el singleton sin
chequear estado previo. Como Jorge no ha editado nada todavía (la
landing recién se desactivó tras detectarse el bug), es seguro pisar.
"""

from django.db import migrations, models


# Textos canónicos del paquete correcto (idénticos a los defaults del modelo)
HERO_TITLE = "Tres días para volver a tu centro"
HERO_SUBTITLE = "Refugio Aremko · 2 noches en cabaña con masajes y tinas calientes"
CUPO_TEXTO = "Cupos limitados — 5 cabañas"
PAQUETE_INCLUYE = (
    "Dos noches en cabaña de naturaleza — Cabaña privada para 2 personas\n"
    "Masaje en pareja — Una sesión profesional, en simultáneo\n"
    "Tinas calientes en pareja — Dos tardes con vista al bosque\n"
    "🎁 Cortesía Aremko — La segunda noche, regalo nuestro"
)
SEO_TITLE = "Refugio Aremko · 3 días en Puerto Varas | Cabaña + masajes + tinas"
SEO_DESCRIPTION = (
    "Tres días para volver a tu centro. Cabaña en naturaleza, "
    "masaje en pareja, tinas calientes. La segunda noche, cortesía "
    "Aremko. $270.000 por 2 personas."
)
DURACION_TEXTO = "Check-in en el día 1 · Check-out el día 3. Dos noches completas en cabaña."
RESTRICCIONES_FECHAS_TEXTO = (
    "Válido cualquier día durante el mes de lanzamiento "
    "(15-jun a 15-jul-2026). Desde el 16-jul en adelante, "
    "solo domingo a jueves."
)
CANCELACION_TEXTO = "Hasta 48 horas antes del check-in sin costo."
PARA_QUIEN_TEXTO = "Pensado para parejas o adultos buscando una pausa profunda."
COMO_LLEGAR_TEXTO = "15 minutos en auto desde el centro de Puerto Varas."


def aplicar_paquete_correcto(apps, schema_editor):
    """Pisa los valores del singleton RefugioConfig con el paquete correcto.

    Idempotente: corre update sin condiciones previas. Es seguro porque
    el singleton acaba de crearse con defaults equivocados y nadie editó
    aún (la landing fue desactivada justo al detectar el problema).
    """
    RefugioConfig = apps.get_model('ventas', 'RefugioConfig')
    # Singleton — usar el primer (y único) registro si existe
    cfg = RefugioConfig.objects.first()
    if not cfg:
        # Aún no se accedió al admin → el get_solo del modelo creará
        # uno con los defaults nuevos en el primer hit. Nada que hacer.
        print("  [Refugio 0113] Singleton no existe aún — defaults nuevos se aplicarán al primer get_solo()")
        return

    cfg.hero_title = HERO_TITLE
    cfg.hero_subtitle = HERO_SUBTITLE
    cfg.cupo_disponible_texto = CUPO_TEXTO
    cfg.paquete_incluye = PAQUETE_INCLUYE
    cfg.seo_title = SEO_TITLE
    cfg.seo_description = SEO_DESCRIPTION
    cfg.duracion_texto = DURACION_TEXTO
    cfg.restricciones_fechas_texto = RESTRICCIONES_FECHAS_TEXTO
    cfg.cancelacion_texto = CANCELACION_TEXTO
    cfg.para_quien_texto = PARA_QUIEN_TEXTO
    cfg.como_llegar_texto = COMO_LLEGAR_TEXTO
    cfg.save()
    print(f"  [Refugio 0113] Singleton {cfg.id} actualizado al paquete 3D/2N")


def revertir_paquete_correcto(apps, schema_editor):
    """No-op: los campos nuevos se eliminan por la migración inversa
    de RemoveField. Los textos viejos no son recuperables."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0112_landing_refugio'),
    ]

    operations = [
        # 1) Ampliar SEO title/description (los actuales son cortos)
        migrations.AlterField(
            model_name='refugioconfig',
            name='seo_title',
            field=models.CharField(
                default=SEO_TITLE,
                max_length=120,
                verbose_name='SEO Title',
            ),
        ),
        migrations.AlterField(
            model_name='refugioconfig',
            name='seo_description',
            field=models.CharField(
                default=SEO_DESCRIPTION,
                max_length=300,
                verbose_name='SEO Meta Description',
            ),
        ),

        # 2) 5 campos nuevos en RefugioConfig
        migrations.AddField(
            model_name='refugioconfig',
            name='duracion_texto',
            field=models.CharField(
                default=DURACION_TEXTO,
                max_length=300,
                verbose_name='Detalles · Duración',
            ),
        ),
        migrations.AddField(
            model_name='refugioconfig',
            name='restricciones_fechas_texto',
            field=models.TextField(
                default=RESTRICCIONES_FECHAS_TEXTO,
                verbose_name='Detalles · Cuándo usarlo',
            ),
        ),
        migrations.AddField(
            model_name='refugioconfig',
            name='cancelacion_texto',
            field=models.CharField(
                default=CANCELACION_TEXTO,
                max_length=300,
                verbose_name='Detalles · Política de cancelación',
            ),
        ),
        migrations.AddField(
            model_name='refugioconfig',
            name='para_quien_texto',
            field=models.CharField(
                default=PARA_QUIEN_TEXTO,
                max_length=300,
                verbose_name='Detalles · Para quién',
            ),
        ),
        migrations.AddField(
            model_name='refugioconfig',
            name='como_llegar_texto',
            field=models.CharField(
                default=COMO_LLEGAR_TEXTO,
                max_length=300,
                verbose_name='Detalles · Cómo llegar',
            ),
        ),

        # 3) ciudad_origen en RefugioLead
        migrations.AddField(
            model_name='refugiolead',
            name='ciudad_origen',
            field=models.CharField(
                blank=True,
                help_text='De dónde viene el lead — útil para segmentar campañas.',
                max_length=120,
                verbose_name='Ciudad de origen',
            ),
        ),

        # 4) Data migration: pisar el singleton con los textos correctos
        migrations.RunPython(aplicar_paquete_correcto, reverse_code=revertir_paquete_correcto),
    ]
