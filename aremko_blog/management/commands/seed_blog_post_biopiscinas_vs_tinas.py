"""Seed del blog Aremko: "Biopiscinas vs. tinas calientes en Puerto Varas".

Mismo patrón que los seeds anteriores. Idempotente: update_or_create por
slug. Por defecto queda como BORRADOR (is_published=False). Post comparativo
honesto (mismo formato que el post de termas): aclara desde la primera
línea que Aremko NO tiene biopiscinas, para no generar una expectativa
falsa — vende con honestidad, no con ambigüedad de keyword.

Target SEO:
- Keyword root: "biopiscinas puerto varas" — investigación de competencia
  2026-07-08 detectó que cancagua.cl rankea #5 en "biopiscinas" (480
  búsquedas/mes) y #5 en "piscinas termales" (210/mes), términos genéricos
  sin geo donde Aremko no tenía presencia.
- Cluster: TINAS

⚠️ OJO al editar: no describir las tinas de Aremko como "biopiscinas" en
ningún lado — son productos técnicamente distintos (filtración biológica
vs aerotermia+solar). Ver docs/LOOP_SEO.md, hallazgo Cancagua 2026-07-08.

Uso:
    python manage.py seed_blog_post_biopiscinas_vs_tinas            # borrador
    python manage.py seed_blog_post_biopiscinas_vs_tinas --publish  # publicado
"""
from __future__ import annotations

import json

from django.core.management.base import BaseCommand
from django.utils import timezone

from aremko_blog.models import BlogCluster, BlogPost


SLUG = "biopiscinas-vs-tinas-calientes-puerto-varas"
TITLE = "Biopiscinas vs. tinas calientes en Puerto Varas: cuál elegir"
KEYWORD_ROOT = "biopiscinas puerto varas"
META_DESCRIPTION = (
    "¿Biopiscinas o tinas calientes en Puerto Varas? Te explicamos la "
    "diferencia real (filtración natural vs agua a 38-39°C) para que "
    "elijas según lo que buscas."
)
CLUSTER = BlogCluster.TINAS
CTA_TEXT = "Reserva tu tina caliente"
CTA_URL = "/tinas/"

INTRO = (
    'Si buscas "biopiscinas Puerto Varas" y llegaste hasta acá, la '
    "respuesta corta y honesta es: en Aremko no tenemos biopiscinas. "
    "Tenemos otra cosa — tinas artesanales calentadas con aerotermia y "
    "paneles solares, a 38-39°C. Antes de que cierres la pestaña porque no "
    "encontraste lo que buscabas, dejame explicarte la diferencia real, "
    "porque no es solo cambiar de nombre: son dos productos distintos, "
    "para dos ganas distintas, y probablemente uno de los dos es "
    "exactamente lo que necesitas. El dueño de un spa que te manda a la "
    "competencia si corresponde — sí, existimos."
)

BODY_MD = """\
## Qué es una biopiscina (de verdad, no la versión de folleto)

Una biopiscina usa **filtración biológica**: plantas y un sistema natural
en vez de cloro, con agua a temperatura más suave (ambiente o
tibia-templada, no caliente-caliente). Son más grandes, pensadas para
meterse un rato largo, nadar un poco, estar en grupo. El atractivo es lo
ecológico y lo natural del sistema — es agua "viva", no agua tratada
químicamente.

## Qué es una tina caliente en Aremko

Agua a **38-39°C**, con garantía: si llega a 37°C o menos, la tina es
gratis. Se calienta con **aerotermia + paneles solares** — sin leña, sin
humo, sin combustión. Son privadas, para 1-2 personas, pensadas para un
rato corto y concentrado, no para pasar la tarde nadando. El objetivo no es
"agua natural", es "agua caliente de verdad, garantizada, junto al río".

## La comparación sin vueltas

| | Biopiscina | Tina caliente Aremko |
|---|---|---|
| Temperatura | Ambiente / tibia | 38-39°C, garantizado |
| Filtración | Biológica (plantas) | Aerotermia + solar |
| Tamaño | Grande, para nadar | Privada, 1-2 personas |
| Duración típica | Toda la tarde | Sesión corta y concentrada |
| Lo que buscas si la eliges | Naturaleza, ecología, grupo | Calor real, intimidad, ritual |

## Entonces, ¿cuál eligen?

Si lo que quieren es pasar la tarde nadando en agua natural, con onda
ecológica y espacio para grupo — busquen biopiscina, es lo que están
pidiendo y nosotros no somos eso. Si lo que quieren es una hora de agua
caliente de verdad, garantizada, en privado, junto al río, después de un
día largo — eso sí lo tenemos, y lo tenemos bien.
"""

FAQ_ITEMS = [
    {
        "question": "¿Aremko tiene biopiscinas?",
        "answer": (
            "No. Aremko tiene tinas artesanales calentadas con aerotermia "
            "y paneles solares, a 38-39°C — un producto distinto a una "
            "biopiscina."
        ),
    },
    {
        "question": "¿Cuál es la diferencia principal entre biopiscina y tina caliente?",
        "answer": (
            "La biopiscina usa filtración biológica y temperatura suave, "
            "pensada para nadar; la tina de Aremko es agua caliente "
            "garantizada (38-39°C), privada, para una sesión corta."
        ),
    },
    {
        "question": "¿Qué garantía tiene la temperatura de la tina de Aremko?",
        "answer": "Si el agua llega a 37°C o menos, la tina es gratis.",
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
        "Seed del post Aremko 'Biopiscinas vs. tinas calientes'. "
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
