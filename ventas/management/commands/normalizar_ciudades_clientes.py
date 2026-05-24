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


# Marcadores textuales de país NO-Chile (case-insensitive en match).
# Si la ciudad del cliente contiene cualquiera, se marca extranjero.
MARCADORES_EXTRANJERO = [
    'argentina', 'brasil', 'brazil', 'uruguay', 'peru', 'perú', 'bolivia',
    'colombia', 'ecuador', 'usa', 'eeuu', 'ee.uu', 'estados unidos',
    'mexico', 'méxico', 'españa', 'spain', 'francia', 'france',
    'alemania', 'germany', 'italia', 'italy', 'inglaterra', 'uk',
    'noruega', 'norway', 'bélgica', 'belgium', 'belgica',
    'buenos aires', 'mendoza', 'sao paulo', 'são paulo', 'sao pablo',
    'rio de janeiro', 'lima', 'madrid', 'barcelona', 'paris', 'london',
    'miami', 'new york', 'denver', 'dallas', 'guadalajara',
    'oslo', 'bruselas', 'brussels', 'neuquén', 'neuquen', 'santa fe, nm',
]


def _normalizar(texto: str) -> str:
    """Normalización para comparación: lower + trim + collapse espacios + sin puntos."""
    if not texto:
        return ''
    s = texto.strip().lower()
    s = re.sub(r'\s+', ' ', s)
    s = s.replace('.', '').replace(',', '')
    return s


def _es_extranjero_por_texto(texto: str) -> bool:
    """True si contiene marcador inequívoco de país no-Chile."""
    if not texto:
        return False
    s = texto.lower()
    return any(m in s for m in MARCADORES_EXTRANJERO)


class _LookupCiudades:
    """Preindex de Ciudades para lookup O(1) en memoria."""

    def __init__(self):
        # Mapa: texto_normalizado → instancia Ciudad
        self.por_canonico: Dict[str, Ciudad] = {}
        self.por_alias: Dict[str, Ciudad] = {}
        self.extranjero_generico: Optional[Ciudad] = None
        self._cargar()

    def _cargar(self):
        for ciudad in Ciudad.objects.filter(activo=True):
            if ciudad.nombre_canonico == '_otros_extranjero_':
                self.extranjero_generico = ciudad
                continue
            self.por_canonico[_normalizar(ciudad.nombre_canonico)] = ciudad
            for alias in ciudad.aliases_list():
                self.por_alias[_normalizar(alias)] = ciudad

    def lookup(self, texto: str) -> Optional[Ciudad]:
        """Busca por canónico, luego por alias. Devuelve Ciudad o None."""
        if not texto:
            return None
        clave = _normalizar(texto)
        if not clave:
            return None
        # 1. Canónico exacto
        c = self.por_canonico.get(clave)
        if c:
            return c
        # 2. Alias exacto
        return self.por_alias.get(clave)


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

        # ---- Precargar lookup ----
        lookup = _LookupCiudades()
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

    def _clasificar(
        self, cliente, lookup: _LookupCiudades
    ) -> Tuple[str, Optional[Ciudad], str]:
        """Devuelve (metodo, ciudad_normalizada | None, region_geografica).

        Métodos posibles:
            match_canonico  — el texto coincide con un Ciudad.nombre_canonico
            match_alias     — el texto coincide con un alias
            inferencia_comuna — sin ciudad, pero comuna mapea a una Ciudad
            extranjero_texto — el texto contiene marcador de país no-Chile
            extranjero_pais  — Cliente.pais explícito != Chile
            sin_match       — nada cumple → sin_clasificar
        """
        ciudad_texto = (cliente.ciudad or '').strip()
        pais_texto = (cliente.pais or '').strip().lower()

        # 1+2. Match contra ciudad text (canónico o alias)
        if ciudad_texto:
            # 4. Primero detección extranjero por texto (gana sobre canónico
            #    en caso ambiguo — ej "Río Negro Argentina" debería ser extranjero)
            if _es_extranjero_por_texto(ciudad_texto):
                ciudad_extra = lookup.extranjero_generico
                return ('extranjero_texto', ciudad_extra, 'extranjero')

            match = lookup.lookup(ciudad_texto)
            if match:
                metodo = 'match_canonico' if _normalizar(ciudad_texto) in lookup.por_canonico else 'match_alias'
                return (metodo, match, match.region_geografica)

        # 5. País explícito no-Chile (sin ciudad reconocida)
        if pais_texto and pais_texto not in ('chile', 'cl', ''):
            return ('extranjero_pais', lookup.extranjero_generico, 'extranjero')

        # 3. Inferencia desde comuna (solo si no había ciudad o no matcheó)
        if cliente.comuna and cliente.comuna.nombre:
            match = lookup.lookup(cliente.comuna.nombre)
            if match:
                return ('inferencia_comuna', match, match.region_geografica)

        # Sin match
        return ('sin_match', None, 'sin_clasificar')

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
