from django.core.management.base import BaseCommand, CommandError
from ventas.models import Company
import csv


class Command(BaseCommand):
    help = 'Importa empresas desde un CSV con columnas: name,industry,city,website'

    def add_arguments(self, parser):
        parser.add_argument('--file', required=True, help='Ruta al archivo CSV')

    def handle(self, *args, **options):
        path = options['file']
        created = updated = 0
        try:
            with open(path, newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                existing = {c.name.lower(): c for c in Company.objects.filter(name__in=[(r.get('name') or '').strip() for r in reader if (r.get('name') or '').strip()])}
                f.seek(0); reader = csv.DictReader(f)
                for row in reader:
                    name = (row.get('name') or '').strip()
                    if not name:
                        continue
                    industry = (row.get('industry') or '').strip() or None
                    city = (row.get('city') or '').strip() or None
                    website = (row.get('website') or '').strip() or None
                    obj = existing.get(name.lower())
                    if obj:
                        changed = False
                        if industry and getattr(obj, 'industry', None) != industry:
                            obj.industry = industry; changed = True
                        if city and getattr(obj, 'city', None) != city:
                            obj.city = city; changed = True
                        if website and getattr(obj, 'website', None) != website:
                            obj.website = website; changed = True
                        if changed:
                            obj.save()
                            updated += 1
                    else:
                        obj = Company(name=name)
                        if hasattr(obj, 'industry'): obj.industry = industry
                        if hasattr(obj, 'city'): obj.city = city
                        if hasattr(obj, 'website'): obj.website = website
                        obj.save(); created += 1
            self.stdout.write(self.style.SUCCESS(f'Empresas importadas. Nuevas: {created}, Actualizadas: {updated}'))
        except FileNotFoundError:
            raise CommandError(f'Archivo no encontrado: {path}')
