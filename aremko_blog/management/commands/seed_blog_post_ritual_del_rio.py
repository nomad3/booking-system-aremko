"""Seed del blog Aremko: "Ritual del Río".

Mismo patrón que los seeds anteriores (tinas, masajes, escapada romántica).
Idempotente: update_or_create por slug. Por defecto queda como BORRADOR
(is_published=False) — Jorge revisa y publica a mano desde el admin, o con
--publish. Contenido redactado en sesión interactiva 2026-07-08, grounded en
el copy real de /ritual-del-rio/ (no inventa precios ni datos).

Target SEO:
- Keyword root: "ritual del río puerto varas"
- Cluster: RIO (antes vacío)

Uso:
    python manage.py seed_blog_post_ritual_del_rio            # borrador
    python manage.py seed_blog_post_ritual_del_rio --publish  # publicado
"""
from __future__ import annotations

import json

from django.core.management.base import BaseCommand
from django.utils import timezone

from aremko_blog.models import BlogCluster, BlogPost


SLUG = "ritual-del-rio-puerto-varas"
TITLE = "Ritual del Río: la noche de tres actos que solo viven 5 parejas por vez"
KEYWORD_ROOT = "ritual del río puerto varas"
META_DESCRIPTION = (
    "Ritual del Río: masaje nocturno, tina bajo las estrellas y cabaña con "
    "desayuno, junto al río Pescado en Puerto Varas. Solo 5 parejas por "
    "noche, desde $210.000."
)
CLUSTER = BlogCluster.RIO
CTA_TEXT = "Reserva tu noche por WhatsApp"
CTA_URL = "/ritual-del-rio/"

INTRO = (
    'Si buscas "ritual del río Puerto Varas" probablemente ya leíste la '
    'palabra "ritual" y pensaste: ¿esto es una ceremonia con velas, '
    "incienso y alguien recitando algo en voz baja? No. Nadie recita nada. "
    "Es más simple y más rico: un masaje, una tina caliente bajo las "
    "estrellas junto al río, y una cabaña donde dormir abrazados hasta que "
    'llegue el desayuno. Le decimos "ritual" porque tiene un orden — tres '
    "actos, siempre en la misma secuencia, y ese orden es justamente lo que "
    "lo hace funcionar (nadie te manda directo a la tina con la mochila del "
    "trabajo todavía puesta). Solo recibimos 5 parejas por noche, así que "
    "si sigues leyendo, probablemente ya decidiste que quieres ser una de "
    "esas 5."
)

BODY_MD = """\
## Los tres actos, en orden (y por qué el orden importa)

No es al azar, y no es porque nos guste la palabra "ritual". Primero el
**masaje nocturno**, para que suelten la semana antes de tocar el agua —
llegar directo a la tina con la espalda todavía cargada de la oficina es
como bañarse sin sacarse los zapatos: técnicamente se puede, pero para qué.
Después la **tina caliente**, bajo las estrellas, junto al río, mientras
afuera hace 4 grados y a ustedes, con toda honestidad, no les importa. Y al
final, **cabaña y desayuno**: duermen abrazados y despiertan con la mesa
lista, sin tener que decidir nada más esa noche — la única decisión pendiente
es si se levantan o no.

## El bonus que casi nadie pide (pero debería)

Se llama **El Reseteo**: antes o después de la tina caliente, un chapuzón en
Yates, nuestra tina de agua fría, de uso libre para todos los huéspedes. El
contraste frío-calor da un shock que no se olvida — y sienta mejor de lo que
suena en el papel (suena a mala idea, es una gran idea). Va incluido, gratis,
y casi nadie lo pide la primera vez porque nadie lee la letra chica. Ahora ya
la leíste, así que no tienen excusa.

## El rincón que se pierde la mitad de los huéspedes

Al final de la red de pasarelas está el Mirador del Río Pescado — la mejor
vista de todo el spa, y la que menos gente conoce porque está literalmente al
final del camino, donde ya nadie sigue caminando. Los saltos de agua, la isla
que se forma entre las rocas, una mesa para compartir sin apuro. Pide un
café, una copa de espumante, jugos naturales, una pizza o una tabla. La mitad
de las parejas se va sin haber ido nunca — no cometan ese error, ya pagaron
por el lugar, úsenlo entero.

## Por qué no es lo mismo que un hotel, una tina sola, o unas termas públicas

Un hotel es cómodo, tiene wifi y almohadas de sobra — y es tan impersonal
como su propio nombre suena. Las termas públicas tienen agua caliente de
verdad, sí, también tienen fila, un altavoz anunciando algo y cero
posibilidad de intimidad. Una cabaña sola es solo un techo para dormir, por
bonito que sea el techo. El Ritual del Río es lo único en Puerto Varas que
junta río, noche y todo resuelto para dos, en ese orden — no vendemos partes
sueltas de la experiencia, la vendemos completa porque separada no funciona
igual.

## Cuánto cuesta y cómo reservar

$210.000 domingo a jueves, $240.000 viernes y sábado — para 2 personas,
incluye masaje nocturno, tina privada, cabaña y desayuno. Se reserva por
WhatsApp (aseguras el cupo con un abono, el resto lo coordinamos directo, sin
formularios de 12 campos). Solo 5 parejas por noche, así que si la fecha que
quieren está cerca, no la dejen para después — la sexta pareja se queda
mirando desde afuera, y afuera hace 4 grados.
"""

FAQ_ITEMS = [
    {
        "question": "¿Cuánto cuesta el Ritual del Río?",
        "answer": (
            "$210.000 domingo a jueves y $240.000 viernes y sábado, para 2 "
            "personas. Incluye masaje nocturno, tina caliente privada, "
            "cabaña y desayuno."
        ),
    },
    {
        "question": "¿Cómo se reserva el Ritual del Río?",
        "answer": (
            "Por WhatsApp. Se asegura el cupo con un abono y el resto se "
            "coordina directo con el equipo de Aremko."
        ),
    },
    {
        "question": "¿Cuántas parejas reciben por noche?",
        "answer": "Solo 5 parejas por noche, para mantener la privacidad de la experiencia.",
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
        "Seed del post Aremko 'Ritual del Río'. Idempotente: update_or_create "
        "por slug. Por defecto crea borrador; usa --publish para publicar al instante."
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
