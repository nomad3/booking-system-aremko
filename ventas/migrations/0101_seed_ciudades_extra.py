"""
Data migration: seed extra de Ciudades chilenas (Etapa Geo.2 hotfix).

Origen: la corrida real de `normalizar_ciudades_clientes` sobre los 15.902
clientes de producción reveló ~120 textos sin match en el campo `ciudad`,
casi todos ciudades chilenas pequeñas no incluidas en el seed inicial 0100.

Esta migración agrega las top 29 ciudades detectadas en el reporte
`sin_match` (todas con 2+ clientes O ciudades conocidas turísticas) +
aliases para typos detectados.

Todas son región='nacional' (>120 km de Puerto Varas).

Decisiones:
  - "Casa Blanca" se mapea a Casablanca (V Región) como alias
  - "Pallaico" se mapea a Paillaco (XIV Los Ríos) como alias (typo común)
  - "Los Lagos" (la comuna XIV Región, no la región) se incluye
  - "Isla de Pascua" alias "rapa nui"
  - "Quellón" (Chiloé sur) → nacional por decisión Jorge sobre Chiloé

NO incluida: "La Araucanía" — es una REGIÓN, no una ciudad. Si aparece
en el campo `ciudad` del cliente es texto incorrecto que mejor se
captura vía UI inline en Geo.4.

Operaciones idempotentes (update_or_create por nombre_canonico),
reverso elimina solo las del bootstrap extra.
"""
from django.db import migrations


CIUDADES_EXTRA = [
    # ────────────── Top frecuencia (2+ clientes) ──────────────
    {'nombre_canonico': 'Santa Cruz', 'aliases': 'santa cruz', 'region_geografica': 'nacional'},
    {'nombre_canonico': 'Angol', 'aliases': 'angol', 'region_geografica': 'nacional'},
    {'nombre_canonico': 'Quillota', 'aliases': 'quillota', 'region_geografica': 'nacional'},
    {
        'nombre_canonico': 'Quillón',
        'aliases': 'quillon|quillón',
        'region_geografica': 'nacional',
    },
    {'nombre_canonico': 'Santo Domingo', 'aliases': 'santo domingo', 'region_geografica': 'nacional'},
    {'nombre_canonico': 'Navidad', 'aliases': 'navidad', 'region_geografica': 'nacional'},
    {'nombre_canonico': 'Futrono', 'aliases': 'futrono', 'region_geografica': 'nacional'},
    {
        'nombre_canonico': 'Machalí',
        'aliases': 'machali|machalí',
        'region_geografica': 'nacional',
    },
    {
        'nombre_canonico': 'Los Lagos',
        'aliases': 'los lagos',  # comuna XIV Región, no la región completa
        'region_geografica': 'nacional',
    },
    {'nombre_canonico': 'La Cruz', 'aliases': 'la cruz', 'region_geografica': 'nacional'},
    {'nombre_canonico': 'San Felipe', 'aliases': 'san felipe', 'region_geografica': 'nacional'},
    {'nombre_canonico': 'Melipilla', 'aliases': 'melipilla', 'region_geografica': 'nacional'},

    # ────────────── 1 cliente, ciudades chilenas conocidas ──────────────
    {'nombre_canonico': 'Salamanca', 'aliases': 'salamanca', 'region_geografica': 'nacional'},
    {'nombre_canonico': 'Vallenar', 'aliases': 'vallenar', 'region_geografica': 'nacional'},
    {
        'nombre_canonico': 'Olmué',
        'aliases': 'olmue|olmué',
        'region_geografica': 'nacional',
    },
    {
        'nombre_canonico': 'Casablanca',
        'aliases': 'casablanca|casa blanca',  # variante con espacio detectada
        'region_geografica': 'nacional',
    },
    {'nombre_canonico': 'Carahue', 'aliases': 'carahue', 'region_geografica': 'nacional'},
    {
        'nombre_canonico': 'Paillaco',
        'aliases': 'paillaco|pallaico',  # typo "pallaico" detectado en BD
        'region_geografica': 'nacional',
    },
    {'nombre_canonico': 'Linares', 'aliases': 'linares', 'region_geografica': 'nacional'},
    {'nombre_canonico': 'Maitencillo', 'aliases': 'maitencillo', 'region_geografica': 'nacional'},
    {'nombre_canonico': 'Algarrobo', 'aliases': 'algarrobo', 'region_geografica': 'nacional'},
    {'nombre_canonico': 'La Ligua', 'aliases': 'la ligua', 'region_geografica': 'nacional'},
    {'nombre_canonico': 'Cunco', 'aliases': 'cunco', 'region_geografica': 'nacional'},
    {'nombre_canonico': 'Curanilahue', 'aliases': 'curanilahue', 'region_geografica': 'nacional'},
    {
        'nombre_canonico': 'Isla de Pascua',
        'aliases': 'isla de pascua|rapa nui',
        'region_geografica': 'nacional',
    },
    {'nombre_canonico': 'Nacimiento', 'aliases': 'nacimiento', 'region_geografica': 'nacional'},
    {'nombre_canonico': 'San Carlos', 'aliases': 'san carlos', 'region_geografica': 'nacional'},
    {'nombre_canonico': 'Mejillones', 'aliases': 'mejillones', 'region_geografica': 'nacional'},
    {
        'nombre_canonico': 'Quellón',
        'aliases': 'quellon|quellón',
        'region_geografica': 'nacional',  # Chiloé sur, nacional por decisión Jorge
    },
]


def seed_ciudades_extra(apps, schema_editor):
    """Inserta las ciudades extra detectadas en la corrida real."""
    Ciudad = apps.get_model('ventas', 'Ciudad')
    creadas = 0
    actualizadas = 0
    for data in CIUDADES_EXTRA:
        defaults = {k: v for k, v in data.items() if k != 'nombre_canonico'}
        defaults.setdefault('pais', 'Chile')
        defaults['activo'] = True
        _, created = Ciudad.objects.update_or_create(
            nombre_canonico=data['nombre_canonico'],
            defaults=defaults,
        )
        if created:
            creadas += 1
        else:
            actualizadas += 1
    print(
        f"\n  [0101_seed_ciudades_extra] {creadas} creadas, "
        f"{actualizadas} actualizadas. Total extra: {len(CIUDADES_EXTRA)}."
    )


def unseed_ciudades_extra(apps, schema_editor):
    """Reverso: elimina solo las ciudades de este bootstrap extra."""
    Ciudad = apps.get_model('ventas', 'Ciudad')
    ids = [c['nombre_canonico'] for c in CIUDADES_EXTRA]
    deleted, _ = Ciudad.objects.filter(nombre_canonico__in=ids).delete()
    print(f"\n  [0101_seed_ciudades_extra] {deleted} ciudades extra eliminadas.")


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0100_seed_ciudades'),
    ]

    operations = [
        migrations.RunPython(seed_ciudades_extra, unseed_ciudades_extra),
    ]
