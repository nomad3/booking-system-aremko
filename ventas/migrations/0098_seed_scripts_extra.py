"""
Data migration: agrega 3 plantillas que cierran los gaps detectados.

Origen del diagnóstico: `python manage.py analizar_bandeja_potencial`
sobre los 14.228 clientes de producción reveló 364 candidatos priorizados
sin script aplicable. Esta migración los cubre al 100%:

    A.6  →  En Riesgo · Genérico · 1ª salva           (cubre 331 clientes)
    D.3  →  Regular · Genérico · 1ª salva             (cubre 33 clientes)
    A.7  →  En Riesgo · Devoto Masaje × Pareja · 1ª   (cohorte top específica, 142 clientes)

Después de aplicar esta migración:
    - Total plantillas: 14 (0097) + 3 (0098) = 17
    - Cobertura de plantillas: 100% de los candidatos priorizados

Operaciones idempotentes:
    - update_or_create por script_id (re-aplicar no rompe)
    - Reverso borra solo los 3 script_id del bootstrap

Si quieres editar el texto en producción, usa el admin Django (Etapa 7),
NO esta migración.
"""
from django.db import migrations


SCRIPTS_EXTRA = [
    # ────────────── A.6 · En Riesgo genérico (fallback de cascada) ──────────
    # Captura todas las cohortes En Riesgo que no tienen plantilla específica
    # (A.1-A.5, A.7). El placeholder {dias_sin_venir} personaliza por cliente
    # incluso siendo mensaje genérico.
    {
        'script_id': 'A.6',
        'nombre': 'En Riesgo · Genérico · 1ª salva',
        'estado_valor_target': 'En Riesgo',
        'cohorte_estilo': '',
        'cohorte_contexto': '',
        'salva': 1,
        'plantilla_texto': (
            "Hola {nombre}, te escribe Aremko de Puerto Varas.\n\n"
            "Nos acordamos de ti — hace {dias_sin_venir} días que no te vemos. "
            "¿Te tinca venir antes de fin de mes? Cuéntame qué día te acomoda."
        ),
    },

    # ────────────── A.7 · En Riesgo · Devoto Masaje × Pareja ────────────────
    # Cohorte más grande sin script (142 clientes). Tono cálido, foco en
    # "ustedes dos", sin presión ni ofertas explícitas.
    {
        'script_id': 'A.7',
        'nombre': 'En Riesgo · Devoto Masaje × Pareja · 1ª salva',
        'estado_valor_target': 'En Riesgo',
        'cohorte_estilo': 'Devoto del Masaje',
        'cohorte_contexto': 'Visitante Pareja',
        'salva': 1,
        'plantilla_texto': (
            "Hola {nombre}, te escribe Aremko de Puerto Varas.\n\n"
            "¿Hace cuánto que no se regalan una tarde solo para ustedes dos? "
            "Tenemos cupos para masajes en pareja estos días — sin apuro, sin reloj.\n\n"
            "Si quieren darse esa pausa, escríbeme y armamos algo."
        ),
    },

    # ────────────── D.3 · Regular genérico ──────────────────────────────────
    # P4 (Regular atrasado) tenía 0% cobertura porque solo existía D.1
    # (Amante Tinas × Pareja). Este genérico cubre los 33 sin script + futuras
    # cohortes Regular.
    {
        'script_id': 'D.3',
        'nombre': 'Regular · Genérico · 1ª salva',
        'estado_valor_target': 'Regular',
        'cohorte_estilo': '',
        'cohorte_contexto': '',
        'salva': 1,
        'plantilla_texto': (
            "Hola {nombre}, te escribe Aremko.\n\n"
            "Como nos visitas seguido, quería contarte que tenemos algunas "
            "novedades este {mes_proximo} y quería que estuvieras entre los "
            "primeros en saberlo.\n\n"
            "¿Te lo cuento por aquí?"
        ),
    },
]


def seed_scripts_extra(apps, schema_editor):
    """Inserta/actualiza las 3 plantillas adicionales (idempotente)."""
    ScriptWhatsApp = apps.get_model('ventas', 'ScriptWhatsApp')

    creados = 0
    actualizados = 0
    for data in SCRIPTS_EXTRA:
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

    print(f"\n  [0098_seed_scripts_extra] {creados} scripts creados, "
          f"{actualizados} actualizados. Total agregados: {len(SCRIPTS_EXTRA)}.")


def unseed_scripts_extra(apps, schema_editor):
    """Reversión: elimina solo los 3 script_id de esta migración."""
    ScriptWhatsApp = apps.get_model('ventas', 'ScriptWhatsApp')
    ids = [s['script_id'] for s in SCRIPTS_EXTRA]
    deleted, _ = ScriptWhatsApp.objects.filter(script_id__in=ids).delete()
    print(f"\n  [0098_seed_scripts_extra] {deleted} scripts eliminados.")


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0097_seed_scripts_whatsapp'),
    ]

    operations = [
        migrations.RunPython(seed_scripts_extra, unseed_scripts_extra),
    ]
