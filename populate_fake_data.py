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
    """Updates or creates services based on spreadsheet data."""
    print('Updating/Creating services...')
    
    # Data extracted from the spreadsheet image
    services_config = {
        'Cabañas': {
            'Torre': ["16:00"],
            'Tepa': ["16:00"],
            'Acantilado': ["16:00"],
            'Laurel': ["16:00"],
            'Arrayan': ["16:00"],
        },
        'Tinas sin hidromasaje': {
            'Osorno': ["14:30", "17:00"],
            'Calbuco': ["17:00", "19:30"],
            'Tronador': ["19:30"],
            'Hornopiren': ["22:00"],
        },
        'Tinas con hidromasaje': {
            'Puntiagudo': ["14:00", "16:30"],
            'Llaima': ["16:30", "19:00"],
            'Villarrica': ["19:00"],
            'Puyehue': ["21:30"],
        },
        'Masajes': {
            'Relajación o Descontracturante': ["15:30", "16:45", "18:00", "19:15"],
        }
    }

    for category_name, services in services_config.items():
        try:
            category = CategoriaServicio.objects.get(nombre=category_name)
            print(f'Processing category: {category_name}')

            for service_name, slots in services.items():
                # Use update_or_create to handle existing services
                # We only update category and slots, preserving other fields like price/duration
                service, created = Servicio.objects.update_or_create(
                    nombre=service_name,
                    defaults={
                        'categoria': category,
                        'slots_disponibles': slots,
                        'activo': True # Ensure service is active
                        # We DON'T update 'precio_base' or 'duracion' here
                        # Assuming 'horario_apertura' and 'horario_cierre' are also set correctly
                    }
                )

                if created:
                    print(f'  Created service: {service_name} with slots {slots}')
                    # Note: If created, price/duration might be default or null.
                    # Consider adding default values in the model or handling this case.
                else:
                    print(f'  Updated service: {service_name} with slots {slots}')

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
    
    # Create services
    create_services()
    
    # Create clients
    create_clients()
    
    print('Successfully created/updated fake data!')

# --- Remove the duplicate handle method and its functions ---
