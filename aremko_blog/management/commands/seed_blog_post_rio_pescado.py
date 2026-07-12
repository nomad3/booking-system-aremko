"""Seed del blog Aremko: "El Río Pescado en Aremko".

Mismo patrón que los seeds anteriores. Idempotente: update_or_create por
slug. Por defecto queda como BORRADOR (is_published=False). Contenido
evergreen, redactado en sesión interactiva 2026-07-12, grounded en detalles
ya confirmados en otros posts/landings (sonido del río, Mirador del Río
Pescado, Ruta 225 km19) — NO inventa historia de fundación de la empresa
(no hay datos confirmados de eso).

Target SEO:
- Keyword root: "río pescado puerto varas spa"
- Cluster: RIO

Uso:
    python manage.py seed_blog_post_rio_pescado            # borrador
    python manage.py seed_blog_post_rio_pescado --publish  # publicado
"""
from __future__ import annotations

import json

from django.core.management.base import BaseCommand
from django.utils import timezone

from aremko_blog.models import BlogCluster, BlogPost


SLUG = "rio-pescado-aremko-puerto-varas"
TITLE = "El Río Pescado en Aremko: por qué es el protagonista silencioso de cada experiencia"
KEYWORD_ROOT = "río pescado puerto varas spa"
META_DESCRIPTION = (
    "El río Pescado suena junto a las tinas, cabañas y domos de masaje en "
    "Aremko, sin parlantes ni loops. Por qué es el eje real de cada "
    "experiencia."
)
CLUSTER = BlogCluster.RIO
CTA_TEXT = "Conoce nuestros programas"
CTA_URL = "/tinas/"

INTRO = (
    'Todos los programas de Aremko dicen "junto al río Pescado" en algún '
    "lado, y es fácil leerlo como decoración de marketing. No lo es. El "
    "río corre a metros de las tinas, los domos de masaje y las cabañas —"
    " suena de fondo todo el rato, sin pausa, sin loop, sin que nadie "
    "tenga que prender un parlante con sonido de agua pregrabado (sí, eso "
    "existe en otros spas, y sí, es exactamente tan triste como suena). "
    "Este post es sobre por qué ese detalle importa más de lo que parece "
    "a primera vista."
)

BODY_MD = """\
## No es un parlante, es el río de verdad

El sonido constante del agua corriendo es ruido blanco natural — la
frecuencia ayuda a bajar el nivel de alerta mental, algo que ningún
parlante con loop de 4 minutos replica igual, por bien grabado que esté.

## El rincón que casi nadie explora

Al final de la red de pasarelas está el Mirador del Río Pescado — la mejor
vista de todo el spa, con los saltos de agua y la isla que se forma entre
las rocas. Una mesa para compartir sin apuro, café o espumante disponible.
Está en cada uno de nuestros programas y sigue siendo el rincón que más
huéspedes se pierden.

## Por qué está en todos los programas

Ritual del Río, Pausa junto al Río, Refugio y Noche de Aguas Calientes
comparten el mismo terreno junto al río — no es coincidencia de nombre, es
el eje real de la propuesta. Cambia lo que incluye cada uno, no cambia el
río.
"""

FAQ_ITEMS = [
    {
        "question": "¿Cómo se llega a Aremko?",
        "answer": (
            "Por la Ruta 225 hacia Ensenada. En el km 19 hay un desvío "
            "señalizado a Río Pescado; después son 4 km de camino rural "
            "hasta el recinto."
        ),
    },
    {
        "question": "¿Se escucha el río desde todas las cabañas y tinas?",
        "answer": (
            "Sí — el recinto está construido junto al río Pescado a "
            "propósito, y su sonido es parte del diseño de la "
            "experiencia en todos los programas."
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
        "Seed del post Aremko 'El Río Pescado en Aremko'. Idempotente: "
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
