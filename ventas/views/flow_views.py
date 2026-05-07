import json
import hmac
import hashlib
import requests
import os
import traceback
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db import transaction
from ..models import VentaReserva, Pago # Relative import from ventas/views/

# --- Flow Integration Constants ---
FLOW_API_KEY = os.environ.get('FLOW_API_KEY', 'YOUR_DEFAULT_API_KEY') # Replace with default or raise error if needed
FLOW_SECRET_KEY = os.environ.get('FLOW_SECRET_KEY', 'YOUR_DEFAULT_SECRET_KEY')
FLOW_CREATE_API_URL = os.environ.get('FLOW_CREATE_API_URL', 'https://sandbox.flow.cl/api/payment/create') # Default to sandbox
FLOW_STATUS_API_URL = os.environ.get('FLOW_STATUS_API_URL', 'https://sandbox.flow.cl/api/payment/getStatus') # Added Status URL
# Consider using Django's reverse() with request.build_absolute_uri() for dynamic URLs
FLOW_CONFIRMATION_URL = os.environ.get('FLOW_CONFIRMATION_URL', 'http://localhost:8002/payment/confirmation/') # Example using default dev port
FLOW_RETURN_URL = os.environ.get('FLOW_RETURN_URL', 'http://localhost:8002/payment/return/') # Example using default dev port

# --- Helper function to generate Flow signature ---
def generate_flow_signature(params):
    """Generates the HMAC-SHA256 signature for Flow API calls."""
    sorted_items = sorted(params.items())
    data_string = '&'.join(f'{k}={v}' for k, v in sorted_items if k != 's')
    signature = hmac.new(
        FLOW_SECRET_KEY.encode('utf-8'),
        data_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return signature

# --- Flow Payment Creation View ---
@csrf_exempt # Flow confirmation might not send CSRF token
def create_flow_payment(request):
    """
    Initiates a payment order with Flow.cl.
    Expects JSON body with: reserva_id
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid method'}, status=405)

    try:
        body = json.loads(request.body)
        reserva_id = body.get('reserva_id')

        if not reserva_id:
            return JsonResponse({'error': 'Missing reserva_id'}, status=400)

        # Fetch the reservation to get amount, email, etc.
        try:
            venta = VentaReserva.objects.get(pk=reserva_id)
            amount = int(venta.total) # Flow expects integer amount
            concept = f"Reserva Aremko #{venta.id}"
            email = venta.cliente.email
            if not email:
                 # Fallback or error if client has no email?
                 # For now, let's use a placeholder, but this should be handled
                 email = "cliente_sin_email@ejemplo.com"
                 print(f"Warning: Cliente {venta.cliente.id} has no email for Flow payment.")

        except VentaReserva.DoesNotExist:
            return JsonResponse({'error': 'Reservation not found'}, status=404)

        # --- Construct Flow Payload ---
        # Flow API espera 'subject' (no 'concept') segun /api/payment/create.
        # El error "Missing service params: subject" se diagnostico con un test
        # real que devolvio flow_code 104.
        payload = {
            'apiKey': FLOW_API_KEY,
            'amount': amount,
            'subject': concept,
            'currency': 'CLP',
            'email': email,
            'urlConfirmation': f"{FLOW_CONFIRMATION_URL}?reserva_id={reserva_id}",
            'urlReturn': f"{FLOW_RETURN_URL}?reserva_id={reserva_id}",
            'commerceOrder': str(reserva_id),
        }

        # --- Generate Flow Signature ---
        payload['s'] = generate_flow_signature(payload) # Add signature to the payload

        print(f"Flow Create Payload: {payload}") # Debugging

        # --- Make Request to Flow ---
        # NO usar raise_for_status: queremos capturar el body del error 4xx
        # que Flow devuelve con detalles especificos (codigo, mensaje).
        response = requests.post(FLOW_CREATE_API_URL, data=payload, timeout=30)
        print(f"Flow HTTP {response.status_code} - Body: {response.text[:1000]}")  # Debug

        try:
            result = response.json()
        except ValueError:
            return JsonResponse({
                'error': 'Flow respondio con formato invalido',
                'http_status': response.status_code,
                'body_preview': response.text[:500],
            }, status=502)

        # Flow devuelve 200 + url+token en exito, o 4xx/5xx con error
        if response.status_code == 200 and 'url' in result and 'token' in result:
            redirect_url = f"{result['url']}?token={result['token']}"
            return JsonResponse({'url': redirect_url, 'token': result['token']})

        # Caso de error: Flow incluye 'code' y 'message' en el body
        flow_code = result.get('code')
        flow_message = result.get('message') or result.get('error') or 'Unknown error'
        print(f"Flow API error - code={flow_code} message={flow_message} full={result}")
        return JsonResponse({
            'error': f'Flow API error: {flow_message}',
            'flow_code': flow_code,
            'flow_message': flow_message,
            'http_status': response.status_code,
        }, status=400)

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON body'}, status=400)
    except requests.exceptions.RequestException as e:
        print(f"Flow API request error: {e}")
        return JsonResponse({'error': f'Flow API request failed: {e}'}, status=502)
    except Exception as e:
        print(f"Error in create_flow_payment: {e}")
        traceback.print_exc()
        return JsonResponse({'error': f'Internal server error: {str(e)}'}, status=500)


# --- Flow Confirmation View (Webhook) ---
@csrf_exempt # Flow confirmation is a POST from their server
def flow_confirmation(request):
    """Handles the payment confirmation webhook from Flow."""
    if request.method != 'POST':
        return HttpResponse("Invalid method", status=405)

    token = request.POST.get('token')
    if not token:
        print("Flow Confirmation Error: No token received.")
        return HttpResponse("Missing token", status=400)

    print(f"Flow Confirmation Received for token: {token}")

    try:
        # --- Prepare parameters for getStatus API ---
        params = {
            'apiKey': FLOW_API_KEY,
            'token': token
        }
        params['s'] = generate_flow_signature(params)

        # --- Call Flow getStatus API ---
        print(f"Calling Flow getStatus with params: {params}")
        response = requests.get(FLOW_STATUS_API_URL, params=params)
        response.raise_for_status()
        status_data = response.json()
        print(f"Flow getStatus Response: {status_data}")

        # --- Process Payment Status ---
        flow_status = status_data.get('status')
        commerce_order = status_data.get('commerceOrder') # This is our reserva_id
        amount = status_data.get('amount')

        if not commerce_order:
             print("Flow Confirmation Error: commerceOrder missing in status response.")
             return HttpResponse("Missing commerceOrder", status=400)

        try:
            reserva_id = int(commerce_order)
            venta = VentaReserva.objects.get(pk=reserva_id)
        except (ValueError, VentaReserva.DoesNotExist):
            print(f"Flow Confirmation Error: VentaReserva not found for commerceOrder: {commerce_order}")
            return HttpResponse("Reservation not found", status=404)

        # --- Handle Payment Status ---
        # Status values: 1=pending, 2=paid, 3=rejected, 4=cancelled
        if flow_status == 2: # Paid
            # Use transaction.atomic for database consistency
            with transaction.atomic():
                # Check if already paid to prevent duplicate processing
                if venta.estado_pago != 'pagado':
                    print(f"Processing successful payment for VentaReserva {venta.id}")
                    # Create the Pago record
                    Pago.objects.create(
                        venta_reserva=venta,
                        monto=amount,
                        metodo_pago='flow', # Use 'flow' as the method
                        fecha_pago=timezone.now(),
                        # Optionally store Flow details like paymentData if needed
                    )
                    # The Pago save signal should automatically update VentaReserva status
                    venta.refresh_from_db() # Refresh to get updated status
                    if venta.estado_pago == 'pagado':
                         print(f"VentaReserva {venta.id} status updated to 'pagado'.")

                         # Enviar email de GiftCards si existen en la sesión
                         # NOTA: Usamos la sesión del usuario asociado a la venta
                         # Como esto es un webhook, no tenemos acceso directo a request.session
                         # Por eso guardamos los datos en la BD con la VentaReserva

                         # Buscar GiftCards asociadas a esta venta
                         from ..models import GiftCard, GiftCardExperiencia
                         from ..services.giftcard_pdf_service import GiftCardPDFService

                         giftcards = GiftCard.objects.filter(
                             cliente_comprador=venta.cliente,
                             fecha_emision=venta.fecha_reserva.date(),
                             estado='por_cobrar'
                         )

                         if giftcards.exists():
                             print(f"📧 Enviando email de {giftcards.count()} GiftCard(s) para venta {venta.id}")

                             # Actualizar estado de GiftCards a 'cobrado'
                             giftcards.update(estado='cobrado')

                             # Preparar datos para el email
                             # NOTA: Por ahora enviamos datos básicos
                             # En una versión futura, guardar metadata completa en el modelo GiftCard
                             giftcards_data = []
                             for gc in giftcards:
                                 # Intentar obtener imagen de la experiencia
                                 imagen_url = ''
                                 try:
                                     if gc.servicio_asociado:
                                         experiencia = GiftCardExperiencia.objects.filter(
                                             id_experiencia=gc.servicio_asociado,
                                             activo=True
                                         ).first()
                                         if experiencia and experiencia.imagen:
                                             from django.conf import settings
                                             imagen_url = f"{settings.MEDIA_URL}{experiencia.imagen}"
                                 except Exception:
                                     pass

                                 giftcards_data.append({
                                     'codigo': gc.codigo,
                                     'experiencia_nombre': f'Experiencia Aremko (${int(gc.monto_inicial):,})',
                                     'experiencia_imagen_url': imagen_url,
                                     'destinatario_nombre': gc.destinatario_nombre or 'Destinatario',
                                     'mensaje_seleccionado': gc.mensaje_personalizado or 'Disfruta de una experiencia inolvidable en Aremko Spa',
                                     'precio': gc.monto_inicial,
                                     'fecha_emision': gc.fecha_emision,
                                     'fecha_vencimiento': gc.fecha_vencimiento
                                 })

                             # Enviar email al comprador
                             GiftCardPDFService.enviar_giftcard_por_email(
                                 comprador_email=venta.cliente.email,
                                 comprador_nombre=venta.cliente.nombre,
                                 giftcards_data=giftcards_data
                             )

                    else:
                         print(f"Warning: VentaReserva {venta.id} status is still {venta.estado_pago} after creating Pago.")

                else:
                    print(f"VentaReserva {venta.id} already marked as paid. Ignoring duplicate confirmation.")

            return HttpResponse("Payment Confirmed", status=200)

        elif flow_status == 3 or flow_status == 4: # Rejected or Cancelled
            print(f"Flow payment rejected/cancelled for VentaReserva {venta.id}. Status: {flow_status}")
            # Optionally update VentaReserva status to 'cancelado' or similar
            # venta.estado_pago = 'cancelado'
            # venta.save()
            # TODO: Notify client?
            return HttpResponse("Payment Rejected/Cancelled", status=200) # Still return 200 to Flow

        else: # Pending or other status
            print(f"Flow payment status is pending or unknown for VentaReserva {venta.id}. Status: {flow_status}")
            return HttpResponse("Payment Status Pending/Unknown", status=200) # Still return 200

    except requests.exceptions.RequestException as e:
        print(f"Flow Confirmation Error: API request failed: {e}")
        return HttpResponse("Flow API request failed", status=502)
    except Exception as e:
        print(f"Flow Confirmation Error: Internal server error: {e}")
        traceback.print_exc()
        return HttpResponse("Internal server error", status=500)


# --- Flow Return View (User Redirect) ---
@csrf_exempt  # Flow envia POST con el token al redirigir al usuario
def flow_return(request):
    """Handles the user returning from the Flow payment page.

    Flow envia POST con 'token' en el body cuando redirige al usuario
    despues de un pago. El reserva_id viene en query string.
    Tambien aceptamos GET por defensividad.
    """
    token = request.POST.get('token') or request.GET.get('token')
    reserva_id = request.GET.get('reserva_id') or request.POST.get('reserva_id')
    payment_status = 'pendiente' # Default status
    error_message = None
    venta = None

    print(f"Flow Return Received - Token: {token}, Reserva ID: {reserva_id}")

    if token:
        try:
            # --- Prepare parameters for getStatus API ---
            params = {
                'apiKey': FLOW_API_KEY,
                'token': token
            }
            params['s'] = generate_flow_signature(params)

            # --- Call Flow getStatus API ---
            print(f"[flow_return] Calling getStatus URL={FLOW_STATUS_API_URL} params={params}")
            response = requests.get(FLOW_STATUS_API_URL, params=params, timeout=30)
            print(f"[flow_return] HTTP {response.status_code} body={response.text[:500]}")

            if response.status_code != 200:
                # Capturar mensaje de Flow para diagnostico
                try:
                    err = response.json()
                    error_message = f"Flow getStatus error {response.status_code}: {err.get('message') or err}"
                except Exception:
                    error_message = f"Flow getStatus error {response.status_code}: {response.text[:200]}"
                # Caer al render con error
                raise requests.exceptions.HTTPError(error_message)

            status_data = response.json()
            print(f"[flow_return] getStatus parsed: {status_data}")

            flow_status_code = status_data.get('status')
            commerce_order = status_data.get('commerceOrder')

            # Verify commerceOrder matches if possible
            if commerce_order and reserva_id and commerce_order != reserva_id:
                 print(f"Warning: Flow return commerceOrder ({commerce_order}) doesn't match URL reserva_id ({reserva_id})")
                 # Decide how to handle mismatch - maybe trust URL param?

            if flow_status_code == 2:
                payment_status = 'exitoso' # Paid
            elif flow_status_code == 3:
                payment_status = 'rechazado' # Rejected
            elif flow_status_code == 4:
                payment_status = 'cancelado' # Cancelled
            else:
                payment_status = 'pendiente' # Pending

            # Try to fetch the reservation details
            if reserva_id:
                 try:
                     venta = VentaReserva.objects.select_related('cliente').get(pk=reserva_id)
                 except VentaReserva.DoesNotExist:
                     print(f"VentaReserva {reserva_id} not found on return.")
                     error_message = "No se encontró la reserva asociada."


        except requests.exceptions.RequestException as e:
            print(f"Flow Return Error: API request failed: {e}")
            error_message = "No se pudo verificar el estado del pago con Flow."
        except Exception as e:
            print(f"Flow Return Error: Internal server error: {e}")
            traceback.print_exc()
            error_message = "Ocurrió un error inesperado al verificar el pago."
    else:
        print("Flow Return Error: No token received.")
        error_message = "No se recibió información de la transacción."
        # If no token, but we have reserva_id, maybe show pending?
        if reserva_id:
             try:
                 venta = VentaReserva.objects.select_related('cliente').get(pk=reserva_id)
                 payment_status = 'pendiente' # Assume pending if no token
             except VentaReserva.DoesNotExist:
                 error_message = "No se encontró la reserva asociada."


    context = {
        'payment_status': payment_status,
        'error_message': error_message,
        'venta': venta,
        'reserva_id': reserva_id,
        'flow_token': token,
    }

    # Assuming you have a template named 'flow_return.html' in your templates/ventas directory
    return render(request, 'ventas/flow_return.html', context)
