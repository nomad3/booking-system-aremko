"""Seed del blog Aremko: "Tina para grupos en Puerto Varas".

Mismo patrón que los seeds anteriores. Idempotente: update_or_create por
slug. Por defecto queda como BORRADOR (is_published=False). Redactado en
sesión interactiva 2026-07-12, a partir de una idea de Jorge sobre las
tinas grupales (Calbuco, Osorno) — servicio ya existente y bien configurado
en el catálogo real (`/tinas/`), no un producto nuevo.

Datos verificados en /tinas/ (2026-07-12):
- Tina Calbuco: 4 personas, 4 horas de uso exclusivo, $100.000
- Tina Osorno: 5-6 personas, 4 horas de uso exclusivo, $125.000
- Tina normal: 2 personas, 2 horas, $50.000-60.000

Comparación de precio confirmada por Jorge: 2 tinas normales de 2 personas
por 2 horas cuestan $100.000-120.000 — la Tina Calbuco cuesta $100.000 por
4 horas. Mismo presupuesto, el doble de tiempo.

Datos de horarios/condiciones (14:30/19:30, comida y bebida propia sin
cobro, copas y cubetera de hielo prestadas, sin descorche) confirmados por
Jorge — se agregaron TAMBIÉN a la ficha pública de Calbuco/Osorno el mismo
día (ver commit de ventas/templatetags/ventas_extras.py), no solo acá.

Target SEO: ya hay tracción orgánica real sin haber escrito el post
(rank-check DataForSEO 2026-07-12): "tina para grupos puerto varas" pos 1,
"tina 6 personas puerto varas" pos 1, "tina cumpleaños puerto varas" pos 2,
"tina amigos puerto varas" pos 6. El hueco está en búsquedas por OCASIÓN
("despedida de soltera puerto varas", "after office puerto varas", "junta
de amigas puerto varas") — hoy sin contenido dedicado que conecte la
ocasión con el producto.

- Keyword root: "tina para grupos puerto varas"
- Cluster: TINAS

Uso:
    python manage.py seed_blog_post_tina_grupos            # borrador
    python manage.py seed_blog_post_tina_grupos --publish  # publicado
"""
from __future__ import annotations

import json

from django.core.management.base import BaseCommand
from django.utils import timezone

from aremko_blog.models import BlogCluster, BlogPost


SLUG = "tina-para-grupos-puerto-varas"
TITLE = "Tina para grupos en Puerto Varas: 4 horas al mismo precio que 2"
KEYWORD_ROOT = "tina para grupos puerto varas"
META_DESCRIPTION = (
    "Tina para grupos en Puerto Varas: hasta 6 personas, 4 horas de uso "
    "exclusivo, al mismo precio que 2 tinas de 2 horas. Traen su comida y "
    "bebida, sin descorche."
)
CLUSTER = BlogCluster.TINAS
CTA_TEXT = "Reserva tu tina grupal"
CTA_URL = "/tinas/"

INTRO = (
    "Si están armando una despedida de soltera, un after office, una "
    'junta de amigas o un cumpleaños y pensaron en "una tina caliente" '
    "como plan, esto es para ustedes: Aremko tiene tinas pensadas "
    "específicamente para grupos de 4 a 6 personas, con 4 horas de uso "
    "exclusivo — al mismo precio que pagarían por 2 tinas normales de 2 "
    "horas cada una. Mismo dinero, el doble de tiempo. Y no, no van a "
    "tener que esconder la botella de espumante que trajeron: acá no se "
    "cobra descorche."
)

BODY_MD = """\
## Las dos opciones

- **Tina Calbuco** — 4 personas, 4 horas de uso exclusivo, $100.000
- **Tina Osorno** — 5-6 personas, 4 horas de uso exclusivo, $125.000

Ambas junto al río, en el bosque nativo, con uso completamente privado —
nadie más comparte la tina con ustedes durante esas 4 horas.

## Por qué el precio rinde el doble

Una tina normal de 2 personas cuesta $50.000-60.000 por 2 horas. Si un
grupo de 4 reservara dos de esas, pagaría entre $100.000 y $120.000 — por
solo 2 horas. La Tina Calbuco cuesta $100.000 y dura 4 horas. Mismo
presupuesto, el doble de tiempo compartido.

## Traigan lo que quieran

Comida y bebida propias, sin cobro adicional. Nada de pagar descorche por
abrir su propia botella — al contrario, Aremko presta las copas y una
cubetera con hielo, sin costo. Ustedes ponen el espumante, la comida para
picar o la torta; nosotros ponemos el resto.

## Para qué ocasión funciona

Cumpleaños, after office, junta de amigas, despedida de soltera, dos
parejas que salen juntas, padres con hijos grandes — cualquier grupo de 4
a 6 que quiera compartir algo distinto a una mesa de restaurante.

## Horarios y cómo reservar

Dos horarios disponibles: 14:30 o 19:30. Se reserva igual que cualquier
tina, indicando el grupo y la cantidad de personas.
"""

FAQ_ITEMS = [
    {
        "question": "¿Cuánto cuesta la tina para grupos en Aremko?",
        "answer": (
            "Tina Calbuco (4 personas): $100.000. Tina Osorno (5-6 "
            "personas): $125.000. Ambas con 4 horas de uso exclusivo."
        ),
    },
    {
        "question": "¿Podemos traer nuestra propia comida y bebida?",
        "answer": (
            "Sí, sin cobro adicional. Aremko presta copas y cubetera con "
            "hielo, y no cobra descorche."
        ),
    },
    {
        "question": "¿Qué horarios hay disponibles para la tina grupal?",
        "answer": "14:30 o 19:30.",
    },
]


def build_faq_schema_json() -> str:
    return json.dumps(
        {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": item["question"],
                    "acceptedAnswer": {"@type": "Answer", "text": item["answer"]},
                }
                for item in FAQ_ITEMS
            ],
        },
        ensure_ascii=False,
        indent=2,
    )


class Command(BaseCommand):
    help = (
        "Seed del post Aremko 'Tina para grupos en Puerto Varas'. "
        "Idempotente: update_or_create por slug. Por defecto crea borrador; "
        "usa --publish para publicar al instante."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--publish",
            action="store_true",
            help="Si está, marca is_published=True y published_at=now().",
        )

    def handle(self, *args, **options):
        publish = options.get("publish", False)

        defaults = {
            "title": TITLE,
            "meta_description": META_DESCRIPTION,
            "keyword_root": KEYWORD_ROOT,
            "cluster": CLUSTER,
            "intro": INTRO,
            "body_md": BODY_MD,
            "cta_text": CTA_TEXT,
            "cta_url": CTA_URL,
            "faq_schema_json": build_faq_schema_json(),
        }

        if publish:
            defaults["is_published"] = True
            defaults["published_at"] = timezone.now()

        post, created = BlogPost.objects.update_or_create(slug=SLUG, defaults=defaults)

        action = "creado" if created else "actualizado"
        status = "publicado" if publish else "borrador"
        self.stdout.write(
            self.style.SUCCESS(
                f"Post {action} ({status}): {post.title}\n"
                f"  Slug: {post.slug}\n"
                f"  Cluster: {post.cluster}\n"
                f"  Keyword: {post.keyword_root}\n"
                f"  CTA: {post.cta_text} → {post.cta_url}"
            )
        )
