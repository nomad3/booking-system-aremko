#!/bin/bash
# Script para forzar el reload de Gunicorn en Render
# Uso: bash force_reload_gunicorn.sh

echo "======================================================================"
echo "FORZANDO RELOAD DE GUNICORN"
echo "======================================================================"
echo

# 1. Verificar procesos de Gunicorn
echo "1. Procesos Gunicorn actuales:"
ps aux | grep gunicorn | grep -v grep
echo

# 2. Enviar señal HUP (Hot reload) al proceso maestro
echo "2. Enviando señal HUP a Gunicorn (hot reload)..."
pkill -HUP gunicorn
sleep 2

echo "3. Verificando procesos después del reload:"
ps aux | grep gunicorn | grep -v grep
echo

# 4. Probar las URLs de Django
echo "4. Verificando que Django conoce las URLs..."
python manage.py shell <<EOF
from django.urls import reverse
try:
    # Probar que la URL existe
    url = reverse('ventas:comanda_cliente', kwargs={'token': 'test-token'})
    print(f"✅ URL de comanda resuelve correctamente: {url}")
except Exception as e:
    print(f"❌ Error al resolver URL: {e}")
EOF

echo
echo "======================================================================"
echo "RELOAD COMPLETADO"
echo "======================================================================"
echo
echo "💡 Ahora intenta acceder a tu URL de comanda desde el navegador."
echo "   Si sigue sin funcionar, reinicia el servicio completo desde Render Dashboard."
echo
