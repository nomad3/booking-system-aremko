"""Diagnóstico (solo lectura) de la conversión real de Operación Vuelta a Casa.

Responde: de los clientes contactados por WhatsApp en un período, ¿cuántos
compraron de verdad? Compara las compras "amplias" (sin filtros) contra las
reservas atribuidas por la métrica oficial (last-touch, ventana 60d, excluye
cancelado), y clasifica por qué quedan fuera.

Uso:
    python manage.py diagnostico_vuelta_a_casa
    python manage.py diagnostico_vuelta_a_casa --desde 2026-05-08 --hasta 2026-06-07 --ventana 60

NO modifica datos.
"""

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from ventas.models import ContactoWhatsApp, VentaReserva, ReservaServicio, Cliente
from ventas.services.metricas_operadores_service import (
    calcular_metricas_operadores, _mapear_familia,
)


def _d(s):
    return datetime.strptime(s, '%Y-%m-%d').date()


class Command(BaseCommand):
    help = "Diagnóstico de conversión real de Vuelta a Casa (solo lectura)."

    def add_arguments(self, parser):
        parser.add_argument('--desde', default='2026-05-08')
        parser.add_argument('--hasta', default='2026-06-07')
        parser.add_argument('--ventana', type=int, default=60)

    def handle(self, *a, **o):
        tz = timezone.get_current_timezone()
        desde, hasta, VENT = _d(o['desde']), _d(o['hasta']), o['ventana']
        d0 = datetime.combine(desde, datetime.min.time()).replace(tzinfo=tz)
        d1 = datetime.combine(hasta, datetime.max.time()).replace(tzinfo=tz)
        vt = timedelta(days=VENT)
        p = self.stdout.write

        cont = list(ContactoWhatsApp.objects.filter(
            estado='enviado', fecha_envio__gte=d0, fecha_envio__lte=d1,
        ).values('cliente_id', 'fecha_envio', 'operador', 'respondio', 'es_relleno'))

        # ---- 1. Universo ----
        p("\n=== 1. UNIVERSO REAL ===")
        p(f"Mensajes enviados (estado=enviado) en {desde}..{hasta}: {len(cont)}")
        clientes = {c['cliente_id'] for c in cont if c['cliente_id']}
        p(f"Clientes únicos (con cliente_id): {len(clientes)}")
        p(f"Mensajes SIN cliente_id (no atribuibles): {sum(1 for c in cont if not c['cliente_id'])}")
        p(f"Rellenos: {sum(1 for c in cont if c['es_relleno'])} | Óptimos: {sum(1 for c in cont if not c['es_relleno'])}")
        msgs_por_cli = Counter(c['cliente_id'] for c in cont if c['cliente_id'])
        recontactados = sum(1 for v in msgs_por_cli.values() if v > 1)
        p(f"Clientes recontactados (>1 mensaje): {recontactados}")

        # primer/último contacto por cliente
        primer, ultimo = {}, {}
        cont_por_cli = defaultdict(list)
        for c in cont:
            cid = c['cliente_id']
            if not cid:
                continue
            cont_por_cli[cid].append(c)
            f = c['fecha_envio']
            primer[cid] = min(primer.get(cid, f), f)
            ultimo[cid] = max(ultimo.get(cid, f), f)
        for lst in cont_por_cli.values():
            lst.sort(key=lambda c: c['fecha_envio'], reverse=True)

        # ---- reservas de esos clientes desde d0 (amplio, hasta ahora) ----
        res = list(VentaReserva.objects.filter(
            cliente_id__in=clientes, fecha_creacion__gte=d0,
        ).values('id', 'cliente_id', 'fecha_creacion', 'total', 'estado_pago'))
        res_post = [r for r in res if r['fecha_creacion'] >= primer.get(r['cliente_id'], d1)]
        cli_compraron = {r['cliente_id'] for r in res_post}

        # ---- 2. Compras amplias ----
        p("\n=== 2. COMPRAS AMPLIAS (sin filtros de la métrica) ===")
        p(f"Clientes con ≥1 reserva creada DESPUÉS de su mensaje (cualquier estado/ventana): {len(cli_compraron)}")
        p(f"Total de reservas post-mensaje: {len(res_post)}")
        m = calcular_metricas_operadores(desde, hasta, VENT)
        p(f"Métrica OFICIAL → mensajes={m['totales']['mensajes_enviados']}  "
          f"reservas_atribuidas={m['totales']['reservas_atribuidas']}  "
          f"monto=${m['totales']['monto_atribuido']:,}")

        # ---- atribución (réplica de la métrica) ----
        atribuidas = set()
        for r in res:
            if r['estado_pago'] == 'cancelado':
                continue
            fr = r['fecha_creacion']
            for c in cont_por_cli.get(r['cliente_id'], []):
                fe = c['fecha_envio']
                if fe > fr:
                    continue
                if (fr - fe) > vt:
                    break
                atribuidas.add(r['id'])
                break

        # ---- 3. Por qué no se atribuyen ----
        p("\n=== 3. POR QUÉ NO SE ATRIBUYEN (reservas post-mensaje no atribuidas) ===")
        motivos = Counter()
        for r in res_post:
            if r['id'] in atribuidas:
                continue
            if r['estado_pago'] == 'cancelado':
                motivos['cancelado'] += 1
                continue
            fr, cid = r['fecha_creacion'], r['cliente_id']
            prev = [c for c in cont_por_cli.get(cid, []) if c['fecha_envio'] <= fr]
            if not prev:
                motivos['reserva antes del mensaje'] += 1
                continue
            cercano = max(c['fecha_envio'] for c in prev)
            if (fr - cercano) > vt:
                motivos['fuera de ventana 60d'] += 1
            else:
                motivos['otro (revisar)'] += 1
        for k, v in motivos.most_common():
            p(f"  {k}: {v}")
        p(f"  -- estado_pago de TODAS las reservas post-mensaje: {dict(Counter(r['estado_pago'] for r in res_post))}")
        p("  (nota: la métrica solo excluye 'cancelado'; las 'pendiente' SÍ se atribuyen si están en ventana)")

        # ---- 4. Compras múltiples ----
        p("\n=== 4. COMPRAS MÚLTIPLES (>1 reserva post-mensaje) ===")
        porcli = defaultdict(list)
        for r in res_post:
            porcli[r['cliente_id']].append(r)
        mult = sorted([(cid, rs) for cid, rs in porcli.items() if len(rs) > 1],
                      key=lambda x: -len(x[1]))
        p(f"Clientes con >1 reserva post-mensaje: {len(mult)}")
        for cid, rs in mult[:20]:
            cl = Cliente.objects.filter(id=cid).first()
            tot = sum(int(r['total'] or 0) for r in rs)
            fams = self._familias_de({r['id'] for r in rs})
            p(f"  {cl.nombre if cl else cid}: {len(rs)} reservas | ${tot:,} | familias: {sorted(fams)}")

        # ---- 5. Detalle de las atribuidas ----
        p("\n=== 5. DETALLE DE LAS ATRIBUIDAS ===")
        res_by_id = {r['id']: r for r in res}
        for rid in atribuidas:
            r = res_by_id[rid]
            cl = Cliente.objects.filter(id=r['cliente_id']).first()
            op, fmsg = '?', None
            for c in cont_por_cli.get(r['cliente_id'], []):
                if c['fecha_envio'] <= r['fecha_creacion'] and (r['fecha_creacion'] - c['fecha_envio']) <= vt:
                    op, fmsg = c['operador'], c['fecha_envio']
                    break
            fams = self._familias_de({rid})
            p(f"  {cl.nombre if cl else r['cliente_id']} | op={op} | "
              f"msg={fmsg.date() if fmsg else '?'} → reserva={r['fecha_creacion'].date()} | "
              f"familias={sorted(fams)} | ${int(r['total'] or 0):,} | pago={r['estado_pago']}")

        # ---- 6. Interés sin conversión ----
        p("\n=== 6. INTERÉS SIN CONVERSIÓN ===")
        respondieron = {c['cliente_id'] for c in cont if c['respondio'] and c['cliente_id']}
        p(f"Clientes que respondieron: {len(respondieron)}")
        p(f"Respondieron y NO reservaron (post-mensaje): {len(respondieron - cli_compraron)}")
        p(f"Reservaron pero NO habían respondido: {len(cli_compraron - respondieron)}")
        p("")

    def _familias_de(self, reserva_ids):
        fams = set()
        for rs in ReservaServicio.objects.filter(
            venta_reserva_id__in=reserva_ids,
        ).select_related('servicio', 'servicio__categoria'):
            serv = rs.servicio
            cat = serv.categoria.nombre if (serv and serv.categoria_id) else ''
            tipo = serv.tipo_servicio if serv else ''
            fams.add(_mapear_familia(cat, tipo))
        return fams
