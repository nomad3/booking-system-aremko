"""Carga los 50+ circuitos del estudio "Circuitos turísticos desde Puerto Varas
dentro de 300 km" como Circuit publicados SIN días/paradas (modo "Próximamente").

Idempotente: usa get_or_create por slug, así que correr el comando varias veces
no duplica nada. Asigna numbers altos (1001+) para no chocar con seeds previos.

Uso (Render shell):
    python manage.py load_dpv_circuits_from_study
    python manage.py load_dpv_circuits_from_study --dry-run

Cuando se enriquezcan los Places del catálogo, el operador puede ir creando los
días/paradas a mano desde el admin (o vía circuit_composer) y los circuitos
dejarán automáticamente de mostrarse como "Próximamente" en el sitio público.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from destino_puerto_varas.models import Circuit, DurationCase


# ─── Casos de duración requeridos por el estudio ──────────────────────────────
# get_or_create por código. Si DPV_1D y DPV_5D4N no existen aún, se crean.
DURATION_SEED = [
    {
        "code": "DPV_HALF_DAY", "name": "Medio día en Puerto Varas",
        "duration_type": "HALF_DAY", "days": 0, "nights": 0, "sort_order": 10,
    },
    {
        "code": "DPV_1D", "name": "1 día completo",
        "duration_type": "FULL_DAY", "days": 1, "nights": 0, "sort_order": 15,
    },
    {
        "code": "DPV_2D1N", "name": "2 días / 1 noche",
        "duration_type": "TWO_DAYS_ONE_NIGHT", "days": 2, "nights": 1, "sort_order": 20,
    },
    {
        "code": "DPV_3D2N", "name": "3 días / 2 noches",
        "duration_type": "THREE_DAYS_TWO_NIGHTS", "days": 3, "nights": 2, "sort_order": 30,
    },
    {
        "code": "DPV_5D4N", "name": "4 a 6 días",
        "duration_type": "FIVE_DAYS_FOUR_NIGHTS", "days": 5, "nights": 4, "sort_order": 40,
    },
]


# ─── Helper para flags ────────────────────────────────────────────────────────
def F(*flag_keys):
    """Devuelve dict con sólo los flags activados (True). Reduce ruido."""
    valid = {
        "is_nature", "is_culture", "is_gastronomy", "is_adventure",
        "is_family_friendly", "is_romantic", "is_rain_friendly", "is_premium",
    }
    out = {}
    for k in flag_keys:
        assert k in valid, f"flag desconocido: {k}"
        out[k] = True
    return out


# ─── Datos del estudio ────────────────────────────────────────────────────────
# slug | name | duration_code | primary_interest | recommended_profile | flags | short_desc
# (recommended_profile vacío = sin perfil específico)
CIRCUITS = [
    # ═════ MEDIO DÍA (10) ═════
    {
        "slug": "puerto-varas-patrimonial",
        "name": "Puerto Varas patrimonial",
        "duration_code": "DPV_HALF_DAY",
        "primary_interest": "MIXED",
        "recommended_profile": "FAMILY",
        "flags": F("is_culture", "is_family_friendly", "is_rain_friendly"),
        "short_description": "Costanera, Muelle Pedraplén, Iglesia Sagrado Corazón y Museo Pablo Fierro. Patrimonio urbano y vistas al lago.",
    },
    {
        "slug": "frutillar-clasico",
        "name": "Frutillar clásico",
        "duration_code": "DPV_HALF_DAY",
        "primary_interest": "MIXED",
        "recommended_profile": "FAMILY",
        "flags": F("is_culture", "is_family_friendly", "is_gastronomy"),
        "short_description": "Costanera, Teatro del Lago y Museo Colonial Alemán. Cultura, herencia alemana y lago a 30 min de Puerto Varas.",
    },
    {
        "slug": "llanquihue-ribera-humedales",
        "name": "Llanquihue ribera y humedales",
        "duration_code": "DPV_HALF_DAY",
        "primary_interest": "NATURE",
        "recommended_profile": "FAMILY",
        "flags": F("is_nature", "is_gastronomy", "is_family_friendly"),
        "short_description": "Playa Los Cisnes, muelle y río Maullín. Paisaje lacustre, cecinas locales y observación de aves.",
    },
    {
        "slug": "puerto-octay-historico-centinela",
        "name": "Puerto Octay histórico + Centinela",
        "duration_code": "DPV_HALF_DAY",
        "primary_interest": "MIXED",
        "recommended_profile": "FAMILY",
        "flags": F("is_culture", "is_family_friendly"),
        "short_description": "Plaza, iglesia, casas patrimoniales y playa Centinela. Patrimonio lacustre y descanso familiar.",
    },
    {
        "slug": "las-cascadas-y-salto",
        "name": "Las Cascadas y salto",
        "duration_code": "DPV_HALF_DAY",
        "primary_interest": "NATURE",
        "recommended_profile": "FAMILY",
        "flags": F("is_nature", "is_family_friendly"),
        "short_description": "Pueblo de Las Cascadas, sendero al salto y miradores del río Blanco. Bosque y caída de agua.",
    },
    {
        "slug": "puerto-montt-costanera-angelmo",
        "name": "Puerto Montt costanera y Angelmó",
        "duration_code": "DPV_HALF_DAY",
        "primary_interest": "GASTRONOMY",
        "recommended_profile": "FAMILY",
        "flags": F("is_culture", "is_gastronomy", "is_family_friendly", "is_rain_friendly"),
        "short_description": "Costanera, catedral y Mercado de Angelmó. Gastronomía y centro urbano regional a 25 min.",
    },
    {
        "slug": "lahuen-nadi",
        "name": "Monumento Natural Lahuén Ñadi",
        "duration_code": "DPV_HALF_DAY",
        "primary_interest": "NATURE",
        "recommended_profile": "FAMILY",
        "flags": F("is_nature", "is_family_friendly"),
        "short_description": "Relicto de alerces de baja altitud con pasarelas y senderos cortos. Entrada CONAF desde CLP 2.800.",
    },
    {
        "slug": "centro-montana-volcan-osorno-panoramico",
        "name": "Centro de Montaña Volcán Osorno panorámico",
        "duration_code": "DPV_HALF_DAY",
        "primary_interest": "NATURE",
        "recommended_profile": "COUPLE",
        "flags": F("is_nature", "is_family_friendly"),
        "short_description": "Miradores y sillas panorámicas en faldeos del volcán. Telesilla desde CLP 14.000.",
    },
    {
        "slug": "saltos-petrohue-expres",
        "name": "Saltos del Petrohué exprés",
        "duration_code": "DPV_HALF_DAY",
        "primary_interest": "NATURE",
        "recommended_profile": "FAMILY",
        "flags": F("is_nature", "is_family_friendly"),
        "short_description": "Miradores de los saltos y borde del río turquesa. Sendero circuito de 1 km, parque desde CLP 2.800.",
    },
    {
        "slug": "termas-cochamo",
        "name": "Termas Cochamó",
        "duration_code": "DPV_HALF_DAY",
        "primary_interest": "RELAX_ROMANTIC",
        "recommended_profile": "COUPLE",
        "flags": F("is_nature", "is_romantic", "is_rain_friendly"),
        "short_description": "Pozas termales junto al estuario, bosque de arrayanes. Algo más de 1 h desde Puerto Varas.",
    },

    # ═════ 1 DÍA (30) ═════
    {
        "slug": "frutillar-llanquihue",
        "name": "Frutillar + Llanquihue",
        "duration_code": "DPV_1D",
        "primary_interest": "MIXED",
        "recommended_profile": "FAMILY",
        "flags": F("is_culture", "is_gastronomy", "is_family_friendly"),
        "short_description": "Costaneras, muelles y gastronomía lacustre del norte del Lago Llanquihue.",
    },
    {
        "slug": "frutillar-puerto-octay",
        "name": "Frutillar + Puerto Octay",
        "duration_code": "DPV_1D",
        "primary_interest": "MIXED",
        "recommended_profile": "FAMILY",
        "flags": F("is_culture", "is_family_friendly"),
        "short_description": "Cultura alemana y playas del lago entre dos pueblos patrimoniales del Llanquihue.",
    },
    {
        "slug": "frutillar-llanquihue-puerto-octay",
        "name": "Frutillar + Llanquihue + Puerto Octay",
        "duration_code": "DPV_1D",
        "primary_interest": "MIXED",
        "recommended_profile": "FAMILY",
        "flags": F("is_culture", "is_gastronomy", "is_family_friendly"),
        "short_description": "Norte del Lago Llanquihue, patrimonio y gastronomía. Tour de 7 h ofrecido por operadores locales.",
    },
    {
        "slug": "alerce-andino-correntoso",
        "name": "Parque Alerce Andino sector Correntoso",
        "duration_code": "DPV_1D",
        "primary_interest": "NATURE",
        "recommended_profile": "FAMILY",
        "flags": F("is_nature", "is_family_friendly", "is_adventure"),
        "short_description": "Acceso por V-65, bosque y senderos familiares. Visita 3-4 h, parque desde CLP 2.800.",
    },
    {
        "slug": "alerce-andino-chaicas-lenca",
        "name": "Parque Alerce Andino sector Chaicas/Lenca",
        "duration_code": "DPV_1D",
        "primary_interest": "NATURE",
        "recommended_profile": "FAMILY",
        "flags": F("is_nature", "is_family_friendly", "is_adventure"),
        "short_description": "Acceso sur, bosques costeros y senderos. Lenca a 36 km de Puerto Montt.",
    },
    {
        "slug": "calbuco-pedraplen-costanera",
        "name": "Calbuco ciudad + pedraplén + costanera",
        "duration_code": "DPV_1D",
        "primary_interest": "MIXED",
        "recommended_profile": "FAMILY",
        "flags": F("is_culture", "is_gastronomy", "is_family_friendly"),
        "short_description": "Circuito urbano insular con vistas del archipiélago. Visita 3-4 h vía Puerto Montt.",
    },
    {
        "slug": "cochamo-pueblo-ralun",
        "name": "Cochamó pueblo + Ralún",
        "duration_code": "DPV_1D",
        "primary_interest": "NATURE",
        "recommended_profile": "COUPLE",
        "flags": F("is_nature", "is_culture"),
        "short_description": "Primer fiordo de la Patagonia, estuario y patrimonio natural. Cochamó a 93 km.",
    },
    {
        "slug": "maullin-carelmapu",
        "name": "Maullín + Carelmapu",
        "duration_code": "DPV_1D",
        "primary_interest": "NATURE",
        "recommended_profile": "FAMILY",
        "flags": F("is_nature", "is_family_friendly"),
        "short_description": "Humedales, desembocadura del río Maullín y costa. Jornada completa por la costa.",
    },
    {
        "slug": "puelo-termas-del-sol-columpios",
        "name": "Puelo: Termas del Sol + columpios",
        "duration_code": "DPV_1D",
        "primary_interest": "RELAX_ROMANTIC",
        "recommended_profile": "COUPLE",
        "flags": F("is_nature", "is_romantic"),
        "short_description": "Relajo termal y paisaje de río/valle. Puelo a 2,5 h desde Puerto Varas.",
    },
    {
        "slug": "navegacion-peulla-petrohue",
        "name": "Navegación a Peulla desde Petrohué",
        "duration_code": "DPV_1D",
        "primary_interest": "NATURE",
        "recommended_profile": "COUPLE",
        "flags": F("is_nature", "is_romantic", "is_family_friendly", "is_premium"),
        "short_description": "Petrohué, Lago Todos los Santos y Villa Peulla. Catamarán de jornada completa, 8 h.",
    },
    {
        "slug": "ancud-clasico",
        "name": "Ancud clásico",
        "duration_code": "DPV_1D",
        "primary_interest": "MIXED",
        "recommended_profile": "FAMILY",
        "flags": F("is_culture", "is_gastronomy", "is_family_friendly"),
        "short_description": "Fuerte San Antonio, costanera y mercado. Historia, mar y puerta de entrada a Chiloé.",
    },
    {
        "slug": "castro-dalcahue-clasico",
        "name": "Castro + Dalcahue clásico",
        "duration_code": "DPV_1D",
        "primary_interest": "MIXED",
        "recommended_profile": "FAMILY",
        "flags": F("is_culture", "is_gastronomy", "is_family_friendly"),
        "short_description": "Palafitos, iglesia patrimonial y feria artesanal. Ferry Chacao + Ruta 5.",
    },
    {
        "slug": "achao-quinchao",
        "name": "Achao y Quinchao",
        "duration_code": "DPV_1D",
        "primary_interest": "MIXED",
        "recommended_profile": "COUPLE",
        "flags": F("is_culture", "is_nature"),
        "short_description": "Iglesias patrimoniales y paisaje de islas interiores del archipiélago de Chiloé.",
    },
    {
        "slug": "isla-puluqui-calbuco",
        "name": "Isla Puluqui desde Calbuco",
        "duration_code": "DPV_1D",
        "primary_interest": "NATURE",
        "recommended_profile": "FRIENDS",
        "flags": F("is_nature", "is_adventure"),
        "short_description": "Cruce local a isla, pueblos y costa interior. Duración depende de barcaza.",
    },
    {
        "slug": "puyehue-aguas-calientes",
        "name": "Puyehue Aguas Calientes",
        "duration_code": "DPV_1D",
        "primary_interest": "NATURE",
        "recommended_profile": "FAMILY",
        "flags": F("is_nature", "is_romantic", "is_family_friendly"),
        "short_description": "Termas y senderos suaves del Parque Nacional Puyehue. Ingreso gratuito a senderos.",
    },
    {
        "slug": "hornopiren-urbano-rio-blanco",
        "name": "Hornopirén urbano + Río Blanco",
        "duration_code": "DPV_1D",
        "primary_interest": "NATURE",
        "recommended_profile": "FAMILY",
        "flags": F("is_nature", "is_family_friendly"),
        "short_description": "Capital de Hualaihué y cascadas/fiordos cercanos. Requiere ferry La Arena-Puelche.",
    },
    {
        "slug": "ancud-punihuil",
        "name": "Ancud + Puñihuil",
        "duration_code": "DPV_1D",
        "primary_interest": "NATURE",
        "recommended_profile": "FAMILY",
        "flags": F("is_nature", "is_family_friendly"),
        "short_description": "Ciudad de Ancud + islotes pingüineros de Puñihuil con navegación opcional.",
    },
    {
        "slug": "ensenada-saltos-todos-los-santos",
        "name": "Ensenada + Saltos + Lago Todos los Santos",
        "duration_code": "DPV_1D",
        "primary_interest": "NATURE",
        "recommended_profile": "FAMILY",
        "flags": F("is_nature", "is_family_friendly"),
        "short_description": "Ensenada, Saltos del Petrohué y costa lacustre. Parque desde CLP 2.800.",
    },
    {
        "slug": "volcan-osorno-saltos-petrohue",
        "name": "Volcán Osorno + Saltos del Petrohué",
        "duration_code": "DPV_1D",
        "primary_interest": "NATURE",
        "recommended_profile": "FAMILY",
        "flags": F("is_nature", "is_family_friendly", "is_premium"),
        "short_description": "Ícono lacustre-volcánico del destino. Combinación esencial de Puerto Varas.",
    },
    {
        "slug": "puerto-montt-isla-tenglo-angelmo",
        "name": "Puerto Montt + Isla Tenglo + Angelmó",
        "duration_code": "DPV_1D",
        "primary_interest": "GASTRONOMY",
        "recommended_profile": "FAMILY",
        "flags": F("is_culture", "is_gastronomy", "is_family_friendly", "is_rain_friendly"),
        "short_description": "Ciudad puerto, mercado y tramo insular corto. Movimientos internos cortos.",
    },
    {
        "slug": "vuelta-norte-llanquihue",
        "name": "Vuelta norte Lago Llanquihue",
        "duration_code": "DPV_1D",
        "primary_interest": "MIXED",
        "recommended_profile": "FAMILY",
        "flags": F("is_culture", "is_gastronomy", "is_family_friendly"),
        "short_description": "Puerto Varas, Llanquihue, Frutillar y retorno. Tramos cortos en auto o transfer.",
    },
    {
        "slug": "vuelta-este-llanquihue",
        "name": "Vuelta este Lago Llanquihue",
        "duration_code": "DPV_1D",
        "primary_interest": "NATURE",
        "recommended_profile": "FAMILY",
        "flags": F("is_nature", "is_family_friendly"),
        "short_description": "Puerto Varas, Ensenada, Las Cascadas, Puerto Octay y retorno por la ribera este.",
    },
    {
        "slug": "castro-dalcahue-tocoihue-putemun",
        "name": "Castro + Dalcahue + Tocoihue + Putemún",
        "duration_code": "DPV_1D",
        "primary_interest": "MIXED",
        "recommended_profile": "COUPLE",
        "flags": F("is_culture", "is_nature"),
        "short_description": "Cultura, cascada y humedal en el Chiloé central. Jornada larga vía ferry + Ruta 5.",
    },
    {
        "slug": "pn-chiloe-cucao-chanquin",
        "name": "PN Chiloé sector Cucao/Chanquín",
        "duration_code": "DPV_1D",
        "primary_interest": "NATURE",
        "recommended_profile": "FAMILY",
        "flags": F("is_nature", "is_family_friendly"),
        "short_description": "Playa, bosque y pasarelas de Chanquín. Parque desde CLP 2.800.",
    },
    {
        "slug": "chacao-caulin-ancud",
        "name": "Chacao + Caulín + Ancud",
        "duration_code": "DPV_1D",
        "primary_interest": "NATURE",
        "recommended_profile": "FAMILY",
        "flags": F("is_nature", "is_culture", "is_family_friendly"),
        "short_description": "Puerta de entrada a Chiloé, observación costera y ciudad de Ancud.",
    },
    {
        "slug": "paso-desolacion-rincon-osorno",
        "name": "Paso Desolación o Rincón del Osorno",
        "duration_code": "DPV_1D",
        "primary_interest": "ADVENTURE",
        "recommended_profile": "FRIENDS",
        "flags": F("is_nature", "is_adventure"),
        "short_description": "Trekking de mayor exigencia en PN Vicente Pérez Rosales. 5-12 km según tramo.",
    },
    {
        "slug": "valle-cochamo-cascada-escondida",
        "name": "Valle de Cochamó base + Cascada Escondida",
        "duration_code": "DPV_1D",
        "primary_interest": "ADVENTURE",
        "recommended_profile": "FRIENDS",
        "flags": F("is_nature", "is_adventure"),
        "short_description": "Pueblo, desvío a cascada y acceso al valle. Caminata corta, cascada CLP 2.500.",
    },
    {
        "slug": "rio-puelo-llanada-grande",
        "name": "Río Puelo + Llanada Grande / El Salto",
        "duration_code": "DPV_1D",
        "primary_interest": "ADVENTURE",
        "recommended_profile": "FRIENDS",
        "flags": F("is_nature", "is_adventure"),
        "short_description": "Valle de río, lagos interiores y salto. 45 min de Cochamó a Llanada Grande.",
    },
    {
        "slug": "puyehue-anticura-senderos",
        "name": "Puyehue Anticura + senderos concesionados",
        "duration_code": "DPV_1D",
        "primary_interest": "NATURE",
        "recommended_profile": "FAMILY",
        "flags": F("is_nature", "is_adventure"),
        "short_description": "Senderos, cascadas y sector cordillerano. Senderos concesionados (El Indio, La Princesa).",
    },

    # ═════ 2 DÍAS (10) ═════
    {
        "slug": "lago-llanquihue-ascenso-osorno",
        "name": "Lago Llanquihue + ascenso al Volcán Osorno",
        "duration_code": "DPV_2D1N",
        "primary_interest": "ADVENTURE",
        "recommended_profile": "FRIENDS",
        "flags": F("is_nature", "is_adventure", "is_premium"),
        "short_description": "Día 1 Puerto Varas, día 2 ascenso técnico al Osorno con guía especializado. 192 km en total.",
    },
    {
        "slug": "paso-el-leon-petrohue",
        "name": "Paso El León + Petrohué",
        "duration_code": "DPV_2D1N",
        "primary_interest": "ADVENTURE",
        "recommended_profile": "FRIENDS",
        "flags": F("is_nature", "is_adventure"),
        "short_description": "Valle del Manso, cruce histórico y cierre en Saltos del Petrohué. Sendero 12 km.",
    },
    {
        "slug": "valle-cochamo-pernocta",
        "name": "Valle de Cochamó con pernocta",
        "duration_code": "DPV_2D1N",
        "primary_interest": "ADVENTURE",
        "recommended_profile": "FRIENDS",
        "flags": F("is_nature", "is_adventure"),
        "short_description": "Aproximación + trekking/cabalgata al valle. 3-4 h hasta los toboganes naturales.",
    },
    {
        "slug": "chiloe-norte-2d",
        "name": "Chiloé norte (2 días)",
        "duration_code": "DPV_2D1N",
        "primary_interest": "MIXED",
        "recommended_profile": "FAMILY",
        "flags": F("is_culture", "is_gastronomy", "is_family_friendly"),
        "short_description": "Ancud-Castro con pernocta intermedia. 112 km + ferry, segundo día por Ruta 5.",
    },
    {
        "slug": "chiloe-central-patrimonial",
        "name": "Chiloé central patrimonial",
        "duration_code": "DPV_2D1N",
        "primary_interest": "MIXED",
        "recommended_profile": "FAMILY",
        "flags": F("is_culture", "is_family_friendly"),
        "short_description": "Castro, Dalcahue, Quinchao y Achao. Iglesias patrimoniales con ferry corto.",
    },
    {
        "slug": "puyehue-slow",
        "name": "Puyehue slow",
        "duration_code": "DPV_2D1N",
        "primary_interest": "RELAX_ROMANTIC",
        "recommended_profile": "COUPLE",
        "flags": F("is_nature", "is_romantic"),
        "short_description": "Aguas Calientes + Anticura con pernocta. Termas + senderos a ritmo tranquilo.",
    },
    {
        "slug": "hualaihue-termal",
        "name": "Hualaihué termal",
        "duration_code": "DPV_2D1N",
        "primary_interest": "RELAX_ROMANTIC",
        "recommended_profile": "COUPLE",
        "flags": F("is_nature", "is_romantic"),
        "short_description": "Puelo, Termas del Sol y Hornopirén. Corredor bimodal hacia el sur.",
    },
    {
        "slug": "los-alerces-corto",
        "name": "Los Alerces corto",
        "duration_code": "DPV_2D1N",
        "primary_interest": "NATURE",
        "recommended_profile": "FRIENDS",
        "flags": F("is_nature", "is_adventure"),
        "short_description": "Alerce Andino + Hornopirén. Primera aproximación a la Ruta de los Parques.",
    },
    {
        "slug": "calbuco-archipielago",
        "name": "Calbuco archipiélago",
        "duration_code": "DPV_2D1N",
        "primary_interest": "MIXED",
        "recommended_profile": "FAMILY",
        "flags": F("is_nature", "is_culture", "is_family_friendly"),
        "short_description": "Calbuco, Caicaén y Puluqui con pernocta. Combinación terrestre + cruce local.",
    },
    {
        "slug": "pn-chiloe-cucao-chepu",
        "name": "Parque Nacional Chiloé + Cucao + Chepu",
        "duration_code": "DPV_2D1N",
        "primary_interest": "NATURE",
        "recommended_profile": "FAMILY",
        "flags": F("is_nature", "is_family_friendly", "is_adventure"),
        "short_description": "Bosque, costa y humedales con base en Castro/Ancud. Bote opcional a Chepu.",
    },

    # ═════ 3 DÍAS (8) ═════
    {
        "slug": "imperdibles-chiloe",
        "name": "Imperdibles de Chiloé",
        "duration_code": "DPV_3D2N",
        "primary_interest": "MIXED",
        "recommended_profile": "FAMILY",
        "flags": F("is_culture", "is_nature", "is_gastronomy", "is_family_friendly"),
        "short_description": "Castro y palafitos, Isla Aucar/Quemchi, Parque Tantauco. 130 km en Chiloé.",
    },
    {
        "slug": "chiloe-norte-central-profundo",
        "name": "Chiloé norte y central profundo",
        "duration_code": "DPV_3D2N",
        "primary_interest": "MIXED",
        "recommended_profile": "COUPLE",
        "flags": F("is_culture", "is_nature"),
        "short_description": "Ancud, Chepu, Muelle de la Luz, Castro, Aucar, Tenaún y San Juan. Inmersión patrimonial.",
    },
    {
        "slug": "chiloe-patrimonio-esencial",
        "name": "Chiloé patrimonio esencial",
        "duration_code": "DPV_3D2N",
        "primary_interest": "MIXED",
        "recommended_profile": "FAMILY",
        "flags": F("is_culture", "is_gastronomy", "is_family_friendly"),
        "short_description": "Ancud, Dalcahue y Castro con dos pernoctas. Patrimonio esencial chilote.",
    },
    {
        "slug": "chiloe-naturaleza-costa-oeste",
        "name": "Chiloé naturaleza y costa oeste",
        "duration_code": "DPV_3D2N",
        "primary_interest": "NATURE",
        "recommended_profile": "FRIENDS",
        "flags": F("is_nature", "is_adventure"),
        "short_description": "Castro, Cucao/PN Chiloé, Chepu/Muelle de la Luz. Costa oeste + parque + humedal.",
    },
    {
        "slug": "llanquihue-petrohue-peulla",
        "name": "Llanquihue + Petrohué + Peulla",
        "duration_code": "DPV_3D2N",
        "primary_interest": "NATURE",
        "recommended_profile": "COUPLE",
        "flags": F("is_nature", "is_culture", "is_romantic", "is_premium"),
        "short_description": "Puerto Varas/Frutillar, Petrohué, Lago Todos los Santos y Peulla. Día urbano + navegación.",
    },
    {
        "slug": "patagonia-verde-corto",
        "name": "Patagonia Verde corto",
        "duration_code": "DPV_3D2N",
        "primary_interest": "NATURE",
        "recommended_profile": "FRIENDS",
        "flags": F("is_nature", "is_adventure"),
        "short_description": "Cochamó, Puelo y Hornopirén. Fiordos, ríos, termas y bosque templado.",
    },
    {
        "slug": "los-alerces-express",
        "name": "Los Alerces express",
        "duration_code": "DPV_3D2N",
        "primary_interest": "NATURE",
        "recommended_profile": "FRIENDS",
        "flags": F("is_nature", "is_adventure"),
        "short_description": "Alerce Andino, Hornopirén y Caleta Gonzalo/Pumalín norte. Tramo norte de Ruta Los Alerces.",
    },
    {
        "slug": "chiloe-sur-tantauco",
        "name": "Chiloé sur con Tantauco",
        "duration_code": "DPV_3D2N",
        "primary_interest": "NATURE",
        "recommended_profile": "FRIENDS",
        "flags": F("is_nature", "is_adventure"),
        "short_description": "Castro, Quellón, Yaldad/Chaiguata y Muelle de la Luz/Chepu. Sur profundo.",
    },

    # ═════ 4-6 DÍAS (4) ═════
    {
        "slug": "carretera-austral-patagonia-verde",
        "name": "Carretera Austral por la Patagonia Verde",
        "duration_code": "DPV_5D4N",
        "primary_interest": "ADVENTURE",
        "recommended_profile": "FRIENDS",
        "flags": F("is_nature", "is_adventure", "is_premium"),
        "short_description": "Cochamó, Río Puelo/Lago Tagua Tagua, Hornopirén, Pumalín y Chaitén. 470 km autoguiado.",
    },
    {
        "slug": "ruta-los-alerces",
        "name": "Ruta Los Alerces",
        "duration_code": "DPV_5D4N",
        "primary_interest": "NATURE",
        "recommended_profile": "FRIENDS",
        "flags": F("is_nature", "is_adventure", "is_premium"),
        "short_description": "Alerce Andino, Hornopirén y Pumalín Douglas Tompkins. Ruta terrestre y marítima de la Ruta de los Parques.",
    },
    {
        "slug": "puerto-varas-y-chiloe",
        "name": "Puerto Varas y Chiloé",
        "duration_code": "DPV_5D4N",
        "primary_interest": "MIXED",
        "recommended_profile": "FAMILY",
        "flags": F("is_nature", "is_culture", "is_gastronomy", "is_family_friendly", "is_premium"),
        "short_description": "Puerto Varas, Frutillar, Puelo, Peulla, Ancud, Aucar/Tenaún/San Juan y Castro. Itinerario completo de 6 días.",
    },
    {
        "slug": "cruce-andino-ida-vuelta",
        "name": "Cruce Andino ida y vuelta con pernocta",
        "duration_code": "DPV_5D4N",
        "primary_interest": "RELAX_ROMANTIC",
        "recommended_profile": "COUPLE",
        "flags": F("is_nature", "is_romantic", "is_premium"),
        "short_description": "Puerto Varas, Petrohué, Peulla y cruce lacustre/binacional con noche intermedia. Desde USD 600.",
    },
]


class Command(BaseCommand):
    help = "Carga 50+ circuitos del estudio como 'Próximamente' (sin días/paradas)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Muestra qué se haría sin tocar la base de datos.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        # 1) Asegurar DurationCases
        durations = self._ensure_durations(dry_run)

        # 2) Cargar circuitos
        next_number = self._next_circuit_number()
        sort_order_by_duration = {
            "DPV_HALF_DAY": 100,
            "DPV_1D": 200,
            "DPV_2D1N": 300,
            "DPV_3D2N": 400,
            "DPV_5D4N": 500,
        }

        created = 0
        skipped = 0
        sort_order_offset = {k: 0 for k in sort_order_by_duration}

        for entry in CIRCUITS:
            slug = entry["slug"]
            if Circuit.objects.filter(slug=slug).exists():
                self.stdout.write(self.style.WARNING(f"  [skip] {slug} ya existe"))
                skipped += 1
                # Aún así avanzamos sort_order para mantener orden visual estable
                sort_order_offset[entry["duration_code"]] += 10
                continue

            duration = durations.get(entry["duration_code"])
            if duration is None:
                self.stdout.write(
                    self.style.ERROR(f"  [error] {slug}: duración {entry['duration_code']} no existe")
                )
                continue

            base_sort = sort_order_by_duration[entry["duration_code"]]
            sort_order = base_sort + sort_order_offset[entry["duration_code"]]
            sort_order_offset[entry["duration_code"]] += 10

            payload = dict(
                number=next_number,
                name=entry["name"][:200],
                slug=slug,
                short_description=entry["short_description"][:255],
                long_description="",
                duration_case=duration,
                primary_interest=entry["primary_interest"],
                recommended_profile=entry.get("recommended_profile", ""),
                published=True,
                featured=False,
                sort_order=sort_order,
            )
            payload.update(entry["flags"])

            if dry_run:
                self.stdout.write(f"  [dry-run] crearía #{next_number} '{entry['name']}'")
            else:
                with transaction.atomic():
                    Circuit.objects.create(**payload)
                self.stdout.write(self.style.SUCCESS(f"  [ok] #{next_number} '{entry['name']}'"))

            next_number += 1
            created += 1

        verb = "crearían" if dry_run else "creados"
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"Resumen: {created} circuitos {verb}, {skipped} ya existían."
        ))
        self.stdout.write(
            "Los circuitos no tienen días/paradas — aparecerán como 'Próximamente'. "
            "Para completar uno, usá el admin (Composer manual o agregar paradas)."
        )

    # ─── helpers ─────────────────────────────────────────────────────────────

    def _ensure_durations(self, dry_run: bool) -> dict[str, DurationCase]:
        result = {}
        for d in DURATION_SEED:
            obj = DurationCase.objects.filter(code=d["code"]).first()
            if obj:
                result[d["code"]] = obj
                continue
            if dry_run:
                self.stdout.write(f"  [dry-run] crearía DurationCase {d['code']}")
                result[d["code"]] = DurationCase(**d)  # placeholder, no persisted
                continue
            obj = DurationCase.objects.create(**d)
            self.stdout.write(self.style.SUCCESS(f"  [ok] DurationCase {d['code']} creado"))
            result[d["code"]] = obj
        return result

    def _next_circuit_number(self) -> int:
        """Empieza en 1001 para no chocar con seeds previos (101-199 reservados)."""
        max_existing = (
            Circuit.objects.filter(number__gte=1000)
            .order_by("-number")
            .values_list("number", flat=True)
            .first()
        )
        return (max_existing or 1000) + 1
