"""
Data migration: carga las 14 plantillas iniciales de ScriptWhatsApp.

Operación Vuelta a Casa — Etapa 2.

Catálogo inicial:
    A.1 - A.5  →  En Riesgo (5 cohortes)
    B.1 - B.2  →  Dormido (genérico, salvas 1 y 2)
    C.1 - C.3  →  En Prueba (días 30, 60, 80)
    D.1        →  Regular (Amante Tinas × Pareja)
    D.2        →  Gran Gastador Ocasional (genérico)
    E.1        →  Leal (mesa chica)
    E.2        →  Campeón (mesa chica)

Notas:
- Los strings de estado_valor_target, cohorte_estilo y cohorte_contexto deben
  coincidir EXACTO con los choices de ClienteTaxonomia (ver modelos.py).
- E.1 y E.2 comparten texto pero apuntan a estados distintos (Leal vs Campeón)
  porque cada cliente solo tiene UN eje_valor a la vez. Son mesa chica = 1 sola
  salva, contacto mensual por inactividad de contacto (no por caída de tramo).
- Cohorte vacía '' = aplica a cualquier valor del eje (matching genérico).
- update_or_create por script_id: la migración es re-aplicable sin chocar y no
  pisa cambios manuales que el operador haya hecho en otras columnas si vuelve
  a correrse (porque update_or_create solo sobreescribe defaults explícitos).

Si necesitas editar el texto de una plantilla en producción, hazlo desde el
admin Django, NO desde esta migración. Esta migración es solo el bootstrap.
"""
from django.db import migrations


# ============================================================================
# Catálogo de plantillas
# ============================================================================
# Cada entrada es la fuente única de verdad. Si cambias algo aquí, también
# considera si vale la pena replicarlo en producción vía admin (la migración
# solo corre una vez por entorno).

SCRIPTS_INICIALES = [
    # ────────────── A. En Riesgo (5 cohortes) ──────────────
    {
        'script_id': 'A.1',
        'nombre': 'En Riesgo · Amante Tinas × Pareja · 1ª salva',
        'estado_valor_target': 'En Riesgo',
        'cohorte_estilo': 'Amante de las Tinas',
        'cohorte_contexto': 'Visitante Pareja',
        'salva': 1,
        'plantilla_texto': (
            "Hola {nombre}, te escribe Aremko de Puerto Varas.\n\n"
            "Nos acordamos de ustedes — la última vez que vinieron a las tinas fue "
            "{ultima_visita_humanizada}. ¿Te tinca venir un día de semana con tu pareja? "
            "Tenemos tarifa más tranquila martes a jueves.\n\n"
            "¿Qué día te acomoda?"
        ),
    },
    {
        'script_id': 'A.2',
        'nombre': 'En Riesgo · Devoto Masaje × Solo · 1ª salva',
        'estado_valor_target': 'En Riesgo',
        'cohorte_estilo': 'Devoto del Masaje',
        'cohorte_contexto': 'Visitante Solo',
        'salva': 1,
        'plantilla_texto': (
            "Hola {nombre}, soy de Aremko.\n\n"
            "Hace {dias_sin_venir} días que no te vemos por un masaje. "
            "Te guardamos un cupo el {sugerencia_dia} a las {sugerencia_hora}.\n\n"
            "¿Lo confirmamos?"
        ),
    },
    {
        'script_id': 'A.3',
        'nombre': 'En Riesgo · Experiencia Completa × Pareja · 1ª salva',
        'estado_valor_target': 'En Riesgo',
        'cohorte_estilo': 'Experiencia Completa',
        'cohorte_contexto': 'Visitante Pareja',
        'salva': 1,
        'plantilla_texto': (
            "Hola {nombre}, te escribe Aremko.\n\n"
            "Como te gusta el día completo (tina + masaje + descanso), te aviso que "
            "abrimos una nueva opción: día spa de 5 horas con almuerzo incluido entre semana.\n\n"
            "¿Te lo cuento por aquí?"
        ),
    },
    {
        'script_id': 'A.4',
        'nombre': 'En Riesgo · Amante Tinas × Grupal · 1ª salva',
        'estado_valor_target': 'En Riesgo',
        'cohorte_estilo': 'Amante de las Tinas',
        'cohorte_contexto': 'Visitante Grupal',
        'salva': 1,
        'plantilla_texto': (
            "Hola {nombre}, soy de Aremko.\n\n"
            "Si están planeando juntarse con tu grupo, te aviso que las reservas de "
            "tinas para 4+ personas se están llenando rápido para {mes_proximo}.\n\n"
            "¿Te paso disponibilidad?"
        ),
    },
    {
        'script_id': 'A.5',
        'nombre': 'En Riesgo · Probador Esporádico · 1ª salva',
        'estado_valor_target': 'En Riesgo',
        'cohorte_estilo': 'Probador Esporádico',
        'cohorte_contexto': '',  # cualquier contexto
        'salva': 1,
        'plantilla_texto': (
            "Hola {nombre}, te escribe Aremko.\n\n"
            "Vimos que la última vez probaste {ultimo_servicio}. Si quieres conocer "
            "otra cosa, te invitamos a probar {servicio_recomendado} con un descuento "
            "de bienvenida.\n\n"
            "¿Te interesa?"
        ),
    },

    # ────────────── B. Dormido (genérico, 2 salvas) ──────────────
    {
        'script_id': 'B.1',
        'nombre': 'Dormido · Genérico · 1ª salva',
        'estado_valor_target': 'Dormido',
        'cohorte_estilo': '',
        'cohorte_contexto': '',
        'salva': 1,
        'plantilla_texto': (
            "Hola {nombre}, te escribe Aremko de Puerto Varas.\n\n"
            "Te extrañamos. Hace {dias_sin_venir} días que no vienes y queremos "
            "invitarte a volver con un detalle de parte nuestra: una copa de espumante "
            "de regalo en tu próxima visita.\n\n"
            "¿Te tinca venir antes de fin de mes?"
        ),
    },
    {
        'script_id': 'B.2',
        'nombre': 'Dormido · Genérico · 2ª salva',
        'estado_valor_target': 'Dormido',
        'cohorte_estilo': '',
        'cohorte_contexto': '',
        'salva': 2,
        'plantilla_texto': (
            "Hola {nombre}, soy de Aremko.\n\n"
            "Sé que no respondiste el mensaje anterior — sin presión. Solo quería "
            "contarte que te guardé un 15% de descuento personal hasta el "
            "{fecha_limite} con el código {cupon_codigo}.\n\n"
            "Si quieres reservar, escríbeme aquí mismo."
        ),
    },

    # ────────────── C. En Prueba (3 momentos del primer mes) ──────────────
    {
        'script_id': 'C.1',
        'nombre': 'En Prueba · Día 30 · 1ª salva',
        'estado_valor_target': 'En Prueba',
        'cohorte_estilo': '',
        'cohorte_contexto': '',
        'salva': 1,
        'plantilla_texto': (
            "Hola {nombre}, te escribe Aremko.\n\n"
            "Pasó un mes desde tu primera visita a {ultimo_servicio} y quería "
            "preguntarte cómo te sentiste. Si te animas a contarnos algo, lo "
            "leemos con cariño.\n\n"
            "Y si quieres volver, tenemos cupos los {sugerencia_dia}."
        ),
    },
    {
        'script_id': 'C.2',
        'nombre': 'En Prueba · Día 60 · 2ª salva',
        'estado_valor_target': 'En Prueba',
        'cohorte_estilo': '',
        'cohorte_contexto': '',
        'salva': 2,
        'plantilla_texto': (
            "Hola {nombre}, soy de Aremko.\n\n"
            "La última vez viniste a {ultimo_servicio}. ¿Conoces nuestro "
            "{servicio_recomendado}? Mucha gente que vino primero por una cosa "
            "después se enganchó con la otra."
        ),
    },
    {
        'script_id': 'C.3',
        'nombre': 'En Prueba · Día 80 · 3ª salva',
        'estado_valor_target': 'En Prueba',
        'cohorte_estilo': '',
        'cohorte_contexto': '',
        'salva': 3,
        'plantilla_texto': (
            "Hola {nombre}, soy de Aremko.\n\n"
            "Te queremos de vuelta antes de fin de mes. Si reservas esta semana te "
            "incluimos un pequeño regalo sin costo.\n\n"
            "¿Qué día?"
        ),
    },

    # ────────────── D. Regular + Gran Gastador Ocasional ──────────────
    {
        'script_id': 'D.1',
        'nombre': 'Regular · Amante Tinas × Pareja · 1ª salva',
        'estado_valor_target': 'Regular',
        'cohorte_estilo': 'Amante de las Tinas',
        'cohorte_contexto': 'Visitante Pareja',
        'salva': 1,
        'plantilla_texto': (
            "Hola {nombre},\n\n"
            "Como te gustan las tinas en pareja, te aviso que estamos estrenando una "
            "nueva opción y quería que tú estuvieras entre los primeros en probarlo. "
            "Te guardo cupo si quieres.\n\n"
            "¿Te parece?"
        ),
    },
    {
        'script_id': 'D.2',
        'nombre': 'GG Ocasional · Mes próximo · 1ª salva',
        'estado_valor_target': 'Gran Gastador Ocasional',
        'cohorte_estilo': '',
        'cohorte_contexto': '',
        'salva': 1,
        'plantilla_texto': (
            "Hola {nombre},\n\n"
            "Sé que vienes a Aremko cuando es algo especial. Si tienes algo que "
            "celebrar este {mes_proximo} (cumpleaños, aniversario, escapada), arma "
            "con nosotros un día a tu medida.\n\n"
            "Cuéntame qué tienen en mente y te propongo opciones."
        ),
    },

    # ────────────── E. Mesa chica (Leal + Campeón, 1 salva, 1 toque mensual) ──
    # Nota Etapa 3: estos clientes entran a la bandeja por INACTIVIDAD DE
    # CONTACTO (>30 días desde último outbound), NO por caída de tramo. Son
    # Prioridad 0 en el algoritmo (antes que Prioridades 1-6).
    {
        'script_id': 'E.1',
        'nombre': 'Leal · Mesa Chica · 1ª salva',
        'estado_valor_target': 'Leal',
        'cohorte_estilo': '',
        'cohorte_contexto': '',
        'salva': 1,
        'plantilla_texto': (
            "Hola {nombre}, ¿cómo has estado? Te escribo de Aremko.\n\n"
            "Estamos pensando en ti — eres parte de nuestra mesa chica de clientes. "
            "Si tienes ganas de venir este mes, quiero reservarte personalmente el "
            "horario que mejor te acomode.\n\n"
            "¿Cuándo te tinca?"
        ),
    },
    {
        'script_id': 'E.2',
        'nombre': 'Campeón · Mesa Chica · 1ª salva',
        'estado_valor_target': 'Campeón',
        'cohorte_estilo': '',
        'cohorte_contexto': '',
        'salva': 1,
        'plantilla_texto': (
            "Hola {nombre}, ¿cómo has estado? Te escribo de Aremko.\n\n"
            "Estamos pensando en ti — eres parte de nuestra mesa chica de clientes. "
            "Si tienes ganas de venir este mes, quiero reservarte personalmente el "
            "horario que mejor te acomode.\n\n"
            "¿Cuándo te tinca?"
        ),
    },
]


def seed_scripts(apps, schema_editor):
    """Inserta o actualiza las 14 plantillas iniciales.

    Usa update_or_create por script_id para que sea idempotente:
    si la migración corre dos veces (o si alguien agregó manualmente un
    script con el mismo ID antes), no rompe nada — sobrescribe defaults.
    """
    ScriptWhatsApp = apps.get_model('ventas', 'ScriptWhatsApp')

    creados = 0
    actualizados = 0
    for data in SCRIPTS_INICIALES:
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

    # Logging visible en consola de migración
    print(f"\n  [0097_seed_scripts_whatsapp] {creados} scripts creados, "
          f"{actualizados} actualizados. Total: {len(SCRIPTS_INICIALES)} plantillas.")


def unseed_scripts(apps, schema_editor):
    """Reversión: elimina solo las 14 plantillas creadas por esta migración.

    Borra por script_id (no por filtro amplio) para no afectar plantillas
    que el operador haya agregado manualmente vía admin después del bootstrap.
    """
    ScriptWhatsApp = apps.get_model('ventas', 'ScriptWhatsApp')
    ids_iniciales = [s['script_id'] for s in SCRIPTS_INICIALES]
    deleted, _ = ScriptWhatsApp.objects.filter(script_id__in=ids_iniciales).delete()
    print(f"\n  [0097_seed_scripts_whatsapp] {deleted} scripts eliminados.")


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0096_operacion_vuelta_a_casa'),
    ]

    operations = [
        migrations.RunPython(seed_scripts, unseed_scripts),
    ]
