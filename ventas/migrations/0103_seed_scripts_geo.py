"""
Data migration: Etapa Geo.3.c — 7 plantillas WhatsApp geo-conscientes.

Carga plantillas específicas para clientes 'nacional' (pack alojamiento)
y 'sin_clasificar' (neutras con captura implícita de ubicación).

Naming convention: <letra><número>-<sufijo-región>
  - A.1-N  = "En Riesgo · Amante Tinas × Pareja · nacional"
  - B.1-SC = "Dormido · genérico · sin_clasificar"

4 plantillas nacionales (region_geografica_target='nacional'):
  A.1-N · En Riesgo · Amante de las Tinas · Visitante Pareja · salva 1
  A.2-N · En Riesgo · Devoto del Masaje · Visitante Solo · salva 1
  A.3-N · En Riesgo · Experiencia Completa · Visitante Pareja · salva 1
  B.1-N · Dormido · genérico · salva 1

3 plantillas sin_clasificar (region_geografica_target='sin_clasificar'):
  A.1-SC · En Riesgo · Amante de las Tinas · Visitante Pareja · salva 1
  B.1-SC · Dormido · genérico · salva 1
  C.1-SC · En Prueba · genérico · salva 1

Operaciones idempotentes (update_or_create por script_id).
"""
from django.db import migrations


SCRIPTS_GEO = [
    # ────────────── NACIONAL — Pack alojamiento ──────────────
    {
        'script_id': 'A.1-N',
        'nombre': 'En Riesgo · Amante Tinas × Pareja · nacional · 1ª salva',
        'estado_valor_target': 'En Riesgo',
        'cohorte_estilo': 'Amante de las Tinas',
        'cohorte_contexto': 'Visitante Pareja',
        'salva': 1,
        'region_geografica_target': 'nacional',
        'plantilla_texto': (
            "Hola {nombre}, te escribe Aremko de Puerto Varas.\n\n"
            "Como les gustaron las tinas la última vez, te aviso que tenemos "
            "un pack romántico: 2 noches en cabaña con tina caliente privada "
            "+ desayunos. Tarifa pre-temporada hasta {fecha_limite}.\n\n"
            "¿Te tinca una escapada al sur?"
        ),
    },
    {
        'script_id': 'A.2-N',
        'nombre': 'En Riesgo · Devoto Masaje × Solo · nacional · 1ª salva',
        'estado_valor_target': 'En Riesgo',
        'cohorte_estilo': 'Devoto del Masaje',
        'cohorte_contexto': 'Visitante Solo',
        'salva': 1,
        'region_geografica_target': 'nacional',
        'plantilla_texto': (
            "Hola {nombre}, te escribe Aremko.\n\n"
            "Si te animas a una pausa larga, tenemos pack 3 noches en cabaña "
            "individual + masaje diario. Perfecto para desconectarte del todo.\n\n"
            "¿Te interesa que te cuente?"
        ),
    },
    {
        'script_id': 'A.3-N',
        'nombre': 'En Riesgo · Experiencia Completa × Pareja · nacional · 1ª salva',
        'estado_valor_target': 'En Riesgo',
        'cohorte_estilo': 'Experiencia Completa',
        'cohorte_contexto': 'Visitante Pareja',
        'salva': 1,
        'region_geografica_target': 'nacional',
        'plantilla_texto': (
            "Hola {nombre}, te escribe Aremko.\n\n"
            "Como les gustó el día completo, te aviso que abrimos un pack "
            "2 noches + spa + almuerzo para que vuelvan sin estrés de "
            "organizar nada. Hasta {fecha_limite} con tarifa especial.\n\n"
            "¿Les armo opciones?"
        ),
    },
    {
        'script_id': 'B.1-N',
        'nombre': 'Dormido · Genérico · nacional · 1ª salva',
        'estado_valor_target': 'Dormido',
        'cohorte_estilo': '',
        'cohorte_contexto': '',
        'salva': 1,
        'region_geografica_target': 'nacional',
        'plantilla_texto': (
            "Hola {nombre}, te escribe Aremko de Puerto Varas.\n\n"
            "Te extrañamos. Hace {dias_sin_venir} días que no vienes al sur. "
            "Si están pensando en una escapada, tenemos un pack 2 noches + spa "
            "con un detalle especial de bienvenida.\n\n"
            "¿Te tinca volver antes de fin de mes?"
        ),
    },

    # ────────────── SIN_CLASIFICAR — Neutras + captura implícita ──────────────
    {
        'script_id': 'A.1-SC',
        'nombre': 'En Riesgo · Amante Tinas × Pareja · sin_clasificar · 1ª salva',
        'estado_valor_target': 'En Riesgo',
        'cohorte_estilo': 'Amante de las Tinas',
        'cohorte_contexto': 'Visitante Pareja',
        'salva': 1,
        'region_geografica_target': 'sin_clasificar',
        'plantilla_texto': (
            "Hola {nombre}, te escribe Aremko de Puerto Varas.\n\n"
            "Hace {dias_sin_venir} días que no nos vemos. Si quieren volver, "
            "cuéntenme qué fecha les acomoda y desde dónde nos visitan — "
            "así les propongo el mejor plan (en el día o con cabaña)."
        ),
    },
    {
        'script_id': 'B.1-SC',
        'nombre': 'Dormido · Genérico · sin_clasificar · 1ª salva',
        'estado_valor_target': 'Dormido',
        'cohorte_estilo': '',
        'cohorte_contexto': '',
        'salva': 1,
        'region_geografica_target': 'sin_clasificar',
        'plantilla_texto': (
            "Hola {nombre}, te escribe Aremko de Puerto Varas.\n\n"
            "Te extrañamos. Hace {dias_sin_venir} días que no vienes. "
            "¿Quieres volver pronto? Cuéntame fecha + desde dónde vienes, "
            "así organizo todo a tu medida."
        ),
    },
    {
        'script_id': 'C.1-SC',
        'nombre': 'En Prueba · Genérico · sin_clasificar · día 30',
        'estado_valor_target': 'En Prueba',
        'cohorte_estilo': '',
        'cohorte_contexto': '',
        'salva': 1,
        'region_geografica_target': 'sin_clasificar',
        'plantilla_texto': (
            "Hola {nombre}, te escribe Aremko.\n\n"
            "Pasó un mes desde tu primera visita. ¿Cómo te sentiste? "
            "Si quieres volver, cuéntame qué fecha + desde dónde vienes "
            "para sugerirte el mejor plan."
        ),
    },
]


def seed_scripts_geo(apps, schema_editor):
    """Inserta/actualiza las 7 plantillas geo (idempotente)."""
    ScriptWhatsApp = apps.get_model('ventas', 'ScriptWhatsApp')
    creados = 0
    actualizados = 0
    for data in SCRIPTS_GEO:
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
        f"\n  [0103_seed_scripts_geo] {creados} creados, {actualizados} actualizados. "
        f"Total geo: {len(SCRIPTS_GEO)} plantillas (4 nacional + 3 sin_clasificar)."
    )


def unseed_scripts_geo(apps, schema_editor):
    """Reverso: elimina solo las 7 plantillas geo de este bootstrap."""
    ScriptWhatsApp = apps.get_model('ventas', 'ScriptWhatsApp')
    ids = [s['script_id'] for s in SCRIPTS_GEO]
    deleted, _ = ScriptWhatsApp.objects.filter(script_id__in=ids).delete()
    print(f"\n  [0103_seed_scripts_geo] {deleted} plantillas geo eliminadas.")


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0102_scriptwhatsapp_region_geografica_target'),
    ]

    operations = [
        migrations.RunPython(seed_scripts_geo, unseed_scripts_geo),
    ]
