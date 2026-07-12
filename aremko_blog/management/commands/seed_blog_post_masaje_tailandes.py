"""Seed del blog Aremko: "Masaje Tailandés en Puerto Varas".

Mismo patrón que los seeds anteriores. Idempotente: update_or_create por
slug. Por defecto queda como BORRADOR (is_published=False). Contenido
redactado en sesión interactiva 2026-07-08, grounded en el catálogo real
(Tailandés: $40.000, 50 min, sin reserva web directa, confirmado vía
screenshot del admin) + descripción factual general de la técnica.

Target SEO:
- Keyword root: "masaje tailandés puerto varas"
- Cluster: MASAJES

Uso:
    python manage.py seed_blog_post_masaje_tailandes            # borrador
    python manage.py seed_blog_post_masaje_tailandes --publish  # publicado
"""
from __future__ import annotations

import json

from django.core.management.base import BaseCommand
from django.utils import timezone

from aremko_blog.models import BlogCluster, BlogPost


SLUG = "masaje-tailandes-puerto-varas"
TITLE = "Masaje Tailandés en Puerto Varas: la técnica que estira antes de relajar"
KEYWORD_ROOT = "masaje tailandés puerto varas"
META_DESCRIPTION = (
    "Masaje Tailandés en Puerto Varas: presión y estiramiento asistido, "
    "con ropa cómoda puesta. Qué esperar de tu sesión, $40.000, 50 "
    "minutos."
)
CLUSTER = BlogCluster.MASAJES
CTA_TEXT = "Reserva tu masaje Tailandés"
CTA_URL = "/masajes/"

INTRO = (
    'El masaje Tailandés es el que más se confunde con "un masaje '
    'cualquiera pero de Tailandia" — y sí, es de esa tradición, pero la '
    "diferencia real no es el origen, es la mecánica: acá el terapeuta los "
    "estira a ustedes, no solo les soba la espalda. Es una mezcla de "
    "presión con los dedos, palmas y a veces codos, combinada con "
    "estiramientos asistidos — como si el yoga y el masaje hubieran tenido "
    "un hijo eficiente. Con ropa cómoda puesta, sin aceite, y con bastante "
    "más movimiento del que esperan de un masaje."
)

BODY_MD = """\
## Qué es y cómo se siente

Combina presión (dedos, palmas, a veces antebrazos) con **estiramientos
asistidos** — el terapeuta mueve las articulaciones y extiende los músculos
por ustedes, en ángulos que probablemente no logran solos. Se hace con ropa
cómoda puesta, sin aceite. La sensación es más activa que un masaje de
relajación: hay tramos de presión firme y tramos de estiramiento que se
sienten casi como una clase de movilidad, pero sin que ustedes tengan que
hacer nada.

## Por qué "estira antes de relajar"

El objetivo no es solo aflojar músculo, es **liberar rango de movimiento**
primero. La relajación llega después, como consecuencia, no como punto de
partida. Si salen de un masaje de relajación sintiendo que faltó algo de
movimiento, este es probablemente el que estaban buscando sin saberlo.

## Qué ropa llevar

Ropa cómoda y flexible — nada ajustado, nada que restrinja el movimiento
cuando el terapeuta les estire una pierna hacia el techo. Piensen ropa de
yoga, no ropa de oficina.

## Precio, duración y cómo reservar

$40.000, 50 minutos. Es uno de los masajes nuevos del catálogo — se
coordina por WhatsApp.
"""

FAQ_ITEMS = [
    {
        "question": "¿Qué es el masaje Tailandés?",
        "answer": (
            "Una técnica que combina presión con estiramientos asistidos, "
            "hecha con ropa cómoda puesta, sin aceite."
        ),
    },
    {
        "question": "¿Qué ropa debo llevar para un masaje Tailandés?",
        "answer": (
            "Ropa cómoda y flexible tipo yoga, ya que incluye "
            "estiramientos activos."
        ),
    },
    {
        "question": "¿Cuánto cuesta el masaje Tailandés?",
        "answer": "$40.000, 50 minutos.",
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
        "Seed del post Aremko 'Masaje Tailandés en Puerto Varas'. "
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
