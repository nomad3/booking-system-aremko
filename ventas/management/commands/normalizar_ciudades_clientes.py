"""
normalizar_ciudades_clientes
============================

Asigna `Cliente.ciudad_normalizada` + `Cliente.region_geografica` para
clientes con el campo `ciudad` poblado (texto libre) o con `comuna` (FK).

Operación Vuelta a Casa, Etapa Geo.2.b.

Estrategia en cascada (primer match gana):
  1. Match exacto contra Ciudad.nombre_canonico (case-insensitive + trim)
  2. Match contra alias en Ciudad.aliases (split por |, case-insensitive)
  3. Inferencia comuna→ciudad: si Cliente.ciudad está vacío pero tiene
     comuna, mapear comuna.nombre contra Ciudades (canónico + aliases)
  4. Detección extranjero por marcadores en texto (Argentina, USA, etc.)
     → asigna region='extranjero' con Ciudad genérica '_otros_extranjero_'
  5. Sin match → region='sin_clasificar', ciudad_normalizada=NULL

Respeta ediciones manuales:
  - Clientes con ciudad_normalizada_manual=True se SALTAN siempre
  - Cuando el admin Django edita ciudad_normalizada, signal/save setea
    ciudad_normalizada_manual=True (ver admin.py)

Uso:
    python manage.py normalizar_ciudades_clientes
    python manage.py normalizar_ciudades_clientes --dry-run
    python manage.py normalizar_ciudades_clientes --limit 100
    python manage.py normalizar_ciudades_clientes --solo-sin-clasificar

Performance: ~5-10s sobre 15.902 clientes. Lookup en memoria
(precarga las ~65 Ciudades + sus aliases en un dict).
"""

from __future__ import annotations

import re
import time
from collections import Counter
from typing import Dict, List, Optional, Tuple

from django.core.management.base import BaseCommand
from django.db.models import Q

from ventas.models import Ciudad, Cliente


# La lógica de clasificación vive en un único servicio (Plan Geo E0).
from ventas.services.geo_service import get_lookup, clasificar, _normalizar


class Command(BaseCommand):
    help = (
        "Normaliza Cliente.ciudad (texto libre) → Cliente.ciudad_normalizada "
        "+ region_geografica. Respeta ediciones manuales (ciudad_normalizada_manual=True)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='No escribe a DB. Solo reporta distribución.',
        )
        parser.add_argument(
            '--limit', type=int, default=None,
            help='Procesa solo N clientes (útil para testing).',
        )
        parser.add_argument(
            '--solo-sin-clasificar', action='store_true',
            help=(
                "Procesa solo clientes con region_geografica='sin_clasificar'. "
                "Útil para corridas incrementales sin reclasificar todo."
            ),
        )

    # ====================================================================
    # Entry point
    # ====================================================================

    def handle(self, *args, **opts):
        t0 = time.time()
        dry_run = opts['dry_run']
        limit = opts['limit']
        solo_sin_clasificar = opts['solo_sin_clasificar']

        self.stdout.write(self.style.NOTICE(
            f"Normalizar ciudades clientes {'(DRY-RUN)' if dry_run else '(escribiendo)'}"
        ))

        # ---- Precargar lookup (fresco desde el catálogo) ----
        lookup = get_lookup(refresh=True)
        self.stdout.write(
            f"  Ciudades cargadas: {len(lookup.por_canonico)} canónicas "
            f"+ {len(lookup.por_alias)} aliases "
            f"+ extranjero_generico={'sí' if lookup.extranjero_generico else 'NO'}"
        )

        # ---- Construir queryset ----
        qs = Cliente.objects.select_related('comuna').filter(
            ciudad_normalizada_manual=False  # NUNCA tocar manuales
        )
        if solo_sin_clasificar:
            qs = qs.filter(region_geografica='sin_clasificar')
        if limit:
            qs = qs[:limit]

        total = qs.count()
        self.stdout.write(f"  Clientes a procesar: {total}")
        if total == 0:
            self.stdout.write(self.style.SUCCESS("Nada que hacer. Saliendo."))
            return

        # ---- Procesar ----
        stats = Counter()
        no_match_textos = Counter()
        cambios_pendientes: List[Cliente] = []  # buffer para bulk_update

        # IMPORTANTE: usamos bulk_update en lugar de cliente.save() porque
        # Cliente.save() ejecuta un override que valida teléfono — si algún
        # cliente tiene teléfono no soportado (ej. +1 USA), un solo save()
        # lanza ValidationError y aborta TODA la corrida.
        # bulk_update va directo a SQL UPDATE, no ejecuta save(), no valida.
        # Bonus: es ~10x más rápido (1 query por chunk vs 1 por cliente).

        for cliente in qs.iterator(chunk_size=500):
            metodo, nueva_ciudad, nueva_region = self._clasificar(cliente, lookup)
            stats[metodo] += 1

            # Si no match y había texto, registrar para reporte
            if metodo == 'sin_match' and (cliente.ciudad or '').strip():
                no_match_textos[_normalizar(cliente.ciudad)] += 1

            # ¿Cambió algo respecto al estado actual?
            cambio = (
                cliente.ciudad_normalizada_id != (nueva_ciudad.id if nueva_ciudad else None)
                or cliente.region_geografica != nueva_region
            )
            if cambio:
                cliente.ciudad_normalizada = nueva_ciudad
                cliente.region_geografica = nueva_region
                # NO tocamos ciudad_normalizada_manual (sigue False)
                cambios_pendientes.append(cliente)

        # ---- Persistir en bulk (si no es dry-run) ----
        actualizados = len(cambios_pendientes)
        if not dry_run and cambios_pendientes:
            Cliente.objects.bulk_update(
                cambios_pendientes,
                ['ciudad_normalizada', 'region_geografica'],
                batch_size=500,
            )

        # ---- Reporte ----
        elapsed = time.time() - t0
        self._reportar(stats, no_match_textos, actualizados, total, elapsed, dry_run)

    # ====================================================================
    # Clasificación de un cliente (función pura, testeable)
    # ====================================================================

    def _clasificar(self, cliente, lookup):
        """Delega en el servicio único de clasificación (ventas/services/geo_service).
        Devuelve (metodo, ciudad_normalizada | None, region_geografica)."""
        return clasificar(cliente.pais, cliente.ciudad, cliente.comuna, cliente.region, lookup)

    # ====================================================================
    # Reporte
    # ====================================================================

    def _reportar(self, stats, no_match_textos, actualizados, total, elapsed, dry_run):
        modo = '(simulación)' if dry_run else '(persistido)'
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f"✓ Procesados: {total} clientes en {elapsed:.2f}s {modo}"
        ))
        self.stdout.write(f"  Cambios efectivos: {actualizados}")
        self.stdout.write('')
        self.stdout.write('  Distribución por método de clasificación:')
        for metodo in ['match_canonico', 'match_alias', 'inferencia_comuna',
                       'comuna_nacional', 'nacional_inferido',
                       'extranjero_texto', 'extranjero_pais', 'sin_match']:
            n = stats.get(metodo, 0)
            pct = (n / total * 100) if total else 0
            self.stdout.write(f"    {metodo:<25} {n:>6}  ({pct:.1f}%)")

        # Top no-match (para detectar variantes que faltan en el seed)
        if no_match_textos:
            top = no_match_textos.most_common(30)
            self.stdout.write('')
            self.stdout.write(
                f"  Top 30 textos sin match (variantes a evaluar para agregar al seed):"
            )
            for texto, n in top:
                self.stdout.write(f"    {n:>4}  {texto}")
