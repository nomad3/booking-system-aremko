"""
diagnosticar_bandeja_dia
=========================

Diagnóstico read-only de la bandeja de un día específico — útil cuando
Jorge ve un número raro de contactos y queremos saber por qué.

Uso:
    python manage.py diagnosticar_bandeja_dia              # hoy
    python manage.py diagnosticar_bandeja_dia --fecha 2026-05-27
    python manage.py diagnosticar_bandeja_dia --cliente "Jorge Aguilera"
    python manage.py diagnosticar_bandeja_dia --telefono 958655810

Reporta:
    1. Inventario por estado/script
    2. Settings de exclusión activos
    3. Si quedaron pendientes del día anterior (arrastre)
    4. Última actualización de ClienteTaxonomia (stale check)
    5. Cliente específico: por qué pasó/falló filtros (si --cliente / --telefono)
    6. Tabla 1-línea por contacto del día con análisis de filtros
"""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta
from typing import Optional

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from ventas.models import Cliente, ClienteTaxonomia, ContactoWhatsApp


class Command(BaseCommand):
    help = "Diagnóstico read-only de bandeja WhatsApp para una fecha."

    def add_arguments(self, parser):
        parser.add_argument('--fecha', type=str, default=None,
                            help='YYYY-MM-DD. Default: hoy.')
        parser.add_argument('--cliente', type=str, default=None,
                            help='Substring del nombre — análisis específico.')
        parser.add_argument('--telefono', type=str, default=None,
                            help='Substring de teléfono — análisis específico.')
        parser.add_argument('--limite-detalle', type=int, default=30,
                            help='Cuántos contactos mostrar en detalle.')

    def handle(self, *args, **opts):
        fecha_str = opts['fecha']
        if fecha_str:
            fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        else:
            fecha = timezone.now().date()
        ayer = fecha - timedelta(days=1)
        limite = opts['limite_detalle']
        cli_filter = opts['cliente']
        tel_filter = opts['telefono']

        sep = '=' * 72
        self.stdout.write(f"\n{sep}\n  DIAGNÓSTICO BANDEJA {fecha}\n{sep}")

        # ────────── 1. INVENTARIO ──────────
        qs = (
            ContactoWhatsApp.objects
            .filter(fecha_sugerido=fecha)
            .select_related('cliente', 'script')
        )
        total = qs.count()
        self.stdout.write(f"\n[1] Total contactos con fecha_sugerido={fecha}: {total}")

        estados = Counter(qs.values_list('estado', flat=True))
        self.stdout.write(f"    Por estado:")
        for e, n in estados.most_common():
            self.stdout.write(f"      - {e}: {n}")

        scripts = Counter(qs.values_list('script__script_id', flat=True))
        self.stdout.write(f"    Por script:")
        for s, n in scripts.most_common():
            self.stdout.write(f"      - {s}: {n}")

        prioridades = Counter(qs.filter(estado='pendiente').values_list('prioridad', flat=True))
        self.stdout.write(f"    Por prioridad (solo pendientes):")
        for p, n in sorted(prioridades.items()):
            self.stdout.write(f"      - P{p}: {n}")

        # ────────── 2. PENDIENTES DE AYER (¿se arrastraron?) ──────────
        pend_ayer = ContactoWhatsApp.objects.filter(
            fecha_sugerido=ayer, estado='pendiente'
        ).count()
        self.stdout.write(
            f"\n[2] Pendientes que quedaron en {ayer} (estado=pendiente): {pend_ayer}"
        )
        self.stdout.write(
            f"    (Si > 0 → el arrastre debió moverlos a {fecha}. "
            f"Si =0 → todos procesados ayer.)"
        )

        # ────────── 3. SETTINGS RELEVANTES ──────────
        iexact = getattr(settings, 'OVC_CLIENTES_EXCLUIDOS_IEXACT', []) or []
        icontains = getattr(settings, 'OVC_CLIENTES_EXCLUIDOS_ICONTAINS', []) or []
        dias_min_map = getattr(settings, 'OVC_DIAS_MINIMO_DESDE_ULTIMA_VISITA', {}) or {}
        max_acum = getattr(settings, 'OVC_DIAS_MAX_ACUMULACION', 7)
        usar_ia = getattr(settings, 'OVC_USAR_VARIACIONES_IA', False)

        self.stdout.write(f"\n[3] Settings:")
        self.stdout.write(f"    OVC_CLIENTES_EXCLUIDOS_IEXACT = {iexact}")
        self.stdout.write(f"    OVC_CLIENTES_EXCLUIDOS_ICONTAINS = {icontains}")
        self.stdout.write(f"    OVC_DIAS_MINIMO_DESDE_ULTIMA_VISITA = {dias_min_map}")
        self.stdout.write(f"    OVC_DIAS_MAX_ACUMULACION = {max_acum}")
        self.stdout.write(f"    OVC_USAR_VARIACIONES_IA = {usar_ia}")

        # ────────── 4. ÚLTIMA ACTUALIZACIÓN TAXONOMÍA ──────────
        ultima_tax = (
            ClienteTaxonomia.objects.order_by('-actualizado').first()
            if hasattr(ClienteTaxonomia, 'actualizado')
            else ClienteTaxonomia.objects.order_by('-id').first()
        )
        if ultima_tax:
            fecha_act = (
                getattr(ultima_tax, 'actualizado', None)
                or getattr(ultima_tax, 'fecha_calculo', None)
            )
            self.stdout.write(
                f"\n[4] Última actualización ClienteTaxonomia: "
                f"cliente_id={ultima_tax.cliente_id} fecha={fecha_act}"
            )
            if fecha_act:
                delta = timezone.now() - fecha_act if hasattr(fecha_act, 'tzinfo') else None
                if delta:
                    self.stdout.write(
                        f"    Hace ~{delta.total_seconds()/3600:.1f}h. "
                        f"{'⚠ STALE (>26h)' if delta.total_seconds() > 26*3600 else 'fresca'}"
                    )

        # ────────── 5. CLIENTE ESPECÍFICO ──────────
        if cli_filter or tel_filter:
            self.stdout.write(f"\n[5] Análisis cliente específico:")
            clientes_match = Cliente.objects.all()
            if cli_filter:
                clientes_match = clientes_match.filter(nombre__icontains=cli_filter)
            if tel_filter:
                clientes_match = clientes_match.filter(telefono__icontains=tel_filter)

            for cli in clientes_match[:5]:
                self._reporte_cliente(cli, iexact, icontains, dias_min_map, fecha)

        # ────────── 6. DETALLE LÍNEA POR LÍNEA DE PENDIENTES ──────────
        self.stdout.write(
            f"\n[6] Detalle de los primeros {limite} pendientes "
            f"(orden por prioridad ASC, id DESC):"
        )
        self.stdout.write(
            f"    {'#':>3} {'cli_id':>6} {'P':>2} {'nombre':30} {'tel':>9} "
            f"| {'eje_valor':12} {'dias':>5} {'min':>3} {'check':5} "
            f"| {'fecha_envio':16} {'estado':10}"
        )
        for i, c in enumerate(
            qs.filter(estado='pendiente').order_by('prioridad', '-id')[:limite], 1
        ):
            cli = c.cliente
            tax = getattr(cli, 'taxonomia', None)
            eje_v = (tax.eje_valor if tax else '?')[:12]
            dias = tax.dias_desde_ultima_visita if tax else None
            dias_min = dias_min_map.get(eje_v.strip(), 0)
            # ¿debería haber sido bloqueado por filtro días mínimos?
            bloqueado_filtro = (
                dias_min > 0 and dias is not None and dias < dias_min
            )
            marker = (
                '⚠BUG' if bloqueado_filtro
                else ('—' if dias_min == 0 else 'ok')
            )
            tel_short = (cli.telefono or '?')[-9:]
            nombre_short = (cli.nombre or '?')[:30]
            fecha_envio = c.fecha_envio.strftime('%Y-%m-%d %H:%M') if c.fecha_envio else '-'
            self.stdout.write(
                f"    {i:>3} {cli.id:>6} P{c.prioridad} {nombre_short:30} {tel_short:>9} "
                f"| {eje_v:12} {str(dias):>5} {str(dias_min):>3} {marker:5} "
                f"| {fecha_envio:16} {c.estado:10}"
            )

        # ────────── 7. CONTACTOS HISTÓRICOS PARA ESTE CLIENTE EN BANDEJA ──────────
        self.stdout.write(
            f"\n[7] Para los pendientes de HOY, ¿qué pasó con su contacto "
            f"de días anteriores? (busca último 'no_aplica' / 'descartado' / "
            f"'bloqueado' por cliente):"
        )
        for c in qs.filter(estado='pendiente').order_by('prioridad', '-id')[:limite]:
            anteriores = (
                ContactoWhatsApp.objects
                .filter(cliente_id=c.cliente_id)
                .exclude(fecha_sugerido=fecha)
                .order_by('-fecha_sugerido')[:3]
            )
            if anteriores:
                hist = ', '.join(
                    f"{a.fecha_sugerido}:{a.estado}" for a in anteriores
                )
                self.stdout.write(f"    cli={c.cliente_id} {c.cliente.nombre[:25]:25} → {hist}")

        self.stdout.write(f"\n{sep}\n  FIN DIAGNÓSTICO\n{sep}\n")

    def _reporte_cliente(
        self, cli: Cliente, iexact: list, icontains: list,
        dias_min_map: dict, fecha: date,
    ):
        """Detalle completo de UN cliente — por qué pasó / no pasó filtros."""
        tax = getattr(cli, 'taxonomia', None)
        self.stdout.write(f"\n    ───── cliente_id={cli.id} ─────")
        self.stdout.write(f"    nombre (literal, con quotes): '{cli.nombre}'")
        self.stdout.write(f"    len(nombre)={len(cli.nombre or '')}  "
                          f"repr={repr(cli.nombre)}")
        self.stdout.write(f"    telefono: {cli.telefono}")
        self.stdout.write(f"    opt_out_whatsapp: {cli.opt_out_whatsapp}")
        self.stdout.write(f"    proximo_contacto_no_antes_de: "
                          f"{cli.proximo_contacto_no_antes_de}")
        self.stdout.write(f"    ultimo_contacto_outbound: "
                          f"{cli.ultimo_contacto_outbound}")
        if tax:
            self.stdout.write(f"    tax.eje_valor: '{tax.eje_valor}'")
            self.stdout.write(f"    tax.dias_desde_ultima_visita: "
                              f"{tax.dias_desde_ultima_visita}")
            self.stdout.write(f"    tax.ultima_visita: {tax.ultima_visita}")
            actualizado = getattr(tax, 'actualizado', None)
            if actualizado:
                self.stdout.write(f"    tax.actualizado: {actualizado}")
        else:
            self.stdout.write(f"    ⚠ sin ClienteTaxonomia")

        # Matching contra filtros de exclusión
        nombre = cli.nombre or ''
        nombre_lower = nombre.lower().strip()
        matches_iexact = [p for p in iexact if nombre.lower() == p.lower()]
        matches_iexact_trim = [p for p in iexact if nombre_lower == p.lower().strip()]
        matches_icontains = [p for p in icontains if p.lower() in nombre_lower]
        self.stdout.write(f"    matches iexact exacto: {matches_iexact}")
        self.stdout.write(f"    matches iexact con trim: {matches_iexact_trim}")
        self.stdout.write(f"    matches icontains: {matches_icontains}")

        # ¿Filtro días mínimos debería bloquear?
        if tax:
            dmin = dias_min_map.get(tax.eje_valor, 0)
            ddias = tax.dias_desde_ultima_visita
            if dmin > 0 and ddias is not None and ddias < dmin:
                self.stdout.write(
                    self.style.WARNING(
                        f"    ⚠ FILTRO DÍAS MÍNIMOS DEBÍA BLOQUEAR: "
                        f"{tax.eje_valor} requiere {dmin}d, tiene {ddias}d"
                    )
                )

        # Contactos históricos de este cliente
        contactos = ContactoWhatsApp.objects.filter(
            cliente_id=cli.id
        ).order_by('-fecha_sugerido')[:5]
        if contactos:
            self.stdout.write(f"    Últimos 5 ContactoWhatsApp:")
            for c in contactos:
                self.stdout.write(
                    f"      - {c.fecha_sugerido} estado={c.estado} "
                    f"script={c.script.script_id} P{c.prioridad}"
                )
