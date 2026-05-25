"""
Data migration: Etapa Geo.3.d — 4 plantillas mesa chica geo.

Origen: la primera corrida real de --dry-run después de Geo.3.c reveló
12 Leal/Campeón sin plantilla (7 sin_clasificar + 4 nacional + 1 Camp SC).
La regla "no fallback nacional/sin_clasificar" los bloqueó correctamente —
pero la mesa chica es Prioridad 0, no podemos perderlos.

Esta migración agrega 4 variantes geo-conscientes de E.1 (Leal) y E.2
(Campeón) — mismo concepto "mesa chica" pero con texto apropiado para
clientes que no vienen en el día:

  E.1-N  · Leal · nacional
  E.2-N  · Campeón · nacional
  E.1-SC · Leal · sin_clasificar
  E.2-SC · Campeón · sin_clasificar

Diferencia clave vs E.1/E.2 universales (que asumen sur):
  - sur:           "ven este mes, te reservo horario personalmente"
  - nacional:      "si están pensando escapada al sur, te armo pack a medida"
  - sin_clasificar: "cuéntame fecha y desde dónde, te armo el mejor plan"

Operaciones idempotentes (update_or_create por script_id).
"""
from django.db import migrations


SCRIPTS_MESA_CHICA_GEO = [
    # ────────────── NACIONAL ──────────────
    {
        'script_id': 'E.1-N',
        'nombre': 'Leal · Mesa Chica · nacional · 1ª salva',
        'estado_valor_target': 'Leal',
        'cohorte_estilo': '',
        'cohorte_contexto': '',
        'salva': 1,
        'region_geografica_target': 'nacional',
        'plantilla_texto': (
            "Hola {nombre}, ¿cómo has estado? Te escribo de Aremko.\n\n"
            "Estamos pensando en ti — eres parte de nuestra mesa chica de "
            "clientes. Si están pensando en una escapada al sur, te armo "
            "un pack a medida con todo incluido. Solo dime fecha aproximada "
            "y armamos algo perfecto.\n\n"
            "Un abrazo."
        ),
    },
    {
        'script_id': 'E.2-N',
        'nombre': 'Campeón · Mesa Chica · nacional · 1ª salva',
        'estado_valor_target': 'Campeón',
        'cohorte_estilo': '',
        'cohorte_contexto': '',
        'salva': 1,
        'region_geografica_target': 'nacional',
        'plantilla_texto': (
            "Hola {nombre}, ¿cómo has estado? Te escribo de Aremko.\n\n"
            "Estamos pensando en ti — eres parte de nuestra mesa chica de "
            "clientes. Si están pensando en una escapada al sur, te armo "
            "un pack a medida con todo incluido. Solo dime fecha aproximada "
            "y armamos algo perfecto.\n\n"
            "Un abrazo."
        ),
    },

    # ────────────── SIN_CLASIFICAR ──────────────
    {
        'script_id': 'E.1-SC',
        'nombre': 'Leal · Mesa Chica · sin_clasificar · 1ª salva',
        'estado_valor_target': 'Leal',
        'cohorte_estilo': '',
        'cohorte_contexto': '',
        'salva': 1,
        'region_geografica_target': 'sin_clasificar',
        'plantilla_texto': (
            "Hola {nombre}, ¿cómo has estado? Te escribo de Aremko.\n\n"
            "Estamos pensando en ti — eres parte de nuestra mesa chica de "
            "clientes. Si quieres venir pronto, cuéntame fecha y desde dónde "
            "nos visitas, así te armo el mejor plan a tu medida.\n\n"
            "Un abrazo."
        ),
    },
    {
        'script_id': 'E.2-SC',
        'nombre': 'Campeón · Mesa Chica · sin_clasificar · 1ª salva',
        'estado_valor_target': 'Campeón',
        'cohorte_estilo': '',
        'cohorte_contexto': '',
        'salva': 1,
        'region_geografica_target': 'sin_clasificar',
        'plantilla_texto': (
            "Hola {nombre}, ¿cómo has estado? Te escribo de Aremko.\n\n"
            "Estamos pensando en ti — eres parte de nuestra mesa chica de "
            "clientes. Si quieres venir pronto, cuéntame fecha y desde dónde "
            "nos visitas, así te armo el mejor plan a tu medida.\n\n"
            "Un abrazo."
        ),
    },
]


def seed_mesa_chica_geo(apps, schema_editor):
    """Inserta/actualiza las 4 plantillas mesa chica geo (idempotente)."""
    ScriptWhatsApp = apps.get_model('ventas', 'ScriptWhatsApp')
    creados = 0
    actualizados = 0
    for data in SCRIPTS_MESA_CHICA_GEO:
        script_id = data['script_id']
        defaults = {k: v for k, v in data.items() if k != 'script_id'}
        defaults['activo'] = True
        _, created = ScriptWhatsApp.objects.update_or_create(
            script_id=script_id,
            defaults=defaults,
        )
        if created:
            creados += 1
        else:
            actualizados += 1
    print(
        f"\n  [0104_seed_scripts_mesa_chica_geo] {creados} creados, "
        f"{actualizados} actualizados. Total: {len(SCRIPTS_MESA_CHICA_GEO)} plantillas."
    )


def unseed_mesa_chica_geo(apps, schema_editor):
    """Reverso: elimina solo las 4 plantillas de este bootstrap."""
    ScriptWhatsApp = apps.get_model('ventas', 'ScriptWhatsApp')
    ids = [s['script_id'] for s in SCRIPTS_MESA_CHICA_GEO]
    deleted, _ = ScriptWhatsApp.objects.filter(script_id__in=ids).delete()
    print(f"\n  [0104_seed_scripts_mesa_chica_geo] {deleted} plantillas eliminadas.")


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0103_seed_scripts_geo'),
    ]

    operations = [
        migrations.RunPython(seed_mesa_chica_geo, unseed_mesa_chica_geo),
    ]
