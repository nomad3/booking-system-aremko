"""Seed del blog Aremko: "Masajes cerca de Puerto Montt".

Mismo patrón que los seeds anteriores. Idempotente: update_or_create por
slug. Por defecto queda como BORRADOR (is_published=False). Contenido
redactado en sesión interactiva 2026-07-08, grounded en el catálogo real de
masajes. Distancia desde Puerto Montt (≈1 hora en auto) confirmada por
Jorge — no inventada.

Target SEO:
- Keyword root: "masajes puerto montt" (cluster de keywords ~1.000
  búsquedas/mes vía DataForSEO, hoy en posición 20-32, sin contenido
  dedicado)
- Cluster: MASAJES

Uso:
    python manage.py seed_blog_post_masajes_puerto_montt            # borrador
    python manage.py seed_blog_post_masajes_puerto_montt --publish  # publicado
"""
from __future__ import annotations

import json

from django.core.management.base import BaseCommand
from django.utils import timezone

from aremko_blog.models import BlogCluster, BlogPost


SLUG = "masajes-cerca-de-puerto-montt"
TITLE = "Masajes cerca de Puerto Montt: por qué cruzar hasta Puerto Varas vale la pena"
KEYWORD_ROOT = "masajes puerto montt"
META_DESCRIPTION = (
    "¿Buscas masajes cerca de Puerto Montt? A una hora está Aremko: 6 "
    "tipos de masaje junto al río Pescado en Puerto Varas, con tina "
    "caliente opcional después."
)
CLUSTER = BlogCluster.MASAJES
CTA_TEXT = "Reserva tu masaje"
CTA_URL = "/masajes/"

INTRO = (
    'Si buscas "masajes cerca de Puerto Montt" probablemente ya viste una '
    "lista de salones dentro de la ciudad — algunos buenos, la mayoría en "
    "un local comercial con el ruido de la calle de fondo. Hay otra "
    "opción, a una hora de camino, que cambia completamente la ecuación: "
    "en vez de un masaje entre dos trámites, uno junto al río Pescado, en "
    "un domo de madera nativa, con la opción de quedarse después en una "
    "tina caliente. Una hora suena a mucho para un masaje de 50 minutos —"
    " y lo sería, si fuera solo eso."
)

BODY_MD = """\
## Por qué vale la hora completa

Seamos honestos: una hora de auto por 50 minutos de masaje, solo por el
masaje, no cierra la cuenta. Un salón dentro de Puerto Montt te resuelve lo
mismo sin moverte del radio urbano. La hora empieza a valer la pena cuando
el plan no es "un masaje", es "salir de la ciudad, cruzar hasta el río, y
no volver corriendo apenas terminen" — ahí la hora deja de ser un costo y
pasa a ser parte de la desconexión.

## Lo que se llevan además del masaje

- Domos de madera nativa metidos en el bosque, no una sala con aroma
  artificial de eucalipto en spray
- El río Pescado sonando de fondo, sin parlante ni playlist
- La opción de quedarse después en tina caliente (ver Pausa junto al Río,
  si quieren hacer tarde completa)

## Los 6 tipos de masaje disponibles

Relajación o Descontracturante ($40.000), Deportivo ($45.000), Piedras
Calientes ($45.000), Drenaje Linfático ($45.000), Tailandés ($40.000,
nuevo) y Tui-Na ($45.000, nuevo). Todos de 50 minutos. El de Relajación o
Descontracturante se reserva directo online; los demás, por WhatsApp.

## Cómo armar el viaje para que valga la hora

Si van a cruzar desde Puerto Montt, no vengan solo por el masaje — arruinen
la excusa de "no tengo tiempo" combinándolo con la Pausa junto al Río
(masaje + tina en la misma tarde). Así la hora de ida rinde por los dos
lados: llegan, se relajan en serio, y no sienten que manejaron una hora
para 50 minutos nada más.
"""

FAQ_ITEMS = [
    {
        "question": "¿Cuánto se demora en llegar a Aremko desde Puerto Montt?",
        "answer": "Aproximadamente una hora en auto.",
    },
    {
        "question": "¿Qué masaje pedir si vengo desde Puerto Montt por primera vez?",
        "answer": (
            "Relajación o Descontracturante — el más amable y el único "
            "con reserva web directa."
        ),
    },
    {
        "question": "¿Puedo combinar el masaje con una tina caliente?",
        "answer": (
            "Sí — ver Pausa junto al Río, tina + masaje en pareja en la "
            "misma tarde."
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
        "Seed del post Aremko 'Masajes cerca de Puerto Montt'. Idempotente: "
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
