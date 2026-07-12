"""Seed del blog Aremko: "Pausa junto al Río".

Mismo patrón que los seeds anteriores. Idempotente: update_or_create por
slug. Por defecto queda como BORRADOR (is_published=False). Contenido
redactado en sesión interactiva 2026-07-08, grounded en el copy real de
/pausa-junto-al-rio/ (no inventa precios ni datos).

Target SEO:
- Keyword root: "pausa junto al río puerto varas"
- Cluster: RIO

Uso:
    python manage.py seed_blog_post_pausa_junto_al_rio            # borrador
    python manage.py seed_blog_post_pausa_junto_al_rio --publish  # publicado
"""
from __future__ import annotations

import json

from django.core.management.base import BaseCommand
from django.utils import timezone

from aremko_blog.models import BlogCluster, BlogPost


SLUG = "pausa-junto-al-rio-puerto-varas"
TITLE = "Pausa junto al Río: tina y masaje en pareja en una sola tarde"
KEYWORD_ROOT = "pausa junto al río puerto varas"
META_DESCRIPTION = (
    "Pausa junto al Río: tina caliente privada + masaje en pareja, una "
    "tarde junto al Río Pescado en Puerto Varas. Desde $110.000 para dos, "
    "sin dormir afuera."
)
CLUSTER = BlogCluster.RIO
CTA_TEXT = "Reserva tu Pausa por WhatsApp"
CTA_URL = "/pausa-junto-al-rio/"

INTRO = (
    'Si googleaste "pausa junto al río Puerto Varas" es porque no tienes un '
    "fin de semana libre, pero sí una tarde. Buena noticia: no necesitas "
    "más que eso. La Pausa es tina caliente privada + masaje en pareja, los "
    "dos en una sola tarde, con el Río Pescado sonando de fondo — y se van "
    "a dormir a su propia cama, no a la nuestra. Desde $110.000 para dos, "
    "domingo a jueves. Si el plan es cortar la semana sin cargar el auto "
    "para dos días, esto es exactamente eso."
)

BODY_MD = """\
## Qué incluye, sin letra chica

- Tina caliente privada junto al río
- Masaje en pareja (relajación o descontracturante — eligen ustedes)
- El sonido del Río Pescado y el bosque nativo, de fondo todo el rato

## El bonus que va incluido

El Reseteo: un chapuzón en Yates (nuestra tina fría, de uso libre) antes o
después de la tina caliente. El contraste no se olvida.

## El rincón que casi nadie conoce

Al final de la pasarela está el Mirador del Río Pescado — mesa con vista a
los saltos de agua, café o espumante para acompañar.

## Por qué no es lo mismo que una piscina temperada o unas termas llenas

No es una piscina temperada. No son las termas llenas de gente. Es medio día
de spa real: agua caliente privada + manos expertas, junto al río, todo
listo cuando llegan.

## Precio y cómo reservar

$110.000 domingo a jueves, $130.000 viernes y sábado, para 2 personas. Se
reserva por WhatsApp.
"""

FAQ_ITEMS = [
    {
        "question": "¿Cuánto cuesta la Pausa junto al Río?",
        "answer": (
            "$110.000 domingo a jueves y $130.000 viernes y sábado, para 2 "
            "personas. Incluye tina caliente privada y masaje en pareja."
        ),
    },
    {
        "question": "¿Hay que quedarse a dormir?",
        "answer": (
            "No. La Pausa junto al Río es una experiencia de una sola "
            "tarde — tina y masaje, sin alojamiento."
        ),
    },
    {
        "question": "¿Cómo se reserva la Pausa junto al Río?",
        "answer": "Por WhatsApp, coordinando fecha y hora directo con el equipo de Aremko.",
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
        "Seed del post Aremko 'Pausa junto al Río'. Idempotente: "
        "update_or_create por slug. Por defecto crea borrador; usa --publish "
        "para publicar al instante."
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
