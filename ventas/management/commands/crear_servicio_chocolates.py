"""
Crea (idempotente) el servicio 'Caja de chocolates' $15.000 para el configurador
de experiencia romántica (Fase 1, Puerta B).

Vive en la categoría 'Ambientaciones' a propósito: así el filtro de la invitación
sorpresa lo esconde automáticamente (como toda ambientación) y hereda la regla
"va sobre la tina". Se crea con publicado_web=False para NO aparecer como una card
suelta en /tinas/ — solo lo usa el configurador programáticamente.

Uso (en la Shell de Render):
    python manage.py crear_servicio_chocolates
"""
from django.core.management.base import BaseCommand
from ventas.models import Servicio, CategoriaServicio


NOMBRE = 'Caja de chocolates'
PRECIO = 15000


class Command(BaseCommand):
    help = "Crea/asegura el servicio 'Caja de chocolates' $15.000 en categoría Ambientaciones"

    def handle(self, *args, **options):
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.SUCCESS("🍫 Servicio Caja de chocolates (configurador romántico)"))
        self.stdout.write("=" * 70 + "\n")

        categoria = CategoriaServicio.objects.filter(nombre__iexact='Ambientaciones').first()
        if not categoria:
            self.stdout.write(self.style.ERROR(
                "No existe la categoría 'Ambientaciones'. Aborta — revisa el catálogo."
            ))
            return

        servicio, creado = Servicio.objects.get_or_create(
            nombre=NOMBRE,
            defaults={
                'precio_base': PRECIO,
                'duracion': 1,  # add-on, la duración no aplica (hereda slot de la tina)
                'categoria': categoria,
                'tipo_servicio': 'otro',
                'capacidad_minima': 1,
                'capacidad_maxima': 1,
                'activo': True,
                'publicado_web': False,  # solo lo usa el configurador; no card en /tinas/
                'slots_disponibles': [],
            },
        )

        if creado:
            self.stdout.write(self.style.SUCCESS(
                f"✅ Creado: '{servicio.nombre}' (id={servicio.id}) — ${PRECIO:,} — cat. {categoria.nombre}"
            ))
        else:
            # Ya existía: asegurar precio y categoría correctos (idempotente, no duplica)
            cambios = []
            if servicio.precio_base != PRECIO:
                servicio.precio_base = PRECIO
                cambios.append('precio_base')
            if servicio.categoria_id != categoria.id:
                servicio.categoria = categoria
                cambios.append('categoria')
            if not servicio.activo:
                servicio.activo = True
                cambios.append('activo')
            if cambios:
                servicio.save(update_fields=cambios)
                self.stdout.write(self.style.WARNING(
                    f"↺ Ya existía (id={servicio.id}); actualizado: {', '.join(cambios)}"
                ))
            else:
                self.stdout.write(
                    f"✓ Ya existía y está correcto (id={servicio.id}, ${int(servicio.precio_base):,})"
                )

        self.stdout.write("")
