# -*- coding: utf-8 -*-
"""Vuelca (solo lectura) los PackDescuento configurados en el admin — para diagnosticar
por qué un día que debería tener descuento (ej. lunes en el pack cabaña+tina) no lo trae.

No modifica nada. Muestra dias_semana_validos con su traducción a nombre de día
(0=Domingo...6=Sábado, mismo mapeo que usa PackDescuentoService).

Uso:
    python manage.py ver_packs_descuento
"""
from django.core.management.base import BaseCommand

_DIAS = ['Domingo', 'Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado']


class Command(BaseCommand):
    help = "Lista los PackDescuento configurados: nombre, descuento, días válidos, servicios."

    def handle(self, *args, **opts):
        from ventas.models import PackDescuento

        packs = PackDescuento.objects.all().order_by('id')
        if not packs.exists():
            self.stdout.write(self.style.WARNING("No hay PackDescuento configurados."))
            return

        for p in packs:
            dias = p.dias_semana_validos or []
            dias_nombres = [f"{d}={_DIAS[d]}" if 0 <= d <= 6 else f"{d}=?" for d in dias]
            self.stdout.write(f"\n{'='*60}")
            self.stdout.write(f"PackDescuento #{p.id}: {p.nombre}")
            self.stdout.write(f"  activo: {getattr(p, 'activo', '?')}")
            self.stdout.write(f"  descuento: ${int(p.descuento or 0):,}")
            self.stdout.write(f"  dias_semana_validos (crudo): {dias}")
            self.stdout.write(f"  dias_semana_validos (traducido): {dias_nombres or '(ninguno = todos los días?)'}")
            self.stdout.write(f"  usa_servicios_especificos: {getattr(p, 'usa_servicios_especificos', '?')}")
            if getattr(p, 'usa_servicios_especificos', False):
                nombres = list(p.servicios_especificos.values_list('nombre', flat=True))
                self.stdout.write(f"  servicios_especificos: {nombres}")
            else:
                self.stdout.write(f"  servicios_requeridos (por tipo): {getattr(p, 'servicios_requeridos', '?')}")
            self.stdout.write(f"  misma_fecha: {getattr(p, 'misma_fecha', '?')}")
            lunes_incluido = 1 in dias
            self.stdout.write(
                self.style.SUCCESS("  >>> Lunes SÍ está en días válidos.")
                if lunes_incluido else
                self.style.ERROR("  >>> Lunes NO está en días válidos (posible causa del caso real reportado).")
            )
