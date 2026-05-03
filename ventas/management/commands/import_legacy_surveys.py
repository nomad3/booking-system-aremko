# -*- coding: utf-8 -*-
"""
Importa respuestas históricas del Google Form de encuesta de satisfacción
al modelo EncuestaSatisfaccion (Tarea 1.4 plan maestro Fase A4).

Uso:
    # Dry run (no guarda, solo reporta lo que haría):
    python manage.py import_legacy_surveys --dry-run

    # Probar con 10 filas:
    python manage.py import_legacy_surveys --limit 10 --dry-run

    # Importar todas:
    python manage.py import_legacy_surveys

    # Desde un CSV local en lugar de la URL pública del Google Sheet:
    python manage.py import_legacy_surveys --csv-path /tmp/encuesta.csv

Idempotente: por defecto salta filas ya importadas (matching por timestamp).
Para reimportar todo, usar --reset (cuidado, borra todas las legacy).
"""
import csv
import re
import urllib.request
from datetime import datetime, timedelta
from io import StringIO

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone


DEFAULT_CSV_URL = (
    'https://docs.google.com/spreadsheets/d/'
    '1zksZuPFfKgVOY7o-pEHg0M0XcnNx88Va4488JsODDtc/'
    'export?format=csv&gid=1278969957'
)


# ===== Mapeos de valores legacy → nuevos =====

NPS_TEXT_TO_SCORE = {
    'definitivamente si': 9,
    'probablemente si': 7,
    'no estoy seguro(a)': 5,
    'no estoy seguro': 5,
    'probablemente no': 3,
    'definitivamente no': 1,
}

MASAJE_TEXT_TO_SCORE = {
    'excelente': 5,
    'regular': 3,
    'deficiente': 1,
}

# Map first dominant value (split by comma) -> code
COMO_SE_ENTERO_MAP = {
    'soy cliente': 'soy_cliente',
    'ya los conocia': 'soy_cliente',
    'ya lo conocia': 'soy_cliente',
    'ya lo conocía': 'soy_cliente',
    'ya he ido antes': 'soy_cliente',
    'vivo cerca': 'soy_cliente',
    'instagram': 'instagram',
    'facebook': 'facebook',
    'google': 'google',
    'busqueda en google': 'google',
    'recomendacion de un conocido o familiar': 'recomendacion',
    'recomendación de un conocido o familiar': 'recomendacion',
    'recomendación de un establecimiento turistico': 'recomendacion',
    'recomendacion de un establecimiento turistico': 'recomendacion',
    'familiar': 'recomendacion',
    'tik tok': 'otro',
    'tiktok': 'otro',
    'regalo': 'otro',
    'wsapp': 'otro',
    'letrero en carretera': 'publicidad',
    'publicidad en el camino': 'publicidad',
    'otro': 'otro',
}

SERVICIO_LEGACY_TO_CODE = {
    'arriendo de tinas con hidromasaje': 'tina_hidromasaje',
    'arriendo de tinas sin hidromasaje': 'tina_sin_hidromasaje',
    'masajes': 'masaje',
    'alojamiento en cabañas para dos personas': 'alojamiento',
}


def parse_int_1_5(raw):
    """Parsea calificación 1-5 desde string. Retorna None si no aplica."""
    if not raw:
        return None
    raw = raw.strip()
    if not raw:
        return None
    try:
        v = int(raw)
        if 1 <= v <= 5:
            return v
    except (ValueError, TypeError):
        pass
    return None


def parse_masaje(raw):
    """Convierte 'Excelente / Regular / Deficiente' → 5/3/1."""
    if not raw:
        return None
    return MASAJE_TEXT_TO_SCORE.get(raw.strip().lower())


def parse_nps_from_text(raw):
    """Convierte texto de recomendación → NPS 0-10."""
    if not raw:
        return None
    # Tomar el primer valor antes de coma (a veces hay combinaciones raras)
    primero = raw.split(',')[0].strip().lower()
    return NPS_TEXT_TO_SCORE.get(primero)


def parse_como_se_entero(raw):
    """Toma el primer valor antes de coma y mapea a código.

    Retorna (codigo, texto_original_si_otro).
    """
    if not raw:
        return ('', '')
    primero = raw.split(',')[0].strip()
    primero_low = primero.lower()
    code = COMO_SE_ENTERO_MAP.get(primero_low)
    if code:
        otro = primero if code == 'otro' else ''
        return (code, otro)
    # No matchea ninguna categoría → 'otro' con el texto original
    return ('otro', primero[:200])


def parse_servicios(raw):
    """Convierte 'Arriendo de tinas con hidromasaje, Masajes' → ['tina_hidromasaje', 'masaje']."""
    if not raw:
        return []
    items = [s.strip().lower() for s in raw.split(',') if s.strip()]
    codes = []
    for item in items:
        code = SERVICIO_LEGACY_TO_CODE.get(item)
        if code and code not in codes:
            codes.append(code)
    return codes


def parse_timestamp(raw):
    """Parsea '4/7/2024 10:47:58' (DD/MM/YYYY HH:MM:SS) → datetime aware."""
    if not raw:
        return None
    raw = raw.strip()
    formatos = [
        '%d/%m/%Y %H:%M:%S',
        '%d/%m/%Y %H:%M',
        '%d-%m-%Y %H:%M:%S',
    ]
    for fmt in formatos:
        try:
            naive = datetime.strptime(raw, fmt)
            return timezone.make_aware(naive, timezone.get_current_timezone())
        except ValueError:
            continue
    return None


EMAIL_RE = re.compile(r'[\w\.-]+@[\w\.-]+\.\w+')


def parse_contact_text(raw):
    """De la columna 'Podemos contactarte (nombre y mail)' extrae (acepta_seguimiento, nombre, email).

    - Si dice 'Si' / 'Sí' / 'Si claro' → permite_seguimiento=True, sin nombre/email
    - Si dice 'No' → permite_seguimiento=False
    - Si tiene email → permite_seguimiento=True + extrae email + nombre (resto)
    - Si tiene solo nombre → permite_seguimiento=True + nombre
    - Vacío → todos None
    """
    if not raw:
        return (None, '', '')
    raw = raw.strip()
    if not raw:
        return (None, '', '')
    low = raw.lower()
    if low in ('no', 'no.', 'no gracias'):
        return (False, '', '')
    if low in ('si', 'sí', 'si claro', 'si.', 'sí.', 'sí claro', 'sí, gracias', 'si gracias'):
        return (True, '', '')

    email_match = EMAIL_RE.search(raw)
    email = email_match.group(0) if email_match else ''
    nombre = raw
    if email:
        nombre = raw.replace(email, '').strip(' ,-')
    return (True, nombre[:200], email[:254])


class Command(BaseCommand):
    help = 'Importa respuestas históricas del Google Form a EncuestaSatisfaccion'

    def add_arguments(self, parser):
        parser.add_argument('--csv-url', default=DEFAULT_CSV_URL,
                            help='URL del Google Sheet (export CSV)')
        parser.add_argument('--csv-path', default='',
                            help='Path local de un CSV (alternativa a --csv-url)')
        parser.add_argument('--limit', type=int, default=0,
                            help='Procesar solo N filas (default: todas)')
        parser.add_argument('--dry-run', action='store_true',
                            help='No guarda nada, solo reporta')
        parser.add_argument('--reset', action='store_true',
                            help='Borra todas las encuestas con origen=legacy_google_form antes de importar')
        parser.add_argument('--verbose-rows', action='store_true',
                            help='Imprime detalle de cada fila procesada')

    def handle(self, *args, **opts):
        from ventas.models import EncuestaSatisfaccion, Cliente

        self.stdout.write(self.style.SUCCESS('\n📊 IMPORTACIÓN DE RESPUESTAS LEGACY DE ENCUESTA'))

        # 1. Cargar CSV
        if opts['csv_path']:
            self.stdout.write(f'📄 Leyendo CSV local: {opts["csv_path"]}')
            with open(opts['csv_path'], encoding='utf-8') as f:
                csv_text = f.read()
        else:
            self.stdout.write(f'📥 Descargando CSV: {opts["csv_url"]}')
            req = urllib.request.Request(opts['csv_url'], headers={'User-Agent': 'aremko-import/1.0'})
            with urllib.request.urlopen(req, timeout=30) as resp:
                csv_text = resp.read().decode('utf-8')

        reader = csv.reader(StringIO(csv_text))
        headers = next(reader)
        rows = list(reader)
        self.stdout.write(f'📊 {len(rows)} filas en el CSV (excluyendo header)')

        if opts['limit']:
            rows = rows[:opts['limit']]
            self.stdout.write(self.style.WARNING(f'⚠️ --limit activo: procesando solo {len(rows)} filas'))

        # 2. Reset si pidió
        if opts['reset']:
            count_existing = EncuestaSatisfaccion.objects.filter(origen='legacy_google_form').count()
            if not opts['dry_run']:
                EncuestaSatisfaccion.objects.filter(origen='legacy_google_form').delete()
                self.stdout.write(self.style.WARNING(f'🗑️  Borradas {count_existing} encuestas legacy previas'))
            else:
                self.stdout.write(self.style.WARNING(f'🗑️  [DRY-RUN] Borraría {count_existing} encuestas legacy previas'))

        # 3. Procesar filas
        stats = {
            'creadas': 0, 'duplicadas': 0, 'sin_timestamp': 0, 'error': 0,
            'cliente_match': 0, 'sin_nombre_email': 0,
            'permite_seguimiento_si': 0, 'permite_seguimiento_no': 0,
        }

        for i, row in enumerate(rows, start=1):
            try:
                # Padding por si hay menos columnas
                row = list(row) + [''] * max(0, 18 - len(row))

                fecha_respuesta = parse_timestamp(row[0])
                if not fecha_respuesta:
                    stats['sin_timestamp'] += 1
                    if opts['verbose_rows']:
                        self.stdout.write(self.style.WARNING(f'  Fila {i}: sin timestamp válido ({row[0]!r})'))
                    continue

                # Skip duplicado por timestamp exacto
                if EncuestaSatisfaccion.objects.filter(
                    origen='legacy_google_form',
                    fecha_respuesta=fecha_respuesta,
                ).exists():
                    stats['duplicadas'] += 1
                    if opts['verbose_rows']:
                        self.stdout.write(f'  Fila {i}: duplicada ({fecha_respuesta})')
                    continue

                permite_seg, nombre, email = parse_contact_text(row[16])
                if not nombre and not email:
                    stats['sin_nombre_email'] += 1

                como_code, como_otro = parse_como_se_entero(row[13])
                nps = parse_nps_from_text(row[14])
                servicios = parse_servicios(row[1])

                # Vincular a Cliente por email si encontramos
                cliente = None
                if email:
                    cliente = Cliente.objects.filter(email__iexact=email).first()
                    if cliente:
                        stats['cliente_match'] += 1

                # Aproximar fecha_visita = fecha_respuesta - 1 día (encuesta sale D+1)
                fecha_visita = (fecha_respuesta - timedelta(days=1)).date()

                if permite_seg is True:
                    stats['permite_seguimiento_si'] += 1
                elif permite_seg is False:
                    stats['permite_seguimiento_no'] += 1

                obj = EncuestaSatisfaccion(
                    cliente=cliente,
                    fecha_respuesta=fecha_respuesta,
                    fecha_visita=fecha_visita,
                    origen='legacy_google_form',
                    contacto_nombre=nombre,
                    contacto_email=email,
                    servicios_contratados=servicios,
                    cal_temperatura_tina=parse_int_1_5(row[2]),
                    cal_transparencia_agua=parse_int_1_5(row[3]),
                    cal_limpieza_tinas=parse_int_1_5(row[4]),
                    cal_limpieza_cabana=parse_int_1_5(row[5]),
                    cal_temperatura_cabana=parse_int_1_5(row[6]),
                    cal_limpieza_sala_masajes=parse_int_1_5(row[7]),
                    cal_servicio_masajes=parse_masaje(row[8]),
                    cal_calidad_precio=parse_int_1_5(row[9]),
                    cal_atencion_ventas=parse_int_1_5(row[10]),
                    cal_compra_web=parse_int_1_5(row[11]),
                    cal_atencion_visita=parse_int_1_5(row[12]),
                    nps_score=nps,
                    sugerencias=row[15][:5000] if len(row) > 15 else '',
                    como_se_entero=como_code,
                    como_se_entero_otro=como_otro[:200],
                    permite_seguimiento=permite_seg,
                )

                if opts['dry_run']:
                    if opts['verbose_rows']:
                        self.stdout.write(
                            f'  [DRY] Fila {i}: {fecha_respuesta.date()} '
                            f'NPS={nps} servicios={servicios} masaje_cal={obj.cal_servicio_masajes}'
                        )
                else:
                    with transaction.atomic():
                        obj.save()

                stats['creadas'] += 1

            except Exception as e:
                stats['error'] += 1
                self.stdout.write(self.style.ERROR(f'❌ Fila {i}: {type(e).__name__}: {e}'))

        # 4. Reportar
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=== RESUMEN ==='))
        prefix = '[DRY-RUN] ' if opts['dry_run'] else ''
        for k, v in stats.items():
            self.stdout.write(f'  {prefix}{k}: {v}')

        if not opts['dry_run']:
            total_legacy = EncuestaSatisfaccion.objects.filter(origen='legacy_google_form').count()
            total_all = EncuestaSatisfaccion.objects.count()
            self.stdout.write('')
            self.stdout.write(f'📊 Total encuestas legacy en BD: {total_legacy}')
            self.stdout.write(f'📊 Total encuestas en BD: {total_all}')

        self.stdout.write(self.style.SUCCESS('\n✅ Importación finalizada'))
