"""
Servicio para integración con Flow.cl (pasarela de pagos chilena)
Encapsula la lógica de creación de pagos y validación de webhooks
"""
import hmac
import hashlib
import requests
import os
import logging

logger = logging.getLogger(__name__)


class FlowService:
    """Servicio para manejar pagos con Flow.cl"""

    def __init__(self):
        self.api_key = os.environ.get('FLOW_API_KEY', 'YOUR_DEFAULT_API_KEY')
        self.secret_key = os.environ.get('FLOW_SECRET_KEY', 'YOUR_DEFAULT_SECRET_KEY')
        self.create_api_url = os.environ.get('FLOW_CREATE_API_URL', 'https://sandbox.flow.cl/api/payment/create')
        self.status_api_url = os.environ.get('FLOW_STATUS_API_URL', 'https://sandbox.flow.cl/api/payment/getStatus')

    def generate_signature(self, params):
        """
        Genera la firma HMAC-SHA256 para las llamadas API de Flow

        Args:
            params (dict): Parámetros a firmar

        Returns:
            str: Firma hexadecimal
        """
        sorted_items = sorted(params.items())
        data_string = '&'.join(f'{k}={v}' for k, v in sorted_items if k != 's')
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            data_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature

    def create_payment(self, order_data):
        """
        Crea una orden de pago en Flow

        Args:
            order_data (dict): Datos de la orden con las siguientes claves:
                - commerceOrder: ID único de la orden
                - subject: Descripción del pago
                - currency: Moneda (ej: 'CLP')
                - amount: Monto en pesos (int)
                - email: Email del pagador
                - urlConfirmation: URL del webhook de confirmación
                - urlReturn: URL de retorno del usuario

        Returns:
            dict: Respuesta de Flow con 'url' y 'token' si es exitoso

        Raises:
            Exception: Si hay error en la comunicación con Flow
        """
        try:
            # Preparar payload para Flow
            payload = {
                'apiKey': self.api_key,
                'commerceOrder': order_data['commerceOrder'],
                'subject': order_data.get('subject', 'Pago Aremko Spa'),
                'currency': order_data.get('currency', 'CLP'),
                'amount': int(order_data['amount']),
                'email': order_data['email'],
                'urlConfirmation': order_data['urlConfirmation'],
                'urlReturn': order_data['urlReturn'],
            }

            # Agregar campos opcionales si existen
            if 'optional' in order_data:
                payload['optional'] = order_data['optional']

            # Generar firma
            payload['s'] = self.generate_signature(payload)

            logger.info(f"Creating Flow payment for order: {order_data['commerceOrder']}")

            # Hacer request a Flow
            response = requests.post(self.create_api_url, data=payload, timeout=30)
            response.raise_for_status()
            result = response.json()

            if 'url' in result and 'token' in result:
                logger.info(f"Flow payment created successfully. Token: {result['token']}")
                return {
                    'success': True,
                    'url': result['url'],
                    'token': result['token']
                }
            else:
                error_msg = result.get('message', 'Unknown error from Flow')
                logger.error(f"Flow payment creation failed: {error_msg}")
                return {
                    'success': False,
                    'error': error_msg
                }

        except requests.exceptions.Timeout:
            logger.error("Flow API timeout")
            return {
                'success': False,
                'error': 'Timeout al comunicar con Flow'
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"Flow API request error: {str(e)}")
            return {
                'success': False,
                'error': f'Error de comunicación con Flow: {str(e)}'
            }
        except Exception as e:
            logger.error(f"Unexpected error creating Flow payment: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': f'Error inesperado: {str(e)}'
            }

    def get_payment_status(self, token):
        """
        Obtiene el estado de un pago desde Flow

        Args:
            token (str): Token del pago de Flow

        Returns:
            dict: Datos del estado del pago con las siguientes claves:
                - status: Código de estado (1=pendiente, 2=pagado, 3=rechazado, 4=cancelado)
                - commerceOrder: ID de la orden
                - amount: Monto pagado
                - payer: Email del pagador
                - paymentData: Datos adicionales del pago

        Raises:
            Exception: Si hay error en la comunicación con Flow
        """
        try:
            # Preparar parámetros
            params = {
                'apiKey': self.api_key,
                'token': token
            }
            params['s'] = self.generate_signature(params)

            logger.info(f"Getting Flow payment status for token: {token}")

            # Hacer request a Flow
            response = requests.get(self.status_api_url, params=params, timeout=30)
            response.raise_for_status()
            status_data = response.json()

            logger.info(f"Flow status retrieved: {status_data.get('status')}")

            return {
                'success': True,
                'status': status_data.get('status'),
                'commerceOrder': status_data.get('commerceOrder'),
                'amount': status_data.get('amount'),
                'payer': status_data.get('payer'),
                'paymentData': status_data.get('paymentData', {}),
                'raw_data': status_data
            }

        except requests.exceptions.Timeout:
            logger.error("Flow API timeout on status check")
            return {
                'success': False,
                'error': 'Timeout al verificar estado del pago'
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"Flow API status request error: {str(e)}")
            return {
                'success': False,
                'error': f'Error al verificar estado: {str(e)}'
            }
        except Exception as e:
            logger.error(f"Unexpected error getting Flow status: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': f'Error inesperado: {str(e)}'
            }

    def validate_signature(self, params):
        """
        Valida la firma de un webhook de Flow

        Args:
            params (dict): Parámetros recibidos del webhook incluyendo la firma 's'

        Returns:
            bool: True si la firma es válida, False en caso contrario
        """
        received_signature = params.get('s')
        if not received_signature:
            return False

        expected_signature = self.generate_signature(params)
        return hmac.compare_digest(received_signature, expected_signature)
