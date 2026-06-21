# -*- coding: utf-8 -*-
"""Carga las 3 reseñas reales (TripAdvisor) en la landing del Ritual del Río.

Idempotente: vuelve a dejar los mismos textos cada vez que se corre.
Uso en el Shell de Render:

    python manage.py cargar_resenas_ritual

Para sobrescribir aunque ya haya texto distinto editado a mano, usar --force
(por defecto NO pisa una reseña que el equipo haya cambiado manualmente).
"""
from django.core.management.base import BaseCommand


RESENAS = [
    {
        "texto": "Reservé la noche romántica… tina caliente a 39°, entre la "
                 "naturaleza, a unos metros del río. Realmente todo maravilloso.",
        "autor": "Claudia · viaje en pareja",
    },
    {
        "texto": "Rodeado de bosque y con una vista hermosa al río… un espacio "
                 "ideal para descansar y desconectarse.",
        "autor": "Natalia · Puerto Montt",
    },
    {
        "texto": "Muy lindo el lugar y romántico. Ideal para relajarse y "
                 "conectarse. Los masajes, increíbles.",
        "autor": "Nicolás · viaje en pareja",
    },
]


class Command(BaseCommand):
    help = "Carga las 3 reseñas reales en la landing del Ritual del Río (idempotente)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force", action="store_true",
            help="Sobrescribe aunque la reseña ya tenga un texto distinto.",
        )

    def handle(self, *args, **options):
        from ventas.models import RitualRioLandingConfig

        force = options["force"]
        cfg = RitualRioLandingConfig.get_solo()

        cambios = 0
        for i, r in enumerate(RESENAS, start=1):
            campo_texto = f"resena{i}_texto"
            campo_autor = f"resena{i}_autor"
            actual = (getattr(cfg, campo_texto) or "").strip()

            if actual and not force:
                self.stdout.write(self.style.WARNING(
                    f"Reseña {i}: ya tiene texto (se respeta). Usa --force para pisarla."
                ))
                continue

            setattr(cfg, campo_texto, r["texto"])
            setattr(cfg, campo_autor, r["autor"])
            cambios += 1
            self.stdout.write(self.style.SUCCESS(f"Reseña {i}: cargada → {r['autor']}"))

        if cambios:
            cfg.save()
            self.stdout.write(self.style.SUCCESS(
                f"\nListo: {cambios} reseña(s) guardada(s) en la landing del Ritual del Río."
            ))
        else:
            self.stdout.write("\nSin cambios.")
