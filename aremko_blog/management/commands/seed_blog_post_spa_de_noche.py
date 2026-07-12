"""Seed del blog Aremko: "Spa de noche en Puerto Varas".

Mismo patrón que los seeds anteriores. Idempotente: update_or_create por
slug. Por defecto queda como BORRADOR (is_published=False). Redactado en
sesión interactiva 2026-07-12, a partir de una idea de Jorge ("solo Aremko
funciona cuando se esconde el sol") que se AJUSTÓ tras verificar la
afirmación:

- Horario real de Aremko hasta medianoche: confirmado por Jorge 2026-07-12.
- Horario real de un spa boutique comparable de la zona (Cancagua,
  Frutillar) verificado en vivo el mismo día: cierra a las 22:00 todos los
  días — NO "solo Aremko funciona de noche" (afirmación original,
  refutable), sino "Aremko funciona más tarde y es el único que combina
  la experiencia con alojamiento para pasar la noche".
- A propósito NO se nombra a ningún competidor específico en el post
  (mismo criterio que el post de biopiscinas vs tinas) — comparación
  genérica y defendible, no ataque directo a una marca.

Target SEO: ya hay tracción orgánica real sin haber trabajado el ángulo
(rank-check 2026-07-12 vía DataForSEO): "tinas de noche puerto varas" pos
1, "spa abierto de noche puerto varas" pos 2, "spa de noche puerto varas"
pos 6. Además apunta a "qué hacer de noche en puerto varas" / "actividades
nocturnas puerto varas" — hoy sin contenido dedicado, dominadas por
agregadores de turismo.

- Keyword root: "spa de noche puerto varas"
- Cluster: SPA

Uso:
    python manage.py seed_blog_post_spa_de_noche            # borrador
    python manage.py seed_blog_post_spa_de_noche --publish  # publicado
"""
from __future__ import annotations

import json

from django.core.management.base import BaseCommand
from django.utils import timezone

from aremko_blog.models import BlogCluster, BlogPost


SLUG = "spa-de-noche-puerto-varas"
TITLE = "Spa de noche en Puerto Varas: hasta medianoche, con opción de quedarte a dormir"
KEYWORD_ROOT = "spa de noche puerto varas"
META_DESCRIPTION = (
    "Spa de noche en Puerto Varas: tinas y masajes hasta medianoche, con "
    "opción de quedarte a dormir. La única experiencia de naturaleza "
    "abierta hasta tan tarde."
)
CLUSTER = BlogCluster.SPA
CTA_TEXT = "Reserva tu noche"
CTA_URL = "/tinas/"

INTRO = (
    'Si buscas "qué hacer de noche en Puerto Varas" y ya viste la lista '
    "de bares y restaurantes de siempre, hay una opción que probablemente "
    "no consideraste: meterte a una tina caliente junto al río a las 22:30 "
    "de un martes. La mayoría de los spas de naturaleza de la zona cierran "
    "con el sol — Aremko funciona hasta medianoche, y es el único que "
    "además te deja quedarte a dormir ahí mismo. No es un dato menor para "
    "quien llega tarde de trabajar, o para el turista que recién a las 8pm "
    "terminó de hacer el circuito de miradores del día."
)

BODY_MD = """\
## Hasta medianoche, en serio

No es "hasta que oscurezca" ni "según disponibilidad" — Aremko opera hasta
medianoche. Eso significa que salir del trabajo a las 19:00, cenar, y
llegar a las 21:30 a meterse en agua caliente es un plan real, no una
excepción que hay que negociar por WhatsApp.

## Por qué la mayoría cierra antes

La lógica de un spa de día es simple: personal, luz natural, y un flujo de
visitantes que entra y sale en horario de oficina. La mayoría de los spas
boutique de la zona sigue ese modelo — cierran alrededor de las 22:00, lo
cual para el sur de Chile en pleno verano austral es prácticamente todavía
de día. Aremko decidió operar distinto: de noche, con luz artificial
pensada para eso, y personal dedicado a ese horario.

## Lo que nadie más ofrece: quedarte a dormir

La diferencia real no es solo la hora de cierre — es que Aremko combina la
tina de noche con **alojamiento**. Ritual del Río y Noche de Aguas
Calientes están armados exactamente para eso: llegan de noche, se meten al
agua, y duermen ahí mismo en una cabaña, sin manejar de vuelta con el pelo
mojado a las 23:00. Ningún otro spa de naturaleza de la zona ofrece esa
combinación completa.

## Para quién es esto en la práctica

- **Locales que salen tarde de trabajar**: la Pausa junto al Río o la
  Noche de Aguas Calientes resuelven un after-work real, no uno teórico
  que exige salir a las 18:00 en punto.
- **Turistas con el día ocupado**: si el circuito de miradores, el lago o
  el volcán les tomó hasta la tarde, no tienen que elegir entre eso y el
  spa — pueden hacer ambos el mismo día.
- **Quien busca algo distinto a cenar y volver al hotel**: la noche en
  Puerto Varas no tiene por qué terminar en un restaurante.

## Cómo reservar

Ritual del Río y Noche de Aguas Calientes son los programas pensados
específicamente para llegar de noche. Ambos se reservan por WhatsApp,
coordinando la hora exacta de llegada.
"""

FAQ_ITEMS = [
    {
        "question": "¿Hasta qué hora funciona Aremko?",
        "answer": "Hasta medianoche.",
    },
    {
        "question": "¿Se puede llegar directo de noche, después del trabajo?",
        "answer": (
            "Sí — Noche de Aguas Calientes está pensado exactamente para "
            "eso: llegar de tarde-noche, tina caliente, y dormir en una "
            "cabaña boutique con desayuno incluido."
        ),
    },
    {
        "question": "¿Hay otro spa de naturaleza en la zona que funcione hasta tan tarde y con alojamiento?",
        "answer": (
            "La mayoría de los spas boutique de la zona cierra alrededor "
            "de las 22:00 y funciona como visita de día, sin alojamiento "
            "para pasar la noche. Aremko combina ambas cosas: horario "
            "hasta medianoche y la opción de dormir ahí mismo."
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
        "Seed del post Aremko 'Spa de noche en Puerto Varas'. Idempotente: "
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
