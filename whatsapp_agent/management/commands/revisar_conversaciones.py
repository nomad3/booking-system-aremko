# -*- coding: utf-8 -*-
"""Vuelca conversaciones reales de WhatsApp (WhatsAppMessage) para revisión cualitativa
del tono/estilo de Luna — NO modifica nada, solo lee y muestra en consola.

Jorge (2026-07-01): quiere revisar cómo conversa Luna hoy con clientes reales, para
rediseñarla como "consejera boutique" en vez de "mostrador de precios".

Teléfonos MASCARADOS (solo últimos 4 dígitos) — no hace falta el número completo
para juzgar tono/estilo, y así el volcado es más liviano de pegar/leer.

Nota: 'out' (saliente) puede ser Luna (automático) O Deborah (manual) — el modelo
WhatsAppMessage no distingue quién lo mandó a nivel de mensaje individual.

Uso:
    python manage.py revisar_conversaciones
    python manage.py revisar_conversaciones --limit 40 --min-mensajes 4
    python manage.py revisar_conversaciones --desde 2026-06-01
"""
from datetime import datetime, timezone as dt_timezone
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Vuelca conversaciones de WhatsApp (solo lectura) para revisión de tono/estilo de Luna."

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=30,
                             help='Cuántas conversaciones (teléfonos) mostrar, más recientes primero (default 30).')
        parser.add_argument('--min-mensajes', type=int, default=3,
                             help='Ignorar conversaciones con menos mensajes que esto (default 3, filtra ruido).')
        parser.add_argument('--desde', type=str, default=None,
                             help='Fecha YYYY-MM-DD: solo conversaciones con algún mensaje desde esa fecha.')

    def handle(self, *args, **opts):
        from django.db.models import Max, Count
        from ventas.models import WhatsAppMessage as WAMsg

        limit = opts['limit']
        min_msgs = opts['min_mensajes']
        desde = opts.get('desde')

        qs = WAMsg.objects.all()
        if desde:
            try:
                fecha = datetime.strptime(desde, '%Y-%m-%d').replace(tzinfo=dt_timezone.utc)
                qs = qs.filter(timestamp__gte=fecha)
            except ValueError:
                self.stderr.write(self.style.ERROR(f"Fecha inválida: {desde} (usa YYYY-MM-DD)"))
                return

        agg = list(
            qs.values('phone')
            .annotate(ultimo_ts=Max('timestamp'), total=Count('id'))
            .filter(total__gte=min_msgs)
            .order_by('-ultimo_ts')[:limit]
        )

        total_msgs_global = WAMsg.objects.count()
        total_conversaciones_global = WAMsg.objects.values('phone').distinct().count()

        self.stdout.write(self.style.SUCCESS(
            f"\n=== RESUMEN GLOBAL ===\n"
            f"Total mensajes en BD: {total_msgs_global}\n"
            f"Total conversaciones (teléfonos distintos): {total_conversaciones_global}\n"
            f"Mostrando: {len(agg)} conversaciones (más recientes, min {min_msgs} mensajes)\n"
            f"{'='*60}\n"
        ))

        for i, a in enumerate(agg, 1):
            phone = a['phone'] or '(sin teléfono)'
            phone_mask = f"...{phone[-4:]}" if len(phone) >= 4 else phone
            msgs = list(
                WAMsg.objects.filter(phone=a['phone']).order_by('timestamp')
                .values('direction', 'body', 'msg_type', 'timestamp', 'requiere_atencion')
            )
            self.stdout.write(f"\n{'─'*60}\nCONVERSACIÓN {i}/{len(agg)} · tel {phone_mask} · {len(msgs)} mensajes\n{'─'*60}")
            for m in msgs:
                quien = 'CLIENTE' if m['direction'] == 'in' else 'AREMKO(Luna/Deborah)'
                ts = m['timestamp'].strftime('%Y-%m-%d %H:%M') if m['timestamp'] else '?'
                body = (m['body'] or f"[{m['msg_type']}]").replace('\n', ' ⏎ ')
                self.stdout.write(f"[{ts}] {quien}: {body}")

        self.stdout.write(self.style.SUCCESS(f"\n{'='*60}\nFIN — {len(agg)} conversaciones mostradas.\n"))
