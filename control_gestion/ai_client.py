"""
Cliente LLM para Control de Gestión

Soporta múltiples proveedores:
- OpenAI (gpt-4o-mini, gpt-4, etc.)
- Mock (sin costo, para desarrollo/testing)

Configuración vía variables de entorno:
- LLM_PROVIDER: "openai" o "mock" (default: mock)
- OPENAI_API_KEY: Tu API key de OpenAI
- LLM_MODEL: Modelo a usar (default: gpt-4o-mini)
"""

import os
import json
from typing import Any, Optional
import logging

logger = logging.getLogger(__name__)


class LLMClient:
    """
    Cliente unificado para llamadas a LLM
    
    Soporta OpenAI y modo mock (sin costo).
    El modo mock devuelve respuestas estáticas útiles para desarrollo.
    """
    
    def __init__(self):
        """Inicializar cliente según configuración"""
        self.provider = os.getenv("LLM_PROVIDER", "mock").lower()
        self.model = os.getenv("LLM_MODEL", "gpt-4o-mini")
        self.api_key = os.getenv("OPENAI_API_KEY")
        self._openai = None
        
        # Si no hay API key, forzar modo mock
        if self.provider == "openai" and not self.api_key:
            logger.warning(
                "LLM_PROVIDER=openai pero no hay OPENAI_API_KEY. "
                "Cambiando a modo mock."
            )
            self.provider = "mock"
        
        logger.info(f"LLMClient inicializado en modo: {self.provider}")
    
    def _ensure_openai(self):
        """Inicializar cliente OpenAI si es necesario"""
        if self._openai is None:
            try:
                import openai
                openai.api_key = self.api_key
                self._openai = openai
                logger.info(f"Cliente OpenAI inicializado (model: {self.model})")
            except ImportError:
                logger.error(
                    "Paquete 'openai' no está instalado. "
                    "Instala con: pip install openai"
                )
                raise
        return self._openai
    
    def _mock_completion(self, system: str, user: str) -> str:
        """
        Respuesta mock para desarrollo sin costo
        
        Devuelve respuestas útiles según el prompt del sistema.
        """
        user_lower = user.lower() if user else ""
        
        # Mock para diferentes tipos de prompts
        if "tarea" in system.lower() and "json" in system.lower():
            # message_to_task
            return json.dumps({
                "title": f"Atender: {user[:50]}",
                "description": f"Solicitud del cliente: {user[:200]}",
                "checklist": [
                    "Recibir y confirmar solicitud",
                    "Preparar recursos necesarios",
                    "Ejecutar tarea",
                    "Verificar resultado"
                ],
                "priority": "ALTA" if "urgente" in user_lower or "tina" in user_lower else "NORMAL",
                "suggested_owner_role": "RECEPCION" if "cliente" in user_lower else "OPERACION",
                "promise_due_at": "2025-11-08T12:00:00",
                "location_ref": "TINA_4" if "tina" in user_lower else ""
            }, ensure_ascii=False)
        
        elif "checklist" in system.lower():
            # generate_checklist
            return json.dumps([
                "Preparar área y verificar limpieza",
                "Revisar insumos y materiales necesarios",
                "Ejecutar según protocolo SOP",
                "Verificar temperatura/condiciones",
                "Inspección final y registro",
                "Comunicar al siguiente turno si aplica"
            ], ensure_ascii=False)
        
        elif "resumen" in system.lower() or "diario" in system.lower():
            # summarize_day
            return (
                "📊 **Resumen del Día**\n\n"
                "✅ **Completadas**: Tareas importantes finalizadas\n"
                "⏳ **En Curso**: Tareas activas en progreso\n"
                "🚫 **Bloqueadas**: Requieren atención\n\n"
                "🎯 **Prioridades para mañana**:\n"
                "1. Resolver bloqueos pendientes\n"
                "2. Completar tareas en curso\n"
                "3. Preparar servicios del día"
            )
        
        elif "prioridad" in system.lower() or "clasifica" in system.lower():
            # classify_priority
            prioridad = "ALTA_CLIENTE_EN_SITIO" if any(
                palabra in user_lower 
                for palabra in ["urgente", "inmediato", "sitio", "tina", "cliente"]
            ) else "NORMAL"
            
            return json.dumps({
                "priority": prioridad,
                "reason": f"Análisis de palabras clave en: {user[:100]}"
            }, ensure_ascii=False)
        
        elif "evalúa" in system.lower() or "completada" in system.lower():
            # qa_task_completion
            return json.dumps({
                "status": "Completo",
                "motivo": "Tarea completada correctamente según checklist",
                "siguiente_accion": "Documentar resultados y pasar a siguiente tarea"
            }, ensure_ascii=False)
        
        else:
            # Respuesta genérica
            return f"MOCK RESPONSE: {user[:280] if user else 'Sin input'}"
    
    def _oai_completion(self, system: str, user: str) -> str:
        """
        Llamada real a OpenAI
        
        Args:
            system: System prompt
            user: User prompt
            
        Returns:
            Respuesta del modelo
        """
        try:
            oai = self._ensure_openai()
            
            response = oai.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user}
                ],
                temperature=0.2,  # Más determinista para tareas operativas
                max_tokens=2000
            )
            
            content = response.choices[0].message.content
            logger.info(f"OpenAI completion exitoso (model: {self.model})")
            
            return content
        
        except Exception as e:
            logger.error(f"Error en llamada a OpenAI: {str(e)}")
            # Fallback a mock en caso de error
            logger.warning("Fallback a modo mock por error en OpenAI")
            return self._mock_completion(system, user)
    
    def complete(self, system: str, user: str) -> str:
        """
        Generar completion con el proveedor configurado
        
        Args:
            system: System prompt (contexto, instrucciones)
            user: User prompt (input del usuario)
            
        Returns:
            Texto de respuesta del LLM
        """
        if not system or not user:
            logger.warning("System o user prompt vacío")
            return ""
        
        try:
            if self.provider == "openai":
                return self._oai_completion(system, user)
            else:
                return self._mock_completion(system, user)
        
        except Exception as e:
            logger.error(f"Error en complete(): {str(e)}")
            return self._mock_completion(system, user)
    
    def is_mock(self) -> bool:
        """Retorna True si está en modo mock"""
        return self.provider == "mock"
    
    def get_info(self) -> dict:
        """Retorna información del cliente LLM"""
        return {
            "provider": self.provider,
            "model": self.model if self.provider == "openai" else "mock",
            "is_mock": self.is_mock()
        }

