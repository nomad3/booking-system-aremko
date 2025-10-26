# -*- coding: utf-8 -*-
"""
Servicio de integración con Mercado Pago Link
"""

import os
import requests
import json
import logging
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from ..models import VentaReserva, Pago

logger = logging.getLogger(__name__)


class MercadoPagoService:
    """
    Servicio para manejar pagos con Mercado Pago Link
    """
    
    def __init__(self):
        self.access_token = getattr(settings, 'MERCADOPAGO_ACCESS_TOKEN', None)
        self.webhook_secret = getattr(settings, 'MERCADOPAGO_WEBHOOK_SECRET', None)
        self.base_url = 'https://api.mercadopago.com'
        self.sandbox = getattr(settings, 'MERCADOPAGO_SANDBOX', True)
        self._config_checked = False
    
    def _check_config(self):
        """Verifica la configuración solo cuando se use el servicio"""
        if not self._config_checked:
            if not self.access_token:
                logger.warning("MERCADOPAGO_ACCESS_TOKEN no configurado")
            self._config_checked = True
    
    def create_payment_link(self, reserva_id, amount, description, customer_email, customer_name):
        """
        Crea un link de pago en Mercado Pago
        
        Args:
            reserva_id (int): ID de la reserva
            amount (float): Monto a pagar
            description (str): Descripción del pago
            customer_email (str): Email del cliente
            customer_name (str): Nombre del cliente
            
        Returns:
            dict: Respuesta de la API con el link de pago
        """
        self._check_config()
        try:
            if not self.access_token:
                return {'success': False, 'error': 'Mercado Pago no configurado'}
            
            # Preparar datos del pago
            payment_data = {
                "items": [
                    {
                        "id": f"reserva_{reserva_id}",
                        "title": description,
                        "description": f"Reserva #{reserva_id} - {description}",
                        "quantity": 1,
                        "unit_price": float(amount),
                        "currency_id": "CLP"
                    }
                ],
                "payer": {
                    "name": customer_name,
                    "email": customer_email
                },
                "back_urls": {
                    "success": f"{settings.BASE_URL}/payment/mercadopago/success/?reserva_id={reserva_id}",
                    "failure": f"{settings.BASE_URL}/payment/mercadopago/failure/?reserva_id={reserva_id}",
                    "pending": f"{settings.BASE_URL}/payment/mercadopago/pending/?reserva_id={reserva_id}"
                },
                "auto_return": "approved",
                "external_reference": str(reserva_id),
                "notification_url": f"{settings.BASE_URL}/payment/mercadopago/webhook/",
                "additional_info": f"Reserva Aremko #{reserva_id}"
            }
            
            # Headers para la API
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json',
                'X-Idempotency-Key': f"reserva_{reserva_id}_{int(timezone.now().timestamp())}"
            }
            
            # Crear el link de pago
            response = requests.post(
                f'{self.base_url}/checkout/preferences',
                headers=headers,
                json=payment_data,
                timeout=30
            )
            
            if response.status_code == 201:
                data = response.json()
                return {
                    'success': True,
                    'payment_link': data.get('init_point'),
                    'preference_id': data.get('id'),
                    'sandbox_init_point': data.get('sandbox_init_point') if self.sandbox else None
                }
            else:
                logger.error(f"Error creando link Mercado Pago: {response.status_code} - {response.text}")
                return {
                    'success': False,
                    'error': f'Error API Mercado Pago: {response.status_code}',
                    'details': response.text
                }
                
        except Exception as e:
            logger.error(f"Error en create_payment_link: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def get_payment_status(self, payment_id):
        """
        Obtiene el estado de un pago
        
        Args:
            payment_id (str): ID del pago en Mercado Pago
            
        Returns:
            dict: Estado del pago
        """
        try:
            if not self.access_token:
                return {'success': False, 'error': 'Mercado Pago no configurado'}
            
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(
                f'{self.base_url}/v1/payments/{payment_id}',
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'success': True,
                    'status': data.get('status'),
                    'status_detail': data.get('status_detail'),
                    'external_reference': data.get('external_reference'),
                    'transaction_amount': data.get('transaction_amount'),
                    'date_approved': data.get('date_approved')
                }
            else:
                logger.error(f"Error obteniendo estado pago: {response.status_code} - {response.text}")
                return {'success': False, 'error': f'Error API: {response.status_code}'}
                
        except Exception as e:
            logger.error(f"Error en get_payment_status: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def process_webhook(self, data):
        """
        Procesa webhook de Mercado Pago
        
        Args:
            data (dict): Datos del webhook
            
        Returns:
            dict: Resultado del procesamiento
        """
        self._check_config()
        try:
            # Verificar que es un webhook válido
            if data.get('type') != 'payment':
                return {'success': False, 'error': 'Tipo de webhook inválido'}
            
            payment_id = data.get('data', {}).get('id')
            if not payment_id:
                return {'success': False, 'error': 'ID de pago no encontrado'}
            
            # Obtener estado del pago
            payment_status = self.get_payment_status(payment_id)
            if not payment_status.get('success'):
                return payment_status
            
            # Obtener reserva por external_reference
            external_reference = payment_status.get('external_reference')
            if not external_reference:
                return {'success': False, 'error': 'External reference no encontrado'}
            
            try:
                reserva_id = int(external_reference)
                reserva = VentaReserva.objects.get(id=reserva_id)
            except (ValueError, VentaReserva.DoesNotExist):
                return {'success': False, 'error': 'Reserva no encontrada'}
            
            # Procesar según el estado del pago
            status = payment_status.get('status')
            
            if status == 'approved':
                # Pago aprobado - crear registro de pago
                with transaction.atomic():
                    # Verificar si ya existe el pago
                    existing_payment = Pago.objects.filter(
                        venta_reserva=reserva,
                        metodo_pago='mercadopago_link',
                        monto=payment_status.get('transaction_amount', 0)
                    ).first()
                    
                    if not existing_payment:
                        Pago.objects.create(
                            venta_reserva=reserva,
                            monto=payment_status.get('transaction_amount', 0),
                            metodo_pago='mercadopago_link',
                            fecha_pago=timezone.now()
                        )
                        logger.info(f"Pago Mercado Pago procesado para reserva {reserva_id}")
                    
                return {'success': True, 'message': 'Pago procesado correctamente'}
            
            elif status in ['rejected', 'cancelled']:
                logger.info(f"Pago Mercado Pago {status} para reserva {reserva_id}")
                return {'success': True, 'message': f'Pago {status}'}
            
            else:
                logger.info(f"Pago Mercado Pago pendiente ({status}) para reserva {reserva_id}")
                return {'success': True, 'message': f'Pago pendiente: {status}'}
                
        except Exception as e:
            logger.error(f"Error procesando webhook Mercado Pago: {str(e)}")
            return {'success': False, 'error': str(e)}


# Instancia global del servicio
mercadopago_service = MercadoPagoService()