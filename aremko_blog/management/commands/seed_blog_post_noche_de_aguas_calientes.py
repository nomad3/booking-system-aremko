"""Seed del blog Aremko: "Noche de Aguas Calientes".

Mismo patrón que los seeds anteriores. Idempotente: update_or_create por
slug. Por defecto queda como BORRADOR (is_published=False). Contenido
redactado en sesión interactiva 2026-07-08, grounded en el copy real de
/noche-de-aguas-calientes/ (no inventa precios ni datos).

Target SEO:
- Keyword root: "noche de aguas calientes puerto varas"
- Cluster: RIO

Uso:
    python manage.py seed_blog_post_noche_de_aguas_calientes            # borrador
    python manage.py seed_blog_post_noche_de_aguas_calientes --publish  # publicado
"""
from __future__ import annotations

import json

from django.core.management.base import BaseCommand
from django.utils import timezone

from aremko_blog.models import BlogCluster, BlogPost


SLUG = "noche-de-aguas-calientes-puerto-varas"
TITLE = "Noche de Aguas Calientes: llega después del trabajo, sin itinerario"
KEYWORD_ROOT = "noche de aguas calientes puerto varas"
META_DESCRIPTION = (
    "Noche de Aguas Calientes: tina caliente + cabaña boutique con "
    "desayuno, en Puerto Varas. Llegan de tarde, sin armar itinerario. "
    "Desde $160.000 para dos."
)
CLUSTER = BlogCluster.RIO
CTA_TEXT = "Reserva tu noche por WhatsApp"
CTA_URL = "/noche-de-aguas-calientes/"

INTRO = (
    '"Noche de Aguas Calientes" no tiene truco en el nombre: es exactamente '
    "eso, sin metáforas escondidas. Llegan de tarde-noche, directo a una "
    "tina caliente junto al río, y duermen en una cabaña boutique con "
    "desayuno incluido. Al día siguiente deciden ustedes — algunos salen "
    "temprano a seguir el viaje, otros se quedan en la cama hasta que el "
    "hambre gane la discusión. Sin armar itinerario, sin pedir el día libre "
    "completo, sin cargar el auto para un fin de semana entero. Desde "
    "$160.000 para dos, según cabaña y tina disponibles."
)

BODY_MD = """\
## Qué incluye

- Tina caliente privada junto al río, la noche que llegan
- Cabaña boutique (check-in 16:00 · check-out 11:00)
- Desayuno incluido a la mañana siguiente, para cuando por fin decidan
  levantarse

## Por qué esta noche y no otra cosa

No necesitan armar un itinerario ni pedir el día completo libre — esto no
es una expedición, es una noche. No es cargar el auto para un fin de semana
entero con tres mudas de ropa "por si acaso". Llegan cuando salen del
trabajo, se meten a la tina, duermen bien — y al día siguiente deciden si
arrancan temprano o se quedan hasta tarde, sin que nadie los apure con el
check-out.

## El bonus incluido

El Reseteo: tina fría Yates, de uso libre, antes o después de la tina
caliente. Nadie lo pide la primera vez, casi todos vuelven por él la
segunda.

## Precio y reserva

Desde $160.000 para dos, según cabaña y tina disponibles — te cotizan exacto
por WhatsApp, sin vueltas.
"""

FAQ_ITEMS = [
    {
        "question": "¿Cuánto cuesta la Noche de Aguas Calientes?",
        "answer": (
            "Desde $160.000 para dos, según cabaña y tina disponibles. Se "
            "cotiza el valor exacto por WhatsApp."
        ),
    },
    {
        "question": "¿La Noche de Aguas Calientes incluye masaje?",
        "answer": (
            "No. Incluye tina caliente privada, cabaña boutique y "
            "desayuno — sin masaje. Para masaje + tina el mismo día, ver "
            "Pausa junto al Río."
        ),
    },
    {
        "question": "¿Cuáles son los horarios de check-in y check-out?",
        "answer": "Check-in a las 16:00 y check-out a las 11:00.",
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
        "Seed del post Aremko 'Noche de Aguas Calientes'. Idempotente: "
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
