from django.core.management.base import BaseCommand, CommandError
from ventas.models import Company, Contact
import csv


class Command(BaseCommand):
    help = 'Importa contactos desde un CSV: first_name,last_name,email,phone,job_title,company_name'

    def add_arguments(self, parser):
        parser.add_argument('--file', required=True, help='Ruta al archivo CSV')

    def handle(self, *args, **options):
        path = options['file']
        created = updated = 0
        try:
            with open(path, newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                emails = [ (r.get('email') or '').strip().lower() for r in reader if (r.get('email') or '').strip() ]
                existing = {c.email.lower(): c for c in Contact.objects.filter(email__in=emails)}
                f.seek(0); reader = csv.DictReader(f)
                companies = [ (r.get('company_name') or '').strip() for r in reader if (r.get('company_name') or '').strip() ]
                existing_companies = {c.name.lower(): c for c in Company.objects.filter(name__in=companies)}
                f.seek(0); reader = csv.DictReader(f)
                for row in reader:
                    email = (row.get('email') or '').strip().lower()
                    if not email:
                        continue
                    first_name = (row.get('first_name') or '').strip() or '-'
                    last_name = (row.get('last_name') or '').strip()
                    phone = (row.get('phone') or '').strip() or None
                    job_title = (row.get('job_title') or '').strip() or None
                    company_name = (row.get('company_name') or '').strip()
                    company_obj = None
                    if company_name:
                        company_obj = existing_companies.get(company_name.lower())
                        if not company_obj:
                            company_obj = Company.objects.create(name=company_name)
                            existing_companies[company_name.lower()] = company_obj
                    obj = existing.get(email)
                    if obj:
                        changed = False
                        if obj.first_name != first_name:
                            obj.first_name = first_name; changed = True
                        if last_name and obj.last_name != last_name:
                            obj.last_name = last_name; changed = True
                        if phone and obj.phone != phone:
                            obj.phone = phone; changed = True
                        if job_title and getattr(obj, 'job_title', None) != job_title:
                            obj.job_title = job_title; changed = True
                        if company_obj and obj.company_id != company_obj.id:
                            obj.company = company_obj; changed = True
                        if changed:
                            obj.save(); updated += 1
                    else:
                        Contact.objects.create(
                            first_name=first_name, last_name=last_name, email=email,
                            phone=phone, job_title=job_title, company=company_obj
                        )
                        created += 1
            self.stdout.write(self.style.SUCCESS(f'Contactos importados. Nuevos: {created}, Actualizados: {updated}'))
        except FileNotFoundError:
            raise CommandError(f'Archivo no encontrado: {path}')
