#!/usr/bin/env python
"""
Script para forzar reload de Gunicorn sin usar pkill
Uso: python reload_gunicorn_alternativo.py
"""
import os
import signal
import subprocess
import sys

print("=" * 70)
print("FORZANDO RELOAD DE GUNICORN (Método Alternativo)")
print("=" * 70)
print()

# Método 1: Buscar procesos de Gunicorn usando /proc
print("1. Buscando procesos de Gunicorn...")
gunicorn_pids = []

try:
    # Buscar en /proc todos los procesos
    for pid in os.listdir('/proc'):
        if not pid.isdigit():
            continue

        try:
            cmdline_path = f'/proc/{pid}/cmdline'
            if os.path.exists(cmdline_path):
                with open(cmdline_path, 'r') as f:
                    cmdline = f.read().replace('\x00', ' ')
                    if 'gunicorn' in cmdline and 'aremko_project.wsgi' in cmdline:
                        gunicorn_pids.append(int(pid))
                        print(f"   ✅ Proceso Gunicorn encontrado: PID {pid}")
        except (IOError, OSError, PermissionError):
            continue

except Exception as e:
    print(f"   ⚠️ Error buscando procesos: {e}")

print()

if not gunicorn_pids:
    print("❌ No se encontraron procesos de Gunicorn")
    print("   El servidor puede no estar corriendo o usar otro método")
    sys.exit(1)

# Método 2: Enviar señal HUP al proceso maestro (el de menor PID)
master_pid = min(gunicorn_pids)
print(f"2. Enviando señal HUP al proceso maestro (PID {master_pid})...")

try:
    os.kill(master_pid, signal.SIGHUP)
    print(f"   ✅ Señal HUP enviada correctamente al PID {master_pid}")
except Exception as e:
    print(f"   ❌ Error enviando señal: {e}")
    sys.exit(1)

print()
print("3. Esperando 3 segundos para que Gunicorn recargue...")
import time
time.sleep(3)

print()
print("4. Verificando procesos después del reload...")
new_pids = []
try:
    for pid in os.listdir('/proc'):
        if not pid.isdigit():
            continue

        try:
            cmdline_path = f'/proc/{pid}/cmdline'
            if os.path.exists(cmdline_path):
                with open(cmdline_path, 'r') as f:
                    cmdline = f.read().replace('\x00', ' ')
                    if 'gunicorn' in cmdline and 'aremko_project.wsgi' in cmdline:
                        new_pids.append(int(pid))
        except (IOError, OSError, PermissionError):
            continue

    print(f"   ✅ Procesos Gunicorn activos: {len(new_pids)}")
    for pid in new_pids:
        print(f"      - PID {pid}")

except Exception as e:
    print(f"   ⚠️ Error verificando procesos: {e}")

print()
print("=" * 70)
print("RELOAD COMPLETADO")
print("=" * 70)
print()
print("💡 Prueba ahora tu URL desde el navegador.")
print("   Si sigue sin funcionar, reinicia el servicio desde Render Dashboard.")
print()
