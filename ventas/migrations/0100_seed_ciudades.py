"""
Data migration: seed inicial de Ciudades (Etapa Geo.2.a).

Carga ~65 ciudades canónicas con sus aliases, decididas en base al reporte
real de producción (reporte_ciudades_clientes ejecutado 2026-05-24):

  - SUR (≤120 km Puerto Varas) — 22 ciudades cubriendo todas las cohortes
    de clientes detectadas en el sur de Los Lagos
  - NACIONAL (resto de Chile, incluyendo Valdivia y Chiloé) — 40+ ciudades
    desde Arica hasta Punta Arenas
  - EXTRANJERO — 1 fila genérica '_otros_extranjero_' como fallback;
    la detección extranjero se hace por marcadores de país en el comando

Decisiones tomadas con Jorge (sobre datos reales del reporte Geo.1):
  - Valdivia → NACIONAL (240km, requiere alojamiento)
  - Castro/Ancud/Chiloé → NACIONAL (requiere ferry + alojamiento)
  - Sin rapidfuzz: aliases manuales cubren 99% de las 159 variantes únicas

Operaciones idempotentes:
  - update_or_create por nombre_canonico
  - Reverso elimina solo las filas del bootstrap (preserva ciudades agregadas
    manualmente vía admin después)
"""
from django.db import migrations


CIUDADES_SEED = [
    # ────────────── SUR (≤120 km Puerto Varas) ──────────────
    # Verbo: vienen en el día. Mensaje WhatsApp puntual.
    {
        'nombre_canonico': 'Puerto Varas',
        'aliases': 'puerto varas|pto varas|pto. varas|p. varas|ptovaras|puert varas|pvaras|puerto-varas',
        'region_geografica': 'sur',
    },
    {
        'nombre_canonico': 'Puerto Montt',
        'aliases': 'puerto montt|pto montt|pto. montt|p. montt|pmontt|ptomontt|puerto-montt',
        'region_geografica': 'sur',
    },
    {
        'nombre_canonico': 'Frutillar',
        'aliases': 'frutillar|frutillar bajo|frutillar alto',
        'region_geografica': 'sur',
    },
    {
        'nombre_canonico': 'Llanquihue',
        'aliases': 'llanquihue',
        'region_geografica': 'sur',
    },
    {
        'nombre_canonico': 'Calbuco',
        'aliases': 'calbuco',
        'region_geografica': 'sur',
    },
    {
        'nombre_canonico': 'Maullín',
        'aliases': 'maullin|maullín',
        'region_geografica': 'sur',
    },
    {
        'nombre_canonico': 'Alerce',
        'aliases': 'alerce',
        'region_geografica': 'sur',
    },
    {
        'nombre_canonico': 'Ensenada',
        'aliases': 'ensenada',
        'region_geografica': 'sur',
    },
    {
        'nombre_canonico': 'Cochamó',
        'aliases': 'cochamo|cochamó',
        'region_geografica': 'sur',
    },
    {
        'nombre_canonico': 'Hornopirén',
        'aliases': 'hornopiren|hornopirén',
        'region_geografica': 'sur',
    },
    {
        'nombre_canonico': 'Puerto Octay',
        'aliases': 'puerto octay|pto octay|p. octay',
        'region_geografica': 'sur',
    },
    {
        'nombre_canonico': 'Fresia',
        'aliases': 'fresia',
        'region_geografica': 'sur',
    },
    {
        'nombre_canonico': 'Purranque',
        'aliases': 'purranque',
        'region_geografica': 'sur',
    },
    {
        'nombre_canonico': 'Osorno',
        'aliases': 'osorno',
        'region_geografica': 'sur',
    },
    {
        'nombre_canonico': 'Puyehue',
        'aliases': 'puyehue',
        'region_geografica': 'sur',
    },
    {
        'nombre_canonico': 'Río Negro',
        'aliases': 'rio negro|río negro',
        'region_geografica': 'sur',
    },
    {
        'nombre_canonico': 'Río Bueno',
        'aliases': 'rio bueno|río bueno',
        'region_geografica': 'sur',
    },
    {
        'nombre_canonico': 'La Unión',
        'aliases': 'la union|la unión',
        'region_geografica': 'sur',
    },
    {
        'nombre_canonico': 'Las Cascadas',
        'aliases': 'las cascadas',
        'region_geografica': 'sur',
    },
    {
        'nombre_canonico': 'Entre Lagos',
        'aliases': 'entre lagos|entrelagos',
        'region_geografica': 'sur',
    },
    {
        'nombre_canonico': 'Pelluco',
        'aliases': 'pelluco',
        'region_geografica': 'sur',
    },
    {
        'nombre_canonico': 'Chamiza',
        'aliases': 'chamiza',
        'region_geografica': 'sur',
    },

    # ────────────── NACIONAL — Santiago + comunas RM ──────────────
    {
        'nombre_canonico': 'Santiago',
        'aliases': 'santiago|stgo|santiago de chile|santiago centro|sgo',
        'region_geografica': 'nacional',
    },
    {'nombre_canonico': 'Las Condes', 'aliases': 'las condes', 'region_geografica': 'nacional'},
    {'nombre_canonico': 'Providencia', 'aliases': 'providencia', 'region_geografica': 'nacional'},
    {'nombre_canonico': 'Vitacura', 'aliases': 'vitacura', 'region_geografica': 'nacional'},
    {'nombre_canonico': 'Ñuñoa', 'aliases': 'nunoa|ñuñoa|nuñoa', 'region_geografica': 'nacional'},
    {'nombre_canonico': 'Maipú', 'aliases': 'maipu|maipú', 'region_geografica': 'nacional'},
    {'nombre_canonico': 'La Florida', 'aliases': 'la florida', 'region_geografica': 'nacional'},
    {'nombre_canonico': 'Lo Barnechea', 'aliases': 'lo barnechea', 'region_geografica': 'nacional'},
    {'nombre_canonico': 'San Bernardo', 'aliases': 'san bernardo', 'region_geografica': 'nacional'},
    {'nombre_canonico': 'Puente Alto', 'aliases': 'puente alto', 'region_geografica': 'nacional'},

    # ────────────── NACIONAL — Concepción + área ──────────────
    {
        'nombre_canonico': 'Concepción',
        'aliases': 'concepcion|concepción|conce',
        'region_geografica': 'nacional',
    },
    {'nombre_canonico': 'Talcahuano', 'aliases': 'talcahuano', 'region_geografica': 'nacional'},
    {'nombre_canonico': 'Chiguayante', 'aliases': 'chiguayante', 'region_geografica': 'nacional'},
    {
        'nombre_canonico': 'San Pedro de la Paz',
        'aliases': 'san pedro de la paz|san pedro',
        'region_geografica': 'nacional',
    },

    # ────────────── NACIONAL — Valparaíso + área ──────────────
    {
        'nombre_canonico': 'Valparaíso',
        'aliases': 'valparaiso|valparaíso|valpo',
        'region_geografica': 'nacional',
    },
    {
        'nombre_canonico': 'Viña del Mar',
        'aliases': 'vina del mar|viña del mar|viña|vina',
        'region_geografica': 'nacional',
    },
    {
        'nombre_canonico': 'Quilpué',
        'aliases': 'quilpue|quilpué',
        'region_geografica': 'nacional',
    },
    {'nombre_canonico': 'Villa Alemana', 'aliases': 'villa alemana', 'region_geografica': 'nacional'},
    {
        'nombre_canonico': 'Concón',
        'aliases': 'concon|concón',
        'region_geografica': 'nacional',
    },
    {'nombre_canonico': 'San Antonio', 'aliases': 'san antonio', 'region_geografica': 'nacional'},

    # ────────────── NACIONAL — Sur centro (Araucanía / Los Ríos) ──────────────
    {'nombre_canonico': 'Temuco', 'aliases': 'temuco', 'region_geografica': 'nacional'},
    {'nombre_canonico': 'Padre Las Casas', 'aliases': 'padre las casas', 'region_geografica': 'nacional'},
    {'nombre_canonico': 'Villarrica', 'aliases': 'villarrica', 'region_geografica': 'nacional'},
    {
        'nombre_canonico': 'Valdivia',
        'aliases': 'valdivia',
        'region_geografica': 'nacional',  # decisión Jorge: 240km, requiere alojamiento
    },

    # ────────────── NACIONAL — Centro/Sur (regiones VI a IX) ──────────────
    {'nombre_canonico': 'Rancagua', 'aliases': 'rancagua', 'region_geografica': 'nacional'},
    {
        'nombre_canonico': 'Curicó',
        'aliases': 'curico|curicó',
        'region_geografica': 'nacional',
    },
    {'nombre_canonico': 'Talca', 'aliases': 'talca', 'region_geografica': 'nacional'},
    {
        'nombre_canonico': 'Chillán',
        'aliases': 'chillan|chillán',
        'region_geografica': 'nacional',
    },
    {
        'nombre_canonico': 'Los Ángeles',
        'aliases': 'los angeles|los ángeles',
        'region_geografica': 'nacional',
    },

    # ────────────── NACIONAL — Norte ──────────────
    {'nombre_canonico': 'Antofagasta', 'aliases': 'antofagasta', 'region_geografica': 'nacional'},
    {'nombre_canonico': 'La Serena', 'aliases': 'la serena', 'region_geografica': 'nacional'},
    {'nombre_canonico': 'Coquimbo', 'aliases': 'coquimbo', 'region_geografica': 'nacional'},
    {'nombre_canonico': 'Iquique', 'aliases': 'iquique', 'region_geografica': 'nacional'},
    {'nombre_canonico': 'Arica', 'aliases': 'arica', 'region_geografica': 'nacional'},
    {'nombre_canonico': 'Calama', 'aliases': 'calama', 'region_geografica': 'nacional'},
    {
        'nombre_canonico': 'Copiapó',
        'aliases': 'copiapo|copiapó',
        'region_geografica': 'nacional',
    },

    # ────────────── NACIONAL — Patagonia austral ──────────────
    {
        'nombre_canonico': 'Coyhaique',
        'aliases': 'coyhaique|coyahique|coihaique',  # typo coyahique detectado en BD
        'region_geografica': 'nacional',
    },
    {
        'nombre_canonico': 'Puerto Aysén',
        'aliases': 'puerto aysen|puerto aysén|aysen|aysén',
        'region_geografica': 'nacional',
    },
    {'nombre_canonico': 'Punta Arenas', 'aliases': 'punta arenas', 'region_geografica': 'nacional'},

    # ────────────── NACIONAL — Chiloé (decisión Jorge) ──────────────
    {'nombre_canonico': 'Castro', 'aliases': 'castro', 'region_geografica': 'nacional'},
    {'nombre_canonico': 'Ancud', 'aliases': 'ancud', 'region_geografica': 'nacional'},
    {'nombre_canonico': 'Dalcahue', 'aliases': 'dalcahue', 'region_geografica': 'nacional'},
    {'nombre_canonico': 'Chacao', 'aliases': 'chacao', 'region_geografica': 'nacional'},
    {
        'nombre_canonico': 'Chiloé',
        'aliases': 'chiloe|chiloé',
        'region_geografica': 'nacional',
    },

    # ────────────── EXTRANJERO (fallback genérico) ──────────────
    # Fila única que captura cualquier extranjero. La detección de "es
    # extranjero" la hace el comando normalizar_ciudades_clientes por
    # marcadores en el texto (Argentina, Buenos Aires, USA, etc.).
    {
        'nombre_canonico': '_otros_extranjero_',
        'aliases': '',
        'region_geografica': 'extranjero',
        'pais': '_varios_',
    },
]


def seed_ciudades(apps, schema_editor):
    """Inserta o actualiza las ciudades del seed inicial."""
    Ciudad = apps.get_model('ventas', 'Ciudad')
    creadas = 0
    actualizadas = 0
    for data in CIUDADES_SEED:
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
        f"\n  [0100_seed_ciudades] {creadas} creadas, {actualizadas} actualizadas. "
        f"Total seed: {len(CIUDADES_SEED)} ciudades."
    )


def unseed_ciudades(apps, schema_editor):
    """Reversa: elimina solo las ciudades del seed (preserva las del admin)."""
    Ciudad = apps.get_model('ventas', 'Ciudad')
    ids = [c['nombre_canonico'] for c in CIUDADES_SEED]
    deleted, _ = Ciudad.objects.filter(nombre_canonico__in=ids).delete()
    print(f"\n  [0100_seed_ciudades] {deleted} ciudades eliminadas.")


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0099_ciudad_geo'),
    ]

    operations = [
        migrations.RunPython(seed_ciudades, unseed_ciudades),
    ]
