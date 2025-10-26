"""
Cliente para API MCP de Propuestas Personalizadas - Aremko
Conecta con el FastAPI desplegado en Render
"""
import httpx
import asyncio
from typing import Dict, Any, Optional
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class MCPAPIClient:
    """Cliente para el API de propuestas personalizadas basado en IA"""

    # URL del MCP Server en Render
    BASE_URL = "https://aremko-mcp-server.onrender.com/api/v1/aremko"
    API_KEY = "aremko_mcp_2024_secure_key"
    TENANT = "aremko"
    TIMEOUT = 30.0  # segundos

    def __init__(self):
        self.headers = {
            "X-API-Key": self.API_KEY,
            "X-Tenant": self.TENANT,
            "Content-Type": "application/json"
        }

    async def generar_propuesta(self, customer_id: int) -> Dict[str, Any]:
        """
        Genera propuesta personalizada para un cliente

        Args:
            customer_id: ID del cliente en ventas_cliente

        Returns:
            Dict con la propuesta personalizada:
            {
                "customer_profile": {...},
                "insights": {...},
                "recommendations": [...],
                "offer": {...},
                "email_body": "HTML content"
            }
        """
        try:
            async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
                response = await client.get(
                    f"{self.BASE_URL}/proposals/customer/{customer_id}",
                    headers=self.headers
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Error generando propuesta para cliente {customer_id}: {e}")
            raise Exception(f"Error en API: {str(e)}")

    async def enviar_propuesta_email(self, customer_id: int) -> Dict[str, Any]:
        """
        Genera y envía propuesta por email al cliente

        Args:
            customer_id: ID del cliente

        Returns:
            Dict con resultado del envío:
            {
                "success": True/False,
                "message": "...",
                "email_sent_to": "email@example.com"
            }
        """
        try:
            async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
                response = await client.post(
                    f"{self.BASE_URL}/proposals/send/{customer_id}",
                    headers=self.headers
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Error enviando propuesta a cliente {customer_id}: {e}")
            raise Exception(f"Error enviando email: {str(e)}")

    async def generar_propuestas_batch(
        self,
        segment: Optional[str] = None,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        Genera propuestas en batch para múltiples clientes

        Args:
            segment: Segmento RFM (opcional): "VIP", "Champions", "At Risk", etc.
            limit: Número máximo de propuestas a generar

        Returns:
            Dict con resultados del batch:
            {
                "total_generated": 10,
                "proposals": [...]
            }
        """
        try:
            params = {"limit": limit}
            if segment:
                params["segment"] = segment

            async with httpx.AsyncClient(timeout=60.0) as client:  # Mayor timeout para batch
                response = await client.post(
                    f"{self.BASE_URL}/proposals/batch",
                    headers=self.headers,
                    params=params
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Error generando batch de propuestas: {e}")
            raise Exception(f"Error en batch: {str(e)}")

    async def health_check(self) -> bool:
        """
        Verifica que el API esté disponible

        Returns:
            True si el API responde correctamente
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    f"{self.BASE_URL.replace('/aremko', '')}/health",
                    headers=self.headers
                )
                return response.status_code == 200
        except:
            return False


# Helper function para usar en vistas síncronas
def generar_propuesta_sync(customer_id: int) -> Dict[str, Any]:
    """
    Versión síncrona de generar_propuesta para usar en vistas Django normales
    """
    client = MCPAPIClient()
    return asyncio.run(client.generar_propuesta(customer_id))


def enviar_propuesta_sync(customer_id: int) -> Dict[str, Any]:
    """
    Versión síncrona de enviar_propuesta_email
    """
    client = MCPAPIClient()
    return asyncio.run(client.enviar_propuesta_email(customer_id))
