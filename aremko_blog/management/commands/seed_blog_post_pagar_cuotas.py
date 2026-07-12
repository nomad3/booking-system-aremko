"""Seed del blog Aremko: "Cómo pagar tu reserva en cuotas con Mercado Pago".

Mismo patrón que los seeds anteriores. Idempotente: update_or_create por
slug. Por defecto queda como BORRADOR (is_published=False). Post de
soporte/FAQ, NO de adquisición — describe con precisión el alcance real
de la funcionalidad (confirmado por investigación de código 2026-07-08):
Mercado Pago Checkout Pro aplica SOLO al saldo pendiente de una reserva ya
creada, vía la Ficha de Reserva tokenizada. NO aplica al carrito público
(sigue en Flow.cl, migración pendiente sin fecha, P-09). El post NO promete
"reserva y paga en cuotas desde cero" porque esa funcionalidad no existe
todavía.

Target SEO:
- Keyword root: "pagar reserva aremko cuotas"
- Cluster: BOUTIQUE

Uso:
    python manage.py seed_blog_post_pagar_cuotas            # borrador
    python manage.py seed_blog_post_pagar_cuotas --publish  # publicado
"""
from __future__ import annotations

import json

from django.core.management.base import BaseCommand
from django.utils import timezone

from aremko_blog.models import BlogCluster, BlogPost


SLUG = "pagar-reserva-aremko-cuotas-mercado-pago"
TITLE = "Cómo pagar tu reserva en Aremko en hasta 12 cuotas con Mercado Pago"
KEYWORD_ROOT = "pagar reserva aremko cuotas"
META_DESCRIPTION = (
    "Cómo pagar el saldo de tu reserva en Aremko hasta en 12 cuotas con "
    "Mercado Pago — vía tu Ficha de Reserva, condiciones según tu banco."
)
CLUSTER = BlogCluster.BOUTIQUE
CTA_TEXT = "Consulta tu reserva"
CTA_URL = "/"

INTRO = (
    "Si ya reservaste en Aremko y te llegó el link de tu Ficha de Reserva, "
    "probablemente viste la opción de pagar hasta en 12 cuotas y te "
    "quedaste con dudas. Vamos directo: es real, es Mercado Pago, y hoy "
    "funciona sobre el saldo pendiente de una reserva que ya existe — no "
    'es todavía un botón de "reserva ahora en cuotas" desde el carrito de '
    "la web. Acá te explicamos exactamente cómo funciona, sin prometer más "
    "de lo que hay."
)

BODY_MD = """\
## Cómo funciona hoy

Cuando reservas en Aremko, te llega un link a tu Ficha de Reserva. Desde
ahí puedes pagar el saldo pendiente con Mercado Pago Checkout Pro, que
ofrece hasta 12 cuotas.

## Lo que hay que saber antes de elegir cuotas

El número de cuotas y si tienen o no interés lo determina tu banco o la
tarjeta que uses, no Aremko — no podemos garantizar "sin interés" porque
no depende de nosotros. Revisa las condiciones que te muestre Mercado Pago
al momento de pagar, antes de confirmar.

## Qué NO es (todavía)

No es una opción de compra en cuotas desde el carrito público al momento
de reservar por primera vez — eso todavía no existe. Aplica solo al saldo
de una reserva que ya hiciste.
"""

FAQ_ITEMS = [
    {
        "question": "¿Puedo reservar en Aremko y pagar en cuotas desde el primer momento?",
        "answer": (
            "No todavía. El pago en cuotas con Mercado Pago aplica al "
            "saldo pendiente de una reserva ya creada, a través del link "
            "de tu Ficha de Reserva."
        ),
    },
    {
        "question": "¿Las cuotas de Mercado Pago son sin interés?",
        "answer": (
            "Depende de tu banco o tarjeta — Aremko no define ni "
            "garantiza esa condición. Revisa el detalle que te muestre "
            "Mercado Pago antes de confirmar el pago."
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
        "Seed del post Aremko 'Pagar reserva en cuotas'. Idempotente: "
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
