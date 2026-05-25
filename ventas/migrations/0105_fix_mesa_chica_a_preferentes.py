"""
Data migration: reemplaza "mesa chica" por "clientes preferentes" en las 6
plantillas E (Leal + Campeón en sus 3 variantes geo).

Decisión de Jorge: "mesa chica" se siente menos chileno/más distante.
"Clientes preferentes" comunica el mismo concepto (selección VIP) con
tono más natural.

Plantillas afectadas:
  E.1     (Leal · universal)
  E.2     (Campeón · universal)
  E.1-N   (Leal · nacional)
  E.2-N   (Campeón · nacional)
  E.1-SC  (Leal · sin_clasificar)
  E.2-SC  (Campeón · sin_clasificar)

Reemplazos:
  "nuestra mesa chica de clientes" → "nuestros clientes preferentes"
  "nuestra mesa chica"             → "uno de nuestros clientes preferentes"
                                     (variante corta, por si admin la editó)

Idempotente: si la plantilla ya fue cambiada (o si nunca tuvo el string),
el .replace() simplemente no hace nada y no se persiste.

Reverso: deshace el cambio (clientes preferentes → mesa chica) para que
Jorge pueda volver atrás si no le convence el tono.
"""
from django.db import migrations


SCRIPTS_AFECTADOS = ['E.1', 'E.2', 'E.1-N', 'E.2-N', 'E.1-SC', 'E.2-SC']

REEMPLAZOS_FORWARD = [
    # Orden importa: probar primero la más larga (más específica).
    ('nuestra mesa chica de clientes', 'nuestros clientes preferentes'),
    ('nuestra mesa chica', 'uno de nuestros clientes preferentes'),
]

REEMPLAZOS_REVERSE = [
    # Orden inverso: deshacer primero la corta, después la larga.
    ('uno de nuestros clientes preferentes', 'nuestra mesa chica'),
    ('nuestros clientes preferentes', 'nuestra mesa chica de clientes'),
]


def _aplicar_reemplazos(apps, reemplazos, label):
    ScriptWhatsApp = apps.get_model('ventas', 'ScriptWhatsApp')
    actualizados = 0
    for script in ScriptWhatsApp.objects.filter(script_id__in=SCRIPTS_AFECTADOS):
        original = script.plantilla_texto
        nuevo = original
        for buscar, reemplazar in reemplazos:
            nuevo = nuevo.replace(buscar, reemplazar)
        if nuevo != original:
            script.plantilla_texto = nuevo
            script.save(update_fields=['plantilla_texto'])
            actualizados += 1
    print(
        f"\n  [0105_fix_mesa_chica_a_preferentes] {label}: "
        f"{actualizados} plantillas actualizadas (de {len(SCRIPTS_AFECTADOS)} posibles)."
    )


def forward(apps, schema_editor):
    _aplicar_reemplazos(apps, REEMPLAZOS_FORWARD, "mesa chica → clientes preferentes")


def reverse(apps, schema_editor):
    _aplicar_reemplazos(apps, REEMPLAZOS_REVERSE, "clientes preferentes → mesa chica")


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0104_seed_scripts_mesa_chica_geo'),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]
