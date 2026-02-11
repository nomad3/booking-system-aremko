#!/bin/bash
# Script para detener y reiniciar el gateway con Kimi

echo "=== Deteniendo OpenClaw Gateway ==="

# Primero intentar detener el proceso por PID
if [ -f ~/.openclaw/.data/gateway.pid ]; then
    PID=$(cat ~/.openclaw/.data/gateway.pid)
    echo "Encontrado PID: $PID"
    kill $PID 2>/dev/null || echo "No se pudo detener con PID"
    sleep 2
fi

# Matar todos los procesos openclaw-gateway
pkill -f "openclaw-gateway" || echo "No hay procesos openclaw-gateway activos"

# Matar procesos node relacionados con openclaw
pkill -f "node.*openclaw" || echo "No hay procesos node openclaw activos"

# Verificar si quedan procesos
echo ""
echo "=== Verificando procesos restantes ==="
ps aux | grep -E "(openclaw|18789)" | grep -v grep || echo "No hay procesos openclaw activos"

# Limpiar archivo PID
rm -f ~/.openclaw/.data/gateway.pid

echo ""
echo "=== Reiniciando OpenClaw Gateway con Kimi ==="
echo ""

# Reiniciar el gateway
nohup openclaw gateway > ~/openclaw_gateway.log 2>&1 &

echo "Gateway iniciándose... Esperando 5 segundos..."
sleep 5

# Verificar si está corriendo
if ps aux | grep -q "[o]penclaw-gateway"; then
    echo "✓ Gateway reiniciado exitosamente"
    echo ""
    echo "=== Verificando configuración ==="
    curl -s http://localhost:18789/health | jq . || echo "Gateway aún iniciándose..."
    echo ""
    echo "Logs disponibles en: ~/openclaw_gateway.log"
    echo "Para ver logs en tiempo real: tail -f ~/openclaw_gateway.log"
else
    echo "✗ Error al reiniciar el gateway"
    echo "Revisa los logs: cat ~/openclaw_gateway.log"
fi