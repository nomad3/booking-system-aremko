"""Seed del blog Aremko: "Refugio Aremko".

Mismo patrón que los seeds anteriores. Idempotente: update_or_create por
slug. Por defecto queda como BORRADOR (is_published=False). Contenido
redactado en sesión interactiva 2026-07-08, grounded en el copy real de
/refugio/ (no inventa precios ni datos).

OJO: la landing real de /refugio/ dice "15 minutos en auto desde el centro
de Puerto Varas" — Jorge confirmó 2026-07-08 que el dato correcto es 20
minutos (mismo usado en el resto del sitio). Este post usa 20. La landing
tiene un ticket aparte para corregirse (task_51d4d0c7).

Target SEO:
- Keyword root: "refugio aremko puerto varas"
- Cluster: RIO

Uso:
    python manage.py seed_blog_post_refugio_aremko            # borrador
    python manage.py seed_blog_post_refugio_aremko --publish  # publicado
"""
from __future__ import annotations

import json

from django.core.management.base import BaseCommand
from django.utils import timezone

from aremko_blog.models import BlogCluster, BlogPost


SLUG = "refugio-aremko-puerto-varas"
TITLE = "Refugio Aremko: dos noches en cabaña, con la segunda de regalo"
KEYWORD_ROOT = "refugio aremko puerto varas"
META_DESCRIPTION = (
    "Refugio Aremko: 2 noches en cabaña junto al Río Pescado, la 2ª de "
    "regalo. Masaje en pareja y tinas calientes ambas tardes. $290.000 "
    "para dos, garantía 38°C."
)
CLUSTER = BlogCluster.RIO
CTA_TEXT = "Reserva tu Refugio"
CTA_URL = "/refugio/"

INTRO = (
    'Si buscas "Refugio Aremko" esto es lo que ofrecemos: dos noches en la '
    "misma cabaña — la segunda es cortesía nuestra, no un descuento con "
    "letra chica escondido en un asterisco — con un masaje en pareja y dos "
    'tardes de tina caliente con vista al bosque. Decimos que "dos días '
    'acá equivalen a una semana" y no es una frase de folleto: la '
    "respaldamos con una garantía poco común, y poco cómoda para nosotros: "
    "si tu tina no llega a 38°C, es gratis. $290.000 por los dos, "
    "experiencia completa, sin sorpresas al llegar."
)

BODY_MD = """\
## Qué incluye

- 2 noches en cabaña privada para 2 personas
- Desayuno ambos días (el de la segunda mañana sabe mejor, es matemática
  del descanso acumulado)
- 1 masaje en pareja (sesión simultánea, nadie espera turno)
- 2 tardes de tinas calientes con vista al bosque
- La 2ª noche, cortesía Aremko — sí, gratis de verdad, no "50% en tu
  próxima visita"

## La garantía Aremko

Si tu tina no llega a 38°C, es gratis. No es un eslogan — es la condición
real de la reserva, y la razón por la que revisamos el termómetro más de lo
que revisamos el teléfono.

## Cuándo y cómo funciona

Válido cualquier día durante el lanzamiento (15-jun al 15-jul-2026); desde
el 16-jul, solo domingo a jueves. Check-in día 1, check-out día 3.
Cancelación gratis hasta 48h antes. A 20 minutos en auto del centro de
Puerto Varas — ni tan cerca que sea una excursión de tarde, ni tan lejos
que necesiten planificarlo como si fuera Chiloé.

## Lo que dicen quienes ya vinieron

4,5★ con 669 reseñas en Google, 4,4 en Tripadvisor (N°1 de Puerto Varas).
No lo escribimos nosotros, lo escribieron ellos.

## Precio y reserva

$290.000 por 2 personas, experiencia completa. Se reserva por WhatsApp o
formulario en la web — el que les acomode más.
"""

FAQ_ITEMS = [
    {
        "question": "¿Cuánto cuesta el Refugio Aremko?",
        "answer": (
            "$290.000 por 2 personas, experiencia completa: 2 noches en "
            "cabaña (la segunda de regalo), desayuno ambos días, 1 masaje "
            "en pareja y 2 tardes de tina caliente."
        ),
    },
    {
        "question": "¿Qué garantía tiene la tina del Refugio?",
        "answer": "Si la tina no llega a 38°C, el servicio es gratis.",
    },
    {
        "question": "¿Hasta cuándo está vigente el precio de lanzamiento?",
        "answer": (
            "El Refugio es válido cualquier día hasta el 15 de julio de "
            "2026. Desde el 16 de julio en adelante, solo domingo a jueves."
        ),
    },
    {
        "question": "¿Cuál es la política de cancelación del Refugio?",
        "answer": "Cancelación sin costo hasta 48 horas antes del check-in.",
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
        "Seed del post Aremko 'Refugio Aremko'. Idempotente: "
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
