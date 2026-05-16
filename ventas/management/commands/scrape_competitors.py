"""
Comando para scrapear sitios web de competidores y crear snapshots.
Uso: python manage.py scrape_competitors
"""
from django.core.management.base import BaseCommand
from ventas.models import Competitor, CompetitorSnapshot
import requests
from bs4 import BeautifulSoup
import re
from decimal import Decimal


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
            # Hacer request con timeout y user agent
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }
            response = requests.get(competitor.website, headers=headers, timeout=15)
            response.raise_for_status()

            html_content = response.text
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

            # Extraer precios - buscar patrones como $XX.XXX o $XXXXX
            precio_pattern = r'\$\s*(\d{1,2}[\.,]?\d{3})'
            precios_encontrados = re.findall(precio_pattern, html_content)

            if precios_encontrados:
                # Limpiar y convertir precios
                precios = []
                for precio_str in precios_encontrados:
                    try:
                        precio_limpio = precio_str.replace('.', '').replace(',', '')
                        precio = int(precio_limpio)
                        # Filtrar precios razonables para entrada (entre 5.000 y 50.000)
                        if 5000 <= precio <= 50000:
                            precios.append(precio)
                    except:
                        continue

                if precios:
                    # Usar el precio más bajo como referencia para entrada adulto
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
