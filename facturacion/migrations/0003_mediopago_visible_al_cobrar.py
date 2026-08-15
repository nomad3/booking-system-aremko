from django.db import migrations, models

# Los que Jorge dejó de usar (2026-08-15). Se ocultan del selector de cobro;
# los pagos históricos con estos medios quedan intactos.
OCULTAR_AL_COBRAR = [
    'transferencia',        # transferencia genérica, sin cuenta identificada
    'webpay',
    'descuento',            # pseudo-pago obsoleto: el descuento tiene su campo
    'machjorge', 'machalda',
    'bicegoalda', 'bcialda', 'andesalda',
    'mercadopagoaremko',
    'scotiabankalda',
    'copecjorge', 'copecalda',
]


def ocultar_medios_en_desuso(apps, schema_editor):
    MedioPago = apps.get_model('facturacion', 'MedioPago')
    MedioPago.objects.filter(codigo__in=OCULTAR_AL_COBRAR).update(visible_al_cobrar=False)


def mostrar_todos(apps, schema_editor):
    MedioPago = apps.get_model('facturacion', 'MedioPago')
    MedioPago.objects.filter(codigo__in=OCULTAR_AL_COBRAR).update(visible_al_cobrar=True)


class Migration(migrations.Migration):
    """MedioPago.visible_al_cobrar: switch para esconder del selector de pago
    los medios que ya no se usan, sin borrarlos ni tocar el historial.

    Columna pre-agregada a mano en Render antes del push (el admin nuevo la LEE
    al armar el selector de cobro), igual que en ventas/0134. Ver
    [[feedback_deploy_columna_preagregada]].
    """

    dependencies = [
        ('facturacion', '0002_certificacion_set_pruebas'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='mediopago',
                    name='visible_al_cobrar',
                    field=models.BooleanField(
                        default=True,
                        verbose_name='Visible al cobrar',
                        help_text='ON: aparece en el selector de método de pago del admin. '
                                  'OFF: se esconde del selector SIN borrar nada — los pagos '
                                  'históricos con este medio siguen intactos y se siguen viendo.',
                    ),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE facturacion_mediopago "
                        "ADD COLUMN IF NOT EXISTS visible_al_cobrar boolean NOT NULL DEFAULT true;"
                    ),
                    reverse_sql=(
                        "ALTER TABLE facturacion_mediopago DROP COLUMN IF EXISTS visible_al_cobrar;"
                    ),
                ),
            ],
        ),
        migrations.RunPython(ocultar_medios_en_desuso, mostrar_todos),
    ]
