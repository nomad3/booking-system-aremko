import threading

# Almacena datos de cada hilo para que el request esté disponible globalmente
_thread_locals = threading.local()

def get_current_request():
    """Obtiene el request del hilo actual."""
    return getattr(_thread_locals, 'request', None)

def get_current_user():
    """Obtiene el usuario del hilo actual."""
    request = get_current_request()
    if request and hasattr(request, 'user'):
        return request.user
    return None

class ThreadLocalMiddleware:
    """Middleware para almacenar el request y usuario actual en thread-local."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Almacenar el request completo en lugar de solo el usuario
        _thread_locals.request = request
        try:
            response = self.get_response(request)
            return response
        finally:
            # Asegurarse de limpiar el thread local después de cada request
            self.clear_thread_locals()

    def clear_thread_locals(self):
        """Limpia las variables thread-local."""
        if hasattr(_thread_locals, 'request'):
            del _thread_locals.request
