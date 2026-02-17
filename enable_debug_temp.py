import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.conf import settings

print("=== HABILITAR DEBUG TEMPORALMENTE ===\n")

print(f"DEBUG actual: {settings.DEBUG}")
print(f"ALLOWED_HOSTS: {settings.ALLOWED_HOSTS[:3]}...")

print("\nPara ver el error detallado en el navegador:")
print("1. Edita aremko_project/settings.py")
print("2. Cambia temporalmente DEBUG = True")
print("3. Intenta abrir la VentaReserva 4972")
print("4. Verás el error detallado con traceback")
print("5. IMPORTANTE: Vuelve a poner DEBUG = False después")

print("\nO ejecuta este comando para ver logs detallados:")
print("journalctl -u gunicorn -f --no-pager | grep -A 50 'ERROR'")