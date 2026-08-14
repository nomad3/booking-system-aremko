"""
Exporta los alojamientos del catálogo DPV como CSV, para prospección comercial.

    python manage.py exportar_alojamientos

Solo lectura: imprime el CSV por pantalla (la Shell de Render no deja bajar
archivos, así que se copia y pega). Una fila por lugar tipo LODGING con los
campos que la prospección de Datamatic necesita: cómo se llama, dónde está,
si tiene web propia, Instagram, y —la señal más valiosa— por dónde recibe
reservas (una `reservations_url` apuntando a Booking/Airbnb es dependencia
de OTAs: comisión de 15-18% que el negocio está pagando hoy).

La columna `elegido` va vacía a propósito: la llena Jorge a mano — el filtro
de zona y de olfato es humano, y los diagnósticos (que cuestan tiempo y
consultas) se corren solo sobre los marcados.
"""
import csv
import io

from django.core.management.base import BaseCommand

from destino_puerto_varas.models import Place


class Command(BaseCommand):
    help = "Imprime CSV con los alojamientos del catálogo DPV (solo lectura)"

    def add_arguments(self, parser):
        parser.add_argument("--tipo", default="LODGING",
                            help="place_type a exportar (por defecto LODGING).")
        parser.add_argument("--todos", action="store_true",
                            help="Incluir también los no publicados.")

    def handle(self, *args, **op):
        qs = Place.objects.filter(place_type=op["tipo"]).order_by("name")
        if not op["todos"]:
            qs = qs.filter(published=True)

        salida = io.StringIO()
        w = csv.writer(salida)
        w.writerow(["elegido", "nombre", "ubicacion", "precio", "web",
                    "instagram", "url_reservas", "telefono", "ficha_dpv"])
        for p in qs:
            w.writerow([
                "",  # la marca Jorge
                p.name,
                (p.location_label or "").strip(),
                (p.price_range or "").strip(),
                (p.website or "").strip(),
                (p.instagram or "").strip(),
                (getattr(p, "reservations_url", "") or "").strip(),
                (p.phone or "").strip(),
                f"https://destinopuertovaras.cl/lugares/{p.slug}/" if p.slug else "",
            ])

        self.stdout.write(salida.getvalue())
        self.stdout.write(f"# {qs.count()} alojamiento(s). Copia desde la línea "
                          f"«elegido,...» hasta aquí y pégalo en el chat o en un .csv.")
