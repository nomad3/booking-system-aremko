import json
import traceback
from datetime import datetime
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.db import transaction
from django.db.models.signals import pre_save # Import pre_save signal
from django.contrib import messages
from ..models import Servicio, Cliente, VentaReserva, ReservaServicio, Pago # Relative imports
# Import the specific signal receiver to disconnect/reconnect
from ..signals import validar_disponibilidad_admin

def cart_view(request):
    """
    Vista que renderiza la página del carrito de compras
    """
    # Obtener carrito de compras de la sesión o crear uno nuevo
    cart = request.session.get('cart', {'servicios': [], 'total': 0})

    context = {
        'cart': cart
    }
    return render(request, 'ventas/cart.html', context)

def add_to_cart(request):
    """
    Vista para agregar un servicio al carrito de compras
    """
    if request.method == 'POST':
        servicio_id = request.POST.get('servicio_id')
        fecha = request.POST.get('fecha')
        hora = request.POST.get('hora')
        cantidad_personas = int(request.POST.get('cantidad_personas', 1))

        print(f"Adding to cart: servicio_id={servicio_id}, fecha={fecha}, hora={hora}, cantidad_personas={cantidad_personas}")

        try:
            servicio = Servicio.objects.get(id=servicio_id)

            # --- Capacity Validation ---
            # Ensure minimum capacity is met
            if cantidad_personas < servicio.capacidad_minima:
                 messages.error(request, f"La cantidad mínima de personas para '{servicio.nombre}' es {servicio.capacidad_minima}.")
                 referer_url = request.META.get('HTTP_REFERER', reverse('ventas:homepage')) # Added namespace
                 return redirect(referer_url)

            # Ensure maximum capacity is not exceeded
            if cantidad_personas > servicio.capacidad_maxima:
                 messages.error(request, f"La capacidad máxima para '{servicio.nombre}' es {servicio.capacidad_maxima} personas.")
                 referer_url = request.META.get('HTTP_REFERER', reverse('ventas:homepage')) # Added namespace
                 return redirect(referer_url)

            # --- Cabin Specific Logic (Price is fixed, quantity handled by general capacity check) ---
            # No specific quantity adjustment needed here anymore as max_cap handles it.
            # if servicio.tipo_servicio == 'cabana':
            #     cantidad_personas = min(cantidad_personas, servicio.capacidad_maxima) # Already checked above
            #     print(f"Cabin selected, quantity: {cantidad_personas}")

            # Obtener carrito actual o crear uno nuevo
            cart = request.session.get('cart', {'servicios': [], 'total': 0})

            # Agregar servicio al carrito
            item = {
                'id': servicio.id,  # Use 'id' consistently
                'nombre': servicio.nombre,
                'precio': float(servicio.precio_base),
                'fecha': fecha,
                'hora': hora,
                'cantidad_personas': cantidad_personas,
                'tipo_servicio': servicio.tipo_servicio, # Add service type to cart item
                 # Calculate subtotal based on service type
                'subtotal': float(servicio.precio_base) if servicio.tipo_servicio == 'cabana' else float(servicio.precio_base) * cantidad_personas
            }

            print(f"Cart item to add: {item}")

            cart['servicios'].append(item)

            # Recalcular total
            cart['total'] = sum(item['subtotal'] for item in cart['servicios'])

            # Guardar carrito en la sesión
            request.session['cart'] = cart
            request.session.modified = True

            print(f"Updated cart: {cart}")

            # Redirigir a la página del carrito
            return redirect('ventas:cart') # Redirect to cart view with namespace
        except Servicio.DoesNotExist:
            # Handle error appropriately, maybe redirect back with a message
            messages.error(request, "El servicio seleccionado no existe.")
            referer_url = request.META.get('HTTP_REFERER', reverse('ventas:homepage')) # Added namespace
            return redirect(referer_url)
        except Exception as e:
            messages.error(request, f"Ocurrió un error al agregar al carrito: {e}")
            referer_url = request.META.get('HTTP_REFERER', reverse('ventas:homepage')) # Added namespace
            return redirect(referer_url)

    # If not POST, redirect or show an error
    messages.error(request, "Método no permitido.")
    return redirect(reverse('ventas:homepage')) # Redirect to homepage or appropriate page with namespace

def remove_from_cart(request):
    if request.method == 'POST':
        try:
            index = int(request.POST.get('index', ''))
            cart = request.session.get('cart', {'servicios': [], 'total': 0})

            if 'servicios' in cart and 0 <= index < len(cart['servicios']):
                del cart['servicios'][index]
                found = True
            else:
                found = False
                print(f"Error removing from cart: Index {index} out of bounds or 'servicios' key missing.")

            # Recalculate total
            total = sum(float(item.get('subtotal', 0)) for item in cart.get('servicios', []))
            cart['total'] = total

            request.session['cart'] = cart
            request.session.modified = True

            if found:
                return JsonResponse({'success': True})
            else:
                return JsonResponse({'success': False, 'error': 'Ítem no encontrado en el carrito.'})

        except ValueError:
             print("Error removing from cart: Invalid index format.")
             return JsonResponse({'success': False, 'error': 'Índice inválido.'})
        except Exception as e:
            print(f"Error removing from cart: {str(e)}")
            traceback.print_exc()
            return JsonResponse({'success': False, 'error': f'Error interno del servidor: {str(e)}'})

    return JsonResponse({'success': False, 'error': 'Método no permitido'})

def checkout_view(request):
    # Get cart from session
    cart = request.session.get('cart', {'servicios': [], 'total': 0})

    # Get relevant payment methods for checkout
    # Filter Pago.METODOS_PAGO to only include public-facing options
    public_payment_methods = [
        choice for choice in Pago.METODOS_PAGO
        if choice[0] in ['transferencia', 'flow'] # Explicitly define public methods for now
    ]

    context = {
        'cart': cart,
        'payment_methods': public_payment_methods, # Add payment methods to context
    }

    return render(request, 'ventas/checkout.html', context)

def complete_checkout(request):
    if request.method == 'POST':
        try:
            # Get form data
            nombre = request.POST.get('nombre')
            email = request.POST.get('email')
            telefono = request.POST.get('telefono')
            documento_identidad = request.POST.get('documento_identidad', '')
            metodo_pago = request.POST.get('metodo_pago') # Get payment method

            # Get cart from session
            cart = request.session.get('cart', {'servicios': [], 'total': 0})

            # Debug cart structure
            print("CART STRUCTURE:")
            print(f"Cart type: {type(cart)}")
            print(f"Cart keys: {cart.keys()}")
            print(f"Cart servicios: {cart.get('servicios', [])}")

            if not cart.get('servicios'):
                return JsonResponse({'success': False, 'error': 'El carrito está vacío'})

            # Validate availability before creating anything
            unavailable_slots = []
            for servicio_item in cart['servicios']: # Renamed variable
                servicio_id = servicio_item.get('id')
                if not servicio_id:
                    continue

                servicio_obj = Servicio.objects.get(id=servicio_id)
                fecha = datetime.strptime(servicio_item['fecha'], '%Y-%m-%d').date()
                hora = servicio_item['hora']

                # Check if the slot is still available
                existing_reservas = ReservaServicio.objects.filter(
                    servicio=servicio_obj,
                    fecha_agendamiento=fecha,
                    hora_inicio=hora
                )

                if existing_reservas.exists():
                    unavailable_slots.append(f"Slot {hora} no disponible para {servicio_obj.nombre}")

            if unavailable_slots:
                # Join the list of unavailable slots into a single string
                error_message = ", ".join(unavailable_slots)
                return JsonResponse({'success': False, 'error': f"Algunos horarios ya no están disponibles: {error_message}"})


            # Clean/normalize phone number (basic example)
            # Consider using phonenumbers library for robust parsing/validation
            cleaned_telefono = ''.join(filter(str.isdigit, telefono))
            if len(cleaned_telefono) > 9 and not telefono.startswith('+'):
                 formatted_telefono = '+' + cleaned_telefono # Basic international format assumption
            else:
                 formatted_telefono = telefono

            # Get or create cliente using the phone number
            cliente, created = Cliente.objects.get_or_create(
                telefono=formatted_telefono, # Use phone number for lookup
                defaults={
                    'nombre': nombre,
                    'email': email, # Still save email if provided
                    'documento_identidad': documento_identidad
                }
            )

            # If cliente exists, update name/email if they were changed in the form
            if not created:
                update_needed = False
                if cliente.nombre != nombre:
                    cliente.nombre = nombre
                    update_needed = True
                # Update email only if it's provided and different, or if it was null before
                if email and cliente.email != email:
                    cliente.email = email
                    update_needed = True
                elif not cliente.email and email: # Add email if it was missing
                    cliente.email = email
                    update_needed = True
                # Update document if provided and different
                if documento_identidad and cliente.documento_identidad != documento_identidad:
                     cliente.documento_identidad = documento_identidad
                     update_needed = True
                elif not cliente.documento_identidad and documento_identidad: # Add doc if missing
                     cliente.documento_identidad = documento_identidad
                     update_needed = True

                if update_needed:
                    cliente.save()

            # Create VentaReserva
            with transaction.atomic():
                # Temporarily disconnect the specific validation signal
                signal_disconnected = False
                try:
                    pre_save.disconnect(validar_disponibilidad_admin, sender=ReservaServicio)
                    signal_disconnected = True
                    print("DEBUG: Disconnected validar_disponibilidad_admin signal.") # Debug print

                    venta = VentaReserva.objects.create(
                        cliente=cliente,
                        total=cart['total'], # Initial total from cart
                        estado_pago='pendiente',
                        estado_reserva='pendiente',
                        fecha_reserva=timezone.now()
                    )

                    # Create ReservaServicio for each service in cart
                    for servicio_item in cart['servicios']: # Renamed variable
                        # Get the service ID
                        servicio_id = servicio_item.get('id')

                        if not servicio_id:
                            print(f"Warning: Missing service ID in cart item: {servicio_item}")
                            continue

                        servicio_obj = Servicio.objects.get(id=servicio_id)
                        fecha = datetime.strptime(servicio_item['fecha'], '%Y-%m-%d').date()

                        # Create the reservation without pre_save validation
                        ReservaServicio.objects.create(
                            venta_reserva=venta,
                            servicio=servicio_obj,
                            fecha_agendamiento=fecha,
                            hora_inicio=servicio_item['hora'],
                            cantidad_personas=servicio_item['cantidad_personas']
                        )

                    # Recalculate total based on the services actually added and save
                    venta.calcular_total() # This should save the VentaReserva instance

                    # If bank transfer, ensure estado_pago remains 'pendiente'.
                    if metodo_pago == 'transferencia':
                        venta.estado_pago = 'pendiente' # Explicitly set as pending
                        venta.save(update_fields=['estado_pago']) # Save only this field change

                    # Clear cart
                    request.session['cart'] = {'servicios': [], 'total': 0}
                    request.session.modified = True

                    # Generate the detail URL
                    detail_url = reverse('ventas:venta_reserva_detail', kwargs={'pk': venta.id}) # Added namespace

                    # Return success response including the detail URL
                    response_data = {
                        'success': True,
                        'message': 'Reserva creada exitosamente',
                        'reserva_id': venta.id,
                        'metodo_pago': metodo_pago,
                        'redirect_url': detail_url # Add the redirect URL
                    }

                    return JsonResponse(response_data)
                finally:
                    # Reconnect the signal if it was disconnected
                    if signal_disconnected:
                        pre_save.connect(validar_disponibilidad_admin, sender=ReservaServicio)
                        print("DEBUG: Reconnected validar_disponibilidad_admin signal.") # Debug print

        except Servicio.DoesNotExist:
             return JsonResponse({'success': False, 'error': 'Uno de los servicios en el carrito ya no existe.'})
        except Exception as e:
            print(f"Error in complete_checkout: {e}")
            traceback.print_exc()
            return JsonResponse({'success': False, 'error': f'Ocurrió un error inesperado: {str(e)}'})

    # If not POST, return error as JSON
    return JsonResponse({'success': False, 'error': 'Método no permitido'})
