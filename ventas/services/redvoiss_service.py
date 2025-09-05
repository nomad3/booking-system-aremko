# -*- coding: utf-8 -*-
"""
Servicio de integración con API REST de Redvoiss para envío de SMS
Basado en la documentación oficial v1.3.3 de Redvoiss
"""

import json
import requests
from requests.auth import HTTPBasicAuth
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
import logging

from ..models import Cliente, Campaign, CampaignInteraction

logger = logging.getLogger(__name__)


class RedvoissService:
    """
    Servicio para integración con API REST de Redvoiss
    """
    
    def __init__(self):
        self.base_url = getattr(settings, 'REDVOISS_API_URL', 'https://sms.lanube.cl/services/rest')
        self.username = getattr(settings, 'REDVOISS_USERNAME', '')
        self.password = getattr(settings, 'REDVOISS_PASSWORD', '')
        
        if not self.username or not self.password:
            logger.warning("Credenciales de Redvoiss no configuradas en settings - SMS deshabilitado")
            self.credentials_configured = False
        else:
            self.credentials_configured = True
    
    def greet(self):
        """
        Prueba la conexión con la API de Redvoiss usando el endpoint greet
        Returns: dict con status y mensaje
        """
        if not self.credentials_configured:
            return {
                'success': False,
                'message': 'Credenciales de Redvoiss no configuradas',
                'status_code': None
            }
        
        try:
            url = f"{self.base_url}/greet"
            response = requests.get(
                url,
                auth=HTTPBasicAuth(self.username, self.password),
                timeout=30
            )
            
            if response.status_code == 200:
                return {
                    'success': True,
                    'message': response.text.strip(),
                    'status_code': response.status_code
                }
            else:
                return {
                    'success': False,
                    'message': f"Error HTTP {response.status_code}: {response.text}",
                    'status_code': response.status_code
                }
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error conectando con Redvoiss: {str(e)}")
            return {
                'success': False,
                'message': f"Error de conexión: {str(e)}",
                'status_code': None
            }
    
    def send_sms(self, destination, message, campaign=None, cliente_id=None, bulk_name=None):
        """
        Envía un SMS individual usando la API REST de Redvoiss
        
        Args:
            destination (str): Número de destino en formato internacional (ej: 56912345678)
            message (str): Mensaje a enviar
            campaign (Campaign, optional): Instancia de campaña asociada
            cliente_id (str, optional): ID del cliente para tracking
            bulk_name (str, optional): Nombre del lote/campaña
            
        Returns:
            dict: Resultado del envío con batch_id y detalles
        """
        if not self.credentials_configured:
            return {
                'success': False,
                'error': 'Credenciales de Redvoiss no configuradas',
                'batch_id': None
            }
        
        try:
            # Limpiar número de destino (remover espacios, guiones, etc.)
            destination = self._clean_phone_number(destination)
            
            if not self._validate_phone_number(destination):
                return {
                    'success': False,
                    'error': f'Número de teléfono inválido: {destination}',
                    'batch_id': None
                }
            
            # Preparar payload según documentación Redvoiss
            payload = {
                "bulkName": bulk_name or f"SMS Aremko {timezone.now().strftime('%Y%m%d_%H%M')}",
                "message": message,
                "message_details": [{
                    "destination": destination,
                    "field": "",  # Campo vacío ya que el mensaje no usa variables
                    "idCliente": cliente_id or ""
                }],
                "isCommercial": False  # Mensajes no comerciales por defecto
            }
            
            url = f"{self.base_url}/send"
            headers = {'Content-Type': 'application/json'}
            
            response = requests.post(
                url,
                auth=HTTPBasicAuth(self.username, self.password),
                headers=headers,
                data=json.dumps(payload),
                timeout=30
            )
            
            if response.status_code == 200:
                try:
                    result = response.json()
                    batch_id = result.get('batchId')
                    
                    logger.info(f"SMS enviado exitosamente. BatchID: {batch_id}, Destino: {destination}")
                    
                    # Registrar interacción si hay campaña
                    if campaign and cliente_id:
                        self._log_sms_interaction(campaign, cliente_id, batch_id, message, destination)
                    
                    return {
                        'success': True,
                        'batch_id': batch_id,
                        'destination': destination,
                        'message': message,
                        'response': result
                    }
                    
                except json.JSONDecodeError:
                    logger.error(f"Respuesta JSON inválida de Redvoiss: {response.text}")
                    return {
                        'success': False,
                        'error': f'Respuesta inválida del servidor: {response.text}',
                        'batch_id': None
                    }
            else:
                logger.error(f"Error enviando SMS: HTTP {response.status_code} - {response.text}")
                return {
                    'success': False,
                    'error': f'Error HTTP {response.status_code}: {response.text}',
                    'batch_id': None
                }
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error de conexión enviando SMS: {str(e)}")
            return {
                'success': False,
                'error': f'Error de conexión: {str(e)}',
                'batch_id': None
            }
        except Exception as e:
            logger.error(f"Error inesperado enviando SMS: {str(e)}")
            return {
                'success': False,
                'error': f'Error inesperado: {str(e)}',
                'batch_id': None
            }
    
    def send_bulk_sms(self, message_list, campaign=None, bulk_name=None):
        """
        Envía múltiples SMS en un solo lote
        
        Args:
            message_list (list): Lista de diccionarios con 'destination', 'message', 'cliente_id'
            campaign (Campaign, optional): Instancia de campaña asociada
            bulk_name (str, optional): Nombre del lote
            
        Returns:
            dict: Resultado del envío masivo
        """
        try:
            # Validar que hay mensajes para enviar
            if not message_list:
                return {
                    'success': False,
                    'error': 'No hay mensajes para enviar',
                    'batch_id': None
                }
            
            # Preparar message_details para el lote
            message_details = []
            for msg_data in message_list:
                destination = self._clean_phone_number(msg_data.get('destination', ''))
                if self._validate_phone_number(destination):
                    message_details.append({
                        "destination": destination,
                        "field": msg_data.get('field', ''),
                        "idCliente": msg_data.get('cliente_id', '')
                    })
                else:
                    logger.warning(f"Número inválido ignorado: {destination}")
            
            if not message_details:
                return {
                    'success': False,
                    'error': 'No hay números de teléfono válidos',
                    'batch_id': None
                }
            
            # Preparar payload para envío masivo
            payload = {
                "bulkName": bulk_name or f"SMS Masivo Aremko {timezone.now().strftime('%Y%m%d_%H%M')}",
                "message": message_list[0].get('message', ''),  # Mismo mensaje para todos
                "message_details": message_details,
                "isCommercial": False
            }
            
            url = f"{self.base_url}/send"
            headers = {'Content-Type': 'application/json'}
            
            response = requests.post(
                url,
                auth=HTTPBasicAuth(self.username, self.password),
                headers=headers,
                data=json.dumps(payload),
                timeout=60  # Timeout mayor para envíos masivos
            )
            
            if response.status_code == 200:
                result = response.json()
                batch_id = result.get('batchId')
                
                logger.info(f"SMS masivo enviado. BatchID: {batch_id}, Cantidad: {len(message_details)}")
                
                # Registrar interacciones si hay campaña
                if campaign:
                    for msg_data in message_list:
                        if msg_data.get('cliente_id'):
                            self._log_sms_interaction(
                                campaign, 
                                msg_data['cliente_id'], 
                                batch_id, 
                                msg_data.get('message', ''),
                                msg_data.get('destination', '')
                            )
                
                return {
                    'success': True,
                    'batch_id': batch_id,
                    'messages_sent': len(message_details),
                    'response': result
                }
            else:
                logger.error(f"Error enviando SMS masivo: HTTP {response.status_code} - {response.text}")
                return {
                    'success': False,
                    'error': f'Error HTTP {response.status_code}: {response.text}',
                    'batch_id': None
                }
                
        except Exception as e:
            logger.error(f"Error enviando SMS masivo: {str(e)}")
            return {
                'success': False,
                'error': f'Error: {str(e)}',
                'batch_id': None
            }
    
    def check_batch_status(self, batch_id):
        """
        Consulta el estado de un lote de mensajes enviado
        
        Args:
            batch_id (str): ID del lote a consultar
            
        Returns:
            dict: Estado de los mensajes del lote
        """
        try:
            url = f"{self.base_url}/batch/{batch_id}/status"
            headers = {'Content-Type': 'application/json'}
            
            response = requests.get(
                url,
                auth=HTTPBasicAuth(self.username, self.password),
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return {
                    'success': True,
                    'batch_id': batch_id,
                    'messages': result
                }
            else:
                return {
                    'success': False,
                    'error': f'Error HTTP {response.status_code}: {response.text}',
                    'batch_id': batch_id
                }
                
        except Exception as e:
            logger.error(f"Error consultando estado del batch {batch_id}: {str(e)}")
            return {
                'success': False,
                'error': f'Error: {str(e)}',
                'batch_id': batch_id
            }
    
    def send_sms_with_reply(self, destination, message, campaign=None, cliente_id=None, bulk_name=None):
        """
        Envía SMS habilitado para recibir respuestas
        
        Args:
            destination (str): Número de destino
            message (str): Mensaje a enviar
            campaign (Campaign, optional): Campaña asociada
            cliente_id (str, optional): ID del cliente
            bulk_name (str, optional): Nombre del lote
            
        Returns:
            dict: Resultado del envío con capacidad de respuesta
        """
        if not self.credentials_configured:
            return {
                'success': False,
                'error': 'Credenciales de Redvoiss no configuradas',
                'batch_id': None
            }
        
        try:
            destination = self._clean_phone_number(destination)
            
            if not self._validate_phone_number(destination):
                return {
                    'success': False,
                    'error': f'Número de teléfono inválido: {destination}',
                    'batch_id': None
                }
            
            payload = {
                "bulkName": bulk_name or f"SMS Respuesta Aremko {timezone.now().strftime('%Y%m%d_%H%M')}",
                "message": message,
                "message_details": [{
                    "destination": destination,
                    "field": "",
                    "idCliente": cliente_id or ""
                }],
                "isCommercial": False
            }
            
            url = f"{self.base_url}/sendWithReply"
            headers = {'Content-Type': 'application/json'}
            
            response = requests.post(
                url,
                auth=HTTPBasicAuth(self.username, self.password),
                headers=headers,
                data=json.dumps(payload),
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                batch_id = result.get('batchId')
                
                logger.info(f"SMS con respuesta enviado. BatchID: {batch_id}, Destino: {destination}")
                
                # Registrar interacción
                if campaign and cliente_id:
                    self._log_sms_interaction(campaign, cliente_id, batch_id, message, destination, with_reply=True)
                
                return {
                    'success': True,
                    'batch_id': batch_id,
                    'destination': destination,
                    'message': message,
                    'with_reply': True,
                    'response': result
                }
            else:
                return {
                    'success': False,
                    'error': f'Error HTTP {response.status_code}: {response.text}',
                    'batch_id': None
                }
                
        except Exception as e:
            logger.error(f"Error enviando SMS con respuesta: {str(e)}")
            return {
                'success': False,
                'error': f'Error: {str(e)}',
                'batch_id': None
            }
    
    def check_batch_replies(self, batch_id):
        """
        Consulta las respuestas recibidas para un lote de mensajes
        
        Args:
            batch_id (str): ID del lote a consultar
            
        Returns:
            dict: Respuestas recibidas
        """
        try:
            url = f"{self.base_url}/batch/{batch_id}/replies"
            headers = {'Content-Type': 'application/json'}
            
            response = requests.get(
                url,
                auth=HTTPBasicAuth(self.username, self.password),
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return {
                    'success': True,
                    'batch_id': batch_id,
                    'replies': result.get('messageReplyList', [])
                }
            else:
                return {
                    'success': False,
                    'error': f'Error HTTP {response.status_code}: {response.text}',
                    'batch_id': batch_id
                }
                
        except Exception as e:
            logger.error(f"Error consultando respuestas del batch {batch_id}: {str(e)}")
            return {
                'success': False,
                'error': f'Error: {str(e)}',
                'batch_id': batch_id
            }
    
    def _clean_phone_number(self, phone):
        """
        Limpia y formatea número de teléfono
        """
        if not phone:
            return ""
        
        # Remover espacios, guiones, paréntesis
        phone = str(phone).strip().replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
        
        # Si empieza con +56, mantenerlo
        if phone.startswith('+56'):
            return phone
        
        # Si empieza con 56, agregar +
        if phone.startswith('56') and len(phone) >= 11:
            return f'+{phone}'
        
        # Si es número chileno sin código de país, agregarlo
        if len(phone) == 9 and phone.startswith('9'):
            return f'+56{phone}'
        
        return phone
    
    def _validate_phone_number(self, phone):
        """
        Valida formato de número de teléfono chileno
        """
        if not phone:
            return False
        
        # Formato esperado: +56912345678 (12 caracteres)
        if phone.startswith('+56') and len(phone) == 12:
            number_part = phone[3:]  # Remover +56
            return number_part.isdigit() and number_part.startswith('9')
        
        return False
    
    def _log_sms_interaction(self, campaign, cliente_id, batch_id, message, destination, with_reply=False):
        """
        Registra la interacción SMS en el sistema CRM
        """
        try:
            from ..models import Contact
            
            # Buscar contacto por cliente_id o teléfono
            contact = None
            if cliente_id:
                try:
                    cliente = Cliente.objects.get(id=cliente_id)
                    contact = Contact.objects.filter(phone=cliente.telefono).first()
                except Cliente.DoesNotExist:
                    pass
            
            if not contact:
                # Buscar por teléfono directamente
                contact = Contact.objects.filter(phone=destination).first()
            
            if contact:
                interaction_type = 'SMS_REPLY' if with_reply else 'SMS_SENT'
                CampaignInteraction.objects.create(
                    contact=contact,
                    campaign=campaign,
                    interaction_type=interaction_type,
                    details={
                        'batch_id': batch_id,
                        'message': message,
                        'destination': destination,
                        'with_reply': with_reply
                    }
                )
                logger.info(f"Interacción SMS registrada para contacto {contact.id}")
            else:
                logger.warning(f"No se encontró contacto para registrar interacción SMS: {destination}")
                
        except Exception as e:
            logger.error(f"Error registrando interacción SMS: {str(e)}")


# Instancia global del servicio
redvoiss_service = RedvoissService()