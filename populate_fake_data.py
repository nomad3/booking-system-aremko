import os
import django
import random
from datetime import datetime, time, timedelta
from django.utils import timezone

# --- Django Setup ---
# Set the DJANGO_SETTINGS_MODULE environment variable
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings') 
# Initialize Django
django.setup()
# --- End Django Setup ---

# Now import models after Django setup
from ventas.models import CategoriaServicio, Servicio, Cliente 

# Note: This script is now standalone, not a management command.
# We'll define functions directly instead of using BaseCommand.

def create_categories():
    """Creates service categories based on spreadsheet."""
    print('Creating/Updating categories...')
    # Categories from the spreadsheet
    categories = [
        'Cabañas', 
        'Tinas sin hidromasaje', 
        'Tinas con hidromasaje', 
        'Masajes'
    ]
    
    for category_name in categories:
        category, created = CategoriaServicio.objects.get_or_create(
            nombre=category_name
        )
        
        if created:
            print(f'  Created category: {category_name}')
        else:
            print(f'  Category already exists: {category_name}')


def update_or_create_services():
    """Updates or creates services based on spreadsheet and provided data."""
    print('Updating/Creating services...')
    
    # Data combining spreadsheet slots and provided price/duration info
    # Using consistent price/duration per category for missing values
    # Define the standard weekly slots
    standard_slots = {
        "monday": ["16:00", "18:00"],
        "tuesday": [],
        "wednesday": ["16:00", "18:00"],
        "thursday": ["16:00", "18:00"],
        "friday": ["14:00", "16:00", "18:00", "20:00"],
        "saturday": ["14:00", "16:00", "18:00", "20:00"],
        "sunday": ["14:00", "16:00"]
    }

    # Define default capacities (can be overridden per service)
    default_min_cap = 1
    default_max_cap = 10 # Example default max

    services_config = {
        'Cabañas': {
            # Cabins: Min 1, Max 2
            'Torre':      {'slots': standard_slots, 'precio': 90000, 'duracion': 1440, 'min_cap': 1, 'max_cap': 2},
            'Tepa':       {'slots': standard_slots, 'precio': 90000, 'duracion': 1440, 'min_cap': 1, 'max_cap': 2},
            'Acantilado': {'slots': standard_slots, 'precio': 90000, 'duracion': 1440, 'min_cap': 1, 'max_cap': 2},
            'Laurel':     {'slots': standard_slots, 'precio': 90000, 'duracion': 1440, 'min_cap': 1, 'max_cap': 2},
            'Arrayan':    {'slots': standard_slots, 'precio': 90000, 'duracion': 1440, 'min_cap': 1, 'max_cap': 2},
        },
        'Tinas sin hidromasaje': {
             # Assuming default capacities for these unless specified otherwise
            'Osorno':     {'slots': standard_slots, 'precio': 25000, 'duracion': 120, 'min_cap': default_min_cap, 'max_cap': default_max_cap},
            'Calbuco':    {'slots': standard_slots, 'precio': 25000, 'duracion': 120, 'min_cap': default_min_cap, 'max_cap': default_max_cap},
            'Tronador':   {'slots': standard_slots, 'precio': 25000, 'duracion': 120, 'min_cap': default_min_cap, 'max_cap': default_max_cap},
            'Hornopiren': {'slots': standard_slots, 'precio': 25000, 'duracion': 120, 'min_cap': default_min_cap, 'max_cap': default_max_cap},
        },
        'Tinas con hidromasaje': {
            'Puntiagudo': {'slots': standard_slots, 'precio': 30000, 'duracion': 120, 'min_cap': default_min_cap, 'max_cap': default_max_cap},
            'Llaima':     {'slots': standard_slots, 'precio': 30000, 'duracion': 120, 'min_cap': default_min_cap, 'max_cap': default_max_cap},
            'Villarrica': {'slots': standard_slots, 'precio': 30000, 'duracion': 120, 'min_cap': default_min_cap, 'max_cap': default_max_cap},
            'Puyehue':    {'slots': standard_slots, 'precio': 30000, 'duracion': 120, 'min_cap': default_min_cap, 'max_cap': default_max_cap},
        },
        'Masajes': {
             # Assuming massages are for 1 person
            'Relajación o Descontracturante': {'slots': standard_slots, 'precio': 80000, 'duracion': 50, 'min_cap': 1, 'max_cap': 1},
        }
    }

    for category_name, services in services_config.items():
        try:
            category = CategoriaServicio.objects.get(nombre=category_name)
            print(f'Processing category: {category_name}')

            for service_name, details in services.items():
                slots = details['slots']
                precio = details['precio']
                duracion = details['duracion']
                try:
                    # Try to get the existing service
                    service = Servicio.objects.get(nombre=service_name)
                    # If it exists, update only category, slots, and activo status
                    service.categoria = category
                    service.slots_disponibles = slots
                    service.activo = True
                    # Update capacities if provided in config
                    service.capacidad_minima = details.get('min_cap', default_min_cap)
                    service.capacidad_maxima = details.get('max_cap', default_max_cap)
                    service.save()
                    print(f'  Updated service: {service_name} (Min: {service.capacidad_minima}, Max: {service.capacidad_maxima}) with slots {slots}')
                except Servicio.DoesNotExist:
                    # If it doesn't exist, create it with the provided details
                    Servicio.objects.create(
                        nombre=service_name,
                        categoria=category,
                        slots_disponibles=slots,
                        activo=True,
                        precio_base=precio,
                        duracion=duracion,
                        capacidad_minima=details.get('min_cap', default_min_cap),
                        capacidad_maxima=details.get('max_cap', default_max_cap),
                        horario_apertura=time(9, 0), # Default opening (adjust if needed)
                        horario_cierre=time(23, 59) # Default closing (adjust if needed)
                    )
                    print(f'  Created service: {service_name} (Min: {details.get("min_cap", default_min_cap)}, Max: {details.get("max_cap", default_max_cap)}) with price {precio}, duration {duracion}, slots {slots}.')
                except Exception as e_inner:
                    # Catch potential errors during update/create for a specific service
                    print(f'ERROR processing service "{service_name}" in category "{category_name}": {e_inner}')

        except CategoriaServicio.DoesNotExist:
            print(f'WARNING: Category "{category_name}" not found. Skipping services.')
        except Exception as e:
             print(f'ERROR processing service "{service_name}" in category "{category_name}": {e}')


def create_clients():
    """Creates sample clients."""
    print('Creating clients...')
    # Sample client data
    clients_data = [
        {'nombre': 'Juan Pérez', 'email': 'juan.perez@example.com', 'telefono': '912345678'},
        {'nombre': 'María González', 'email': 'maria.gonzalez@example.com', 'telefono': '923456789'},
        {'nombre': 'Carlos Rodríguez', 'email': 'carlos.rodriguez@example.com', 'telefono': '934567890'},
        {'nombre': 'Ana Martínez', 'email': 'ana.martinez@example.com', 'telefono': '945678901'},
        {'nombre': 'Pedro Sánchez', 'email': 'pedro.sanchez@example.com', 'telefono': '956789012'},
        {'nombre': 'Laura López', 'email': 'laura.lopez@example.com', 'telefono': '967890123'},
        {'nombre': 'Miguel Fernández', 'email': 'miguel.fernandez@example.com', 'telefono': '978901234'},
        {'nombre': 'Sofía Díaz', 'email': 'sofia.diaz@example.com', 'telefono': '989012345'},
        {'nombre': 'Javier Moreno', 'email': 'javier.moreno@example.com', 'telefono': '990123456'},
        {'nombre': 'Carmen Álvarez', 'email': 'carmen.alvarez@example.com', 'telefono': '901234567'},
    ]
    
    for client_data in clients_data:
        client, created = Cliente.objects.get_or_create(
            email=client_data['email'],
            defaults={
                'nombre': client_data['nombre'],
                'telefono': client_data['telefono'],
                'ciudad': 'Santiago',
                'pais': 'Chile'
            }
        )
        
        if created:
            print(f'  Created client: {client_data["nombre"]}')
        else:
            print(f'  Client already exists: {client_data["nombre"]}')

# --- Main execution block ---
if __name__ == '__main__':
    print('Starting fake data population...')
    
    # Create service categories
    create_categories()
    
    # Update or Create services using the new function name
    update_or_create_services()
    
    # Create clients
    create_clients()
    
    print('Successfully created/updated fake data!')

# --- Remove the duplicate handle method and its functions ---
