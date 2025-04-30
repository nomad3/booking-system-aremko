import os
import django
import random
from datetime import datetime, time, timedelta, date # Added date
from django.utils import timezone
from decimal import Decimal # Import Decimal

# --- Django Setup ---
# Set the DJANGO_SETTINGS_MODULE environment variable
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
# Initialize Django
django.setup()
# --- End Django Setup ---

# Now import models after Django setup
from django.db import IntegrityError # Import IntegrityError
from django.contrib.auth.models import User
from ventas.models import (
    CategoriaServicio, Servicio, Cliente, VentaReserva, ReservaServicio, Pago,
    Producto, Proveedor, CategoriaProducto, Compra, DetalleCompra, GiftCard,
    Lead, Company, Contact, Activity, Campaign, Deal, CampaignInteraction # Added CRM models
)

# Note: This script is now standalone, not a management command.

# --- Helper Functions ---
def get_random_user():
    """Gets a random existing user or creates one if none exist."""
    users = User.objects.all()
    if users.exists():
        return random.choice(users)
    else:
        # Create a default user if none exist
        print("  Creating default user 'testcreator'...")
        return User.objects.create_user(username='testcreator', password='password')

def get_random_contact():
    """Gets a random existing contact."""
    contacts = Contact.objects.all()
    if contacts.exists():
        return random.choice(contacts)
    return None

def get_random_lead():
    """Gets a random existing lead."""
    leads = Lead.objects.filter(status__in=['New', 'Contacted', 'Qualified']) # Get leads that might have activities
    if leads.exists():
        return random.choice(leads)
    return None

def get_random_deal():
    """Gets a random existing deal."""
    deals = Deal.objects.filter(stage__in=['Prospecting', 'Qualification', 'Proposal', 'Negotiation']) # Get open deals
    if deals.exists():
        return random.choice(deals)
    return None

def get_random_campaign():
    """Gets a random existing campaign."""
    campaigns = Campaign.objects.all()
    if campaigns.exists():
        return random.choice(campaigns)
    return None

# --- Data Creation Functions ---

def create_categories():
    """Creates/Updates service categories."""
    print('Creating/Updating categories...')
    categories = ['Cabañas', 'Tinas sin hidromasaje', 'Tinas con hidromasaje', 'Masajes']
    for category_name in categories:
        category, created = CategoriaServicio.objects.get_or_create(nombre=category_name)
        print(f'  {"Created" if created else "Exists"}: {category_name}')

def update_or_create_services():
    """Updates or creates services."""
    print('Updating/Creating services...')
    standard_slots = { "monday": ["16:00", "18:00"], "tuesday": [], "wednesday": ["16:00", "18:00"], "thursday": ["16:00", "18:00"], "friday": ["14:00", "16:00", "18:00", "20:00"], "saturday": ["14:00", "16:00", "18:00", "20:00"], "sunday": ["14:00", "16:00"] }
    default_min_cap, default_max_cap = 1, 10
    services_config = {
        'Cabañas': { 'Torre': {'slots': standard_slots, 'precio': 90000, 'duracion': 1440, 'min_cap': 1, 'max_cap': 2}, 'Tepa': {'slots': standard_slots, 'precio': 90000, 'duracion': 1440, 'min_cap': 1, 'max_cap': 2}, 'Acantilado': {'slots': standard_slots, 'precio': 90000, 'duracion': 1440, 'min_cap': 1, 'max_cap': 2}, 'Laurel': {'slots': standard_slots, 'precio': 90000, 'duracion': 1440, 'min_cap': 1, 'max_cap': 2}, 'Arrayan': {'slots': standard_slots, 'precio': 90000, 'duracion': 1440, 'min_cap': 1, 'max_cap': 2}, },
        'Tinas sin hidromasaje': { 'Osorno': {'slots': standard_slots, 'precio': 25000, 'duracion': 120, 'min_cap': 5, 'max_cap': 6}, 'Calbuco': {'slots': standard_slots, 'precio': 25000, 'duracion': 120, 'min_cap': default_min_cap, 'max_cap': default_max_cap}, 'Tronador': {'slots': standard_slots, 'precio': 25000, 'duracion': 120, 'min_cap': default_min_cap, 'max_cap': default_max_cap}, 'Hornopiren': {'slots': standard_slots, 'precio': 25000, 'duracion': 120, 'min_cap': default_min_cap, 'max_cap': default_max_cap}, },
        'Tinas con hidromasaje': { 'Puntiagudo': {'slots': standard_slots, 'precio': 30000, 'duracion': 120, 'min_cap': default_min_cap, 'max_cap': default_max_cap}, 'Llaima': {'slots': standard_slots, 'precio': 30000, 'duracion': 120, 'min_cap': default_min_cap, 'max_cap': default_max_cap}, 'Villarrica': {'slots': standard_slots, 'precio': 30000, 'duracion': 120, 'min_cap': default_min_cap, 'max_cap': default_max_cap}, 'Puyehue': {'slots': standard_slots, 'precio': 30000, 'duracion': 120, 'min_cap': default_min_cap, 'max_cap': default_max_cap}, },
        'Masajes': { 'Relajación o Descontracturante': {'slots': standard_slots, 'precio': 80000, 'duracion': 50, 'min_cap': 1, 'max_cap': 1}, }
    }
    for category_name, services in services_config.items():
        try:
            category = CategoriaServicio.objects.get(nombre=category_name)
            print(f'Processing category: {category_name}')
            for service_name, details in services.items():
                try:
                    service, created = Servicio.objects.update_or_create(
                        nombre=service_name,
                        defaults={
                            'categoria': category,
                            'slots_disponibles': details['slots'],
                            'activo': True,
                            'precio_base': details['precio'],
                            'duracion': details['duracion'],
                            'capacidad_minima': details.get('min_cap', default_min_cap),
                            'capacidad_maxima': details.get('max_cap', default_max_cap),
                            'horario_apertura': time(9, 0),
                            'horario_cierre': time(23, 59)
                        }
                    )
                    print(f'  {"Created" if created else "Updated"} service: {service_name}')
                except Exception as e_inner: print(f'ERROR processing service "{service_name}": {e_inner}')
        except CategoriaServicio.DoesNotExist: print(f'WARNING: Category "{category_name}" not found.')
        except Exception as e: print(f'ERROR processing category "{category_name}": {e}')

def create_clients():
    """Creates sample clients."""
    print('Creating clients...')
    clients_data = [
        {'nombre': 'Juan Pérez CRM', 'email': 'juan.perez.crm@example.com', 'telefono': '911111111'},
        {'nombre': 'María González CRM', 'email': 'maria.gonzalez.crm@example.com', 'telefono': '922222222'},
        {'nombre': 'Carlos Rodríguez CRM', 'email': 'carlos.r.crm@example.com', 'telefono': '933333333'},
        {'nombre': 'Ana Martínez CRM', 'email': 'ana.martinez.crm@example.com', 'telefono': '944444444'},
        {'nombre': 'Pedro Sánchez CRM', 'email': 'pedro.sanchez.crm@example.com', 'telefono': '955555555'},
    ]
    created_count = 0
    for client_data in clients_data:
        try:
            client, created = Cliente.objects.get_or_create(
                telefono=client_data['telefono'],
                defaults=client_data
            )
            if created:
                print(f'  Created client: {client_data["nombre"]}')
                created_count += 1
        except Exception as e: print(f'  Error creating client {client_data["nombre"]}: {e}')
    print(f'Finished creating clients. Created: {created_count}')

# --- CRM Data Creation Functions ---

def create_companies():
    print("Creating companies...")
    companies = ["Tech Solutions Inc.", "Global Innovations Ltd.", "Marketing Masters Co."]
    for name in companies:
        company, created = Company.objects.get_or_create(name=name)
        print(f'  {"Created" if created else "Exists"}: {name}')

def create_campaigns():
    print("Creating campaigns...")
    campaigns_data = [
        {'name': 'Verano 2025', 'status': 'Active', 'target_min_visits': 2, 'target_min_spend': 50000, 'email_subject_template': '☀️ Oferta Verano Aremko!', 'email_body_template': 'Hola {nombre_cliente}, ¡disfruta del verano con nosotros!', 'sms_template': 'Aremko Verano: Descuentos especiales para ti {nombre_cliente}!'},
        {'name': 'Clientes VIP Invierno', 'status': 'Planning', 'target_min_visits': 5, 'target_min_spend': 100000, 'whatsapp_template': 'Hola {nombre_cliente}, como cliente VIP de Aremko, tenemos una sorpresa invernal para ti.'},
        {'name': 'Reactivación Inactivos', 'status': 'Completed', 'target_min_visits': 0, 'target_min_spend': 0}, # Example completed
    ]
    for data in campaigns_data:
        campaign, created = Campaign.objects.get_or_create(name=data['name'], defaults=data)
        print(f'  {"Created" if created else "Exists"}: {data["name"]}')

def create_contacts():
    print("Creating contacts...")
    user = get_random_user()
    company1 = Company.objects.filter(name="Tech Solutions Inc.").first()
    company2 = Company.objects.filter(name="Global Innovations Ltd.").first()
    # Try linking to existing clients if email matches
    cliente_juan = Cliente.objects.filter(email='juan.perez.crm@example.com').first()
    cliente_maria = Cliente.objects.filter(email='maria.gonzalez.crm@example.com').first()

    contacts_data = [
        {'first_name': 'Juan', 'last_name': 'Pérez (Contacto)', 'email': 'juan.perez.crm@example.com', 'phone': cliente_juan.telefono if cliente_juan else '911111111', 'company': company1, 'linked_user': None},
        {'first_name': 'Maria', 'last_name': 'González (Contacto)', 'email': 'maria.gonzalez.crm@example.com', 'phone': cliente_maria.telefono if cliente_maria else '922222222', 'company': company2, 'linked_user': user},
        {'first_name': 'Laura', 'last_name': 'Tech', 'email': 'laura.tech@techsolutions.com', 'phone': '966666666', 'company': company1, 'job_title': 'Developer'},
        {'first_name': 'Roberto', 'last_name': 'Global', 'email': 'roberto.global@globalinnovations.com', 'phone': '977777777', 'company': company2, 'job_title': 'Manager'},
    ]
    created_count = 0
    for data in contacts_data:
        contact, created = Contact.objects.get_or_create(email=data['email'], defaults=data)
        if created:
            print(f'  Created contact: {data["first_name"]} {data["last_name"]}')
            created_count += 1
    print(f'Finished creating contacts. Created: {created_count}')

def create_leads():
    print("Creating leads...")
    campaign1 = Campaign.objects.filter(name='Verano 2025').first()
    campaign2 = Campaign.objects.filter(name='Clientes VIP Invierno').first()
    leads_data = [
        {'first_name': 'Pedro', 'last_name': 'Prospecto', 'email': 'pedro.prospecto@email.com', 'status': 'New', 'source': 'Website Form', 'campaign': campaign1},
        {'first_name': 'Sofia', 'last_name': 'Interesada', 'email': 'sofia.interesada@email.com', 'status': 'Contacted', 'source': 'Referral', 'phone': '944444444'},
        {'first_name': 'Andres', 'last_name': 'Calificado', 'email': 'andres.calificado@email.com', 'status': 'Qualified', 'source': 'Campaign', 'campaign': campaign2, 'company_name': 'Andres Corp'},
        {'first_name': 'Elena', 'last_name': 'NoCalificada', 'email': 'elena.nocalif@email.com', 'status': 'Unqualified', 'source': 'Cold Call'},
    ]
    created_count = 0
    for data in leads_data:
        lead, created = Lead.objects.get_or_create(email=data['email'], defaults=data)
        if created:
            print(f'  Created lead: {data["first_name"]} {data["last_name"]}')
            created_count += 1
    print(f'Finished creating leads. Created: {created_count}')

def create_deals():
    print("Creating deals...")
    contact1 = Contact.objects.filter(email='juan.perez.crm@example.com').first()
    contact2 = Contact.objects.filter(email='laura.tech@techsolutions.com').first()
    campaign1 = Campaign.objects.filter(name='Verano 2025').first()

    deals_data = [
        {'name': 'Deal Juan Verano', 'contact': contact1, 'stage': 'Proposal', 'amount': Decimal('75000'), 'campaign': campaign1, 'expected_close_date': date.today() + timedelta(days=30)},
        {'name': 'Deal Laura Tech', 'contact': contact2, 'stage': 'Negotiation', 'amount': Decimal('150000'), 'probability': 0.75},
        {'name': 'Deal Perdido', 'contact': contact1, 'stage': 'Closed Lost', 'amount': Decimal('50000')},
    ]
    created_count = 0
    for data in deals_data:
        # Need a unique identifier for get_or_create, using name+contact for simplicity
        deal, created = Deal.objects.get_or_create(
            name=data['name'], contact=data['contact'],
            defaults=data
        )
        if created:
            print(f'  Created deal: {data["name"]}')
            created_count += 1
    print(f'Finished creating deals. Created: {created_count}')

def create_activities():
    print("Creating activities...")
    user = get_random_user()
    lead = get_random_lead()
    contact = get_random_contact()
    deal = get_random_deal()
    campaign = get_random_campaign()
    activities_data = []

    if lead: activities_data.append({'activity_type': 'Call', 'subject': 'Llamada inicial a Lead', 'related_lead': lead, 'created_by': user, 'campaign': campaign})
    if contact: activities_data.append({'activity_type': 'Email Sent', 'subject': 'Email de seguimiento a Contacto', 'related_contact': contact, 'created_by': user, 'campaign': campaign})
    if deal: activities_data.append({'activity_type': 'Meeting', 'subject': f'Reunión Propuesta Deal: {deal.name}', 'related_deal': deal, 'created_by': user})
    if contact and campaign: activities_data.append({'activity_type': 'Note Added', 'subject': 'Nota interna sobre contacto en campaña', 'related_contact': contact, 'campaign': campaign, 'created_by': user})

    created_count = 0
    for data in activities_data:
        # Create activities directly, no need for get_or_create usually
        try:
            Activity.objects.create(**data)
            print(f'  Created activity: {data["subject"]}')
            created_count += 1
        except Exception as e:
            print(f'  Error creating activity "{data.get("subject", "N/A")}": {e}')
    print(f'Finished creating activities. Created: {created_count}')

def create_interactions():
    print("Creating interactions...")
    contact = get_random_contact()
    campaign = get_random_campaign()
    # Find a related activity if possible
    activity = Activity.objects.filter(related_contact=contact, campaign=campaign).first()

    interactions_data = []
    if contact and campaign:
        interactions_data.append({'contact': contact, 'campaign': campaign, 'activity': activity, 'interaction_type': 'EMAIL_OPEN', 'details': {'ip': '192.168.1.100', 'user_agent': 'Chrome/Mac'}})
        interactions_data.append({'contact': contact, 'campaign': campaign, 'activity': activity, 'interaction_type': 'EMAIL_CLICK', 'details': {'clicked_url': 'https://aremko.cl/promo-verano'}})
        # Add more interaction types if needed
        # interactions_data.append({'contact': contact, 'campaign': campaign, 'interaction_type': 'SMS_REPLY', 'details': {'message_body': 'Me interesa!'}})

    created_count = 0
    for data in interactions_data:
        try:
            CampaignInteraction.objects.create(**data)
            print(f'  Created interaction: {data["interaction_type"]} for {data["contact"]}')
            created_count += 1
        except Exception as e:
            print(f'  Error creating interaction for {data.get("contact", "N/A")}: {e}')
    print(f'Finished creating interactions. Created: {created_count}')


# --- Main execution block ---
if __name__ == '__main__':
    print('Starting fake data population...')

    # Create service categories
    create_categories()

    # Update or Create services using the new function name
    update_or_create_services()

    # Create clients
    create_clients()

    # --- Create CRM Data ---
    create_companies()
    create_campaigns()
    create_contacts() # Create contacts after clients/companies
    create_leads()    # Create leads after campaigns
    create_deals()    # Create deals after contacts/campaigns
    create_activities() # Create activities after leads/contacts/deals
    create_interactions() # Create interactions after contacts/campaigns/activities

    print('\nSuccessfully populated fake data!')
