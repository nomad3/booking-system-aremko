# -*- coding: utf-8 -*-
"""¿Qué se paga todos los meses, y cuándo? (pedido de Jorge 2026-08-10)

Recorre TODAS las cuentas y agrupa los gastos por comercio para mostrar el
patrón real de cobro: cuántas veces, qué días, qué montos y cada cuántos días.
Sirve para llenar los «costos de servicios web» con fechas de verdad en vez de
suponerlas — y para ver los casos raros que Jorge describe: Facebook cobra
varias veces al mes, y Google Ads es mensual salvo que se alcance el umbral de
facturación y cobre también a mitad de mes.

SOLO LECTURA. Con --vincular actualiza las fechas de ServicioWeb.

    python manage.py detectar_recurrentes
    python manage.py detectar_recurrentes --desde 2026-06-01 --min 2
    python manage.py detectar_recurrentes --vincular
"""
import re
from collections import defaultdict
from datetime import date, timedelta
from statistics import median

from django.core.management.base import BaseCommand

# Alias → nombre legible. Los bancos escriben el mismo comercio de diez formas
# ("FACEBK *AB12", "PAGO Facebook", "META PLATFORMS"): sin esta tabla el mismo
# servicio aparece como cinco comercios distintos y no se ve la recurrencia.
ALIAS_COMERCIO = [
    (('FACEBK', 'FACEBOOK', 'META PLATFORMS', 'META ADS'), 'Meta Ads'),
    (('GOOGLE ADS', 'GOOGLE*ADS', 'GOOGLEADS'), 'Google Ads'),
    (('GOOGLE CLOUD', 'GOOGLE*CLOUD', 'GSUITE', 'GOOGLE WORKSPACE'), 'Google Cloud/Workspace'),
    (('RENDER.COM', 'RENDER COM', 'RENDERCOM'), 'Render'),
    (('TWILIO', 'SENDGRID'), 'Twilio/SendGrid'),
    (('CLOUDINARY',), 'Cloudinary'),
    (('ANTHROPIC', 'CLAUDE.AI'), 'Anthropic'),
    (('OPENAI', 'CHATGPT'), 'OpenAI'),
    (('OPENROUTER',), 'OpenRouter'),
    (('DATAFORSEO', 'FS DATAFORSEO'), 'DataForSEO'),
    (('ECERT',), 'eCert'),
    (('APPLE.COM', 'APPLE COM'), 'Apple'),
    (('CRELL',), 'Crell (energía)'),
    (('MOVISTAR', 'ENTEL', 'WOM', 'CLARO'), 'Telefonía'),
    (('COPEC', 'SHELL', 'PETROBRAS'), 'Combustible'),
    (('JUMBO', 'LIDER', 'UNIMARC', 'SANTA ISABEL'), 'Supermercado'),
    (('VERCEL',), 'Vercel'),
    (('SUMUP',), 'SumUp'),
]

_RE_PREFIJO = re.compile(
    r'^(cartola [a-z_ ]+:|tarjeta:|traspaso [a-z ]+:|pago automatico|pago|compra)\s+',
    re.IGNORECASE)
_RE_BASURA = re.compile(r'[*#]|\b\d{3,}\b|\b[0-9]{2,}[A-Z]\b|\bN[º°]\s*\S+')


def nombre_comercio(descripcion):
    """Descripción del banco → nombre de comercio comparable.

    Función pura. Quita el prefijo que le pone la carga («Cartola alda: »),
    los identificadores de transacción y los números largos, y aplica la tabla
    de alias. Lo que queda son las primeras palabras significativas.
    """
    texto = _RE_PREFIJO.sub('', (descripcion or '').strip())
    arriba = texto.upper()
    for patrones, nombre in ALIAS_COMERCIO:
        if any(p in arriba for p in patrones):
            return nombre
    limpio = _RE_BASURA.sub(' ', arriba)
    palabras = [p for p in limpio.split() if len(p) > 1]
    return ' '.join(palabras[:3]).title() or 'Sin descripción'


def patron_de(fechas):
    """(etiqueta, intervalo mediano en días) a partir de las fechas de cobro."""
    if len(fechas) < 2:
        return 'una sola vez', None
    dias = [(b - a).days for a, b in zip(fechas, fechas[1:])]
    tipico = int(median(dias))
    por_mes = defaultdict(int)
    for f in fechas:
        por_mes[(f.year, f.month)] += 1
    promedio = sum(por_mes.values()) / len(por_mes)
    if promedio >= 1.6:
        return f'varias veces al mes (~{promedio:.1f})', tipico
    if 25 <= tipico <= 35:
        return 'mensual', tipico
    if 6 <= tipico <= 8:
        return 'semanal', tipico
    if tipico <= 5:
        return 'muy seguido', tipico
    return f'cada ~{tipico} días', tipico


class Command(BaseCommand):
    help = 'Detecta los gastos recurrentes y sus fechas, en todas las cuentas.'

    def add_arguments(self, parser):
        parser.add_argument('--desde', default='2026-07-01')
        parser.add_argument('--min', type=int, default=2,
                            help='Mínimo de cobros para considerarlo recurrente.')
        parser.add_argument('--vincular', action='store_true',
                            help='Actualiza las fechas en costos_web.ServicioWeb.')

    def handle(self, *args, **opts):
        from finanzas.models import MovimientoFinanciero

        desde = date.fromisoformat(opts['desde'])
        movs = (MovimientoFinanciero.objects
                .filter(clase='gasto', fecha__gte=desde)
                .select_related('cuenta', 'categoria').order_by('fecha'))

        grupos = defaultdict(list)
        for m in movs:
            grupos[nombre_comercio(m.descripcion)].append(m)

        recurrentes = {k: v for k, v in grupos.items() if len(v) >= opts['min']}
        sueltos = {k: v for k, v in grupos.items() if len(v) < opts['min']}

        self.stdout.write(f'Desde {desde} · {movs.count()} gastos · '
                          f'{len(recurrentes)} comercios recurrentes · '
                          f'{len(sueltos)} con menos de {opts["min"]} cobros\n')

        orden = sorted(recurrentes.items(),
                       key=lambda kv: -sum(int(m.monto) for m in kv[1]))
        for nombre, lista in orden:
            fechas = [m.fecha for m in lista]
            etiqueta, intervalo = patron_de(fechas)
            total = sum(int(m.monto) for m in lista)
            montos = sorted(int(m.monto) for m in lista)
            dias_mes = sorted({f.day for f in fechas})
            cuentas = sorted({m.cuenta.nombre for m in lista})
            self.stdout.write(
                f'\n{nombre}  —  {len(lista)} cobros · '
                f'total ${total:,} · típico ${int(median(montos)):,}'
                .replace(',', '.'))
            self.stdout.write(f'   patrón: {etiqueta}'
                              + (f' · cada ~{intervalo} días' if intervalo else ''))
            self.stdout.write(f'   días del mes: {", ".join(map(str, dias_mes))}')
            self.stdout.write(f'   cuentas: {", ".join(cuentas)}')
            for m in lista[-6:]:
                cat = m.categoria.nombre if m.categoria else 'sin categoría'
                self.stdout.write(
                    f'      {m.fecha}  ${int(m.monto):>10,}  {cat}'
                    .replace(',', '.'))
            if intervalo:
                proxima = fechas[-1] + timedelta(days=intervalo)
                self.stdout.write(f'   → próximo cobro estimado: {proxima}')

        if opts['vincular']:
            self._vincular(recurrentes)

    def _vincular(self, recurrentes):
        """Escribe las fechas reales en los servicios web ya registrados.

        No crea servicios: solo actualiza los que existen y cuyo nombre calza,
        para no llenar el tablero de filas que nadie pidió.
        """
        from costos_web.models import ServicioWeb

        actualizados = 0
        for servicio in ServicioWeb.objects.all():
            clave = servicio.nombre.strip().upper()
            calce = next((lista for nombre, lista in recurrentes.items()
                          if clave in nombre.upper() or nombre.upper() in clave),
                         None)
            if not calce:
                continue
            fechas = [m.fecha for m in calce]
            _, intervalo = patron_de(fechas)
            servicio.ultima_fecha_pago = fechas[-1]
            if intervalo:
                servicio.proxima_fecha_pago = fechas[-1] + timedelta(days=intervalo)
            servicio.save(update_fields=['ultima_fecha_pago',
                                         'proxima_fecha_pago'])
            actualizados += 1
            self.stdout.write(f'  ✓ {servicio.nombre}: última {fechas[-1]} · '
                              f'próxima {servicio.proxima_fecha_pago}')
        self.stdout.write(f'\nServicios web actualizados: {actualizados}')
