"""Seed del blog Aremko: "Aremko en invierno".

Mismo patrón que los seeds anteriores. Idempotente: update_or_create por
slug. Por defecto queda como BORRADOR (is_published=False). Contenido
evergreen, redactado en sesión interactiva 2026-07-12. El ángulo
"invierno/lluvia mejora la experiencia" YA es mensaje de marca existente
(confirmado en el seed de escapada-romántica, sección tinas: "el mejor
escenario para usarlas es invierno con lluvia... la gente que viene en
julio agradece más que la que viene en enero") — no es un dato nuevo
inventado, es consistente con contenido ya publicado.

Target SEO:
- Keyword root: "spa puerto varas invierno"
- Cluster: SPA

Uso:
    python manage.py seed_blog_post_aremko_invierno            # borrador
    python manage.py seed_blog_post_aremko_invierno --publish  # publicado
"""
from __future__ import annotations

import json

from django.core.management.base import BaseCommand
from django.utils import timezone

from aremko_blog.models import BlogCluster, BlogPost


SLUG = "aremko-invierno-puerto-varas"
TITLE = "Aremko en invierno: por qué julio es mejor que enero para venir"
KEYWORD_ROOT = "spa puerto varas invierno"
META_DESCRIPTION = (
    "Spa en Puerto Varas en invierno: por qué la lluvia y el frío hacen "
    "mejor la experiencia de tina caliente en Aremko. Tinas con techo "
    "total."
)
CLUSTER = BlogCluster.SPA
CTA_TEXT = "Reserva tu tina de invierno"
CTA_URL = "/tinas/"

INTRO = (
    "Las tinas de Aremko tienen techo total, así que el mejor escenario "
    "para usarlas es invierno con lluvia — sí, contraintuitivo, pero el "
    "contraste entre agua caliente, aire frío y lluvia cayendo sobre el "
    "techo es el momento peak de la experiencia. La gente que viene en "
    "julio lo agradece más que la que viene en enero."
)

BODY_MD = """\
## Por qué el invierno gana

En verano, agua caliente es agradable. En invierno, con 4 grados afuera, es
otra categoría de experiencia — el contraste es el punto.

## La lluvia no cancela nada

Las tinas tienen techo total. Lluvia afuera + agua caliente adentro es
exactamente el escenario que están pagando, no un imprevisto que arruina
el plan.

## Menos gente, mismo servicio

Fuera de temporada alta hay más disponibilidad de fechas — para quienes
pueden elegir cuándo venir, es la ventana con menos competencia por cupos.
"""

FAQ_ITEMS = [
    {
        "question": "¿Se puede usar la tina caliente si llueve?",
        "answer": (
            "Sí, sin problema — las tinas tienen techo total. La "
            "combinación de lluvia afuera y agua caliente adentro es "
            "parte de la experiencia, no un imprevisto."
        ),
    },
    {
        "question": "¿Cuál es la mejor época para venir a Aremko?",
        "answer": (
            "El invierno, con temperaturas bajas, hace que el contraste "
            "con el agua caliente sea más notorio — muchos huéspedes lo "
            "prefieren sobre el verano."
        ),
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
        "Seed del post Aremko 'Aremko en invierno'. Idempotente: "
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
