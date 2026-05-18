"""
Comando para scrapear sitios web de competidores y crear snapshots.
Uso: python manage.py scrape_competitors
"""
import json
import re
from decimal import Decimal

from django.core.management.base import BaseCommand
from ventas.models import Competitor, CompetitorSnapshot
import requests
from bs4 import BeautifulSoup

# Umbral para detectar respuestas vacias / anti-bot.
MIN_HTML_BYTES = 500

# Rango razonable de precios para una "entrada general" en CLP.
PRECIO_MIN = 5000
PRECIO_MAX = 80000

# Patrones de precio (en orden de especificidad).
# Capturan: $24.000, $ 24000, CLP 24.000, 24000 CLP, 24.000 CLP, $24.000.-, etc.
PRECIO_PATTERNS = [
    r'\$\s*(\d{1,3}(?:[\.,]\d{3})+|\d{4,6})',          # $24.000 / $24,000 / $24000
    r'\bCLP\s*\$?\s*(\d{1,3}(?:[\.,]\d{3})+|\d{4,6})', # CLP 24.000 / CLP $24.000
    r'(\d{1,3}(?:[\.,]\d{3})+|\d{4,6})\s*CLP\b',      # 24.000 CLP / 24000 CLP
    r'(\d{1,3}(?:[\.,]\d{3})+|\d{4,6})\s*pesos?\b',   # 24.000 pesos
]


def _parse_precio(precio_str):
    """Limpia y convierte un string a int. None si no es un precio razonable."""
    try:
        limpio = precio_str.replace('.', '').replace(',', '').strip()
        precio = int(limpio)
        if PRECIO_MIN <= precio <= PRECIO_MAX:
            return precio
    except (ValueError, TypeError):
        pass
    return None


def _extraer_precios_jsonld(soup):
    """Lee bloques <script type=application/ld+json> y extrae fields 'price'.

    Muchas webs (especialmente WordPress + plugins SEO) declaran precios via
    schema.org en JSON-LD. Es el formato mas estable para scrapear.
    """
    precios = []
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            data = json.loads(script.string or '')
        except (json.JSONDecodeError, TypeError):
            continue

        nodos = data if isinstance(data, list) else [data]
        for nodo in nodos:
            _walk_jsonld(nodo, precios)
    return precios


def _walk_jsonld(obj, precios):
    """Recorre recursivamente buscando claves 'price' / 'lowPrice' / 'priceSpecification'."""
    if isinstance(obj, dict):
        for key in ('price', 'lowPrice', 'highPrice'):
            val = obj.get(key)
            if val is not None:
                p = _parse_precio(str(val))
                if p:
                    precios.append(p)
        for v in obj.values():
            _walk_jsonld(v, precios)
    elif isinstance(obj, list):
        for item in obj:
            _walk_jsonld(item, precios)


class Command(BaseCommand):
    help = 'Scrapea sitios web de competidores y crea snapshots'

    def add_arguments(self, parser):
        parser.add_argument(
            '--competitor',
            type=str,
            help='Nombre del competidor específico a scrapear',
        )

    def handle(self, *args, **options):
        if options['competitor']:
            competitors = Competitor.objects.filter(nombre=options['competitor'], activo=True)
        else:
            competitors = Competitor.objects.filter(activo=True)

        if not competitors.exists():
            self.stdout.write(self.style.ERROR('No se encontraron competidores activos'))
            return

        self.stdout.write(self.style.SUCCESS(f'Scrapeando {competitors.count()} competidor(es)...'))

        for competitor in competitors:
            self.stdout.write(f'\n🔍 Scrapeando: {competitor.nombre} ({competitor.website})')

            try:
                snapshot = self.scrape_competitor(competitor)
                snapshot.save()
                self.stdout.write(self.style.SUCCESS(f'  ✓ Snapshot creado exitosamente'))

                # Mostrar resumen
                if snapshot.precio_entrada_adulto:
                    self.stdout.write(f'    Precio adulto: ${snapshot.precio_entrada_adulto:,.0f}')
                servicios = []
                if snapshot.tiene_piscinas_termales:
                    servicios.append('Piscinas termales')
                if snapshot.tiene_masajes:
                    servicios.append('Masajes')
                if snapshot.tiene_restaurant:
                    servicios.append('Restaurant')
                if snapshot.tiene_alojamiento:
                    servicios.append('Alojamiento')
                if servicios:
                    self.stdout.write(f'    Servicios: {", ".join(servicios)}')

            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  ✗ Error: {str(e)}'))

        self.stdout.write(self.style.SUCCESS(f'\n✓ Scraping completado!'))

    def scrape_competitor(self, competitor):
        """Scrapea un competidor y retorna un CompetitorSnapshot."""
        snapshot = CompetitorSnapshot(competitor=competitor)

        try:
            # User agent realista (algunos sitios devuelven 403 con UAs default).
            headers = {
                'User-Agent': (
                    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/120.0.0.0 Safari/537.36'
                ),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'es-CL,es;q=0.9,en;q=0.8',
            }
            response = requests.get(competitor.website, headers=headers, timeout=15, allow_redirects=True)
            response.raise_for_status()

            html_content = response.text

            # Detectar respuestas vacias / shells JS: si el HTML es muy chico
            # probablemente es un sitio JS-heavy o detras de anti-bot.
            if len(html_content) < MIN_HTML_BYTES:
                snapshot.scraping_exitoso = False
                snapshot.error_mensaje = (
                    f'Respuesta vacia o muy pequeña ({len(html_content)} bytes). '
                    f'HTTP {response.status_code}, URL final: {response.url}. '
                    'Probable sitio JS-heavy o anti-bot — requiere Playwright/JS rendering.'
                )
                return snapshot

            soup = BeautifulSoup(html_content, 'html.parser')

            # Extraer meta description
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if meta_desc:
                snapshot.meta_description = meta_desc.get('content', '')[:300]

            # Texto completo de la página (para buscar keywords)
            page_text = soup.get_text().lower()

            # Detectar servicios basado en keywords
            snapshot.tiene_piscinas_termales = any(word in page_text for word in ['piscina', 'termal', 'termas'])
            snapshot.tiene_masajes = 'masaje' in page_text or 'spa' in page_text
            snapshot.tiene_restaurant = 'restaurant' in page_text or 'cafetería' in page_text or 'gastronomía' in page_text
            snapshot.tiene_alojamiento = 'alojamiento' in page_text or 'hospedaje' in page_text or 'cabañas' in page_text or 'hotel' in page_text

            # Extraer precios: priorizar JSON-LD (schema.org), luego regex en HTML.
            precios_jsonld = _extraer_precios_jsonld(soup)
            precios_html = []
            for pattern in PRECIO_PATTERNS:
                for match in re.findall(pattern, html_content, flags=re.IGNORECASE):
                    p = _parse_precio(match)
                    if p:
                        precios_html.append(p)

            # JSON-LD es mas confiable porque no tiene falsos positivos. Si hay, usar eso.
            precios = precios_jsonld or precios_html

            if precios:
                # Usar el precio mas bajo como referencia para entrada adulto.
                # (Asumimos que el mas barato suele ser la entrada general adulto.)
                snapshot.precio_entrada_adulto = Decimal(min(precios))

            # Buscar horarios
            horario_keywords = ['horario', 'hora', 'abierto', 'atención']
            for keyword in horario_keywords:
                if keyword in page_text:
                    # Intentar encontrar el párrafo que contiene el horario
                    for p in soup.find_all(['p', 'div', 'span']):
                        p_text = p.get_text()
                        if keyword in p_text.lower() and len(p_text) < 200:
                            snapshot.horario_texto = p_text.strip()[:500]
                            break
                if snapshot.horario_texto:
                    break

            # Buscar promociones
            promo_keywords = ['promoción', 'oferta', 'descuento', 'especial']
            for keyword in promo_keywords:
                if keyword in page_text:
                    for p in soup.find_all(['p', 'div', 'h2', 'h3']):
                        p_text = p.get_text()
                        if keyword in p_text.lower() and len(p_text) < 300:
                            snapshot.promociones = p_text.strip()
                            break
                if snapshot.promociones:
                    break

            snapshot.scraping_exitoso = True

        except requests.RequestException as e:
            snapshot.scraping_exitoso = False
            snapshot.error_mensaje = f'Error de red: {str(e)}'
        except Exception as e:
            snapshot.scraping_exitoso = False
            snapshot.error_mensaje = f'Error de parsing: {str(e)}'

        return snapshot
