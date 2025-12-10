"""
Middleware temporal para debuggear errores 500 en uploads
"""
import logging
import traceback

logger = logging.getLogger(__name__)

class DebugImageUploadMiddleware:
    """
    Middleware para capturar y loggear errores de upload de imágenes
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Si es un POST al admin con archivos
        if request.method == 'POST' and '/admin/' in request.path and request.FILES:
            logger.info(f"📤 Upload detectado en: {request.path}")
            logger.info(f"   Archivos: {list(request.FILES.keys())}")

            for file_key, file_obj in request.FILES.items():
                logger.info(f"   {file_key}:")
                logger.info(f"     - Nombre: {file_obj.name}")
                logger.info(f"     - Tamaño: {file_obj.size} bytes")
                logger.info(f"     - Tipo: {file_obj.content_type}")

        try:
            response = self.get_response(request)

            # Si hay error 500 en upload
            if response.status_code == 500 and request.method == 'POST' and request.FILES:
                logger.error("❌ ERROR 500 en upload de imagen!")
                logger.error(f"   Path: {request.path}")
                logger.error(f"   Archivos: {list(request.FILES.keys())}")

        except Exception as e:
            logger.error(f"❌ EXCEPCIÓN en middleware: {e}")
            logger.error(f"   Traceback completo:")
            logger.error(traceback.format_exc())
            raise

        return response