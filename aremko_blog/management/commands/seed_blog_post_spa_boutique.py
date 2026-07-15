"""Seed del blog Aremko: "Qué significa spa boutique en Aremko".

Mismo patrón que los seeds anteriores. Idempotente: update_or_create por
slug. Por defecto queda como BORRADOR (is_published=False). Contenido
evergreen de posicionamiento de marca, redactado en sesión interactiva
2026-07-12, grounded en hechos ya confirmados (capacidad limitada del
Ritual del Río, cabañas privadas, equipo titular).

Target SEO:
- Keyword root: "spa puerto varas" (head term — retargeteado en Ciclo 2 del
  loop SEO 2026-07-14; antes "spa boutique puerto varas"). Es keyword protegida
  estancada en pos 7; este post (con un H2 que lidera con la frase exacta) +
  enlaces internos buscan empujar la cabeza de búsqueda.
- Cluster: SPA (antes vacío)

Uso:
    python manage.py seed_blog_post_spa_boutique            # borrador
    python manage.py seed_blog_post_spa_boutique --publish  # publicado
"""
from __future__ import annotations

import json

from django.core.management.base import BaseCommand
from django.utils import timezone

from aremko_blog.models import BlogCluster, BlogPost


SLUG = "que-es-spa-boutique-aremko"
TITLE = 'Qué significa "spa boutique" en Aremko (y en qué se diferencia de un spa de hotel)'
KEYWORD_ROOT = "spa puerto varas"
META_DESCRIPTION = (
    "Spa en Puerto Varas: qué es un spa boutique y en qué se diferencia del "
    "spa de un hotel. Tinas junto al río, masajes y ritual privado en Aremko."
)
CLUSTER = BlogCluster.SPA
CTA_TEXT = "Conoce la experiencia Aremko"
CTA_URL = "/tinas/"

INTRO = (
    '"Spa boutique" es una de esas frases que todos usan y pocos '
    "explican. En un spa de hotel, el spa es un servicio adicional dentro "
    "de algo más grande — comparten pasillo con el gimnasio y la piscina "
    "de niños. En un spa boutique, el spa ES el negocio completo: "
    "capacidad limitada a propósito (el Ritual del Río recibe solo 5 "
    "parejas por noche), cabañas privadas en vez de habitaciones con "
    "pasillo común, y un equipo que hace una sola cosa en vez de rotar "
    "entre recepción, spa y room service."
)

BODY_MD = """\
## Spa en Puerto Varas: qué esperar

Si buscás un spa en Puerto Varas, lo que encontrás en Aremko no es un
circuito de piscinas con pulsera de colores. Es un spa boutique junto al río
Pescado: tinas de agua caliente a 38-39° al aire libre, masajes con un equipo
titular (no rotativo) y programas privados que combinan tina, masaje y
descanso. Abierto hasta medianoche, a 20 minutos del centro. Menos gente, más
río, y que la tarde sea de ustedes.

## Capacidad limitada, a propósito

No es falta de espacio, es la decisión: menos gente al mismo tiempo
significa privacidad real, no una promesa en el folleto.

## Privado, no compartido

Tinas privadas, no piscinas compartidas. Cabañas propias, no habitaciones
con vecino de pasillo. El "boutique" describe eso — la unidad de
experiencia es de ustedes, no de un grupo de desconocidos.

## Un equipo especializado

Sandra, Carolina, Diana y Paul hacen masajes, no check-in de hotel entre
sesión y sesión. La especialización es parte de por qué la calidad se
sostiene.
"""

FAQ_ITEMS = [
    {
        "question": "¿Qué diferencia a un spa boutique de un spa de hotel?",
        "answer": (
            "En un spa boutique el spa es el negocio completo, no un "
            "servicio adicional: capacidad limitada, espacios privados y "
            "equipo especializado exclusivo."
        ),
    },
    {
        "question": "¿Cuánta gente recibe Aremko a la vez?",
        "answer": (
            "Depende del programa — por ejemplo, el Ritual del Río "
            "recibe solo 5 parejas por noche, a propósito."
        ),
    },
    {
        "question": "¿Dónde hay un spa en Puerto Varas?",
        "answer": (
            "Aremko es un spa boutique en Puerto Varas, junto al río "
            "Pescado, a 20 minutos del centro: tinas de agua caliente a "
            "38-39°, masajes con equipo titular y programas privados, "
            "abierto hasta medianoche."
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
        "Seed del post Aremko 'Qué significa spa boutique en Aremko'. "
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
