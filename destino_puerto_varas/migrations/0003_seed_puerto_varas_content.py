"""Seed real Puerto Varas content: duration cases, places, circuits, rules, aremko recos y travel tips.

Idempotente (get_or_create) y reversible (reverse_code borra filas seeded por slug/context_key).
"""

from django.db import migrations


# ─────────────────────────────────────────────────────────────────────────────
# Catálogos de referencia (slugs/códigos estables usados por seed y reverse)
# ─────────────────────────────────────────────────────────────────────────────

DURATION_CODES = ["DPV_HALF_DAY", "DPV_2D1N", "DPV_3D2N"]

PLACE_SLUGS = [
    "saltos-del-petrohue",
    "volcan-osorno-mirador",
    "lago-todos-los-santos",
    "frutillar-teatro-del-lago",
    "puerto-varas-costanera",
    "mirador-philippi",
    "ensenada-mirador-lago",
    "parque-nacional-vicente-perez-rosales",
    "cerveceria-chester",
    "mercado-puerto-varas",
    "cafe-dane",
    "casino-dreams",
]

CIRCUIT_SLUGS = [
    "relax-medio-dia-puerto-varas",
    "naturaleza-activa-2d1n",
    "aventura-lago-llanquihue-3d2n",
]

AREMKO_CONTEXT_KEYS = [
    "relax_pareja",
    "lluvia",
    "relax",
    "fallback_any",
]

TRAVEL_TIP_TITLES = [
    "Lleva capa de lluvia siempre",
    "Reserva cena con vista al lago",
    "Los Saltos temprano en la mañana",
    "Protector solar incluso nublado",
    "Ropa térmica para el Osorno",
    "Efectivo para ferias locales",
]


# ─────────────────────────────────────────────────────────────────────────────
# Seed helpers
# ─────────────────────────────────────────────────────────────────────────────

def _seed_duration_cases(apps):
    DurationCase = apps.get_model("destino_puerto_varas", "DurationCase")
    data = [
        {
            "code": "DPV_HALF_DAY",
            "name": "Medio día en Puerto Varas",
            "duration_type": "HALF_DAY",
            "days": 0,
            "nights": 0,
            "sort_order": 10,
            "description": "3–4 horas para recorrer lo esencial de Puerto Varas.",
        },
        {
            "code": "DPV_2D1N",
            "name": "2 días / 1 noche",
            "duration_type": "TWO_DAYS_ONE_NIGHT",
            "days": 2,
            "nights": 1,
            "sort_order": 20,
            "description": "Fin de semana: lago, volcán y descanso.",
        },
        {
            "code": "DPV_3D2N",
            "name": "3 días / 2 noches",
            "duration_type": "THREE_DAYS_TWO_NIGHTS",
            "days": 3,
            "nights": 2,
            "sort_order": 30,
            "description": "Escapada completa por Lago Llanquihue y Parque Nacional.",
        },
    ]
    result = {}
    for row in data:
        obj, _ = DurationCase.objects.get_or_create(
            code=row["code"],
            defaults={k: v for k, v in row.items() if k != "code"},
        )
        result[row["code"]] = obj
    return result


def _seed_places(apps):
    Place = apps.get_model("destino_puerto_varas", "Place")
    data = [
        {
            "slug": "saltos-del-petrohue",
            "name": "Saltos del Petrohué",
            "place_type": "ATTRACTION",
            "short_description": "Saltos de agua turquesa con vista al volcán Osorno.",
            "long_description": "Dentro del Parque Nacional Vicente Pérez Rosales. Pasarelas cortas y planas.",
            "location_label": "Parque Nacional Vicente Pérez Rosales",
            "latitude": "-41.179722",
            "longitude": "-72.426111",
            "is_rain_friendly": False,
            "is_romantic": True,
            "is_family_friendly": True,
            "is_adventure_related": False,
            "practical_tips": "Ir temprano para evitar buses de turistas (antes de 10:30).",
            "safety_notes": "No cruzar rejas ni bajar al cauce.",
            "did_you_know": "El color turquesa proviene de sedimentos glaciares del Osorno.",
            "nobody_tells_you": "Hay un sendero corto lateral con mucho menos gente.",
        },
        {
            "slug": "volcan-osorno-mirador",
            "name": "Mirador Volcán Osorno",
            "place_type": "VIEWPOINT",
            "short_description": "Mirador de altura con panorámica al Llanquihue.",
            "long_description": "Se accede por camino pavimentado hasta el refugio; telesilla opcional.",
            "location_label": "Ensenada, camino al refugio",
            "latitude": "-41.100000",
            "longitude": "-72.493889",
            "is_rain_friendly": False,
            "is_romantic": True,
            "is_family_friendly": True,
            "is_adventure_related": True,
            "practical_tips": "Llevar abrigo térmico — la temperatura cae 10-15°C al subir.",
            "safety_notes": "Revisar cierre por viento o nieve antes de ir.",
            "did_you_know": "El Osorno tiene 2.652 m y es uno de los volcanes más simétricos del mundo.",
            "nobody_tells_you": "En días despejados se ven Calbuco, Puntiagudo y Tronador desde el mirador.",
        },
        {
            "slug": "lago-todos-los-santos",
            "name": "Lago Todos los Santos",
            "place_type": "ATTRACTION",
            "short_description": "Lago esmeralda rodeado de bosque nativo y volcanes.",
            "long_description": "También llamado 'Esmeralda'. Navegación opcional a Peulla.",
            "location_label": "Petrohué",
            "latitude": "-41.129444",
            "longitude": "-72.404722",
            "is_rain_friendly": False,
            "is_romantic": True,
            "is_family_friendly": True,
            "is_adventure_related": True,
            "practical_tips": "Contratar navegación con anticipación en temporada alta.",
            "did_you_know": "Su nombre original mapuche es Pirihueico.",
            "nobody_tells_you": "Hay playas pequeñas al costado del muelle casi siempre vacías.",
        },
        {
            "slug": "frutillar-teatro-del-lago",
            "name": "Teatro del Lago (Frutillar)",
            "place_type": "ATTRACTION",
            "short_description": "Teatro flotante con agenda cultural y vista al Osorno.",
            "long_description": "Arquitectura moderna en madera sobre el lago. 40 min desde Puerto Varas.",
            "location_label": "Frutillar Bajo",
            "latitude": "-41.126944",
            "longitude": "-73.000000",
            "is_rain_friendly": True,
            "is_romantic": True,
            "is_family_friendly": True,
            "practical_tips": "Revisar agenda: conciertos, visitas guiadas y kuchen en Frutillar.",
            "did_you_know": "Sede anual de las Semanas Musicales desde 1968.",
            "nobody_tells_you": "El tour del teatro dura 45 min y muchos se lo pierden.",
        },
        {
            "slug": "puerto-varas-costanera",
            "name": "Costanera de Puerto Varas",
            "place_type": "ATTRACTION",
            "short_description": "Paseo peatonal junto al lago con vista al Osorno.",
            "long_description": "Mejor caminata al atardecer, 1.5 km desde la plaza hasta Puerto Chico.",
            "location_label": "Centro de Puerto Varas",
            "latitude": "-41.320000",
            "longitude": "-72.985000",
            "is_rain_friendly": False,
            "is_romantic": True,
            "is_family_friendly": True,
            "practical_tips": "Atardecer 20:30 en verano, 17:30 en invierno.",
            "did_you_know": "La costanera fue remodelada en 2016 tras retirar el relleno sanitario antiguo.",
            "nobody_tells_you": "El mejor ángulo del Osorno es desde el muelle sur de Puerto Chico.",
        },
        {
            "slug": "mirador-philippi",
            "name": "Mirador del Cerro Philippi",
            "place_type": "VIEWPOINT",
            "short_description": "Vista 360° de Puerto Varas y el Llanquihue.",
            "long_description": "Sendero corto (20 min de subida) desde el centro. Cruz en la cima.",
            "location_label": "Centro de Puerto Varas",
            "latitude": "-41.325556",
            "longitude": "-72.977778",
            "is_rain_friendly": False,
            "is_romantic": True,
            "is_family_friendly": True,
            "is_adventure_related": False,
            "practical_tips": "Llevar agua. El camino puede estar resbaloso tras lluvia.",
            "nobody_tells_you": "El amanecer desde la cruz es menos concurrido que el atardecer.",
        },
        {
            "slug": "ensenada-mirador-lago",
            "name": "Ensenada – Mirador del Lago",
            "place_type": "VIEWPOINT",
            "short_description": "Costa este del Llanquihue, vistas a Osorno y Calbuco.",
            "long_description": "45 min desde Puerto Varas, en la ruta a Petrohué.",
            "location_label": "Ensenada",
            "latitude": "-41.200000",
            "longitude": "-72.555556",
            "is_rain_friendly": False,
            "is_romantic": True,
            "is_family_friendly": True,
            "practical_tips": "Parar a comer en alguna de las paradas de la orilla — salmón ahumado.",
        },
        {
            "slug": "parque-nacional-vicente-perez-rosales",
            "name": "Parque Nacional Vicente Pérez Rosales",
            "place_type": "PARK",
            "short_description": "Parque nacional más antiguo de Chile (1926).",
            "long_description": "Reserva de bosque nativo, volcanes, lagos y termas.",
            "location_label": "Petrohué – Peulla",
            "latitude": "-41.166667",
            "longitude": "-72.416667",
            "is_rain_friendly": False,
            "is_romantic": False,
            "is_family_friendly": True,
            "is_adventure_related": True,
            "practical_tips": "Entrada CONAF — llevar efectivo, tienen señal limitada.",
            "did_you_know": "Es Reserva de la Biósfera UNESCO desde 2007.",
        },
        {
            "slug": "cerveceria-chester",
            "name": "Cervecería Chester",
            "place_type": "RESTAURANT",
            "short_description": "Cervezas artesanales locales con vista al lago.",
            "long_description": "Producción propia. Pairing con tablas y cordero.",
            "location_label": "Camino a Ensenada",
            "latitude": "-41.270000",
            "longitude": "-72.900000",
            "is_rain_friendly": True,
            "is_romantic": True,
            "is_family_friendly": False,
            "practical_tips": "Reservar en fin de semana — se llena rápido.",
            "nobody_tells_you": "La Golden es la más pedida por locales.",
        },
        {
            "slug": "mercado-puerto-varas",
            "name": "Mercado de Puerto Varas",
            "place_type": "SHOP",
            "short_description": "Mercado tradicional con productos locales.",
            "long_description": "Cocina regional, mariscos, kuchen y artesanía.",
            "location_label": "Centro de Puerto Varas",
            "latitude": "-41.322000",
            "longitude": "-72.982000",
            "is_rain_friendly": True,
            "is_family_friendly": True,
            "practical_tips": "Probar curanto en olla — es la especialidad regional.",
            "nobody_tells_you": "Los puestos del segundo piso tienen mejor relación precio/calidad.",
        },
        {
            "slug": "cafe-dane",
            "name": "Café Dane's",
            "place_type": "CAFE",
            "short_description": "Café clásico de Puerto Varas, kuchen de herencia alemana.",
            "long_description": "Institución local desde hace décadas. Desayunos abundantes.",
            "location_label": "Del Salvador, Puerto Varas",
            "latitude": "-41.319444",
            "longitude": "-72.986111",
            "is_rain_friendly": True,
            "is_romantic": False,
            "is_family_friendly": True,
            "practical_tips": "Ideal para días lluviosos — ambiente cálido.",
            "nobody_tells_you": "El kuchen de frambuesa se agota antes del mediodía.",
        },
        {
            "slug": "casino-dreams",
            "name": "Casino Dreams Puerto Varas",
            "place_type": "OTHER",
            "short_description": "Casino y entretenimiento nocturno frente al lago.",
            "long_description": "Juegos, restaurantes y espectáculos. Bueno como plan de lluvia.",
            "location_label": "Costanera de Puerto Varas",
            "latitude": "-41.321000",
            "longitude": "-72.983000",
            "is_rain_friendly": True,
            "is_romantic": False,
            "is_family_friendly": False,
            "practical_tips": "Entrada con cédula, mayores de 18.",
        },
    ]
    result = {}
    for row in data:
        obj, _ = Place.objects.get_or_create(
            slug=row["slug"],
            defaults={k: v for k, v in row.items() if k != "slug"},
        )
        result[row["slug"]] = obj
    return result


def _seed_circuits(apps, durations, places):
    Circuit = apps.get_model("destino_puerto_varas", "Circuit")
    CircuitDay = apps.get_model("destino_puerto_varas", "CircuitDay")
    CircuitPlace = apps.get_model("destino_puerto_varas", "CircuitPlace")

    # 1) Circuit: relax medio día
    c1, _ = Circuit.objects.get_or_create(
        slug="relax-medio-dia-puerto-varas",
        defaults=dict(
            number=101,
            name="Relax de medio día en Puerto Varas",
            short_description="Café, costanera y mirador Philippi — plan tranquilo para tarde corta.",
            long_description="Recorrido corto y relajado por el centro y el cerro Philippi.",
            duration_case=durations["DPV_HALF_DAY"],
            primary_interest="RELAX_ROMANTIC",
            recommended_profile="COUPLE",
            is_romantic=True,
            is_family_friendly=True,
            is_adventure=False,
            is_rain_friendly=False,
            is_premium=False,
            published=True,
            featured=True,
            sort_order=10,
        ),
    )
    d1a, _ = CircuitDay.objects.get_or_create(
        circuit=c1, day_number=1,
        defaults=dict(title="Tarde en Puerto Varas", block_type="HALF_DAY",
                      summary="Café, costanera y mirador al atardecer.", sort_order=10),
    )
    for visit_order, (slug, main) in enumerate([
        ("cafe-dane", False),
        ("puerto-varas-costanera", True),
        ("mirador-philippi", False),
    ], start=1):
        CircuitPlace.objects.get_or_create(
            circuit_day=d1a, place=places[slug],
            defaults=dict(visit_order=visit_order, is_main_stop=main),
        )

    # 2) Circuit: naturaleza 2d1n
    c2, _ = Circuit.objects.get_or_create(
        slug="naturaleza-activa-2d1n",
        defaults=dict(
            number=102,
            name="Naturaleza activa 2 días / 1 noche",
            short_description="Saltos del Petrohué, Lago Todos los Santos y mirador del Osorno.",
            long_description="Fin de semana de naturaleza con descanso al atardecer en Puerto Varas.",
            duration_case=durations["DPV_2D1N"],
            primary_interest="NATURE",
            recommended_profile="FAMILY",
            is_romantic=False,
            is_family_friendly=True,
            is_adventure=True,
            is_rain_friendly=False,
            is_premium=False,
            published=True,
            featured=True,
            sort_order=20,
        ),
    )
    d2a, _ = CircuitDay.objects.get_or_create(
        circuit=c2, day_number=1,
        defaults=dict(title="Día 1: Petrohué y Todos los Santos", block_type="FULL_DAY",
                      summary="Saltos del Petrohué temprano, almuerzo en Ensenada, lago al mediodía.", sort_order=10),
    )
    for visit_order, (slug, main) in enumerate([
        ("saltos-del-petrohue", True),
        ("lago-todos-los-santos", True),
        ("ensenada-mirador-lago", False),
    ], start=1):
        CircuitPlace.objects.get_or_create(
            circuit_day=d2a, place=places[slug],
            defaults=dict(visit_order=visit_order, is_main_stop=main),
        )
    d2b, _ = CircuitDay.objects.get_or_create(
        circuit=c2, day_number=2,
        defaults=dict(title="Día 2: Puerto Varas y Frutillar", block_type="HALF_DAY",
                      summary="Costanera en la mañana, Frutillar por la tarde.", sort_order=20),
    )
    for visit_order, (slug, main) in enumerate([
        ("puerto-varas-costanera", False),
        ("frutillar-teatro-del-lago", True),
    ], start=1):
        CircuitPlace.objects.get_or_create(
            circuit_day=d2b, place=places[slug],
            defaults=dict(visit_order=visit_order, is_main_stop=main),
        )

    # 3) Circuit: aventura 3d2n
    c3, _ = Circuit.objects.get_or_create(
        slug="aventura-lago-llanquihue-3d2n",
        defaults=dict(
            number=103,
            name="Aventura Lago Llanquihue 3 días / 2 noches",
            short_description="Osorno, parque nacional y cervecería con pairing local.",
            long_description="Escapada completa: volcán, parque nacional y vida local.",
            duration_case=durations["DPV_3D2N"],
            primary_interest="ADVENTURE",
            recommended_profile="FRIENDS",
            is_romantic=False,
            is_family_friendly=True,
            is_adventure=True,
            is_rain_friendly=False,
            is_premium=True,
            published=True,
            featured=True,
            sort_order=30,
        ),
    )
    d3a, _ = CircuitDay.objects.get_or_create(
        circuit=c3, day_number=1,
        defaults=dict(title="Día 1: Llegada y centro", block_type="ARRIVAL",
                      summary="Instalación, costanera, cena en cervecería.", sort_order=10),
    )
    for visit_order, (slug, main) in enumerate([
        ("puerto-varas-costanera", False),
        ("cerveceria-chester", True),
    ], start=1):
        CircuitPlace.objects.get_or_create(
            circuit_day=d3a, place=places[slug],
            defaults=dict(visit_order=visit_order, is_main_stop=main),
        )
    d3b, _ = CircuitDay.objects.get_or_create(
        circuit=c3, day_number=2,
        defaults=dict(title="Día 2: Volcán Osorno y parque nacional", block_type="FULL_DAY",
                      summary="Mirador Osorno, parque y saltos.", sort_order=20),
    )
    for visit_order, (slug, main) in enumerate([
        ("volcan-osorno-mirador", True),
        ("parque-nacional-vicente-perez-rosales", True),
        ("saltos-del-petrohue", True),
    ], start=1):
        CircuitPlace.objects.get_or_create(
            circuit_day=d3b, place=places[slug],
            defaults=dict(visit_order=visit_order, is_main_stop=main),
        )
    d3c, _ = CircuitDay.objects.get_or_create(
        circuit=c3, day_number=3,
        defaults=dict(title="Día 3: Frutillar y mercado", block_type="DEPARTURE",
                      summary="Kuchen en Frutillar, mercado y salida.", sort_order=30),
    )
    for visit_order, (slug, main) in enumerate([
        ("frutillar-teatro-del-lago", True),
        ("mercado-puerto-varas", False),
    ], start=1):
        CircuitPlace.objects.get_or_create(
            circuit_day=d3c, place=places[slug],
            defaults=dict(visit_order=visit_order, is_main_stop=main),
        )

    return {
        "relax-medio-dia-puerto-varas": c1,
        "naturaleza-activa-2d1n": c2,
        "aventura-lago-llanquihue-3d2n": c3,
    }


def _seed_recommendation_rules(apps, durations, circuits):
    RecommendationRule = apps.get_model("destino_puerto_varas", "RecommendationRule")
    # Regla única por (duration_case, interest, profile, is_rainy) — usamos name como clave única lógica
    rules = [
        # Medio día
        dict(name="HALF_DAY + RELAX + COUPLE",
             duration=durations["DPV_HALF_DAY"], interest="RELAX_ROMANTIC", profile="COUPLE",
             is_rainy=None, circuit=circuits["relax-medio-dia-puerto-varas"], priority=100),
        dict(name="HALF_DAY + RELAX",
             duration=durations["DPV_HALF_DAY"], interest="RELAX_ROMANTIC", profile="",
             is_rainy=None, circuit=circuits["relax-medio-dia-puerto-varas"], priority=80),
        dict(name="HALF_DAY fallback",
             duration=durations["DPV_HALF_DAY"], interest="", profile="",
             is_rainy=None, circuit=circuits["relax-medio-dia-puerto-varas"], priority=10),
        # 2D1N
        dict(name="2D1N + NATURE + FAMILY",
             duration=durations["DPV_2D1N"], interest="NATURE", profile="FAMILY",
             is_rainy=None, circuit=circuits["naturaleza-activa-2d1n"], priority=100),
        dict(name="2D1N + NATURE",
             duration=durations["DPV_2D1N"], interest="NATURE", profile="",
             is_rainy=None, circuit=circuits["naturaleza-activa-2d1n"], priority=80),
        dict(name="2D1N + ADVENTURE",
             duration=durations["DPV_2D1N"], interest="ADVENTURE", profile="",
             is_rainy=None, circuit=circuits["naturaleza-activa-2d1n"], priority=70),
        dict(name="2D1N fallback",
             duration=durations["DPV_2D1N"], interest="", profile="",
             is_rainy=None, circuit=circuits["naturaleza-activa-2d1n"], priority=10),
        # 3D2N
        dict(name="3D2N + ADVENTURE + FRIENDS",
             duration=durations["DPV_3D2N"], interest="ADVENTURE", profile="FRIENDS",
             is_rainy=None, circuit=circuits["aventura-lago-llanquihue-3d2n"], priority=100),
        dict(name="3D2N + ADVENTURE",
             duration=durations["DPV_3D2N"], interest="ADVENTURE", profile="",
             is_rainy=None, circuit=circuits["aventura-lago-llanquihue-3d2n"], priority=80),
        dict(name="3D2N + NATURE",
             duration=durations["DPV_3D2N"], interest="NATURE", profile="",
             is_rainy=None, circuit=circuits["aventura-lago-llanquihue-3d2n"], priority=70),
        dict(name="3D2N fallback",
             duration=durations["DPV_3D2N"], interest="", profile="",
             is_rainy=None, circuit=circuits["aventura-lago-llanquihue-3d2n"], priority=10),
    ]
    for row in rules:
        RecommendationRule.objects.get_or_create(
            name=row["name"],
            defaults=dict(
                duration_case=row["duration"],
                interest=row["interest"],
                profile=row["profile"],
                is_rainy=row["is_rainy"],
                recommended_circuit=row["circuit"],
                priority=row["priority"],
                is_active=True,
            ),
        )


def _seed_aremko_recommendations(apps):
    AremkoRecommendation = apps.get_model("destino_puerto_varas", "AremkoRecommendation")
    data = [
        dict(
            context_key="relax_pareja",
            name="Relax en pareja",
            title="Aremko Spa Boutique — tina caliente en pareja",
            message_text=(
                "Si buscan cerrar el día con relajo, Aremko Spa Boutique en Puerto Varas "
                "ofrece tinas calientes privadas junto al río. Ideal para parejas."
            ),
            recommended_service_type="tina",
            priority=100,
        ),
        dict(
            context_key="lluvia",
            name="Plan de lluvia",
            title="Aremko Spa — spa techado con vista al río",
            message_text=(
                "Con este clima, una sesión de spa o masaje en Aremko es plan perfecto. "
                "Infraestructura techada y tinas calientes climatizadas."
            ),
            recommended_service_type="spa",
            priority=80,
        ),
        dict(
            context_key="relax",
            name="Relax general",
            title="Aremko Spa Boutique — masajes y tinas",
            message_text=(
                "Aremko Spa Boutique tiene masajes, tinas calientes junto al río y cabañas "
                "si te quieres quedar a dormir."
            ),
            recommended_service_type="spa",
            priority=60,
        ),
        dict(
            context_key="fallback_any",
            name="Aremko fallback",
            title="Aremko Spa Boutique",
            message_text=(
                "Si quieres complementar tu plan con spa, masajes o tinas calientes, "
                "Aremko Spa Boutique en Puerto Varas es una buena opción."
            ),
            recommended_service_type="",
            priority=10,
        ),
    ]
    for row in data:
        AremkoRecommendation.objects.get_or_create(
            context_key=row["context_key"],
            defaults={k: v for k, v in row.items() if k != "context_key"},
        )


def _seed_travel_tips(apps, durations):
    TravelTip = apps.get_model("destino_puerto_varas", "TravelTip")
    data = [
        dict(
            title="Lleva capa de lluvia siempre",
            tip_text="Aunque amanezca despejado, la lluvia es impredecible en Puerto Varas — lleva capa o paraguas liviano.",
            interest="",
            profile="",
            duration_case=None,
            applies_when_raining=True,
            applies_when_sunny=False,
            sort_order=10,
        ),
        dict(
            title="Reserva cena con vista al lago",
            tip_text="Los mejores restaurantes con vista al Llanquihue se llenan rápido — reserva al menos 24h antes en fin de semana.",
            interest="GASTRONOMY",
            profile="COUPLE",
            duration_case=None,
            applies_when_raining=False,
            applies_when_sunny=False,
            sort_order=20,
        ),
        dict(
            title="Los Saltos temprano en la mañana",
            tip_text="Visita los Saltos del Petrohué antes de las 10:30 — después llegan todos los buses turísticos.",
            interest="NATURE",
            profile="",
            duration_case=None,
            applies_when_raining=False,
            applies_when_sunny=True,
            sort_order=30,
        ),
        dict(
            title="Protector solar incluso nublado",
            tip_text="La radiación UV en el sur es alta aún con cielo cubierto — protector solar 50+ recomendado.",
            interest="",
            profile="FAMILY",
            duration_case=None,
            applies_when_raining=False,
            applies_when_sunny=True,
            sort_order=40,
        ),
        dict(
            title="Ropa térmica para el Osorno",
            tip_text="En el mirador del Osorno la temperatura cae 10-15°C respecto a Puerto Varas — lleva ropa térmica.",
            interest="ADVENTURE",
            profile="",
            duration_case=durations["DPV_3D2N"],
            applies_when_raining=False,
            applies_when_sunny=False,
            sort_order=50,
        ),
        dict(
            title="Efectivo para ferias locales",
            tip_text="Mercados y ferias artesanales no siempre aceptan tarjeta — lleva algo de efectivo.",
            interest="",
            profile="",
            duration_case=None,
            applies_when_raining=False,
            applies_when_sunny=False,
            sort_order=60,
        ),
    ]
    for row in data:
        TravelTip.objects.get_or_create(
            title=row["title"],
            defaults={k: v for k, v in row.items() if k != "title"},
        )


# ─────────────────────────────────────────────────────────────────────────────
# Entry points
# ─────────────────────────────────────────────────────────────────────────────

def seed_content(apps, schema_editor):
    durations = _seed_duration_cases(apps)
    places = _seed_places(apps)
    circuits = _seed_circuits(apps, durations, places)
    _seed_recommendation_rules(apps, durations, circuits)
    _seed_aremko_recommendations(apps)
    _seed_travel_tips(apps, durations)


def unseed_content(apps, schema_editor):
    """Borra solo lo que seedeamos — identificado por slug/code/context_key/title."""
    DurationCase = apps.get_model("destino_puerto_varas", "DurationCase")
    Place = apps.get_model("destino_puerto_varas", "Place")
    Circuit = apps.get_model("destino_puerto_varas", "Circuit")
    CircuitDay = apps.get_model("destino_puerto_varas", "CircuitDay")
    CircuitPlace = apps.get_model("destino_puerto_varas", "CircuitPlace")
    RecommendationRule = apps.get_model("destino_puerto_varas", "RecommendationRule")
    AremkoRecommendation = apps.get_model("destino_puerto_varas", "AremkoRecommendation")
    TravelTip = apps.get_model("destino_puerto_varas", "TravelTip")

    rule_names = [
        "HALF_DAY + RELAX + COUPLE", "HALF_DAY + RELAX", "HALF_DAY fallback",
        "2D1N + NATURE + FAMILY", "2D1N + NATURE", "2D1N + ADVENTURE", "2D1N fallback",
        "3D2N + ADVENTURE + FRIENDS", "3D2N + ADVENTURE", "3D2N + NATURE", "3D2N fallback",
    ]

    # Orden por FKs
    RecommendationRule.objects.filter(name__in=rule_names).delete()
    CircuitPlace.objects.filter(circuit_day__circuit__slug__in=CIRCUIT_SLUGS).delete()
    CircuitDay.objects.filter(circuit__slug__in=CIRCUIT_SLUGS).delete()
    Circuit.objects.filter(slug__in=CIRCUIT_SLUGS).delete()
    TravelTip.objects.filter(title__in=TRAVEL_TIP_TITLES).delete()
    Place.objects.filter(slug__in=PLACE_SLUGS).delete()
    AremkoRecommendation.objects.filter(context_key__in=AREMKO_CONTEXT_KEYS).delete()
    DurationCase.objects.filter(code__in=DURATION_CODES).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('destino_puerto_varas', '0002_leadconversation_last_assistant_message_at_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_content, reverse_code=unseed_content),
    ]
