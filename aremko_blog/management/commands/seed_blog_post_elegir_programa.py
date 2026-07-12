"""Seed del blog Aremko: "Un día (o dos) en Aremko: cómo elegir el programa".

Mismo patrón que los seeds anteriores. Idempotente: update_or_create por
slug. Por defecto queda como BORRADOR (is_published=False). Post-índice
evergreen que organiza los 4 programas (Grupo A) según tiempo disponible —
no agrega datos nuevos, solo reorganiza los ya confirmados de cada landing.

Target SEO:
- Keyword root: "programas aremko puerto varas"
- Cluster: BOUTIQUE (antes vacío)

Uso:
    python manage.py seed_blog_post_elegir_programa            # borrador
    python manage.py seed_blog_post_elegir_programa --publish  # publicado
"""
from __future__ import annotations

import json

from django.core.management.base import BaseCommand
from django.utils import timezone

from aremko_blog.models import BlogCluster, BlogPost


SLUG = "elegir-programa-aremko-segun-tiempo"
TITLE = "Un día (o dos) en Aremko: cómo elegir el programa según el tiempo que tengas"
KEYWORD_ROOT = "programas aremko puerto varas"
META_DESCRIPTION = (
    "Pausa, Noche de Aguas Calientes, Ritual del Río o Refugio: guía para "
    "elegir tu programa en Aremko según cuánto tiempo tengas, desde "
    "$110.000."
)
CLUSTER = BlogCluster.BOUTIQUE
CTA_TEXT = "Elige tu programa"
CTA_URL = "/tinas/"

INTRO = (
    "Aremko tiene 4 programas y la pregunta que más nos hacen no es "
    '"cuál es mejor" — es "cuál me alcanza el tiempo para hacer". Esta es '
    "la guía rápida, ordenada por cuánto tiempo tienen, no por cuál "
    "cuesta más."
)

BODY_MD = """\
## Si tienen una tarde: Pausa junto al Río

Tina + masaje en pareja, sin quedarse a dormir. Desde $110.000 para dos.

## Si tienen una noche: Noche de Aguas Calientes o Ritual del Río

Noche de Aguas Calientes (desde $160.000) es tina + cabaña, sin masaje —
para cuando llegan tarde y quieren simplicidad. Ritual del Río ($210.000 en
adelante) suma un masaje nocturno antes de la tina, con solo 5 parejas por
noche.

## Si tienen dos días: Refugio Aremko

Dos noches en la misma cabaña, la segunda de regalo, con masaje en pareja y
dos tardes de tina. $290.000 por dos personas, experiencia completa.

## La tabla resumen

| Tienen | Programa | Desde |
|---|---|---|
| Una tarde | Pausa junto al Río | $110.000 |
| Una noche, simple | Noche de Aguas Calientes | $160.000 |
| Una noche, completa | Ritual del Río | $210.000 |
| Dos días | Refugio Aremko | $290.000 |
"""

FAQ_ITEMS = [
    {
        "question": "¿Cuál programa de Aremko elegir si solo tengo una tarde?",
        "answer": (
            "Pausa junto al Río — tina caliente privada + masaje en "
            "pareja, sin quedarse a dormir. Desde $110.000 para dos."
        ),
    },
    {
        "question": "¿Cuál es el programa más completo de Aremko?",
        "answer": (
            "Refugio Aremko: 2 noches en cabaña (la segunda de regalo), "
            "masaje en pareja y 2 tardes de tina. $290.000 por 2 "
            "personas."
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
        "Seed del post Aremko 'Cómo elegir el programa según el tiempo'. "
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
