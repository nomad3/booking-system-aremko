"""Publica el siguiente borrador de la cola priorizada del blog Aremko.

Nivel 2 acotado: NO genera contenido nuevo — eso ya pasó, a mano, en
sesión interactiva, con cada post revisado y corregido por Jorge antes de
sembrarse como borrador (ver los 16 seed_blog_post_* de esta misma app).
Este comando SOLO cambia is_published=False → True + published_at=now()
del primer slug de PRIORITY_ORDER que todavía esté en borrador. Publica
UNO por corrida — pensado para disparo semanal vía cron.

Si algún slug de la lista no existe en la BD, o ya está publicado, lo
salta y sigue con el siguiente. Si todos los de la lista ya están
publicados, no hace nada (mensaje informativo, no falla).

Orden acordado con Jorge 2026-07-12 ("prioridad comercial"): primero los 4
programas (Ritual del Río, Pausa, Refugio, Noche de Aguas Calientes —
cada uno con su propio botón de reserva), después 3 posts keyword-driven
con volumen de búsqueda real (DataForSEO), después los 4 tipos de masaje,
y al final 5 evergreen/soporte. Agregar un post nuevo a la cola: crear su
seed_blog_post_* (borrador) y sumar su slug a PRIORITY_ORDER en el lugar
que corresponda — no requiere tocar el cron ni este comando más allá de
esa línea.

Uso:
    python manage.py publish_next_blog_draft
    python manage.py publish_next_blog_draft --dry-run   # solo muestra cuál publicaría
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.utils import timezone

from aremko_blog.models import BlogPost


PRIORITY_ORDER = [
    # Grupo A — programas (mayor valor comercial directo)
    "ritual-del-rio-puerto-varas",
    "pausa-junto-al-rio-puerto-varas",
    "refugio-aremko-puerto-varas",
    "noche-de-aguas-calientes-puerto-varas",
    # Grupo B — keyword-driven (volumen real detectado vía DataForSEO)
    "masajes-cerca-de-mi-puerto-varas",
    "masajes-cerca-de-puerto-montt",
    "biopiscinas-vs-tinas-calientes-puerto-varas",
    # Grupo D — tipos de masaje (catálogo real)
    "masaje-tui-na-puerto-varas",
    "masaje-tailandes-puerto-varas",
    "drenaje-linfatico-puerto-varas",
    "masaje-deportivo-vs-piedras-calientes-puerto-varas",
    # Grupo C/E — evergreen + soporte
    "rio-pescado-aremko-puerto-varas",
    "que-es-spa-boutique-aremko",
    "elegir-programa-aremko-segun-tiempo",
    "aremko-invierno-puerto-varas",
    "pagar-reserva-aremko-cuotas-mercado-pago",
]


class Command(BaseCommand):
    help = (
        "Publica el siguiente borrador de blog en PRIORITY_ORDER (1 por "
        "corrida, pensado para cron semanal). No genera contenido nuevo."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Solo muestra cuál publicaría, sin modificar la BD.",
        )

    def handle(self, *args, **options):
        dry_run = options.get("dry_run", False)

        for slug in PRIORITY_ORDER:
            post = BlogPost.objects.filter(slug=slug).first()
            if post is None:
                self.stdout.write(self.style.WARNING(f"  {slug}: no existe en la BD, se salta."))
                continue
            if post.is_published:
                continue  # ya publicado, seguir a la siguiente

            if dry_run:
                self.stdout.write(self.style.NOTICE(f"[dry-run] Publicaría: {post.title} ({slug})"))
                return

            post.is_published = True
            post.published_at = timezone.now()
            post.save(update_fields=["is_published", "published_at"])
            self.stdout.write(
                self.style.SUCCESS(
                    f"Publicado: {post.title}\n"
                    f"  Slug: {post.slug}\n"
                    f"  URL: {post.get_absolute_url()}"
                )
            )
            return

        self.stdout.write(self.style.SUCCESS("No hay borradores pendientes en la cola priorizada."))
