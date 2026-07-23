"""
F2 (diagnóstico, SOLO LECTURA): lista los Productos que ya existen y que sirven
para la Experiencia Romántica (jugos, aguas, vino, espumante, chocolates), para
referenciarlos por nombre/id sin crear duplicados.

No modifica nada.

Uso (Shell de Render):
    python manage.py listar_productos_ambientacion
"""
from django.db.models import Q
from django.core.management.base import BaseCommand
from ventas.models import Producto, Servicio


CLAVES = ['jugo', 'agua', 'vino', 'espumante', 'chocolate', 'frambues', 'arandan', 'arándan', 'melon', 'melón']


class Command(BaseCommand):
    help = 'Lista (solo lectura) los productos existentes de bebidas/chocolates para el flujo romántico'

    def handle(self, *args, **options):
        q = Q()
        for c in CLAVES:
            q |= Q(nombre__icontains=c)

        self.stdout.write("\n" + "=" * 78)
        self.stdout.write("PRODUCTOS existentes (bebidas / chocolates)")
        self.stdout.write("=" * 78)
        prods = Producto.objects.filter(q).select_related('categoria').order_by('nombre')
        if not prods:
            self.stdout.write("  (ninguno encontrado)")
        for p in prods:
            cat = p.categoria.nombre if p.categoria_id else '—'
            self.stdout.write(
                f"  id={p.id:<4} ${int(p.precio_base):>7,}  stock={p.cantidad_disponible:<5} "
                f"web={'S' if p.publicado_web else 'N'}  cat={cat:<22} {p.nombre}")

        self.stdout.write("\n" + "=" * 78)
        self.stdout.write("SERVICIOS con esos nombres (para detectar el duplicado de chocolates de F1)")
        self.stdout.write("=" * 78)
        servs = Servicio.objects.filter(q).select_related('categoria').order_by('nombre')
        if not servs:
            self.stdout.write("  (ninguno)")
        for s in servs:
            cat = s.categoria.nombre if s.categoria_id else '—'
            self.stdout.write(
                f"  id={s.id:<4} ${int(s.precio_base):>7,}  activo={'S' if s.activo else 'N'}  "
                f"cat={cat:<22} {s.nombre}")
        self.stdout.write("=" * 78 + "\n")
