import json
import traceback
from datetime import datetime, timedelta
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.contrib import messages
from ..models import (
    Servicio, Cliente, VentaReserva, Pago,
    ServicioBloqueo, ServicioSlotBloqueo, PendingReservation,
)
from ..services.cliente_service import ClienteService
from ..services.pack_descuento_service import PackDescuentoService
from ..services.reservation_service import (
    SlotUnavailableError,
    materializar_venta_desde_carrito,
    validar_disponibilidad_carrito,
)


PENDING_RESERVATION_TTL_MINUTES = 60

# AR-014: Tinas con precio plano por capacidad (cobra capacidad_maxima completa,
# ignora el cantidad_personas enviado desde el cliente para prevenir manipulación).
TINAS_PRECIO_PLANO = {
    'calbuco', 'osorno', 'tronador', 'hornopiren', 'hornopirén',
    'llaima', 'puntiagudo', 'puyehue', 'villarrica',
}


def _es_tina_precio_plano(servicio):
    """True si el servicio es una tina que debe cobrarse por capacidad_maxima."""
    if getattr(servicio, 'tipo_servicio', None) != 'tina':
        return False
    nombre = (getattr(servicio, 'nombre', '') or '').lower()
    return any(tag in nombre for tag in TINAS_PRECIO_PLANO)


def _es_precio_plano_por_unidad(servicio):
    """True si el servicio se cobra siempre por capacidad_maxima completa
    (cabañas + tinas de precio plano). El total mostrado en la card es
    precio_base × capacidad_maxima, por lo que el carrito debe reflejarlo."""
    if getattr(servicio, 'tipo_servicio', None) == 'cabana':
        return True
    return _es_tina_precio_plano(servicio)


# Desayuno: el cliente agrega "Desayuno" (servicio generico publicado en web),
# pero operativamente cada cabaña tiene su desayuno con nombre propio (para
# que recepcion sepa a que cabaña corresponde). Mapeo por keyword en el nombre
# de la cabaña → nombre exacto del servicio especifico en BD.
DESAYUNO_GENERICO_NOMBRE = 'Desayuno'
DESAYUNO_POR_CABANA_KEYWORD = (
    ('torre', 'Desayuno Torre'),
    ('laurel', 'Desayuno Laurel'),
    ('arrayan', 'Desayuno Arrayan'),
    ('arrayán', 'Desayuno Arrayan'),
    ('tepa', 'Desayuno Tepa'),
    ('acantilado', 'Desayuno Acantilado'),
)


def _resolver_desayuno_para_cabana(nombre_cabana):
    """Dado el nombre de una cabaña, devuelve el Servicio del desayuno especifico (o None)."""
    nombre_lower = (nombre_cabana or '').lower()
    for keyword, desayuno_nombre in DESAYUNO_POR_CABANA_KEYWORD:
        if keyword in nombre_lower:
            try:
                return Servicio.objects.get(nombre__iexact=desayuno_nombre)
            except Servicio.DoesNotExist:
                return None
    return None


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

    # "Seguir Comprando": si hay tina en carrito, volver a /tinas/ para que
    # el cliente vea las decoraciones (complemento). Si no, a homepage.
    tipos_en_cart = {s.get('tipo_servicio') for s in cart.get('servicios', [])}
    if 'tina' in tipos_en_cart:
        continue_shopping_url = reverse('tinas')
    elif 'masaje' in tipos_en_cart:
        continue_shopping_url = reverse('masajes')
    elif 'cabana' in tipos_en_cart:
        continue_shopping_url = reverse('alojamientos')
    else:
        continue_shopping_url = reverse('ventas:homepage') + '#servicios'

    context = {
        'cart': cart,
        'sugerencias_pack': sugerencias,
        'continue_shopping_url': continue_shopping_url,
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

            # --- Desayuno: mapear genérico a desayuno especifico de la cabaña ---
            # El cliente agrega "Desayuno" (servicio publicado en web). Operativamente
            # necesitamos que quede registrado como "Desayuno Torre", "Desayuno Tepa",
            # etc. segun la cabaña reservada para que recepcion sepa a donde llevarlo.
            # Distribucion ciclica: 1er desayuno → 1a cabaña, 2do → 2a, 3ro → 1a otra vez.
            if servicio.nombre.strip().lower() == DESAYUNO_GENERICO_NOMBRE.lower():
                cart_preview = request.session.get('cart', {'servicios': [], 'total': 0})
                cabanas_en_cart = [
                    s for s in cart_preview.get('servicios', [])
                    if s.get('tipo_servicio') == 'cabana'
                ]
                if not cabanas_en_cart:
                    messages.error(
                        request,
                        "Primero agrega una cabaña al carrito. El desayuno se asigna a una cabaña reservada."
                    )
                    referer_url = request.META.get('HTTP_REFERER', reverse('ventas:homepage'))
                    return redirect(referer_url)

                desayunos_previos = sum(
                    1 for s in cart_preview.get('servicios', [])
                    if 'desayuno' in (s.get('nombre') or '').lower()
                )
                cabana_target = cabanas_en_cart[desayunos_previos % len(cabanas_en_cart)]
                desayuno_especifico = _resolver_desayuno_para_cabana(cabana_target.get('nombre'))
                if desayuno_especifico:
                    print(
                        f"[DESAYUNO] '{servicio.nombre}' -> '{desayuno_especifico.nombre}' "
                        f"(cabaña destino: {cabana_target.get('nombre')}, "
                        f"desayunos previos: {desayunos_previos})"
                    )
                    servicio = desayuno_especifico
                    servicio_id = str(servicio.id)
                else:
                    print(
                        f"[DESAYUNO] No se encontro servicio especifico para cabaña "
                        f"'{cabana_target.get('nombre')}'. Se mantiene generico."
                    )

            # --- AR-014: Server-side override para servicios de precio plano ---
            # Cabañas y tinas flat se cobran SIEMPRE por capacidad_maxima
            # (precio plano por unidad), ignorando el cantidad_personas enviado
            # desde el cliente. Previene manipulación vía DevTools y alinea el
            # subtotal del carrito con el total mostrado en la card
            # (precio_base × capacidad_maxima).
            if _es_precio_plano_por_unidad(servicio):
                cantidad_original = cantidad_personas
                cantidad_personas = servicio.capacidad_maxima
                if cantidad_original != cantidad_personas:
                    print(
                        f"[AR-014] Precio plano '{servicio.nombre}' "
                        f"({servicio.tipo_servicio}): override cantidad_personas "
                        f"{cantidad_original} -> {cantidad_personas}"
                    )

            # --- Cabañas: check-in fijo a las 16:00 ---
            # Alojamientos solo tienen un horario posible. Forzamos servidor
            # para que cualquier hora enviada sea normalizada a 16:00.
            if getattr(servicio, 'tipo_servicio', None) == 'cabana':
                hora_original = hora
                hora = '16:00'
                if hora_original != hora:
                    print(
                        f"[CABANA] '{servicio.nombre}': override hora "
                        f"{hora_original!r} -> '16:00'"
                    )

            # --- Ambientaciones: requieren tina previa en carrito ---
            # Las decoraciones se venden como complemento de una tina. Para
            # la Agenda Operativa del día se necesita fecha+hora exactas, por
            # lo que heredan el slot de la última tina reservada. Si no hay
            # tina en carrito, bloqueamos. (Defensa servidor contra manipulación
            # cliente-side.)
            cat_nombre = ''
            if getattr(servicio, 'categoria', None):
                cat_nombre = (servicio.categoria.nombre or '').lower()
            if cat_nombre == 'ambientaciones':
                cart_preview = request.session.get(
                    'cart', {'servicios': [], 'total': 0}
                )
                tinas_en_cart = [
                    s for s in cart_preview.get('servicios', [])
                    if s.get('tipo_servicio') == 'tina'
                ]
                if not tinas_en_cart:
                    messages.error(
                        request,
                        "Primero agrega una tina a tu carrito. Las decoraciones "
                        "se coordinan con el horario de la tina reservada."
                    )
                    referer_url = request.META.get(
                        'HTTP_REFERER', reverse('ventas:homepage')
                    )
                    return redirect(referer_url)
                # Hereda fecha y hora de la última tina agregada
                last_tina = tinas_en_cart[-1]
                fecha_original, hora_original = fecha, hora
                fecha = last_tina.get('fecha') or fecha
                hora = last_tina.get('hora') or hora
                print(
                    f"[AMBIENTACION] '{servicio.nombre}': hereda slot de tina "
                    f"'{last_tina.get('nombre')}' -> fecha {fecha_original!r}->"
                    f"{fecha!r}, hora {hora_original!r}->{hora!r}"
                )

            # --- CRITICAL: Check if service is blocked on this date ---
            try:
                fecha_obj = datetime.strptime(fecha, '%Y-%m-%d').date()

                # Check 1: Day-level block
                if ServicioBloqueo.servicio_bloqueado_en_fecha(servicio_id, fecha_obj):
                    messages.error(request, f"El servicio '{servicio.nombre}' no está disponible en la fecha seleccionada (fuera de servicio).")
                    referer_url = request.META.get('HTTP_REFERER', reverse('ventas:homepage'))
                    return redirect(referer_url)

                # Check 2: Slot-level block
                if ServicioSlotBloqueo.slot_bloqueado(servicio_id, fecha_obj, hora):
                    messages.error(request, f"El horario {hora} para '{servicio.nombre}' no está disponible en la fecha seleccionada.")
                    referer_url = request.META.get('HTTP_REFERER', reverse('ventas:homepage'))
                    return redirect(referer_url)

            except ValueError:
                messages.error(request, "Fecha inválida.")
                referer_url = request.META.get('HTTP_REFERER', reverse('ventas:homepage'))
                return redirect(referer_url)

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
                 # Subtotal = precio_base × cantidad_personas.
                 # Para cabañas y tinas flat, cantidad_personas fue forzado
                 # a capacidad_maxima arriba (AR-014), por lo que esto
                 # coincide con el total mostrado en la card.
                'subtotal': float(servicio.precio_base) * cantidad_personas
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
    # Orden importa: el primero aparece arriba en el listado.
    # Flow primero (default), Transferencia segundo (alternativa para evitar 3% fee).
    public_payment_methods = [
        choice for choice in Pago.METODOS_PAGO
        if choice[0] in ['flow', 'transferencia']
    ]

    context = {
        'cart': cart,
        'payment_methods': public_payment_methods, # Add payment methods to context
    }

    return render(request, 'ventas/checkout.html', context)

def complete_checkout(request):
    """Punto de entrada del checkout.

    Comportamiento por metodo de pago:
    - 'transferencia': crea VentaReserva + ReservaServicio + GiftCards inmediatamente
      (la reserva queda 'pendiente' a la espera de la confirmacion bancaria manual).
    - 'flow' (y otros con redireccion a pasarela): NO crea VentaReserva. Solo guarda un
      PendingReservation con el snapshot del carrito y datos del cliente. La reserva real
      se materializa en el webhook de Flow cuando el pago se confirma. Esto evita reservas
      fantasma cuando el cliente abandona el pago.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'})

    try:
        nombre = request.POST.get('nombre')
        email = request.POST.get('email')
        telefono = request.POST.get('telefono')
        documento_identidad = request.POST.get('documento_identidad', '')
        region_id = request.POST.get('region')
        comuna_id = request.POST.get('comuna')
        metodo_pago = request.POST.get('metodo_pago')

        cart = request.session.get('cart', {'servicios': [], 'giftcards': [], 'total': 0})
        if 'giftcards' not in cart:
            cart['giftcards'] = []

        calculos = PackDescuentoService.calcular_total_con_descuentos(cart)
        cart['subtotal'] = calculos['subtotal']
        cart['descuentos'] = calculos['descuentos']
        cart['total_descuentos'] = calculos['total_descuentos']
        cart['total'] = calculos['total']

        if not cart.get('servicios') and not cart.get('giftcards'):
            return JsonResponse({'success': False, 'error': 'El carrito está vacío'})

        unavailable_slots = validar_disponibilidad_carrito(cart)
        if unavailable_slots:
            return JsonResponse({
                'success': False,
                'error': f"Algunos horarios ya no están disponibles: {', '.join(unavailable_slots)}"
            })

        try:
            datos_cliente = {
                'telefono': telefono,
                'nombre': nombre,
                'email': email,
                'documento_identidad': documento_identidad,
            }
            # Plan Geo E2: clasificación desde el checkout. "extranjero" marca país;
            # comuna chilena → la zona (sur/nacional) se deriva sola (Cliente.save).
            if region_id == 'extranjero':
                datos_cliente['pais'] = 'Extranjero'
            else:
                if region_id:
                    datos_cliente['region_id'] = int(region_id)
                if comuna_id:
                    datos_cliente['comuna_id'] = int(comuna_id)
                    datos_cliente['pais'] = 'Chile'

            cliente, created, errors = ClienteService.crear_o_actualizar_cliente(datos_cliente)

            if errors:
                return JsonResponse({
                    'success': False,
                    'error': f'Error al procesar cliente: {"; ".join(errors)}'
                })
            if not cliente:
                return JsonResponse({
                    'success': False,
                    'error': 'Error inesperado al procesar datos del cliente'
                })
        except Exception as e:
            print(f"Error al crear/obtener cliente en checkout: {e}")
            traceback.print_exc()
            return JsonResponse({
                'success': False,
                'error': f'Error al procesar datos del cliente: {str(e)}'
            })

        tiene_masaje = any(
            Servicio.objects.filter(id=item.get('id'), categoria_id=2).exists()
            for item in cart.get('servicios', []) if item.get('id')
        )

        if metodo_pago == 'flow':
            pending = PendingReservation.objects.create(
                cliente=cliente,
                cart_data=cart,
                metodo_pago='flow',
                monto=int(cart['total']),
                expires_at=timezone.now() + timedelta(minutes=PENDING_RESERVATION_TTL_MINUTES),
            )
            request.session['pending_reservation_id'] = pending.id
            request.session.modified = True
            print(f"PendingReservation #{pending.id} creada para {cliente.nombre} (${cart['total']:,.0f})")

            try:
                from ..services.meta_capi_service import send_schedule_event
                client_ip = (request.META.get('HTTP_X_FORWARDED_FOR') or '').split(',')[0].strip() \
                    or request.META.get('REMOTE_ADDR')
                send_schedule_event(
                    pending_id=pending.id,
                    amount=float(cart['total']),
                    email=cliente.email,
                    phone=cliente.telefono,
                    nombre_completo=cliente.nombre,
                    client_ip=client_ip,
                    user_agent=request.META.get('HTTP_USER_AGENT'),
                    fbp=request.COOKIES.get('_fbp'),
                    fbc=request.COOKIES.get('_fbc'),
                    event_source_url=request.build_absolute_uri('/checkout/'),
                )
            except Exception as capi_err:
                print(f"Meta CAPI Schedule fallo (no critico): {capi_err}")

            return JsonResponse({
                'success': True,
                'message': 'Reserva tentativa creada — pendiente de pago Flow',
                'pending_id': pending.id,
                'metodo_pago': 'flow',
                'tiene_masaje': tiene_masaje,
                'total_reserva': float(cart['total']),
            })

        try:
            venta = materializar_venta_desde_carrito(
                cliente=cliente,
                cart_data=cart,
                comprador_form_data={'nombre': nombre, 'email': email, 'telefono': telefono},
                revalidar=False,
            )
        except SlotUnavailableError as e:
            return JsonResponse({
                'success': False,
                'error': f"Algunos horarios ya no están disponibles: {', '.join(e.slots)}"
            })

        request.session['cart'] = {'servicios': [], 'giftcards': [], 'total': 0}
        request.session.modified = True

        detail_url = reverse('ventas:venta_reserva_detail', kwargs={'pk': venta.id})
        return JsonResponse({
            'success': True,
            'message': 'Reserva creada exitosamente',
            'reserva_id': venta.id,
            'metodo_pago': metodo_pago,
            'redirect_url': detail_url,
            'tiene_masaje': tiene_masaje,
            'total_reserva': float(cart['total']),
        })

    except Servicio.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Uno de los servicios en el carrito ya no existe.'})
    except Exception as e:
        print(f"Error in complete_checkout: {e}")
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': f'Ocurrió un error inesperado: {str(e)}'})

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
