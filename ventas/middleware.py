import threading

# Almacena datos de cada hilo para que el request esté disponible globalmente
_thread_locals = threading.local()

def get_current_user():
    """Obtiene el usuario del hilo actual."""
    return getattr(_thread_locals, 'user', None)

class ThreadLocalMiddleware:
    """Middleware para almacenar el usuario actual en thread-local."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _thread_locals.user = getattr(request, 'user', None)
        response = self.get_response(request)
        return response
