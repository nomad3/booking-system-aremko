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
from ..models import VentaReserva, Pago, PendingReservation
from ..services.reservation_service import (
    SlotUnavailableError,
    materializar_venta_desde_carrito,
)

# --- Flow Integration Constants ---
# .strip() defensivo: las env vars de Render pueden venir con \n al final
# si fueron pegadas con un salto de linea (bug detectado en produccion).
FLOW_API_KEY = os.environ.get('FLOW_API_KEY', 'YOUR_DEFAULT_API_KEY').strip()
FLOW_SECRET_KEY = os.environ.get('FLOW_SECRET_KEY', 'YOUR_DEFAULT_SECRET_KEY').strip()
FLOW_CREATE_API_URL = os.environ.get('FLOW_CREATE_API_URL', 'https://sandbox.flow.cl/api/payment/create').strip()
FLOW_STATUS_API_URL = os.environ.get('FLOW_STATUS_API_URL', 'https://sandbox.flow.cl/api/payment/getStatus').strip()
FLOW_CONFIRMATION_URL = os.environ.get('FLOW_CONFIRMATION_URL', 'http://localhost:8002/payment/confirmation/').strip()
FLOW_RETURN_URL = os.environ.get('FLOW_RETURN_URL', 'http://localhost:8002/payment/return/').strip()


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


def _resolve_commerce_order(commerce_order):
    """Decodifica commerceOrder de Flow.

    Formatos:
    - 'P<id>': PendingReservation (flujo nuevo, no crea reserva hasta confirmar pago)
    - '<id>' numerico: VentaReserva legacy (compat con pagos en vuelo durante deploy)

    Devuelve tupla (pending, venta). Una de las dos sera None.
    """
    if not commerce_order:
        return None, None
    if commerce_order.startswith('P'):
        try:
            pending = PendingReservation.objects.get(pk=int(commerce_order[1:]))
            return pending, None
        except (ValueError, PendingReservation.DoesNotExist):
            return None, None
    try:
        venta = VentaReserva.objects.get(pk=int(commerce_order))
        return None, venta
    except (ValueError, VentaReserva.DoesNotExist):
        return None, None


# --- Flow Payment Creation View ---
@csrf_exempt
def create_flow_payment(request):
    """Inicia un pago en Flow.cl a partir de un PendingReservation.

    Espera body JSON con `pending_id` (flujo nuevo) o `reserva_id` (compat legacy).
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid method'}, status=405)

    try:
        body = json.loads(request.body)
        pending_id = body.get('pending_id')
        reserva_id = body.get('reserva_id')

        if not pending_id and not reserva_id:
            return JsonResponse({'error': 'Missing pending_id or reserva_id'}, status=400)

        if pending_id:
            try:
                pending = PendingReservation.objects.select_related('cliente').get(pk=pending_id)
            except PendingReservation.DoesNotExist:
                return JsonResponse({'error': 'Pending reservation not found'}, status=404)
            if pending.estado != 'iniciado':
                return JsonResponse({
                    'error': f'Pending reservation no esta iniciada (estado={pending.estado})'
                }, status=400)
            commerce_order = f'P{pending.id}'
            amount = int(pending.monto)
            subject = f'Reserva Aremko #{pending.id}'
            email = pending.cliente.email or 'cliente_sin_email@ejemplo.com'
            commerce_order_qs = pending.id
            qs_key = 'pending_id'
        else:
            try:
                venta = VentaReserva.objects.get(pk=reserva_id)
            except VentaReserva.DoesNotExist:
                return JsonResponse({'error': 'Reservation not found'}, status=404)
            commerce_order = str(venta.id)
            amount = int(venta.total)
            subject = f'Reserva Aremko #{venta.id}'
            email = venta.cliente.email or 'cliente_sin_email@ejemplo.com'
            commerce_order_qs = venta.id
            qs_key = 'reserva_id'

        payload = {
            'apiKey': FLOW_API_KEY,
            'amount': amount,
            'subject': subject,
            'currency': 'CLP',
            'email': email,
            'urlConfirmation': f"{FLOW_CONFIRMATION_URL}?{qs_key}={commerce_order_qs}",
            'urlReturn': f"{FLOW_RETURN_URL}?{qs_key}={commerce_order_qs}",
            'commerceOrder': commerce_order,
        }
        payload['s'] = generate_flow_signature(payload)

        print(f"Flow Create Payload: {payload}")

        response = requests.post(FLOW_CREATE_API_URL, data=payload, timeout=30)
        print(f"Flow HTTP {response.status_code} - Body: {response.text[:1000]}")

        try:
            result = response.json()
        except ValueError:
            return JsonResponse({
                'error': 'Flow respondio con formato invalido',
                'http_status': response.status_code,
                'body_preview': response.text[:500],
            }, status=502)

        if response.status_code == 200 and 'url' in result and 'token' in result:
            redirect_url = f"{result['url']}?token={result['token']}"
            if pending_id:
                pending.flow_token = result['token']
                pending.flow_url = redirect_url
                pending.save(update_fields=['flow_token', 'flow_url', 'updated_at'])
            return JsonResponse({'url': redirect_url, 'token': result['token']})

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


def _materializar_pending_si_pago_exitoso(pending, amount):
    """Materializa el PendingReservation a VentaReserva tras confirmacion de pago.

    Maneja la revalidacion de slots y el caso 'slot_perdido' (slot tomado mientras
    el cliente pagaba). Idempotente: si ya esta confirmado, no re-procesa.
    """
    if pending.estado == 'confirmado' and pending.venta_reserva_id:
        print(f"PendingReservation #{pending.id} ya confirmado (venta #{pending.venta_reserva_id})")
        return pending.venta_reserva

    cliente = pending.cliente
    cart_data = pending.cart_data

    try:
        with transaction.atomic():
            venta = materializar_venta_desde_carrito(
                cliente=cliente,
                cart_data=cart_data,
                comprador_form_data={
                    'nombre': cliente.nombre,
                    'email': cliente.email or '',
                    'telefono': cliente.telefono or '',
                },
                revalidar=True,
            )
            Pago.objects.create(
                venta_reserva=venta,
                monto=amount,
                metodo_pago='flow',
                fecha_pago=timezone.now(),
            )
            pending.marcar_confirmado(venta)
            venta.refresh_from_db()
            return venta
    except SlotUnavailableError as e:
        detalle = (
            f"Slot perdido al confirmar pago Flow ({timezone.now().isoformat()}): "
            f"{', '.join(e.slots)}. Monto pagado: {amount}. REQUIERE REEMBOLSO MANUAL."
        )
        print(f"ALERTA: {detalle}")
        pending.marcar_slot_perdido(detalle)
        return None


# --- Flow Confirmation View (Webhook) ---
@csrf_exempt
def flow_confirmation(request):
    """Webhook de Flow.cl: confirma estado del pago.

    Si commerceOrder es 'P<id>' (PendingReservation): materializa la VentaReserva
    en exito o registra el rechazo. Si commerceOrder es numerico (legacy
    VentaReserva): comportamiento anterior (crea Pago directamente).
    """
    if request.method != 'POST':
        return HttpResponse("Invalid method", status=405)

    token = request.POST.get('token')
    if not token:
        print("Flow Confirmation Error: No token received.")
        return HttpResponse("Missing token", status=400)

    print(f"Flow Confirmation Received for token: {token}")

    try:
        params = {'apiKey': FLOW_API_KEY, 'token': token}
        params['s'] = generate_flow_signature(params)

        print(f"Calling Flow getStatus with params: {params}")
        response = requests.get(FLOW_STATUS_API_URL, params=params)
        response.raise_for_status()
        status_data = response.json()
        print(f"Flow getStatus Response: {status_data}")

        flow_status = status_data.get('status')
        commerce_order = status_data.get('commerceOrder')
        amount = status_data.get('amount')

        if not commerce_order:
            print("Flow Confirmation Error: commerceOrder missing in status response.")
            return HttpResponse("Missing commerceOrder", status=400)

        pending, venta = _resolve_commerce_order(str(commerce_order))
        if pending is None and venta is None:
            print(f"Flow Confirmation Error: no se encontro entidad para commerceOrder={commerce_order}")
            return HttpResponse("Order not found", status=404)

        # --- Flujo nuevo: PendingReservation ---
        if pending is not None:
            if flow_status == 2:  # Paid
                materializada = _materializar_pending_si_pago_exitoso(pending, amount)
                if materializada is None:
                    return HttpResponse("Slot lost - manual refund required", status=200)

                # Meta CAPI: Purchase server-side (garantiza tracking aunque el cliente
                # no vuelva a flow_return.html). event_id deterministico permite que
                # Meta deduplique con el evento Pixel client-side.
                try:
                    from ..services.meta_capi_service import send_purchase_event
                    cliente = materializada.cliente
                    send_purchase_event(
                        venta_id=materializada.id,
                        amount=float(amount or materializada.pagado or 0),
                        email=cliente.email,
                        phone=cliente.telefono,
                        nombre_completo=cliente.nombre,
                    )
                except Exception as capi_err:
                    # Nunca fallar el webhook por error de CAPI.
                    print(f"Meta CAPI Purchase fallo (no critico): {capi_err}")

                # Enviar GiftCards si las hay (solo si la materializacion fue exitosa)
                from ..models import GiftCard, GiftCardExperiencia
                from ..services.giftcard_pdf_service import GiftCardPDFService
                giftcards = GiftCard.objects.filter(
                    venta_reserva=materializada,
                    estado='por_cobrar',
                )
                if giftcards.exists():
                    print(f"Enviando email de {giftcards.count()} GiftCard(s) para venta {materializada.id}")
                    giftcards.update(estado='cobrado')
                    giftcards_data = []
                    for gc in giftcards:
                        imagen_url = ''
                        try:
                            if gc.servicio_asociado:
                                experiencia = GiftCardExperiencia.objects.filter(
                                    id_experiencia=gc.servicio_asociado, activo=True
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
                            'fecha_vencimiento': gc.fecha_vencimiento,
                        })
                    GiftCardPDFService.enviar_giftcard_por_email(
                        comprador_email=materializada.cliente.email,
                        comprador_nombre=materializada.cliente.nombre,
                        giftcards_data=giftcards_data,
                    )
                return HttpResponse("Payment Confirmed", status=200)

            elif flow_status in (3, 4):
                pending.estado = 'rechazado' if flow_status == 3 else 'cancelado'
                pending.notas = (pending.notas + f'\nFlow status={flow_status} at {timezone.now().isoformat()}').strip()
                pending.save(update_fields=['estado', 'notas', 'updated_at'])
                print(f"PendingReservation #{pending.id} marcado como {pending.estado}")
                return HttpResponse("Payment Rejected/Cancelled", status=200)
            else:
                print(f"Flow status pendiente/desconocido para PendingReservation #{pending.id}: {flow_status}")
                return HttpResponse("Payment Status Pending/Unknown", status=200)

        # --- Flujo legacy: VentaReserva ya existente (compat con pagos en vuelo) ---
        if flow_status == 2:
            recien_pagada = False
            with transaction.atomic():
                if venta.estado_pago != 'pagado':
                    print(f"Processing legacy successful payment for VentaReserva {venta.id}")
                    Pago.objects.create(
                        venta_reserva=venta,
                        monto=amount,
                        metodo_pago='flow',
                        fecha_pago=timezone.now(),
                    )
                    venta.refresh_from_db()
                    recien_pagada = True
                else:
                    print(f"VentaReserva {venta.id} already paid (legacy path)")
            if recien_pagada:
                try:
                    from ..services.meta_capi_service import send_purchase_event
                    send_purchase_event(
                        venta_id=venta.id,
                        amount=float(amount or venta.pagado or 0),
                        email=venta.cliente.email,
                        phone=venta.cliente.telefono,
                        nombre_completo=venta.cliente.nombre,
                    )
                except Exception as capi_err:
                    print(f"Meta CAPI Purchase legacy fallo (no critico): {capi_err}")
            return HttpResponse("Payment Confirmed", status=200)
        elif flow_status in (3, 4):
            print(f"Flow legacy rejected/cancelled for VentaReserva {venta.id}. Status: {flow_status}")
            return HttpResponse("Payment Rejected/Cancelled", status=200)
        else:
            return HttpResponse("Payment Status Pending/Unknown", status=200)

    except requests.exceptions.RequestException as e:
        print(f"Flow Confirmation Error: API request failed: {e}")
        return HttpResponse("Flow API request failed", status=502)
    except Exception as e:
        print(f"Flow Confirmation Error: Internal server error: {e}")
        traceback.print_exc()
        return HttpResponse("Internal server error", status=500)


# --- Flow Return View (User Redirect) ---
@csrf_exempt
def flow_return(request):
    """Vista a la que regresa el cliente desde Flow.

    Resuelve commerceOrder a PendingReservation o VentaReserva legacy. Si el pago
    fue exitoso y la materializacion ya ocurrio (webhook), muestra la VentaReserva.
    Si el webhook todavia no llego, intenta materializar aqui mismo (idempotente).
    """
    token = request.POST.get('token') or request.GET.get('token')
    pending_id_qs = request.GET.get('pending_id') or request.POST.get('pending_id')
    reserva_id_qs = request.GET.get('reserva_id') or request.POST.get('reserva_id')
    payment_status = 'pendiente'
    error_message = None
    venta = None
    pending = None

    print(f"Flow Return Received - Token: {token}, pending_id: {pending_id_qs}, reserva_id: {reserva_id_qs}")

    if token:
        try:
            params = {'apiKey': FLOW_API_KEY, 'token': token}
            params['s'] = generate_flow_signature(params)

            print(f"[flow_return] Calling getStatus URL={FLOW_STATUS_API_URL} params={params}")
            response = requests.get(FLOW_STATUS_API_URL, params=params, timeout=30)
            print(f"[flow_return] HTTP {response.status_code} body={response.text[:500]}")

            if response.status_code != 200:
                try:
                    err = response.json()
                    error_message = f"Flow getStatus error {response.status_code}: {err.get('message') or err}"
                except Exception:
                    error_message = f"Flow getStatus error {response.status_code}: {response.text[:200]}"
                raise requests.exceptions.HTTPError(error_message)

            status_data = response.json()
            print(f"[flow_return] getStatus parsed: {status_data}")

            flow_status_code = status_data.get('status')
            commerce_order = status_data.get('commerceOrder')
            amount = status_data.get('amount')

            pending, venta = _resolve_commerce_order(str(commerce_order) if commerce_order else None)

            if flow_status_code == 2:
                payment_status = 'exitoso'
                # Si es PendingReservation y aun no se materializo, intentarlo aqui
                # (defensa: el webhook normalmente llega antes pero por si acaso).
                if pending is not None and pending.estado == 'iniciado':
                    materializada = _materializar_pending_si_pago_exitoso(pending, amount)
                    if materializada is not None:
                        venta = materializada
                elif pending is not None and pending.venta_reserva_id:
                    venta = pending.venta_reserva
            elif flow_status_code == 3:
                payment_status = 'rechazado'
            elif flow_status_code == 4:
                payment_status = 'cancelado'
            else:
                payment_status = 'pendiente'

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
        if pending_id_qs:
            try:
                pending = PendingReservation.objects.get(pk=pending_id_qs)
                if pending.venta_reserva_id:
                    venta = pending.venta_reserva
            except PendingReservation.DoesNotExist:
                error_message = "No se encontró la reserva asociada."
        elif reserva_id_qs:
            try:
                venta = VentaReserva.objects.select_related('cliente').get(pk=reserva_id_qs)
            except VentaReserva.DoesNotExist:
                error_message = "No se encontró la reserva asociada."

    context = {
        'payment_status': payment_status,
        'error_message': error_message,
        'venta': venta,
        'reserva_id': venta.id if venta else (reserva_id_qs or pending_id_qs),
        'flow_token': token,
        'pending': pending,
    }
    return render(request, 'ventas/flow_return.html', context)
