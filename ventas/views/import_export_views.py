import xlwt
from openpyxl import load_workbook
from datetime import datetime
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from ..models import Cliente # Relative import

# Helper function to check if the user is an administrator
def es_administrador(user):
    return user.is_staff or user.is_superuser

@login_required
def exportar_clientes_excel(request):
    response = HttpResponse(content_type='application/ms-excel')
    response['Content-Disposition'] = 'attachment; filename="Clientes_{}.xls"'.format(
        datetime.now().strftime('%Y%m%d_%H%M%S')
    )

    wb = xlwt.Workbook(encoding='utf-8')
    ws = wb.add_sheet('Clientes')

    # Estilos
    header_style = xlwt.easyxf('font: bold on; pattern: pattern solid, fore_colour gray25;')

    # Headers
    headers = ['ID', 'Nombre', 'Teléfono', 'Email', 'Documento Identidad', 'Ciudad'] # Added Documento and Ciudad
    for col, header in enumerate(headers):
        ws.write(0, col, header, header_style)
        ws.col(col).width = 256 * 20

    # Obtener todos los clientes
    clientes = Cliente.objects.all().order_by('nombre')

    # Datos
    for row, cliente in enumerate(clientes, 1):
        ws.write(row, 0, cliente.id)
        ws.write(row, 1, cliente.nombre)
        ws.write(row, 2, cliente.telefono or '')
        ws.write(row, 3, cliente.email or '')
        ws.write(row, 4, cliente.documento_identidad or '') # Added
        ws.write(row, 5, cliente.ciudad or '') # Added

    wb.save(response)
    return response

@login_required
@user_passes_test(es_administrador)  # Solo administradores pueden importar
def importar_clientes_excel(request):
    BATCH_SIZE = 500

    if request.method == 'POST' and request.FILES.get('archivo_excel'):
        try:
            archivo = request.FILES['archivo_excel']
            # Validate file type (optional but recommended)
            if not archivo.name.endswith(('.xlsx', '.xls')):
                 messages.error(request, 'Formato de archivo inválido. Por favor, suba un archivo Excel (.xlsx o .xls).')
                 return render(request, 'ventas/importar_clientes.html')

            wb = load_workbook(archivo, data_only=True) # data_only=True to get values, not formulas
            ws = wb.active

            clientes_nuevos = []
            clientes_actualizados = []
            errores = []
            total_procesados = 0
            batch_data = []

            # Simple header check (optional)
            expected_headers = ['documento_identidad', 'nombre', 'telefono', 'email', 'ciudad']
            actual_headers = [cell.value.lower().strip().replace(' ', '_') if cell.value else '' for cell in ws[1]]
            # if actual_headers[:len(expected_headers)] != expected_headers:
            #      messages.error(request, f"Las cabeceras del archivo no coinciden. Se esperaban: {', '.join(expected_headers)}")
            #      return render(request, 'ventas/importar_clientes.html')


            for row in ws.iter_rows(min_row=2): # Start from row 2
                # Check if row seems empty
                if all(cell.value is None or str(cell.value).strip() == '' for cell in row):
                    continue

                try:
                    # Get values by position (adjust indices if needed)
                    documento_identidad = row[0].value if row[0].value is not None else ''
                    nombre = row[1].value if row[1].value is not None else ''
                    telefono = row[2].value if row[2].value is not None else ''
                    email = row[3].value if row[3].value is not None else ''
                    # Check if row has enough columns before accessing index 4
                    ciudad = row[4].value if len(row) > 4 and row[4].value is not None else ''

                    # Basic validation: Name is required
                    if not str(nombre).strip():
                        errores.append(f"Error en fila {row[0].row}: El nombre es requerido.")
                        continue

                    # Add data to batch
                    batch_data.append({
                        'row': row[0].row, # Use cell's row attribute for accurate reporting
                        'documento_identidad': documento_identidad,
                        'nombre': nombre,
                        'telefono': telefono,
                        'email': email,
                        'ciudad': ciudad
                    })

                    # Process batch if size reached
                    if len(batch_data) >= BATCH_SIZE:
                        process_batch(batch_data, clientes_nuevos, clientes_actualizados, errores)
                        total_procesados += len(batch_data)
                        messages.info(request, f'Procesados {total_procesados} registros...')
                        batch_data = [] # Reset batch

                except Exception as e:
                    # Catch errors during row processing
                    errores.append(f"Error procesando fila {row[0].row if row and row[0] else 'desconocida'}: {str(e)}")

            # Process the final batch
            if batch_data:
                process_batch(batch_data, clientes_nuevos, clientes_actualizados, errores)
                total_procesados += len(batch_data)

            # Display results
            messages.success(request, f'Importación completada. Total procesados: {total_procesados}.')
            if clientes_nuevos:
                messages.info(request, f'Se crearon {len(clientes_nuevos)} nuevos clientes.')
            if clientes_actualizados:
                messages.info(request, f'Se actualizaron {len(clientes_actualizados)} clientes existentes.')
            if errores:
                messages.warning(request, f'Se encontraron {len(errores)} errores durante la importación.')
                # Show first few errors
                for error in errores[:10]:
                    messages.error(request, error)
                if len(errores) > 10:
                    messages.error(request, f'... y {len(errores) - 10} errores más.')

        except Exception as e:
            messages.error(request, f'Error general al procesar el archivo: {str(e)}')
            import traceback
            traceback.print_exc() # Log detailed error

    return render(request, 'ventas/importar_clientes.html')


# --- Helper Functions for Import ---

def limpiar_telefono(telefono):
    """Limpia y formatea el número telefónico a 9 dígitos si es posible."""
    try:
        if telefono is None: return ''
        telefono_str = str(telefono).strip()
        # Remove common prefixes like +56, 56, 569 etc.
        if telefono_str.startswith('+56'):
            telefono_str = telefono_str[3:]
        elif telefono_str.startswith('56'):
             telefono_str = telefono_str[2:]
        # Remove leading 9 if present after prefix removal
        if telefono_str.startswith('9') and len(telefono_str) == 9:
             pass # Keep the 9 digits
        elif len(telefono_str) == 8: # Assume mobile without leading 9
             telefono_str = '9' + telefono_str

        solo_numeros = ''.join(filter(str.isdigit, telefono_str))

        # Return last 9 digits if valid, otherwise empty
        return solo_numeros if len(solo_numeros) == 9 else ''
    except Exception:
        return ''

def limpiar_email(email):
    """Limpia y valida el email."""
    if not email: return ''
    email_str = str(email).strip().lower()
    # Basic check for '@' and '.'
    return email_str if '@' in email_str and '.' in email_str.split('@')[-1] else ''

def process_batch(batch_data, clientes_nuevos, clientes_actualizados, errores):
    """Procesa un lote de datos de clientes para crear o actualizar."""
    documentos_en_lote = {str(data['documento_identidad']).strip() for data in batch_data if str(data.get('documento_identidad', '')).strip()}
    telefonos_en_lote = {limpiar_telefono(data['telefono']) for data in batch_data if limpiar_telefono(data.get('telefono', ''))}
    emails_en_lote = {limpiar_email(data['email']) for data in batch_data if limpiar_email(data.get('email', ''))}

    # Find existing clients based on unique fields in the batch
    existing_q = Q()
    if documentos_en_lote: existing_q |= Q(documento_identidad__in=documentos_en_lote)
    if telefonos_en_lote: existing_q |= Q(telefono__in=telefonos_en_lote)
    if emails_en_lote: existing_q |= Q(email__in=emails_en_lote)

    existing_clients_map = {}
    if existing_q:
        for client in Cliente.objects.filter(existing_q):
            if client.documento_identidad: existing_clients_map[f"doc_{client.documento_identidad}"] = client
            if client.telefono: existing_clients_map[f"tel_{client.telefono}"] = client
            if client.email: existing_clients_map[f"email_{client.email}"] = client

    clients_to_create = []
    clients_to_update = []
    processed_in_batch = set() # Track clients processed within this batch to avoid duplicates

    with transaction.atomic():
        for data in batch_data:
            try:
                row_num = data['row']
                documento = str(data.get('documento_identidad', '')).strip()
                nombre = str(data.get('nombre', '')).strip()
                telefono_limpio = limpiar_telefono(data.get('telefono', ''))
                email_limpio = limpiar_email(data.get('email', ''))
                ciudad = str(data.get('ciudad', '')).strip()

                # Skip if essential data missing (already checked name, but double-check)
                if not nombre: continue

                # --- Find existing client ---
                found_client = None
                lookup_keys = []
                if documento: lookup_keys.append(f"doc_{documento}")
                if telefono_limpio: lookup_keys.append(f"tel_{telefono_limpio}")
                if email_limpio: lookup_keys.append(f"email_{email_limpio}")

                for key in lookup_keys:
                    if key in existing_clients_map:
                        found_client = existing_clients_map[key]
                        break # Found a match

                # Avoid processing the same DB client multiple times within the batch
                if found_client and found_client.id in processed_in_batch:
                    continue

                if found_client:
                    # --- Update existing client ---
                    update_fields = []
                    if nombre and found_client.nombre != nombre:
                        found_client.nombre = nombre
                        update_fields.append('nombre')
                    # Update only if new data is provided and different
                    if documento and found_client.documento_identidad != documento:
                        found_client.documento_identidad = documento
                        update_fields.append('documento_identidad')
                    if telefono_limpio and found_client.telefono != telefono_limpio:
                        found_client.telefono = telefono_limpio
                        update_fields.append('telefono')
                    if email_limpio and found_client.email != email_limpio:
                        found_client.email = email_limpio
                        update_fields.append('email')
                    if ciudad and found_client.ciudad != ciudad:
                        found_client.ciudad = ciudad
                        update_fields.append('ciudad')

                    if update_fields:
                        # found_client.save(update_fields=update_fields) # Use update_fields for efficiency
                        clients_to_update.append(found_client) # Add to bulk update list
                        clientes_actualizados.append(f"{nombre} (fila {row_num})")

                    processed_in_batch.add(found_client.id)

                else:
                    # --- Prepare to create new client ---
                    # Check for potential duplicates based on data *within the batch* before adding
                    if (documento and f"doc_{documento}" in existing_clients_map) or \
                       (telefono_limpio and f"tel_{telefono_limpio}" in existing_clients_map) or \
                       (email_limpio and f"email_{email_limpio}" in existing_clients_map):
                        # This data matches a client already processed/found in this batch run, skip creation
                        continue

                    new_client_obj = Cliente(
                        documento_identidad=documento or None, # Use None if empty for unique constraints
                        nombre=nombre,
                        telefono=telefono_limpio or None,
                        email=email_limpio or None,
                        ciudad=ciudad or None
                    )
                    clients_to_create.append(new_client_obj)
                    clientes_nuevos.append(f"{nombre} (fila {row_num})")
                    # Add keys to map to prevent duplicates within the batch creation step
                    if documento: existing_clients_map[f"doc_{documento}"] = new_client_obj # Placeholder
                    if telefono_limpio: existing_clients_map[f"tel_{telefono_limpio}"] = new_client_obj
                    if email_limpio: existing_clients_map[f"email_{email_limpio}"] = new_client_obj


            except Exception as e:
                errores.append(f"Error en fila {data.get('row', 'desconocida')}: {str(e)}")

        # Bulk operations (more efficient for large batches)
        if clients_to_create:
            try:
                Cliente.objects.bulk_create(clients_to_create, ignore_conflicts=True) # ignore_conflicts might hide issues
            except Exception as e:
                 errores.append(f"Error en bulk_create: {str(e)}")
        if clients_to_update:
            try:
                 # Determine all fields that might have been updated across the batch
                 all_update_fields = {'nombre', 'documento_identidad', 'telefono', 'email', 'ciudad'}
                 Cliente.objects.bulk_update(clients_to_update, list(all_update_fields))
            except Exception as e:
                 errores.append(f"Error en bulk_update: {str(e)}")
