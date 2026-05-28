"""
0115_plantillas_refugio_aremko
================================

Seed de 4 plantillas WhatsApp del programa "Refugio Aremko":

    B.refugio-N      En Riesgo + region=nacional
    B.refugio-SC     En Riesgo + region=sin_clasificar
    B.refugio-DOR-N  Dormido + region=nacional
    B.refugio-DOR-SC Dormido + region=sin_clasificar

Estrategia (Jorge 2026-05-27 PM, lanzamiento operativo lunes 30-may
06:00): el programa Refugio acelera el lanzamiento previsto del
15-jun. Estas 4 plantillas se aplican ANTES de la cascada normal de
retención (cuando el cliente califica), reemplazando el mensaje
genérico. Si NO califica → cascada normal sin cambios.

Criterios de calificación (en services/bandeja_whatsapp_service.py):
    1. region in (nacional, sin_clasificar) — NO sur (los del sur
       no se desplazan por el paquete; reciben retención normal)
    2. eje_valor in (En Riesgo, Dormido)
    3. salva == 1 (solo primera oportunidad)
    4. anti-saturación 60d sin Refugio previo
    5. cohorte: cualquiera (MVP genérico)

Idempotente vía update_or_create por script_id.
"""

from django.db import migrations, models


PLANTILLAS_REFUGIO = [
    # ── En Riesgo · nacional ───────────────────────────────────────
    {
        'script_id': 'B.refugio-N',
        'nombre': 'Refugio · En Riesgo · nacional',
        'estado_valor_target': 'En Riesgo',
        'cohorte_estilo': '',
        'cohorte_contexto': '',
        'salva': 1,
        'region_geografica_target': 'nacional',
        'plantilla_texto': (
            "¡Hola {nombre}! Te saluda Deborah desde Aremko Spa Boutique.\n\n"
            "Te escribo porque pensamos algo especialmente para quienes vienen "
            "de lejos: Refugio Aremko. Dos noches en cabaña con masaje en "
            "pareja y tinas calientes — la segunda noche, cortesía nuestra.\n\n"
            "Mira los detalles: aremko.cl/refugio\n\n"
            "¿Te tinca que te arme una propuesta para alguna fecha?"
        ),
        'activo': True,
    },
    # ── En Riesgo · sin_clasificar ─────────────────────────────────
    {
        'script_id': 'B.refugio-SC',
        'nombre': 'Refugio · En Riesgo · sin_clasificar',
        'estado_valor_target': 'En Riesgo',
        'cohorte_estilo': '',
        'cohorte_contexto': '',
        'salva': 1,
        'region_geografica_target': 'sin_clasificar',
        'plantilla_texto': (
            "¡Hola {nombre}! Te saluda Deborah desde Aremko Spa Boutique.\n\n"
            "Te escribo porque pensamos algo especial para quienes vienen a "
            "Puerto Varas desde otras ciudades: Refugio Aremko. Dos noches "
            "en cabaña con masaje en pareja y tinas calientes — la segunda "
            "noche, cortesía nuestra.\n\n"
            "Mira los detalles: aremko.cl/refugio\n\n"
            "¿Te tinca que te arme una propuesta para alguna fecha?"
        ),
        'activo': True,
    },
    # ── Dormido · nacional ─────────────────────────────────────────
    {
        'script_id': 'B.refugio-DOR-N',
        'nombre': 'Refugio · Dormido · nacional',
        'estado_valor_target': 'Dormido',
        'cohorte_estilo': '',
        'cohorte_contexto': '',
        'salva': 1,
        'region_geografica_target': 'nacional',
        'plantilla_texto': (
            "¡Hola {nombre}! Te saluda Deborah desde Aremko Spa Boutique.\n\n"
            "Han pasado {dias_sin_venir} días desde tu última visita, "
            "¡cuánto te extrañamos! Te escribo con algo pensado especialmente "
            "para quienes vienen de lejos: Refugio Aremko.\n\n"
            "Dos noches en cabaña con masaje en pareja y tinas calientes — "
            "la segunda noche, cortesía nuestra. Tres días para volver a tu "
            "centro.\n\n"
            "Mira los detalles: aremko.cl/refugio\n\n"
            "¿Te tinca que te arme una propuesta para alguna fecha?"
        ),
        'activo': True,
    },
    # ── Dormido · sin_clasificar ───────────────────────────────────
    {
        'script_id': 'B.refugio-DOR-SC',
        'nombre': 'Refugio · Dormido · sin_clasificar',
        'estado_valor_target': 'Dormido',
        'cohorte_estilo': '',
        'cohorte_contexto': '',
        'salva': 1,
        'region_geografica_target': 'sin_clasificar',
        'plantilla_texto': (
            "¡Hola {nombre}! Te saluda Deborah desde Aremko Spa Boutique.\n\n"
            "Han pasado {dias_sin_venir} días desde tu última visita, "
            "¡cuánto te extrañamos! Te escribo con algo pensado para quienes "
            "vienen a Puerto Varas desde otras ciudades: Refugio Aremko.\n\n"
            "Dos noches en cabaña con masaje en pareja y tinas calientes — "
            "la segunda noche, cortesía nuestra. Tres días para volver a tu "
            "centro.\n\n"
            "Mira los detalles: aremko.cl/refugio\n\n"
            "¿Te tinca que te arme una propuesta para alguna fecha?"
        ),
        'activo': True,
    },
]


def crear_plantillas_refugio(apps, schema_editor):
    ScriptWhatsApp = apps.get_model('ventas', 'ScriptWhatsApp')
    creadas = 0
    actualizadas = 0
    for data in PLANTILLAS_REFUGIO:
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
    print(f"  [Refugio] Plantillas: {creadas} creadas, {actualizadas} actualizadas")


def eliminar_plantillas_refugio(apps, schema_editor):
    ScriptWhatsApp = apps.get_model('ventas', 'ScriptWhatsApp')
    ids = [p['script_id'] for p in PLANTILLAS_REFUGIO]
    n, _ = ScriptWhatsApp.objects.filter(script_id__in=ids).delete()
    print(f"  [Refugio] Plantillas eliminadas: {n}")


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0114_refugio_garantia'),
    ]

    operations = [
        # 1) Ampliar max_length de ScriptWhatsApp.script_id de 10 a 30
        #    Los nuevos script_id Refugio superan los 10 chars:
        #      "B.refugio-N"     = 11
        #      "B.refugio-SC"    = 12
        #      "B.refugio-DOR-N" = 15
        #      "B.refugio-DOR-SC"= 16
        migrations.AlterField(
            model_name='scriptwhatsapp',
            name='script_id',
            field=models.CharField(
                db_index=True,
                help_text="Convención: 'A.1', 'B.2', 'B.refugio-N', etc. Letra=grupo, sufijo opcional.",
                max_length=30,
                unique=True,
            ),
        ),
        # 2) Insertar las 4 plantillas Refugio (idempotente vía update_or_create)
        migrations.RunPython(crear_plantillas_refugio, reverse_code=eliminar_plantillas_refugio),
    ]
