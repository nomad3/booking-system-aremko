"""Seed del blog Aremko: "Masajes cerca de mí en Puerto Varas".

Mismo patrón que los seeds anteriores. Idempotente: update_or_create por
slug. Por defecto queda como BORRADOR (is_published=False). Contenido
redactado en sesión interactiva 2026-07-08, grounded en el catálogo real de
masajes (Servicio, categoría Masajes, confirmado por Jorge vía screenshot
del admin) — 6 tipos reales, precios reales, sin inventar nada.

Target SEO:
- Keyword root: "masajes cerca de mí" (5.400 búsquedas/mes vía DataForSEO,
  hoy en posición 46 — gran volumen, cero contenido dedicado)
- Cluster: MASAJES

Uso:
    python manage.py seed_blog_post_masajes_cerca_de_mi            # borrador
    python manage.py seed_blog_post_masajes_cerca_de_mi --publish  # publicado
"""
from __future__ import annotations

import json

from django.core.management.base import BaseCommand
from django.utils import timezone

from aremko_blog.models import BlogCluster, BlogPost


SLUG = "masajes-cerca-de-mi-puerto-varas"
TITLE = "Masajes cerca de mí en Puerto Varas: la guía para no manejar una hora por nada"
KEYWORD_ROOT = "masajes cerca de mí"
META_DESCRIPTION = (
    "Masajes cerca de ti en Puerto Varas: 6 tipos, 50 minutos cada uno, "
    "junto al río Pescado. Descontracturante, Tui-Na, Tailandés y más. "
    "Reserva por WhatsApp o web."
)
CLUSTER = BlogCluster.MASAJES
CTA_TEXT = "Reserva tu masaje"
CTA_URL = "/masajes/"

INTRO = (
    'Si googleaste "masajes cerca de mí" y el mapa te muestra puntos a 40 '
    'minutos en auto, bienvenido al problema real de "cerca" en el sur de '
    'Chile: acá "cerca" es relativo, y un masaje que implica una hora de '
    "camino de ida ya perdió la mitad de su propósito antes de empezar. En "
    "Aremko estamos a 20 minutos del centro de Puerto Varas, junto al río "
    "Pescado — lo suficiente cerca para que valga la pena, lo suficiente "
    "lejos para que no escuchen el tráfico mientras les sueltan la "
    "espalda. Seis tipos de masaje, 50 minutos cada uno, y nadie les va a "
    'preguntar "¿cómo va todo?" mientras intentan desconectar.'
)

BODY_MD = """\
## Los 6 tipos que tenemos (y no, no son todos lo mismo con nombre distinto)

- **Relajación o Descontracturante** ($40.000) — el que pides si nunca te
  has hecho un masaje y no quieres sorpresas. Es también el único que se
  reserva directo online, sin pasar por WhatsApp.
- **Masaje Deportivo** ($45.000) — para cuando el problema no es estrés,
  es que corriste, cargaste algo pesado, o el gimnasio te ganó.
- **Piedras Calientes** ($45.000) — el clásico que suena a spa de revista,
  y en este caso sí cumple.
- **Drenaje Linfático** ($45.000) — específico, no es para "relajarme un
  poco", es para un objetivo puntual. Pregúntanos si es lo tuyo antes de
  reservarlo a ciegas.
- **Masaje Tailandés** (nuevo, $40.000) — más estiramiento que presión,
  para quienes salen de una sesión de descontracturante sintiendo que
  faltó movimiento.
- **Masaje Tui-Na** (nuevo, $45.000) — técnica china de presión en puntos
  específicos. Es el que más preguntas genera y el que menos gente pide la
  primera vez, por desconocido.

Todos duran 50 minutos. Ninguno dura "45 minutos que en realidad son 35
porque hay que cambiarse".

## Por qué "cerca de mí" en el sur de Chile no significa lo mismo que en Santiago

En una ciudad grande, "cerca de mí" son 10 cuadras. Acá puede ser un pueblo
entero de distancia. Estamos a 20 minutos del centro de Puerto Varas por la
Ruta 225 — ni tan lejos que necesiten planificarlo como una excursión, ni
tan cerca que estén escuchando el mismo ruido del que quieren escapar. El
camino final son 4 km de ripio bien mantenido junto al río — no necesitan
4x4, sí necesitan bajar la velocidad y disfrutar que ya casi llegan.

## Quién les hace el masaje

El equipo titular: Sandra, Carolina, Diana y Paul, cada uno con estilo
propio dentro de su especialidad. Si tienen preferencia (más fuerte, más
suave, alguien en particular que ya conocen) avísennos al reservar — no es
mala educación pedirlo, es lo normal.

## Cómo reservar

El de Relajación o Descontracturante se reserva directo en la web. Los
otros cinco — Deportivo, Piedras Calientes, Drenaje Linfático, Tailandés y
Tui-Na — se coordinan por WhatsApp, porque dependen de disponibilidad del
terapeuta específico para esa técnica. No es burocracia, es que no
improvisamos un Tui-Na con quien tenga el turno libre.
"""

FAQ_ITEMS = [
    {
        "question": "¿Cuánto cuestan los masajes en Aremko?",
        "answer": (
            "Desde $40.000 (Relajación/Descontracturante y Tailandés) "
            "hasta $45.000 (Deportivo, Piedras Calientes, Drenaje "
            "Linfático, Tui-Na). Todos de 50 minutos."
        ),
    },
    {
        "question": "¿Cuál masaje pido si nunca me he hecho uno?",
        "answer": (
            "Relajación o Descontracturante — es el más amable y el único "
            "con reserva web directa."
        ),
    },
    {
        "question": "¿A cuánto queda Aremko del centro de Puerto Varas?",
        "answer": "A 20 minutos en auto, junto al río Pescado.",
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
        "Seed del post Aremko 'Masajes cerca de mí en Puerto Varas'. "
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
