"""
0108_quitar_almuerzo_plantillas
================================

Bug crítico de contenido detectado por Jorge (2026-05-26 PM):
    Plantillas A.3 y A.3-N prometían "almuerzo incluido" pero Aremko NO
    tiene restaurante. Solo ofrece tabla de quesos, jamones o mixta para
    compartir (servicio adicional opcional, no incluido en pack base).

    Riesgo de daño reputacional + frustración + cancelaciones si los
    clientes llegan esperando almuerzo y no hay.

Decisiones de redacción (Jorge):
    - A.3: eliminar tanto "5 horas" como "almuerzo incluido" → texto más
      sobrio "día de spa entre semana".
    - A.3-N: reemplazar "+ almuerzo para que vuelvan sin estrés de
      organizar nada" por "pack 2 noches + spa, ideal para desconectarse.
      Además pueden agregar tabla de quesos, jamones o mixta para
      compartir" — el cliente sabe que la tabla es agregable, no incluida.

NO se toca A.1-N que menciona "desayunos": Aremko SÍ tiene servicio de
desayuno (existe pack alojamiento + tina + desayuno).

Reemplazos exactos por seguridad — la migración loguea cuántos scripts
matched cada patrón, para detectar variantes inesperadas en producción.

Idempotente: si las plantillas ya tienen la versión nueva, no se tocan.
"""

from django.db import migrations


REEMPLAZOS = [
    # (script_id sugerido, fragmento_viejo, fragmento_nuevo)
    (
        'A.3',
        'día spa de 5 horas con almuerzo incluido entre semana',
        'día de spa entre semana',
    ),
    (
        'A.3-N',
        'pack 2 noches + spa + almuerzo para que vuelvan sin estrés de organizar nada',
        'pack 2 noches + spa, ideal para desconectarse. Además pueden agregar tabla de quesos, jamones o mixta para compartir',
    ),
]


def quitar_almuerzo(apps, schema_editor):
    ScriptWhatsApp = apps.get_model('ventas', 'ScriptWhatsApp')

    total_actualizados = 0
    for script_id_hint, viejo, nuevo in REEMPLAZOS:
        # Buscar en TODAS las plantillas que contengan el fragmento viejo
        # (no solo el script_id sugerido — defensive en caso de variantes
        # editadas vía admin que tengan el mismo texto en otro script_id).
        candidatos = ScriptWhatsApp.objects.filter(plantilla_texto__contains=viejo)
        n_matches = candidatos.count()
        if n_matches == 0:
            print(f"  [{script_id_hint}] sin match para '{viejo[:50]}...' (probablemente ya estaba arreglado)")
            continue
        for script in candidatos:
            script.plantilla_texto = script.plantilla_texto.replace(viejo, nuevo)
            script.save(update_fields=['plantilla_texto'])
            total_actualizados += 1
        print(f"  [{script_id_hint}] {n_matches} script(s) actualizado(s)")

    print(f"  Total plantillas con 'almuerzo' eliminadas: {total_actualizados}")

    # Verificación final: nadie debe seguir mencionando "almuerzo"
    sobrevivientes = ScriptWhatsApp.objects.filter(
        plantilla_texto__icontains='almuerzo'
    )
    if sobrevivientes.exists():
        print(f"  ⚠ ATENCIÓN: aún quedan {sobrevivientes.count()} plantillas con 'almuerzo':")
        for s in sobrevivientes:
            print(f"    - {s.script_id}: {s.plantilla_texto[:120]}...")
        print(f"  Requieren fix manual vía admin o shell ad-hoc.")


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0107_saludo_deborah'),
    ]

    operations = [
        migrations.RunPython(quitar_almuerzo, reverse_code=migrations.RunPython.noop),
    ]
