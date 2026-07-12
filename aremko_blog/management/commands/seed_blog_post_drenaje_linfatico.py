"""Seed del blog Aremko: "Drenaje Linfático en Puerto Varas".

Mismo patrón que los seeds anteriores. Idempotente: update_or_create por
slug. Por defecto queda como BORRADOR (is_published=False). Contenido
redactado en sesión interactiva 2026-07-08, grounded en el catálogo real
(Drenaje Linfático: $45.000, 50 min, sin reserva web directa, confirmado
vía screenshot del admin) + descripción factual general de la técnica.

⚠️ Sin afirmaciones médicas específicas — el post remite a consulta médica
para condiciones de salud puntuales, no promete resultados terapéuticos.

Target SEO:
- Keyword root: "drenaje linfático puerto varas"
- Cluster: MASAJES

Uso:
    python manage.py seed_blog_post_drenaje_linfatico            # borrador
    python manage.py seed_blog_post_drenaje_linfatico --publish  # publicado
"""
from __future__ import annotations

import json

from django.core.management.base import BaseCommand
from django.utils import timezone

from aremko_blog.models import BlogCluster, BlogPost


SLUG = "drenaje-linfatico-puerto-varas"
TITLE = "Drenaje Linfático en Puerto Varas: para qué sirve (y cuándo no es lo que necesitas)"
KEYWORD_ROOT = "drenaje linfático puerto varas"
META_DESCRIPTION = (
    "Drenaje Linfático en Puerto Varas: masaje suave y rítmico para "
    "estimular circulación, distinto a un masaje relajante. Cuándo sirve, "
    "$45.000, 50 min."
)
CLUSTER = BlogCluster.MASAJES
CTA_TEXT = "Consulta por tu masaje"
CTA_URL = "/masajes/"

INTRO = (
    "El Drenaje Linfático es el masaje que la gente pide por el nombre sin "
    "saber bien qué es, y después se sorprende porque no se parece en nada "
    'a lo que esperaban. No es fuerte, no es profundo, y si llegan '
    'pidiendo "que me suelten bien la espalda" probablemente se van a ir '
    "un poco decepcionados — porque no es ese el objetivo. Es una técnica "
    "suave y rítmica, pensada para estimular la circulación linfática, no "
    "para destrozar nudos musculares. Sirve, y sirve bien, pero para otra "
    "cosa."
)

BODY_MD = """\
## Qué es en realidad

Movimientos suaves, rítmicos y superficiales — mucho más livianos que un
masaje descontracturante — diseñados para estimular el sistema linfático y
ayudar a movilizar líquido acumulado. No hay presión profunda, no hay
"trabajo de nudos". Si vienen esperando la intensidad de un masaje
deportivo, este no es ese masaje, y está bien, porque no compite con eso —
resuelve algo distinto.

## Para qué sirve realmente

Se usa típicamente para sensación de pesadez, hinchazón o retención de
líquido, y como parte de rutinas de recuperación. **No reemplaza una
consulta médica** — si tienen una condición de salud específica (problemas
circulatorios, cirugías recientes, tratamientos activos), coméntenlo al
reservar; el equipo puede orientarlos sobre si es lo indicado para su caso
o si conviene otra opción.

## Cuándo NO es lo que están buscando

Si lo que quieren es que les "suelten" la espalda o el cuello después de
una semana pesada de trabajo, pidan Relajación/Descontracturante o
Deportivo — el Drenaje Linfático no va a tocar esa tensión muscular, no es
su función.

## Precio, duración y cómo reservar

$45.000, 50 minutos. Se coordina por WhatsApp.
"""

FAQ_ITEMS = [
    {
        "question": "¿El Drenaje Linfático es igual a un masaje relajante?",
        "answer": (
            "No. Es más suave y superficial, enfocado en estimular la "
            "circulación linfática, no en soltar tensión muscular."
        ),
    },
    {
        "question": "¿El Drenaje Linfático sirve para dolor de espalda o contracturas?",
        "answer": (
            "No es su función — para eso conviene pedir "
            "Relajación/Descontracturante o Deportivo."
        ),
    },
    {
        "question": "¿Hay contraindicaciones para el Drenaje Linfático?",
        "answer": (
            "Si tienen una condición de salud específica, coméntenlo al "
            "reservar; no reemplaza una consulta médica."
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
        "Seed del post Aremko 'Drenaje Linfático en Puerto Varas'. "
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
