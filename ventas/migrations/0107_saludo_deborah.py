"""
0107_saludo_deborah
====================

Unifica las 4 variantes de saludo en ScriptWhatsApp.plantilla_texto al saludo
canónico nuevo:

    "Te saluda Deborah desde Aremko Spa Boutique"

Decisión de producto (Jorge, 2026-05-26 PM):
    El saludo "te escribe Aremko" / "soy de Aremko" era impersonal y rompía
    el tono del mensaje (cuerpo en primera persona singular). El nuevo
    establece la firma humana (Deborah) desde el inicio + recordatorio del
    rubro (Spa Boutique) para clientes con mucho tiempo sin venir.

Variantes encontradas y mapeo (orden de procesamiento importa — primero
las más largas para no romper las cortas):

    1. "te escribe Aremko de Puerto Varas" → "te saluda Deborah desde Aremko Spa Boutique"
    2. "Te escribo de Aremko"              → "Te saluda Deborah desde Aremko Spa Boutique"
    3. "te escribe Aremko"                 → "te saluda Deborah desde Aremko Spa Boutique"
    4. "soy de Aremko"                     → "te saluda Deborah desde Aremko Spa Boutique"

La capitalización (te/Te) depende del contexto:
    - Tras coma   ("Hola {nombre}, ...")           → minúscula
    - Tras signo  ("Hola {nombre}, ¿cómo has...?") → mayúscula

Idempotente: si una plantilla ya tiene el saludo nuevo, no se toca.
Reverse: no-op (revertir manualmente si fuera necesario; cambio cosmético).
"""

from django.db import migrations


# Orden importa: primero los matches largos para no comerse subcadenas.
REEMPLAZOS = [
    ('te escribe Aremko de Puerto Varas', 'te saluda Deborah desde Aremko Spa Boutique'),
    ('Te escribo de Aremko',              'Te saluda Deborah desde Aremko Spa Boutique'),
    ('te escribe Aremko',                 'te saluda Deborah desde Aremko Spa Boutique'),
    ('soy de Aremko',                     'te saluda Deborah desde Aremko Spa Boutique'),
]


def actualizar_saludo(apps, schema_editor):
    ScriptWhatsApp = apps.get_model('ventas', 'ScriptWhatsApp')

    actualizados = 0
    sin_match = 0
    detalle_por_patron = {}

    for script in ScriptWhatsApp.objects.all():
        texto_original = script.plantilla_texto or ''
        texto_nuevo = texto_original
        hubo_cambio_en_este = False

        for viejo, nuevo in REEMPLAZOS:
            if viejo in texto_nuevo:
                texto_nuevo = texto_nuevo.replace(viejo, nuevo)
                detalle_por_patron[viejo] = detalle_por_patron.get(viejo, 0) + 1
                hubo_cambio_en_este = True

        if hubo_cambio_en_este:
            script.plantilla_texto = texto_nuevo
            script.save(update_fields=['plantilla_texto'])
            actualizados += 1
        else:
            sin_match += 1

    print(f"  Saludo actualizado en {actualizados} plantillas ({sin_match} sin match):")
    for patron, n in detalle_por_patron.items():
        print(f"    · {n} script(s) tenían '{patron}'")


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0106_contactowhatsapp_estado_expirado_acumulacion'),
    ]

    operations = [
        migrations.RunPython(actualizar_saludo, reverse_code=migrations.RunPython.noop),
    ]
