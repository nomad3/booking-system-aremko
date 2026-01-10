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
from ..models import Servicio, Cliente, VentaReserva, ReservaServicio, Pago, Region, Comuna # Relative imports
# Import the specific signal receiver to disconnect/reconnect
from ..signals import validar_disponibilidad_admin
from ..services.cliente_service import ClienteService
from ..services.pack_descuento_service import PackDescuentoService

def cart_view(request):
    """
    Vista que renderiza la página del carrito de compras
    Soporta servicios y GiftCards con descuentos por packs
    """
    # Obtener carrito de compras de la sesión o crear uno nuevo
    cart = request.session.get('cart', {'servicios': [], 'giftcards': [], 'total': 0})

    # Asegurar que existe la clave giftcards (para carritos antiguos)
    if 'giftcards' not in cart:
        cart['giftcards'] = []

    # Calcular totales con descuentos por packs
    calculos = PackDescuentoService.calcular_total_con_descuentos(cart)

    # Actualizar carrito con información de descuentos
    cart['subtotal'] = calculos['subtotal']
    cart['descuentos'] = calculos['descuentos']
    cart['total_descuentos'] = calculos['total_descuentos']
    cart['total'] = calculos['total']

    # Obtener sugerencias de packs
    sugerencias = []
    if cart['servicios']:
        sugerencias = PackDescuentoService.obtener_sugerencias_pack(cart['servicios'])

    # Guardar el cart actualizado en la sesión
    request.session['cart'] = cart
    request.session.modified = True

    context = {
        'cart': cart,
        'sugerencias_pack': sugerencias
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
            item_type = request.POST.get('type', 'servicio')  # 'servicio' o 'giftcard'
            cart = request.session.get('cart', {'servicios': [], 'giftcards': [], 'total': 0})

            # Asegurar que existe la clave giftcards (para carritos antiguos)
            if 'giftcards' not in cart:
                cart['giftcards'] = []

            found = False

            # Eliminar según el tipo de item
            if item_type == 'giftcard':
                if 'giftcards' in cart and 0 <= index < len(cart['giftcards']):
                    removed_item = cart['giftcards'][index]
                    del cart['giftcards'][index]
                    found = True
                    print(f"✅ GiftCard removida: {removed_item.get('experiencia_nombre', 'Unknown')}")
            else:  # servicio
                if 'servicios' in cart and 0 <= index < len(cart['servicios']):
                    removed_item = cart['servicios'][index]
                    del cart['servicios'][index]
                    found = True
                    print(f"✅ Servicio removido: {removed_item.get('nombre', 'Unknown')}")

            if not found:
                print(f"❌ Error removing from cart: Index {index} out of bounds for type {item_type}")

            # Recalcular total incluyendo servicios y giftcards
            total_servicios = sum(float(item.get('subtotal', 0)) for item in cart.get('servicios', []))
            total_giftcards = sum(float(item.get('precio', 0)) for item in cart.get('giftcards', []))
            cart['total'] = total_servicios + total_giftcards

            request.session['cart'] = cart
            request.session.modified = True

            if found:
                return JsonResponse({'success': True, 'cart_count': len(cart['servicios']) + len(cart['giftcards'])})
            else:
                return JsonResponse({'success': False, 'error': f'Ítem no encontrado en el carrito (tipo: {item_type}, índice: {index}).'})

        except ValueError:
             print("Error removing from cart: Invalid index format.")
             return JsonResponse({'success': False, 'error': 'Índice inválido.'})
        except Exception as e:
            print(f"Error removing from cart: {str(e)}")
            traceback.print_exc()
            return JsonResponse({'success': False, 'error': f'Error interno del servidor: {str(e)}'})

    return JsonResponse({'success': False, 'error': 'Método no permitido'})

def checkout_view(request):
    # Get cart from session (incluye servicios y giftcards)
    cart = request.session.get('cart', {'servicios': [], 'giftcards': [], 'total': 0})

    # Asegurar que existe la clave giftcards (para carritos antiguos)
    if 'giftcards' not in cart:
        cart['giftcards'] = []

    # Calcular totales con descuentos por packs
    calculos = PackDescuentoService.calcular_total_con_descuentos(cart)

    # Actualizar carrito con información de descuentos
    cart['subtotal'] = calculos['subtotal']
    cart['descuentos'] = calculos['descuentos']
    cart['total_descuentos'] = calculos['total_descuentos']
    cart['total'] = calculos['total']

    # Actualizar sesión
    request.session['cart'] = cart
    request.session.modified = True

    # Get relevant payment methods for checkout
    # Filter Pago.METODOS_PAGO to only include public-facing options
    public_payment_methods = [
        choice for choice in Pago.METODOS_PAGO
        if choice[0] in ['transferencia', 'flow', 'mercadopago_link'] # Include Mercado Pago Link
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
            region_id = request.POST.get('region')
            comuna_id = request.POST.get('comuna')
            metodo_pago = request.POST.get('metodo_pago') # Get payment method

            # Get cart from session
            cart = request.session.get('cart', {'servicios': [], 'giftcards': [], 'total': 0})

            # Asegurar que existe la clave giftcards
            if 'giftcards' not in cart:
                cart['giftcards'] = []

            # Calcular totales con descuentos por packs
            calculos = PackDescuentoService.calcular_total_con_descuentos(cart)
            cart['subtotal'] = calculos['subtotal']
            cart['descuentos'] = calculos['descuentos']
            cart['total_descuentos'] = calculos['total_descuentos']
            cart['total'] = calculos['total']

            # Debug cart structure
            print("CART STRUCTURE:")
            print(f"Cart type: {type(cart)}")
            print(f"Cart keys: {cart.keys()}")
            print(f"Cart servicios: {cart.get('servicios', [])}")
            print(f"Cart giftcards: {cart.get('giftcards', [])}")
            if cart.get('descuentos'):
                print(f"Descuentos aplicados: {cart['descuentos']}")
                print(f"Total con descuentos: ${cart['total']:,.0f}")

            # Validar que el carrito no esté vacío (servicios O giftcards)
            if not cart.get('servicios') and not cart.get('giftcards'):
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


            # Crear o actualizar cliente usando el servicio centralizado
            try:
                # Preparar datos del cliente para el servicio
                datos_cliente = {
                    'telefono': telefono,
                    'nombre': nombre,
                    'email': email,
                    'documento_identidad': documento_identidad
                }

                # Agregar región y comuna si se proporcionaron
                if region_id:
                    datos_cliente['region_id'] = int(region_id)
                if comuna_id:
                    datos_cliente['comuna_id'] = int(comuna_id)

                # Usar servicio centralizado para crear/actualizar cliente
                cliente, created, errors = ClienteService.crear_o_actualizar_cliente(datos_cliente)

                if errors:
                    error_message = "; ".join(errors)
                    return JsonResponse({
                        'success': False,
                        'error': f'Error al procesar cliente: {error_message}'
                    })

                if not cliente:
                    return JsonResponse({
                        'success': False,
                        'error': 'Error inesperado al procesar datos del cliente'
                    })

                if created:
                    print(f"✅ Cliente NUEVO creado en checkout: {cliente.nombre} ({cliente.telefono})")
                else:
                    print(f"ℹ️ Cliente EXISTENTE actualizado en checkout: {cliente.nombre} ({cliente.telefono})")

            except Exception as e:
                print(f"❌ Error al crear/obtener cliente en checkout: {e}")
                traceback.print_exc()
                return JsonResponse({
                    'success': False,
                    'error': f'Error al procesar datos del cliente: {str(e)}'
                })

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
                    # Detectar si hay masajes para Google Ads tracking
                    tiene_masaje = False

                    for servicio_item in cart['servicios']: # Renamed variable
                        # Get the service ID
                        servicio_id = servicio_item.get('id')

                        if not servicio_id:
                            print(f"Warning: Missing service ID in cart item: {servicio_item}")
                            continue

                        servicio_obj = Servicio.objects.get(id=servicio_id)

                        # Verificar si es un masaje (categoria_id == 2)
                        if servicio_obj.categoria_id == 2:
                            tiene_masaje = True

                        fecha = datetime.strptime(servicio_item['fecha'], '%Y-%m-%d').date()

                        # Create the reservation without pre_save validation
                        ReservaServicio.objects.create(
                            venta_reserva=venta,
                            servicio=servicio_obj,
                            fecha_agendamiento=fecha,
                            hora_inicio=servicio_item['hora'],
                            cantidad_personas=servicio_item['cantidad_personas']
                        )

                    # Aplicar descuentos por pack como ReservaServicio
                    if calculos.get('total_descuentos', 0) > 0:
                        try:
                            # Buscar servicio especial de descuento
                            servicio_descuento = Servicio.objects.get(
                                nombre__icontains='descuento',
                                precio_base=-1
                            )

                            # Usar fecha del primer servicio del carrito
                            fecha_descuento = datetime.strptime(
                                cart['servicios'][0]['fecha'], '%Y-%m-%d'
                            ).date()

                            # Crear ReservaServicio con el descuento
                            ReservaServicio.objects.create(
                                venta_reserva=venta,
                                servicio=servicio_descuento,
                                fecha_agendamiento=fecha_descuento,
                                hora_inicio='00:00',  # Hora especial para descuentos
                                cantidad_personas=int(calculos['total_descuentos'])
                            )
                            print(f"✅ Descuento pack aplicado: ${calculos['total_descuentos']:,.0f}")
                        except Servicio.DoesNotExist:
                            print("⚠️ Servicio de descuento no encontrado. Verifique que existe un servicio con nombre 'descuento' y precio_base=-1")
                        except Exception as e:
                            print(f"⚠️ Error al aplicar descuento pack: {e}")

                    # Create GiftCard for each giftcard in cart
                    from ..models import GiftCard
                    from datetime import timedelta

                    for giftcard_item in cart.get('giftcards', []):
                        # Crear Cliente para el DESTINATARIO (quien usará el servicio)
                        destinatario_telefono = giftcard_item.get('destinatario_telefono', '')
                        destinatario_email = giftcard_item.get('destinatario_email', '')
                        destinatario_nombre = giftcard_item.get('destinatario_nombre', 'Destinatario')

                        # Solo crear Cliente si tenemos al menos teléfono o email
                        cliente_destinatario = None
                        if destinatario_telefono or destinatario_email:
                            try:
                                # Normalizar teléfono del destinatario
                                if destinatario_telefono:
                                    dest_telefono_normalizado = destinatario_telefono.replace(' ', '').replace('-', '')
                                    if not dest_telefono_normalizado.startswith('+'):
                                        if dest_telefono_normalizado.startswith('9'):
                                            dest_telefono_normalizado = '+56' + dest_telefono_normalizado
                                        elif dest_telefono_normalizado.startswith('56'):
                                            dest_telefono_normalizado = '+' + dest_telefono_normalizado
                                else:
                                    dest_telefono_normalizado = ''

                                # Buscar o crear Cliente destinatario
                                if dest_telefono_normalizado:
                                    cliente_destinatario, created = Cliente.objects.get_or_create(
                                        telefono=dest_telefono_normalizado,
                                        defaults={
                                            'nombre': destinatario_nombre,
                                            'email': destinatario_email
                                        }
                                    )
                                    if created:
                                        print(f"✅ Cliente DESTINATARIO creado: {cliente_destinatario.nombre} ({cliente_destinatario.telefono})")
                                    else:
                                        print(f"ℹ️ Cliente DESTINATARIO existente: {cliente_destinatario.nombre}")
                                else:
                                    # Si no hay teléfono pero hay email, buscar por email
                                    if destinatario_email:
                                        try:
                                            cliente_destinatario = Cliente.objects.get(email=destinatario_email)
                                            print(f"ℹ️ Cliente DESTINATARIO encontrado por email: {cliente_destinatario.nombre}")
                                        except Cliente.DoesNotExist:
                                            # Crear sin teléfono (puede fallar si teléfono es required)
                                            print(f"⚠️ No se puede crear Cliente destinatario sin teléfono: {destinatario_nombre}")
                                        except Cliente.MultipleObjectsReturned:
                                            cliente_destinatario = Cliente.objects.filter(email=destinatario_email).first()
                                            print(f"ℹ️ Múltiples clientes con email {destinatario_email}, usando primero")

                            except Exception as e:
                                print(f"⚠️ Error al crear Cliente destinatario: {e}")
                                traceback.print_exc()

                        # Calcular fecha de vencimiento (1 año desde hoy)
                        fecha_vencimiento = timezone.now().date() + timedelta(days=365)

                        # Crear GiftCard con todos los campos del wizard
                        giftcard = GiftCard.objects.create(
                            monto_inicial=giftcard_item['precio'],
                            monto_disponible=giftcard_item['precio'],
                            fecha_emision=timezone.now().date(),
                            fecha_vencimiento=fecha_vencimiento,
                            estado='por_cobrar',  # Cambiará a 'cobrado' cuando se pague
                            cliente_comprador=cliente,
                            cliente_destinatario=cliente_destinatario,

                            # Vincular a la VentaReserva
                            venta_reserva=venta,

                            # Datos del comprador (capturados en checkout)
                            comprador_nombre=nombre,
                            comprador_email=email,
                            comprador_telefono=telefono,

                            # Datos del destinatario (capturados en wizard)
                            destinatario_nombre=giftcard_item.get('destinatario_nombre', ''),
                            destinatario_email=giftcard_item.get('destinatario_email', ''),
                            destinatario_telefono=giftcard_item.get('destinatario_telefono', ''),

                            # Configuración de mensaje IA (capturados en wizard)
                            tipo_mensaje=giftcard_item.get('tipo_mensaje', ''),
                            mensaje_personalizado=giftcard_item.get('mensaje_seleccionado', ''),

                            # Servicio asociado (experiencia seleccionada)
                            servicio_asociado=giftcard_item.get('experiencia_id', '')
                        )

                        # Guardar metadata de la GiftCard en la sesión para usarla después del pago
                        if 'giftcards_metadata' not in request.session:
                            request.session['giftcards_metadata'] = []

                        request.session['giftcards_metadata'].append({
                            'giftcard_id': giftcard.id,
                            'codigo': giftcard.codigo,
                            'experiencia_nombre': giftcard_item['experiencia_nombre'],
                            'destinatario_nombre': giftcard_item['destinatario_nombre'],
                            'destinatario_email': giftcard_item['destinatario_email'],
                            'destinatario_telefono': giftcard_item.get('destinatario_telefono', ''),
                            'destinatario_cliente_id': cliente_destinatario.id if cliente_destinatario else None,
                            'mensaje_seleccionado': giftcard_item['mensaje_seleccionado'],
                            'tipo_mensaje': giftcard_item['tipo_mensaje'],
                            'venta_id': venta.id
                        })
                        request.session.modified = True

                        print(f"✅ GiftCard creada: {giftcard.codigo} para {giftcard_item['destinatario_nombre']}")

                    # Recalculate total based on the services actually added and save
                    venta.calcular_total() # This should save the VentaReserva instance

                    # If bank transfer, ensure estado_pago remains 'pendiente'.
                    if metodo_pago == 'transferencia':
                        venta.estado_pago = 'pendiente' # Explicitly set as pending
                        venta.save(update_fields=['estado_pago']) # Save only this field change

                    # Clear cart
                    request.session['cart'] = {'servicios': [], 'giftcards': [], 'total': 0}
                    request.session.modified = True

                    # Generate the detail URL
                    detail_url = reverse('ventas:venta_reserva_detail', kwargs={'pk': venta.id}) # Added namespace

                    # Return success response including the detail URL
                    response_data = {
                        'success': True,
                        'message': 'Reserva creada exitosamente',
                        'reserva_id': venta.id,
                        'metodo_pago': metodo_pago,
                        'redirect_url': detail_url, # Add the redirect URL
                        'tiene_masaje': tiene_masaje, # Para Google Ads tracking
                        'total_reserva': float(cart['total']) # Para Google Ads conversion value
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

def get_client_details_by_phone(request):
    """
    API endpoint para buscar cliente por teléfono usando búsqueda robusta
    Utiliza múltiples variantes de formato para garantizar encontrar clientes existentes

    Respuestas:
    - found=True, valid=True: Cliente existe, retorna datos completos
    - found=False, valid=True: Teléfono válido pero cliente no existe
    - found=False, valid=False: Teléfono inválido
    """
    if request.method == 'GET':
        telefono_raw = request.GET.get('telefono', '').strip()

        if not telefono_raw:
            return JsonResponse({
                'found': False,
                'valid': False,
                'error': 'Teléfono vacío'
            })

        # Validar que no contenga letras
        import re
        if re.search(r'[a-zA-Z]', telefono_raw):
            return JsonResponse({
                'found': False,
                'valid': False,
                'error': 'El teléfono no puede contener letras.'
            })

        try:
            print("=" * 80)
            print("🚨 DEBUGGING TELEFONO +56994436882")
            print("=" * 80)
            print(f"🔍 Backend recibió teléfono: '{telefono_raw}'")
            print(f"   Longitud: {len(telefono_raw)} caracteres")
            print(f"   Contiene espacios: {' ' in telefono_raw}")

            # Usar servicio robusto de búsqueda con múltiples variantes
            cliente, telefono_normalizado = ClienteService.buscar_cliente_por_telefono(telefono_raw)

            print(f"   Resultado normalización: '{telefono_normalizado}'")
            print(f"   Cliente encontrado: {cliente.nombre if cliente else 'No encontrado'}")
            print("=" * 80)

            if not telefono_normalizado:
                return JsonResponse({
                    'found': False,
                    'valid': False,
                    'error': 'Formato de teléfono inválido. Usa formato chileno: +56 9 XXXX XXXX'
                })

            if cliente:
                # Cliente encontrado - retornar datos completos con relaciones
                datos_cliente = ClienteService.obtener_datos_completos_cliente(cliente)

                print(f"✅ Cliente encontrado en checkout: {cliente.nombre} ({cliente.email}) - Teléfono: {telefono_normalizado}")

                return JsonResponse({
                    'found': True,
                    'valid': True,
                    'nombre': datos_cliente['cliente']['nombre'],
                    'email': datos_cliente['cliente']['email'],
                    'documento_identidad': datos_cliente['cliente']['documento_identidad'],
                    'telefono_normalizado': telefono_normalizado,

                    # Datos adicionales para el checkout (región y comuna)
                    'region_id': datos_cliente['cliente']['region_id'],
                    'region_nombre': datos_cliente['cliente']['region_nombre'],
                    'comuna_id': datos_cliente['cliente']['comuna_id'],
                    'comuna_nombre': datos_cliente['cliente']['comuna_nombre'],
                    'pais': datos_cliente['cliente']['pais'],

                    # Info adicional del cliente
                    'numero_visitas': datos_cliente['cliente']['numero_visitas'],
                    'gasto_total': datos_cliente['cliente']['gasto_total'],
                    'datos_completos': datos_cliente['cliente']['datos_completos']
                })
            else:
                # Cliente no existe, pero teléfono es válido
                print(f"ℹ️ Cliente nuevo en checkout con teléfono: {telefono_raw} -> normalizado: {telefono_normalizado}")

                return JsonResponse({
                    'found': False,
                    'valid': True,
                    'telefono_normalizado': telefono_normalizado,
                    'message': 'Cliente nuevo. Por favor completa tus datos.'
                })

        except Exception as e:
            print(f"❌ Error en get_client_details_by_phone: {e}")
            traceback.print_exc()
            return JsonResponse({
                'found': False,
                'valid': False,
                'error': f'Error al validar teléfono: {str(e)}'
            })

    return JsonResponse({'error': 'Método no permitido'}, status=405)
