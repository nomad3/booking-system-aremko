# Configuración de Luna API - Fase 1 Completada

## ✅ Archivos Creados

1. **`ventas/views/luna_api_views.py`**:
   - Autenticación con API Key
   - 5 endpoints básicos implementados
   - Logging y manejo de errores

2. **`ventas/urls.py`** (actualizado):
   - URLs configuradas para Luna API
   - Sección claramente marcada

---

## 🔧 Configuración en Render

### Paso 1: Agregar Variable de Entorno

1. Ve a tu servicio web en Render Dashboard
2. Click en **"Environment"** en el menú lateral
3. Click en **"Add Environment Variable"**
4. Agrega la siguiente variable:

```
Key: LUNA_API_KEY
Value: [genera una clave aleatoria segura]
```

**Generar clave segura** (ejecuta en tu terminal local):
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Ejemplo de clave generada:
```
wmRL0kJ52oq15VfTW8db0bZuYYHLoKKq3mXzwGXXnms
```

5. Click en **"Save Changes"**
6. Render automáticamente hará redeploy

---

## 🧪 Testing - Endpoints Disponibles

### 1. Health Check (sin autenticación)

```bash
curl https://aremko.cl/api/luna/health
```

**Respuesta esperada**:
```json
{
  "status": "healthy",
  "service": "luna-api",
  "timestamp": "2026-03-31T15:30:00Z"
}
```

---

### 2. Test Connection (con autenticación)

```bash
curl -X GET https://aremko.cl/api/luna/test \
  -H "X-Luna-API-Key: TU_API_KEY_AQUI"
```

**Respuesta esperada** (éxito):
```json
{
  "success": true,
  "message": "Autenticación exitosa. Luna API funcionando correctamente.",
  "timestamp": "2026-03-31T15:30:00Z",
  "version": "1.0.0"
}
```

**Respuesta esperada** (error - sin API key):
```json
{
  "detail": "API Key no proporcionada. Use header X-Luna-API-Key."
}
```

**Respuesta esperada** (error - API key inválida):
```json
{
  "detail": "API Key inválida."
}
```

---

### 3. Listar Regiones

```bash
curl -X GET https://aremko.cl/api/luna/regiones \
  -H "X-Luna-API-Key: TU_API_KEY_AQUI"
```

**Respuesta esperada**:
```json
{
  "success": true,
  "regiones": [
    {
      "id": 1,
      "nombre": "Región de Los Lagos",
      "comunas": [
        {"id": 10, "nombre": "Puerto Varas"},
        {"id": 11, "nombre": "Puerto Montt"}
      ]
    }
  ]
}
```

---

### 4. Validar Disponibilidad (Fase 2 - en desarrollo)

```bash
curl -X POST https://aremko.cl/api/luna/reservas/validar \
  -H "X-Luna-API-Key: TU_API_KEY_AQUI" \
  -H "Content-Type: application/json" \
  -d '{
    "servicios": [
      {
        "servicio_id": 12,
        "fecha": "2026-04-01",
        "hora": "14:30",
        "cantidad_personas": 2
      }
    ]
  }'
```

**Respuesta actual** (Fase 1):
```json
{
  "success": true,
  "disponibilidad": [],
  "mensaje": "Endpoint en desarrollo - Fase 2"
}
```

---

### 5. Crear Reserva (Fase 3 - en desarrollo)

```bash
curl -X POST https://aremko.cl/api/luna/reservas/create \
  -H "X-Luna-API-Key: TU_API_KEY_AQUI" \
  -H "Content-Type: application/json" \
  -d '{
    "idempotency_key": "test-123",
    "cliente": {
      "nombre": "Juan Pérez",
      "email": "juan@example.com",
      "telefono": "+56912345678",
      "documento_identidad": "12345678-9",
      "region_id": 1,
      "comuna_id": 10
    },
    "servicios": [
      {
        "servicio_id": 12,
        "fecha": "2026-04-01",
        "hora": "14:30",
        "cantidad_personas": 2
      }
    ]
  }'
```

**Respuesta actual** (Fase 1):
```json
{
  "success": true,
  "mensaje": "Endpoint en desarrollo - Fase 3",
  "nota": "La autenticación funciona correctamente"
}
```

---

## 📋 Checklist de Verificación Fase 1

Después de hacer el deploy, verifica:

- [ ] Variable `LUNA_API_KEY` agregada en Render
- [ ] Deploy completado sin errores
- [ ] Health check responde: `curl https://aremko.cl/api/luna/health`
- [ ] Test endpoint con API Key correcta funciona
- [ ] Test endpoint con API Key incorrecta rechaza (error 401/403)
- [ ] Endpoint regiones funciona
- [ ] Logs en Render muestran requests de Luna

---

## 🔒 Seguridad - API Key

### Proteger la API Key

1. **NO** subir la API Key a Git
2. **NO** compartir la API Key públicamente
3. **NO** hardcodear la API Key en código
4. **SÍ** usar variables de entorno
5. **SÍ** rotar la clave cada 3 meses

### Rotar API Key

Si necesitas cambiar la API Key:

1. Genera nueva clave: `python -c "import secrets; print(secrets.token_urlsafe(32))"`
2. Actualiza `LUNA_API_KEY` en Render
3. Actualiza configuración de Luna con la nueva clave
4. Verifica que todo funciona
5. La clave anterior deja de funcionar automáticamente

---

## 📊 Monitoreo

### Ver Logs en Render

1. Ve a tu servicio en Render Dashboard
2. Click en **"Logs"** en el menú lateral
3. Busca entradas con `[Luna API]`

Ejemplo de log exitoso:
```
[Luna API] Solicitud de creación de reserva recibida
```

Ejemplo de log de error:
```
WARNING: Intento de acceso con API Key inválida: abcd123...
```

---

## ⚠️ Troubleshooting

### Error: "API Key no configurada en el servidor"

**Problema**: Variable `LUNA_API_KEY` no está en Render

**Solución**:
1. Ve a Render Dashboard → Environment
2. Agrega `LUNA_API_KEY` con valor seguro
3. Guarda cambios
4. Espera redeploy automático

---

### Error: "ModuleNotFoundError: No module named 'ventas.views.luna_api_views'"

**Problema**: Archivo no se subió a Git o deploy falló

**Solución**:
```bash
# Verificar que el archivo existe localmente
ls -la ventas/views/luna_api_views.py

# Si existe, hacer commit y push
git add ventas/views/luna_api_views.py
git commit -m "Add Luna API views"
git push

# Render hará redeploy automático
```

---

### Error 500 en endpoints

**Problema**: Error interno en el código

**Solución**:
1. Revisa logs en Render Dashboard
2. Busca el traceback completo del error
3. Corrige el problema
4. Haz commit y push
5. Espera redeploy

---

## 🎯 Próximos Pasos

**Fase 2** (siguiente): Implementar validaciones completas
- Validar datos de cliente
- Validar disponibilidad de servicios
- Verificar capacidad
- Calcular totales con descuentos

**Fase 3** (después): Implementar creación de reservas
- Crear VentaReserva
- Crear ReservaServicio
- Integrar con ClienteService
- Manejo de transacciones

---

## 📞 Soporte

Si tienes problemas:
1. Revisa logs en Render
2. Verifica que la API Key está configurada
3. Prueba endpoints uno por uno
4. Revisa este documento

---

**Fecha**: 31 de Marzo, 2026
**Versión**: Fase 1 - Infraestructura Base
**Status**: ✅ Completado