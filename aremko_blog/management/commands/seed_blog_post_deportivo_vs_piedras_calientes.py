"""Seed del blog Aremko: "Masaje Deportivo vs. Piedras Calientes".

Mismo patrón que los seeds anteriores. Idempotente: update_or_create por
slug. Por defecto queda como BORRADOR (is_published=False). Contenido
redactado en sesión interactiva 2026-07-08, grounded en el catálogo real
(ambos $45.000, 50 min, sin reserva web directa, confirmado vía screenshot
del admin).

Target SEO:
- Keyword root: "masaje deportivo puerto varas"
- Cluster: MASAJES

Uso:
    python manage.py seed_blog_post_deportivo_vs_piedras_calientes            # borrador
    python manage.py seed_blog_post_deportivo_vs_piedras_calientes --publish  # publicado
"""
from __future__ import annotations

import json

from django.core.management.base import BaseCommand
from django.utils import timezone

from aremko_blog.models import BlogCluster, BlogPost


SLUG = "masaje-deportivo-vs-piedras-calientes-puerto-varas"
TITLE = "Masaje Deportivo vs. Piedras Calientes: cuál elegir según lo que te duele"
KEYWORD_ROOT = "masaje deportivo puerto varas"
META_DESCRIPTION = (
    "Masaje Deportivo o Piedras Calientes en Puerto Varas: cuál elegir "
    "según si buscas presión profunda o calor relajante. Ambos $45.000, "
    "50 minutos."
)
CLUSTER = BlogCluster.MASAJES
CTA_TEXT = "Reserva tu masaje"
CTA_URL = "/masajes/"

INTRO = (
    'Estos dos se confunden porque los dos suenan "intensos" en el buen '
    "sentido, pero resuelven cosas distintas. El Deportivo es presión "
    "firme y directa a la musculatura cargada — el que piden quienes "
    "entrenan, cargan cosas pesadas, o pasaron el fin de semana con "
    "actividad física real. El de Piedras Calientes usa el calor de las "
    "piedras para que el músculo se relaje primero y la presión entre "
    "después con menos resistencia — el que piden quienes quieren la "
    'intensidad sin la sensación de "trabajo".'
)

BODY_MD = """\
## Masaje Deportivo: para cuando el problema es físico, no solo estrés

Presión firme, dirigida a grupos musculares específicos — piernas, espalda,
hombros — pensado para después de actividad física, no para después de una
reunión larga. Si el motivo de la tensión es que corrieron, entrenaron o
cargaron algo pesado, este es el que responde a eso directamente.

## Piedras Calientes: el calor hace el trabajo previo

Piedras calentadas a temperatura controlada, usadas para precalentar el
músculo antes (y durante) la presión manual. El calor relaja el tejido de
entrada, así que la misma intensidad de trabajo se siente más suave. Es el
clásico que suena a spa de revista — y acá sí cumple lo que promete.

## La comparación sin vueltas

| | Deportivo | Piedras Calientes |
|---|---|---|
| Intensidad | Firme, directa | Firme, pero suavizada por el calor |
| Mejor para | Recuperación física real | Relajación con intensidad |
| Sensación | "Trabajo" muscular | Calor + presión |

## Precio, duración y cómo reservar

Ambos $45.000, 50 minutos. Se coordinan por WhatsApp.
"""

FAQ_ITEMS = [
    {
        "question": "¿Cuál es más fuerte, el Deportivo o el de Piedras Calientes?",
        "answer": (
            "Ambos usan presión firme; la diferencia es que en Piedras "
            "Calientes el calor relaja el músculo antes, así que se "
            "siente menos intenso aunque el trabajo sea similar."
        ),
    },
    {
        "question": "¿Cuál elegir si vengo de entrenar o cargar algo pesado?",
        "answer": "Masaje Deportivo, está pensado directamente para eso.",
    },
    {
        "question": "¿Cuánto cuestan el Deportivo y el de Piedras Calientes?",
        "answer": "Ambos $45.000, 50 minutos.",
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
        "Seed del post Aremko 'Masaje Deportivo vs. Piedras Calientes'. "
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
