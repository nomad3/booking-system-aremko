"""Seed del blog Aremko: "Masaje Tui-Na en Puerto Varas".

Mismo patrón que los seeds anteriores. Idempotente: update_or_create por
slug. Por defecto queda como BORRADOR (is_published=False). Contenido
redactado en sesión interactiva 2026-07-08, grounded en el catálogo real
(Tui-Na: $45.000, 50 min, sin reserva web directa, confirmado vía
screenshot del admin) + descripción factual general de la técnica Tui-Na
(medicina tradicional china) — sin afirmaciones médicas específicas sobre
el protocolo exacto de Aremko más allá de lo confirmado.

Target SEO:
- Keyword root: "masaje tui na puerto varas"
- Cluster: MASAJES

Uso:
    python manage.py seed_blog_post_masaje_tui_na            # borrador
    python manage.py seed_blog_post_masaje_tui_na --publish  # publicado
"""
from __future__ import annotations

import json

from django.core.management.base import BaseCommand
from django.utils import timezone

from aremko_blog.models import BlogCluster, BlogPost


SLUG = "masaje-tui-na-puerto-varas"
TITLE = "Masaje Tui-Na en Puerto Varas: qué es y qué esperar de tu primera sesión"
KEYWORD_ROOT = "masaje tui na puerto varas"
META_DESCRIPTION = (
    "Masaje Tui-Na en Puerto Varas: técnica china de presión en puntos "
    "específicos, con ropa liviana puesta. Qué esperar de tu primera "
    "sesión, $45.000, 50 minutos."
)
CLUSTER = BlogCluster.MASAJES
CTA_TEXT = "Reserva tu masaje Tui-Na"
CTA_URL = "/masajes/"

INTRO = (
    'Si están leyendo esto es porque vieron "Tui-Na" en la lista de '
    "masajes y pensaron lo mismo que casi todos: ¿eso qué es? Es justo. No "
    'es el masaje típico que imaginan cuando dicen "spa" — nada de aceite, '
    "nada de música de ballenas, nada de que se queden inmóviles boca "
    "abajo 50 minutos. El Tui-Na es una técnica de la medicina tradicional "
    "china, con ropa liviana puesta, presión sobre puntos específicos, y "
    "bastante más movimiento del que esperan. Es el masaje que menos gente "
    "pide la primera vez, y el que más vuelve a pedir la segunda."
)

BODY_MD = """\
## Qué es realmente el Tui-Na

Tui-Na viene de la medicina tradicional china: combina presión con las
manos, amasado, y estiramientos aplicados sobre puntos y líneas específicas
del cuerpo (lo que esa tradición llama meridianos). Se hace con **ropa
liviana puesta**, no con aceite sobre piel desnuda — así que si vienen
pensando en el clásico masaje de aceite, ajusten la expectativa, es otra
cosa.

## Qué se siente (y por qué no es "relajante" en el sentido clásico)

Es más intenso y más activo que un descontracturante clásico. No es
doloroso, pero tampoco es el tipo de masaje en el que se duermen a los 5
minutos — hay presión dirigida, hay movimiento, y la sensación durante la
sesión es más de "trabajo específico" que de "flotar en una nube". El
resultado sí es relajante, el proceso es distinto.

## Para quién funciona mejor

Tensión puntual en cuello, hombros o espalda — el tipo de molestia que un
masaje relajante toca por encima pero no resuelve del todo. Si nunca se han
hecho uno, avísenle al terapeuta al llegar; ajustan la intensidad según
cómo respondan.

## Precio, duración y cómo reservar

$45.000, 50 minutos. Es uno de los masajes nuevos del catálogo, así que se
coordina por WhatsApp (no tiene reserva web directa todavía) — el equipo
confirma disponibilidad del terapeuta específico para esta técnica.
"""

FAQ_ITEMS = [
    {
        "question": "¿Qué es el masaje Tui-Na?",
        "answer": (
            "Una técnica de la medicina tradicional china con presión, "
            "amasado y estiramientos sobre puntos específicos del cuerpo, "
            "hecha con ropa liviana puesta (sin aceite)."
        ),
    },
    {
        "question": "¿El Tui-Na duele?",
        "answer": (
            "No debería doler, pero es más intenso y activo que un masaje "
            "relajante clásico — es normal sentir más presión dirigida."
        ),
    },
    {
        "question": "¿Cómo se reserva el masaje Tui-Na?",
        "answer": (
            "Por WhatsApp, ya que depende de la disponibilidad del "
            "terapeuta específico para esta técnica."
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
        "Seed del post Aremko 'Masaje Tui-Na en Puerto Varas'. Idempotente: "
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
