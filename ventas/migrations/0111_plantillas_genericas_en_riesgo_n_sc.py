"""
0111_plantillas_genericas_en_riesgo_n_sc
==========================================

Seed de 2 plantillas genéricas para cubrir el gap detectado en cron
del 27-may PM: 39 candidatos En Riesgo en region=nacional/sin_clasificar
quedaban "sin script aplicable" porque no había plantilla específica
para su combinación cohorte_estilo + cohorte_contexto.

Las nuevas plantillas son catch-all (cohorte_estilo='' y cohorte_contexto='')
y se ubican en el nivel 4 de la cascada (genérico de región). Cuando el
cron busca scripts para En Riesgo + nacional/sin_clasificar + salva 1
sin más matches, encontrará estas como fallback.

Decisión de redacción Jorge 2026-05-27 PM:
    - Texto neutral sin "al sur", "esta semana" ni asunciones geográficas
    - Saludo Deborah Spa Boutique unificado (firma de marca)
    - {nombre} + {dias_sin_venir} + llamado a acción suave

Idempotente vía update_or_create por script_id.
"""

from django.db import migrations


PLANTILLAS_GENERICAS = [
    {
        'script_id': 'A.gen-N',
        'nombre': 'En Riesgo · genérica nacional · salva 1',
        'estado_valor_target': 'En Riesgo',
        'cohorte_estilo': '',     # catch-all estilo
        'cohorte_contexto': '',   # catch-all contexto
        'salva': 1,
        'region_geografica_target': 'nacional',
        'plantilla_texto': (
            "Hola {nombre}, te saluda Deborah desde Aremko Spa Boutique.\n\n"
            "Hace {dias_sin_venir} días que no nos visitas. Si estás pensando "
            "en una escapada estos meses, te armo un plan a tu medida.\n\n"
            "¿Te paso opciones?"
        ),
        'activo': True,
    },
    {
        'script_id': 'A.gen-SC',
        'nombre': 'En Riesgo · genérica sin_clasificar · salva 1',
        'estado_valor_target': 'En Riesgo',
        'cohorte_estilo': '',
        'cohorte_contexto': '',
        'salva': 1,
        'region_geografica_target': 'sin_clasificar',
        'plantilla_texto': (
            "Hola {nombre}, te saluda Deborah desde Aremko Spa Boutique.\n\n"
            "Hace {dias_sin_venir} días que no te vemos. ¿Te tinca darte un "
            "break con masaje, tina o algo así?\n\n"
            "Cuéntame qué te interesa y te paso opciones."
        ),
        'activo': True,
    },
]


def crear_plantillas(apps, schema_editor):
    ScriptWhatsApp = apps.get_model('ventas', 'ScriptWhatsApp')
    creadas = 0
    actualizadas = 0
    for data in PLANTILLAS_GENERICAS:
        obj, created = ScriptWhatsApp.objects.update_or_create(
            script_id=data['script_id'],
            defaults={
                'nombre': data['nombre'],
                'estado_valor_target': data['estado_valor_target'],
                'cohorte_estilo': data['cohorte_estilo'],
                'cohorte_contexto': data['cohorte_contexto'],
                'salva': data['salva'],
                'region_geografica_target': data['region_geografica_target'],
                'plantilla_texto': data['plantilla_texto'],
                'activo': data['activo'],
            },
        )
        if created:
            creadas += 1
        else:
            actualizadas += 1
    print(f"  Plantillas genéricas: {creadas} creadas, {actualizadas} actualizadas")


def eliminar_plantillas(apps, schema_editor):
    ScriptWhatsApp = apps.get_model('ventas', 'ScriptWhatsApp')
    ids = [p['script_id'] for p in PLANTILLAS_GENERICAS]
    n, _ = ScriptWhatsApp.objects.filter(script_id__in=ids).delete()
    print(f"  Plantillas genéricas eliminadas: {n}")


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0110_contactowhatsapp_es_relleno'),
    ]

    operations = [
        migrations.RunPython(crear_plantillas, reverse_code=eliminar_plantillas),
    ]
