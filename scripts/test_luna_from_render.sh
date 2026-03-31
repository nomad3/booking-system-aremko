#!/bin/bash
#
# Script para probar Luna API desde Render
# Ejecutar: bash scripts/test_luna_from_render.sh
#

API_KEY="wmRL0kJ52oq15VfTW8db0bZuYYHLoKKq3mXzwGXXnms"
BASE_URL="https://aremko.cl"

echo "============================================================"
echo "PRUEBA DE LUNA API - FASE 1"
echo "============================================================"

# Test 1: Health Check
echo ""
echo "------------------------------------------------------------"
echo "TEST 1: Health Check (público, sin autenticación)"
echo "------------------------------------------------------------"
curl -s "${BASE_URL}/api/luna/health" | python3 -m json.tool
echo ""

# Test 2: Test Connection
echo ""
echo "------------------------------------------------------------"
echo "TEST 2: Test Connection (con API Key correcta)"
echo "------------------------------------------------------------"
curl -s -H "X-Luna-API-Key: ${API_KEY}" "${BASE_URL}/api/luna/test" | python3 -m json.tool
echo ""

# Test 3: API Key Incorrecta
echo ""
echo "------------------------------------------------------------"
echo "TEST 3: Test con API Key Incorrecta (debe rechazar)"
echo "------------------------------------------------------------"
curl -s -H "X-Luna-API-Key: CLAVE_INCORRECTA" "${BASE_URL}/api/luna/test" | python3 -m json.tool
echo ""

# Test 4: Listar Regiones
echo ""
echo "------------------------------------------------------------"
echo "TEST 4: Listar Regiones y Comunas"
echo "------------------------------------------------------------"
curl -s -H "X-Luna-API-Key: ${API_KEY}" "${BASE_URL}/api/luna/regiones" | python3 -m json.tool | head -30
echo "..."
echo ""

# Test 5: Validar Disponibilidad
echo ""
echo "------------------------------------------------------------"
echo "TEST 5: Validar Disponibilidad (placeholder)"
echo "------------------------------------------------------------"
curl -s -X POST \
  -H "X-Luna-API-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"servicios":[{"servicio_id":12,"fecha":"2026-04-01","hora":"14:30","cantidad_personas":2}]}' \
  "${BASE_URL}/api/luna/reservas/validar" | python3 -m json.tool
echo ""

# Test 6: Crear Reserva
echo ""
echo "------------------------------------------------------------"
echo "TEST 6: Crear Reserva (placeholder)"
echo "------------------------------------------------------------"
curl -s -X POST \
  -H "X-Luna-API-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "idempotency_key":"test-001",
    "cliente":{"nombre":"Test","email":"test@test.com","telefono":"+56912345678","documento_identidad":"12345678-9","region_id":1,"comuna_id":10},
    "servicios":[{"servicio_id":12,"fecha":"2026-04-01","hora":"14:30","cantidad_personas":2}]
  }' \
  "${BASE_URL}/api/luna/reservas/create" | python3 -m json.tool
echo ""

echo "============================================================"
echo "PRUEBAS COMPLETADAS"
echo "============================================================"
echo ""
echo "Si todos los tests respondieron con JSON válido, Fase 1 está OK"
echo ""
