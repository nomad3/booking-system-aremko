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
        payload = {
            'apiKey': FLOW_API_KEY,
            'amount': amount,
            'concept': concept,
            'currency': 'CLP',
            'email': email,
            # Include reserva_id in confirmation/return URLs for tracking
            'urlConfirmation': f"{FLOW_CONFIRMATION_URL}?reserva_id={reserva_id}",
            'urlReturn': f"{FLOW_RETURN_URL}?reserva_id={reserva_id}",
            'commerceOrder': str(reserva_id) # Use reserva_id as the commerce order identifier
        }

        # --- Generate Flow Signature ---
        payload['s'] = generate_flow_signature(payload) # Add signature to the payload

        print(f"Flow Create Payload: {payload}") # Debugging

        # --- Make Request to Flow ---
        response = requests.post(FLOW_CREATE_API_URL, data=payload) # Use specific create URL
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        result = response.json()

        print(f"Flow Response: {result}") # Debugging

        # --- Process Flow Response ---
        if 'url' in result and 'token' in result:
            # Construct the full redirect URL
            redirect_url = f"{result['url']}?token={result['token']}"
            # Optionally: Store the flow token associated with the VentaReserva
            # venta.flow_token = result['token'] # Add a field to VentaReserva model if needed
            # venta.save()
            return JsonResponse({'url': redirect_url, 'token': result['token']})
        else:
            error_detail = result.get('message', 'Unknown error from Flow')
            return JsonResponse({'error': 'Error creating Flow payment', 'details': error_detail}, status=400)

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON body'}, status=400)
    except requests.exceptions.RequestException as e:
        print(f"Flow API request error: {e}")
        return JsonResponse({'error': f'Flow API request failed: {e}'}, status=502) # Bad Gateway
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
                         # TODO: Send confirmation email to client?
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
def flow_return(request):
    """Handles the user returning from the Flow payment page."""
    token = request.GET.get('token')
    reserva_id = request.GET.get('reserva_id') # Get reserva_id passed back
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
            print(f"Calling Flow getStatus for return page with params: {params}")
            response = requests.get(FLOW_STATUS_API_URL, params=params)
            response.raise_for_status()
            status_data = response.json()
            print(f"Flow getStatus Response for return: {status_data}")

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
