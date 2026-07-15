"""Enriquece el post de termas ya PUBLICADO con la intención geo nueva
"termas cerca de Puerto Montt".

Contexto (Ciclo 2 del loop SEO, 2026-07-14): en GSC apareció la query nueva
`termas cerca de puerto montt` (pos 5.85, CTR 14.8%) sin contenido dedicado.
En vez de crear un post nuevo, se amplía el post `/blog/termas-puerto-varas/`
que YA rankea (261 imp) con una sección + un item de FAQ que atacan esa query
con la URL existente.

⚠️ Este post fue escrito a mano por Jorge en el admin (no tiene seed). Por eso
este comando es APPEND-ONLY e IDEMPOTENTE: NO reescribe `body_md` ni el
`faq_schema_json` existentes — solo agrega la sección/FAQ si todavía no están.
Correrlo dos veces no duplica nada. No inventa datos: usa hechos ya confirmados
(20 min de Puerto Montt por la ruta 5, tinas a 38-39° junto al río Pescado,
garantía 37° o gratis, abierto hasta medianoche).

Uso:
    python manage.py enrich_termas_puerto_montt --dry-run   # muestra qué haría
    python manage.py enrich_termas_puerto_montt             # aplica
"""
from __future__ import annotations

import json

from django.core.management.base import BaseCommand

from aremko_blog.models import BlogPost


SLUG = "termas-puerto-varas"

H2_MARKER = "¿Termas cerca de Puerto Montt?"
H2_BLOCK = """\
## ¿Termas cerca de Puerto Montt?

Si buscás termas cerca de Puerto Montt, la respuesta honesta es la misma que en
Puerto Varas: no hay termas naturales a la vuelta de la esquina (las más
cercanas quedan a 1½–2 horas por camino de ripio). Pero Aremko está a solo 20
minutos de Puerto Montt por la ruta 5 — tinas artesanales de agua caliente a
38-39° junto al río Pescado, abiertas hasta medianoche, con una garantía que
ninguna terma natural te da: si el agua está a 37° o menos, la tina es gratis.
Para muchos desde Puerto Montt es el plan de tarde más cercano que de verdad se
siente como unas termas.
"""

FAQ_QUESTION = "¿Hay termas cerca de Puerto Montt?"
FAQ_ANSWER = (
    "No hay termas naturales inmediatas a Puerto Montt; las más cercanas "
    "quedan a 1½–2 horas. La alternativa más cercana son las tinas de agua "
    "caliente de Aremko en Puerto Varas, a 20 minutos por la ruta 5, abiertas "
    "hasta medianoche."
)


def inject_faq(raw: str) -> tuple[str, bool]:
    """Agrega el item de FAQ al schema FAQPage si no está.

    Devuelve (json_resultante, hubo_cambio). Append-only e idempotente. Si el
    JSON existente está vacío se crea un FAQPage nuevo; si es inválido o no es
    un FAQPage reconocible, NO se toca (devuelve el original sin cambio).
    """
    item = {
        "@type": "Question",
        "name": FAQ_QUESTION,
        "acceptedAnswer": {"@type": "Answer", "text": FAQ_ANSWER},
    }
    raw = (raw or "").strip()
    if not raw:
        data = {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [],
        }
    else:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return raw, False
    if not isinstance(data, dict) or data.get("@type") != "FAQPage":
        return raw, False
    entities = data.setdefault("mainEntity", [])
    if not isinstance(entities, list):
        return raw, False
    if any(isinstance(q, dict) and q.get("name") == FAQ_QUESTION for q in entities):
        return raw, False
    entities.append(item)
    return json.dumps(data, ensure_ascii=False, indent=2), True


class Command(BaseCommand):
    help = (
        "Enriquece el post de termas con la sección + FAQ 'termas cerca de "
        "Puerto Montt'. Append-only e idempotente: no pisa el contenido "
        "existente. Usá --dry-run para ver qué haría sin escribir."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Solo muestra qué cambiaría, sin escribir en la BD.",
        )

    def handle(self, *args, **options):
        dry_run = options.get("dry_run", False)

        post = BlogPost.objects.filter(slug=SLUG).first()
        if post is None:
            self.stderr.write(
                self.style.ERROR(f"No existe el post con slug '{SLUG}'. Nada que hacer.")
            )
            return

        changed_fields: list[str] = []

        # --- body_md (append H2 si falta) ---
        if H2_MARKER in (post.body_md or ""):
            self.stdout.write("  body_md: la sección de Puerto Montt ya está presente, se salta.")
        else:
            if not dry_run:
                post.body_md = (post.body_md or "").rstrip() + "\n\n" + H2_BLOCK
            changed_fields.append("body_md")
            self.stdout.write(self.style.NOTICE("  body_md: se agregará la sección '¿Termas cerca de Puerto Montt?'."))

        # --- faq_schema_json (append item si falta y el JSON es compatible) ---
        new_faq, faq_changed = inject_faq(post.faq_schema_json)
        if faq_changed:
            if not dry_run:
                post.faq_schema_json = new_faq
            changed_fields.append("faq_schema_json")
            self.stdout.write(self.style.NOTICE("  faq_schema_json: se agregará el item de FAQ."))
        else:
            self.stdout.write(
                "  faq_schema_json: el item ya está, el JSON está vacío-manejado, o no es un "
                "FAQPage compatible — no se toca."
            )

        if not changed_fields:
            self.stdout.write(self.style.SUCCESS("Nada que cambiar: el post ya estaba enriquecido."))
            return

        if dry_run:
            self.stdout.write(
                self.style.WARNING(f"[dry-run] Cambiaría los campos: {', '.join(changed_fields)} (sin escribir).")
            )
            return

        post.save(update_fields=changed_fields + ["updated_at"])
        self.stdout.write(
            self.style.SUCCESS(
                f"Post enriquecido: {post.title}\n"
                f"  Slug: {post.slug}\n"
                f"  Campos actualizados: {', '.join(changed_fields)}\n"
                f"  URL: {post.get_absolute_url()}"
            )
        )
