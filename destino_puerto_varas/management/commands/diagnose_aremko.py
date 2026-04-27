"""Diagnóstico: lista los hubs 'Aremko Spa Boutique' duplicados y a qué padre apuntan los hijos.

Uso:
    python manage.py diagnose_aremko
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from destino_puerto_varas.models import Place


class Command(BaseCommand):
    help = "Diagnostica duplicados de Aremko Spa Boutique y referencias parent_place."

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("--- Hubs 'Aremko Spa Boutique' ---"))
        hubs = Place.objects.filter(name__icontains="Aremko Spa Boutique").order_by("id")
        for p in hubs:
            self.stdout.write(
                f"  id={p.id} slug={p.slug!r} "
                f"location={p.location_label!r} "
                f"partnership={p.partnership_level} "
                f"children={p.children.count()}"
            )

        self.stdout.write(self.style.MIGRATE_HEADING("--- Lugares con slug que empieza con 'aremko-' ---"))
        for p in Place.objects.filter(slug__startswith="aremko").order_by("slug"):
            parent = p.parent_place
            parent_str = f"id={parent.id} slug={parent.slug!r}" if parent else "NULL"
            self.stdout.write(
                f"  id={p.id} slug={p.slug!r} parent={parent_str}"
            )

        self.stdout.write(self.style.MIGRATE_HEADING("--- Lugares cuyo nombre tiene 'Aremko' (cualquier slug) ---"))
        for p in Place.objects.filter(name__icontains="Aremko").exclude(slug__startswith="aremko").order_by("slug"):
            parent = p.parent_place
            parent_str = f"id={parent.id} slug={parent.slug!r}" if parent else "NULL"
            self.stdout.write(
                f"  id={p.id} slug={p.slug!r} name={p.name!r} parent={parent_str}"
            )
