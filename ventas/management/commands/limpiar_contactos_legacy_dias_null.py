"""
limpiar_contactos_legacy_dias_null
===================================

Limpieza one-shot solicitada por aremko-cli (2026-05-27 PM):

    "Contactos legacy con dias=None: ocultalos del /siguiente/. El operador
    no tiene contexto para decidir y arrastrar el problema a futuras bandejas.
    Si entraron por bug, lo correcto es excluirlos definitivamente."

Marca como estado='descartado' todos los ContactoWhatsApp en estado
'pendiente' cuyo snapshot `dias_sin_venir_snapshot` es NULL AND el segmento
implica historial real (Campeón/Leal/Regular/Gran Gastador Ocasional).

Esos contactos son artefactos del bug race condition resuelto en commit
`ecdef31` — el cron pre-fix permitía pasar el filtro días mínimos cuando
la taxonomía aún estaba stale en el momento del cron.

Uso:
    python manage.py limpiar_contactos_legacy_dias_null              # dry-run
    python manage.py limpiar_contactos_legacy_dias_null --apply      # ejecuta

Idempotente. Loguea cuántos contactos por segmento.
"""

from __future__ import annotations

from collections import Counter

from django.core.management.base import BaseCommand

from ventas.models import ContactoWhatsApp


SEGMENTOS_CON_HISTORIAL = ('Campeón', 'Leal', 'Regular', 'Gran Gastador Ocasional')


class Command(BaseCommand):
    help = (
        "Marca como descartado los ContactoWhatsApp pendientes con "
        "dias_sin_venir_snapshot=None en segmentos Campeón/Leal/Regular/"
        "GG Ocasional (artefactos del bug race condition pre-fix ecdef31)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply', action='store_true',
            help='Aplica los cambios. Sin esto, dry-run.',
        )

    def handle(self, *args, **opts):
        apply_changes = opts['apply']

        qs = ContactoWhatsApp.objects.filter(
            estado='pendiente',
            dias_sin_venir_snapshot__isnull=True,
            eje_valor_snapshot__in=SEGMENTOS_CON_HISTORIAL,
        )

        total = qs.count()
        por_segmento = Counter(qs.values_list('eje_valor_snapshot', flat=True))
        por_script = Counter(qs.values_list('script__script_id', flat=True))

        self.stdout.write(self.style.NOTICE(
            f"\nLegacy cleanup — contactos pendientes con dias_snap=None "
            f"en segmentos de alto valor"
        ))
        self.stdout.write(f"  Total candidatos: {total}")
        if total == 0:
            self.stdout.write(self.style.SUCCESS("  Nada para limpiar — sistema limpio."))
            return

        self.stdout.write(f"  Por segmento:")
        for seg, n in por_segmento.most_common():
            self.stdout.write(f"    - {seg}: {n}")
        self.stdout.write(f"  Por script:")
        for s, n in por_script.most_common():
            self.stdout.write(f"    - {s}: {n}")

        self.stdout.write(f"\n  Muestra primeros 5:")
        for c in qs.select_related('cliente')[:5]:
            self.stdout.write(
                f"    - cli={c.cliente_id} {c.cliente.nombre[:30]:30} "
                f"P{c.prioridad} script={c.script.script_id} "
                f"fecha_sugerido={c.fecha_sugerido}"
            )

        if not apply_changes:
            self.stdout.write(self.style.WARNING(
                f"\n  DRY-RUN. Re-correr con --apply para ejecutar."
            ))
            return

        n_actualizados = qs.update(estado='descartado')
        self.stdout.write(self.style.SUCCESS(
            f"\n  ✓ {n_actualizados} contactos legacy marcados como descartado"
        ))
