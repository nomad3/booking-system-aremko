"""
Analiza clientes únicos en el CSV histórico
"""
import csv

# Sets para almacenar valores únicos
nombres = set()
emails = set()
telefonos = set()

# Contadores
total_filas = 0
sin_email = 0
sin_telefono = 0
sin_ambos = 0

# Leer CSV
with open('data/servicios_historicos.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)

    for row in reader:
        total_filas += 1

        # Nombres únicos
        nombre = row.get('cliente', '').strip()
        if nombre:
            nombres.add(nombre)

        # Emails únicos
        email = row.get('mail', '').strip()
        has_email = email and email != ''
        if has_email:
            emails.add(email)
        else:
            sin_email += 1

        # Teléfonos únicos
        telefono = row.get('telefono', '').strip()
        has_telefono = telefono and telefono != ''
        if has_telefono:
            telefonos.add(telefono)
        else:
            sin_telefono += 1

        # Sin email NI teléfono
        if not has_email and not has_telefono:
            sin_ambos += 1

print(f'Total servicios en CSV: {total_filas:,}')
print(f'Clientes únicos por nombre: {len(nombres):,}')
print(f'Emails únicos válidos: {len(emails):,}')
print(f'Teléfonos únicos válidos: {len(telefonos):,}')

print(f'\nServicios sin email: {sin_email:,}')
print(f'Servicios sin teléfono: {sin_telefono:,}')
print(f'Servicios sin email NI teléfono: {sin_ambos:,}')

print('\n--- Matching Strategy ---')
print(f'Emails únicos: {len(emails):,}')
print(f'Teléfonos únicos: {len(telefonos):,}')
print(f'Total clientes identificables (email O teléfono): {len(emails | telefonos):,}')
