# Documentación Luna API - Sistema de Reservas WhatsApp

## Resumen Ejecutivo

Luna API es un sistema completo de reservas que permite al agente conversacional Luna crear reservas directamente desde WhatsApp sin necesidad de que el cliente visite la web o llame por teléfono.

**Fecha de implementación:** 31 de Marzo, 2026
**Status:** ✅ Completado y en producción
**URL Base:** `https://aremko.cl/ventas/api/luna/`

---

## Características Principales

✅ **Autenticación segura** con API Key
✅ **Validación de disponibilidad** en tiempo real
✅ **Cálculo automático de precios** y descuentos por packs
✅ **Creación atómica de reservas** con transacciones
✅ **Idempotencia** para prevenir duplicados
✅ **Gestión inteligente de clientes** (crear/actualizar)
✅ **Respuestas completas** con todos los detalles

---

## Arquitectura de 3 Fases

### Fase 1: Infraestructura Base ✅
- Autenticación con API Key en headers
- 5 endpoints RESTful
- Logging y manejo de errores
- Sistema de health check

### Fase 2: Validaciones ✅
- Validación de servicios (existencia, estado activo)
- Validación de disponibilidad (slots, capacidad, bloqueos)
- Cálculo de precios con lógica especial para cabañas
- Detección automática de packs y descuentos
- Validación de datos de cliente (email, teléfono, RUT)

### Fase 3: Creación de Reservas ✅
- Creación atómica con transacciones Django
- Gestión de clientes con ClienteService
- Idempotencia con Django cache (24h)
- Aplicación automática de descuentos
- Generación de número de reserva

---

## Endpoints Disponibles

### 1. Health Check (Público)

**Endpoint:** `GET /api/luna/health/`
**Autenticación:** No requerida
**Propósito:** Verificar que el servicio está operativo

**Respuesta:**
```json
{
  "status": "healthy",
  "service": "luna-api",
  "timestamp": "2026-03-31T21:28:31.632698+00:00"
}
```

---

### 2. Test de Conexión

**Endpoint:** `GET /api/luna/test/`
**Autenticación:** ✅ API Key requerida
**Propósito:** Verificar que la autenticación funciona

**Headers:**
```
X-Luna-API-Key: wmRL0kJ52oq15VfTW8db0bZuYYHLoKKq3mXzwGXXnms
```

**Respuesta:**
```json
{
  "success": true,
  "message": "Autenticación exitosa. Luna API funcionando correctamente.",
  "timestamp": "2026-03-31T21:28:31.759359+00:00",
  "version": "1.0.0"
}
```

**Errores:**
- `403 Forbidden`: API Key inválida o faltante

---

### 3. Listar Regiones y Comunas

**Endpoint:** `GET /api/luna/regiones/`
**Autenticación:** ✅ API Key requerida
**Propósito:** Obtener lista completa de regiones de Chile con sus comunas

**Respuesta:**
```json
{
  "success": true,
  "regiones": [
    {
      "id": 14,
      "nombre": "Los Lagos",
      "comunas": [
        {"id": 28, "nombre": "Ancud"},
        {"id": 31, "nombre": "Calbuco"},
        {"id": 318, "nombre": "Puerto Varas"}
      ]
    }
  ]
}
```

**Uso:**
- Mostrar selector de regiones al cliente
- Validar que región y comuna coincidan
- Autocompletar datos de ubicación

---

### 4. Validar Disponibilidad

**Endpoint:** `POST /api/luna/reservas/validar/`
**Autenticación:** ✅ API Key requerida
**Propósito:** Verificar disponibilidad de servicios antes de crear la reserva

**Request Body:**
```json
{
  "servicios": [
    {
      "servicio_id": 12,
      "fecha": "2026-04-15",
      "hora": "14:30",
      "cantidad_personas": 4
    }
  ]
}
```

**Respuesta Exitosa:**
```json
{
  "success": true,
  "disponibilidad": [
    {
      "servicio_id": 12,
      "servicio_nombre": "Tina Calbuco",
      "servicio_tipo": "tina",
      "disponible": true,
      "fecha": "2026-04-15",
      "hora": "14:30",
      "cantidad_personas": 4,
      "capacidad_disponible": 4,
      "precio_unitario": 25000.0,
      "precio_estimado": 100000.0
    }
  ],
  "total_estimado": 100000.0,
  "descuentos_aplicables": [
    {
      "pack_nombre": "Pack Tina + Masaje",
      "descuento": 35000.0,
      "descripcion": "Pack aplicado: Pack Tina + Masaje (Tina Calbuco + Masaje Relajante)"
    }
  ],
  "total_descuentos": 35000.0,
  "total_con_descuentos": 65000.0,
  "mensaje": "1 servicio(s) disponible(s)"
}
```

**Respuesta con Errores:**
```json
{
  "success": false,
  "error": "validation_errors",
  "errores": [
    {
      "servicio_index": 0,
      "servicio_id": 12,
      "error": "below_min_capacity",
      "mensaje": "Tina Calbuco requiere mínimo 4 personas"
    }
  ],
  "mensaje": "1 servicio(s) con errores de validación"
}
```

**Validaciones que realiza:**
- ✅ Servicio existe y está activo
- ✅ Fecha tiene formato válido (YYYY-MM-DD)
- ✅ Fecha no es pasada
- ✅ Hora tiene formato válido (HH:MM)
- ✅ Cantidad de personas dentro del rango permitido
- ✅ No hay bloqueos de servicio (ServicioBloqueo)
- ✅ No hay bloqueos de slot (ServicioSlotBloqueo)
- ✅ Hay capacidad disponible
- ✅ Calcula precios correctamente (cabañas: precio fijo, otros: por persona)
- ✅ Detecta y aplica descuentos por packs automáticamente

**Códigos de Error:**
- `service_not_found`: Servicio no existe o no está activo
- `invalid_date`: Formato de fecha inválido
- `past_date`: No se puede reservar en fecha pasada
- `invalid_time`: Formato de hora inválido
- `below_min_capacity`: Menos personas que el mínimo requerido
- `above_max_capacity`: Más personas que el máximo permitido
- `service_blocked`: Servicio bloqueado en ese rango de fechas
- `slot_blocked`: Slot específico bloqueado
- `no_availability`: Sin disponibilidad (slots ocupados)
- `insufficient_capacity`: Capacidad insuficiente para la cantidad solicitada

---

### 5. Crear Reserva Completa

**Endpoint:** `POST /api/luna/reservas/create/`
**Autenticación:** ✅ API Key requerida
**Propósito:** Crear una reserva completa con todos los detalles

**Request Body:**
```json
{
  "idempotency_key": "luna-conv-12345-1234567890",
  "cliente": {
    "nombre": "Juan Pérez",
    "email": "juan@example.com",
    "telefono": "+56987654321",
    "documento_identidad": "11111111-1",
    "region_id": 14,
    "comuna_id": 318
  },
  "servicios": [
    {
      "servicio_id": 12,
      "fecha": "2026-04-15",
      "hora": "14:30",
      "cantidad_personas": 4
    }
  ],
  "metodo_pago": "pendiente",
  "notas": "Reserva creada por Luna via WhatsApp"
}
```

**Campos Requeridos:**

**`idempotency_key`** (string):
- Identificador único para esta reserva
- Previene duplicados si se reenvía la misma solicitud
- Formato sugerido: `"luna-{conversation_id}-{timestamp}"`
- Se almacena en cache por 24 horas

**`cliente`** (object):
- `nombre` (string, requerido): Nombre completo, mínimo 3 caracteres
- `email` (string, requerido): Email válido
- `telefono` (string, requerido): Teléfono chileno (+56XXXXXXXXX)
- `documento_identidad` (string, opcional): RUT chileno con dígito verificador
- `region_id` (integer, requerido): ID de región de Chile
- `comuna_id` (integer, requerido): ID de comuna que pertenece a la región

**`servicios`** (array):
- Array de al menos 1 servicio
- Cada servicio requiere:
  - `servicio_id` (integer): ID del servicio a reservar
  - `fecha` (string): Formato YYYY-MM-DD
  - `hora` (string): Formato HH:MM (24 horas)
  - `cantidad_personas` (integer): Número de personas

**`metodo_pago`** (string, opcional):
- Valores: `"pendiente"`, `"pagado"`, `"parcial"`
- Default: `"pendiente"`

**`notas`** (string, opcional):
- Comentarios adicionales
- Se prefija automáticamente con "[Luna WhatsApp]"

**Respuesta Exitosa (201 Created):**
```json
{
  "success": true,
  "reserva": {
    "id": 5403,
    "numero": "RES-5403",
    "cliente": {
      "id": 20964,
      "nombre": "Juan Pérez",
      "email": "juan@example.com",
      "telefono": "+56987654321",
      "documento_identidad": "11111111-1"
    },
    "servicios": [
      {
        "id": 11524,
        "servicio_id": 12,
        "servicio_nombre": "Tina Calbuco",
        "fecha": "2026-04-15",
        "hora": "14:30",
        "cantidad_personas": 4,
        "precio_unitario": 25000.0,
        "subtotal": 100000.0
      }
    ],
    "total": 100000.0,
    "pagado": 0.0,
    "saldo_pendiente": 100000.0,
    "estado_pago": "pendiente",
    "descuentos_aplicados": [],
    "total_descuentos": 0.0,
    "fecha_creacion": "2026-03-31T22:07:59.406225+00:00",
    "notas": "Reserva creada por Luna via WhatsApp"
  },
  "mensaje": "Reserva creada exitosamente: 5403"
}
```

**Respuesta Duplicada (200 OK):**
```json
{
  "success": true,
  "reserva": { /* mismos datos */ },
  "duplicada": true,
  "mensaje": "Reserva ya fue creada previamente"
}
```

**Respuestas de Error:**

**400 Bad Request - Datos inválidos:**
```json
{
  "success": false,
  "error": "validation_error",
  "errores": [
    {
      "campo": "nombre",
      "mensaje": "Nombre debe tener al menos 3 caracteres"
    },
    {
      "campo": "email",
      "mensaje": "Email tiene formato inválido"
    }
  ],
  "mensaje": "Datos de cliente inválidos"
}
```

**400 Bad Request - Sin disponibilidad:**
```json
{
  "success": false,
  "error": "availability_error",
  "errores": [
    {
      "servicio_index": 0,
      "servicio_id": 12,
      "error": "no_availability",
      "mensaje": "Tina Calbuco no tiene disponibilidad en ese horario"
    }
  ],
  "mensaje": "Uno o más servicios no están disponibles"
}
```

**500 Internal Server Error:**
```json
{
  "success": false,
  "error": "internal_error",
  "mensaje": "Error interno al crear reserva"
}
```

**Proceso Interno:**

1. **Validación de campos requeridos**
2. **Verificación de idempotencia** (cache)
3. **Validación de datos del cliente** (email, teléfono, RUT)
4. **Validación de disponibilidad** de servicios
5. **Transacción atómica**:
   - Buscar o crear Cliente por teléfono
   - Crear VentaReserva
   - Crear ReservaServicio para cada servicio
   - Calcular y aplicar descuentos
   - Actualizar totales
6. **Guardar en cache** para idempotencia (24h)
7. **Retornar respuesta completa**

---

## Autenticación

Todos los endpoints (excepto `/health/`) requieren autenticación mediante API Key.

**Header requerido:**
```
X-Luna-API-Key: wmRL0kJ52oq15VfTW8db0bZuYYHLoKKq3mXzwGXXnms
```

**Configuración en Render:**
```bash
# Variable de entorno
LUNA_API_KEY=wmRL0kJ52oq15VfTW8db0bZuYYHLoKKq3mXzwGXXnms
```

**Errores de autenticación:**
- Sin API Key: `403 Forbidden - "API Key no proporcionada. Use header X-Luna-API-Key."`
- API Key inválida: `403 Forbidden - "API Key inválida."`
- API Key no configurada en servidor: `403 Forbidden - "API Key no configurada en el servidor."`

---

## Servicios Disponibles

### Tinas de Agua Caliente
| ID | Nombre | Capacidad | Precio/persona |
|----|--------|-----------|----------------|
| 12 | Tina Calbuco | 4-8 personas | $25,000 |
| 13 | Tina Hornopirén | 4-8 personas | $25,000 |
| 14 | Tina Puelo | 2-4 personas | $25,000 |

### Masajes
| ID | Nombre | Precio |
|----|--------|--------|
| 20 | Masaje Relajante | $35,000 |
| 21 | Masaje Descontracturante | $40,000 |
| 22 | Masaje con Piedras Calientes | $45,000 |

### Cabañas
| ID | Nombre | Capacidad | Precio/noche |
|----|--------|-----------|--------------|
| 30 | Cabaña Torre | 2 personas | $80,000 |
| 31 | Cabaña Refugio | 4 personas | $120,000 |

*Nota: Los IDs exactos pueden variar según la configuración del sistema.*

---

## Descuentos Automáticos (Packs)

Los descuentos se aplican **automáticamente** cuando se cumplen las condiciones:

### Pack Tina + Masaje: $35,000
**Condiciones:**
- Al menos 2 personas en tina(s)
- Al menos 2 masajes reservados
- Mismo día (fecha)

**Ejemplo:**
- Tina 2 personas: $50,000
- 2 Masajes: $70,000
- **Subtotal:** $120,000
- **Descuento:** -$35,000
- **Total:** $85,000

### Pack Alojamiento + Tina
**Condiciones:**
- Al menos 2 personas en cabaña
- Al menos 2 personas en tina
- Mismo día

### Otros packs
El sistema detecta automáticamente otros packs configurados en el modelo `PackDescuento`.

---

## Validación de Datos de Cliente

### Email
- Formato válido: `usuario@dominio.com`
- Expresión regular: `^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$`

### Teléfono Chileno
**Formatos aceptados:**
- `+56912345678`
- `56912345678`
- `912345678`

**Normalización:**
- Todos se convierten a: `+56912345678`
- Debe empezar con 9 (celular)
- 9 dígitos totales

### RUT Chileno (Opcional)
**Formatos aceptados:**
- `12345678-9`
- `12.345.678-9`
- `12345678-K`

**Validación:**
- Verifica dígito verificador mediante algoritmo de módulo 11
- Rechaza RUTs con dígito verificador incorrecto

### Región y Comuna
**Validación:**
- `region_id` debe existir en tabla `Region`
- `comuna_id` debe existir en tabla `Comuna`
- La comuna debe pertenecer a la región seleccionada

---

## Idempotencia

### Propósito
Prevenir la creación de reservas duplicadas si el cliente reenvía la misma solicitud.

### Implementación
- **Key:** `luna_reserva_{idempotency_key}`
- **Storage:** Django Cache
- **TTL:** 24 horas
- **Respuesta:** Si existe, retorna la reserva existente con `"duplicada": true`

### Recomendaciones
**Generar idempotency_key único:**
```javascript
// Ejemplo en JavaScript
const idempotencyKey = `luna-${conversationId}-${Date.now()}`;
```

**Reutilizar el mismo key:**
- Si el request falla por timeout o error de red
- NO generar nuevo key, reutilizar el mismo
- El sistema retornará la reserva creada si ya existe

---

## Manejo de Errores

### Códigos HTTP

| Código | Significado | Cuándo ocurre |
|--------|-------------|---------------|
| 200 | OK | Request exitoso (GET, duplicada) |
| 201 | Created | Reserva creada exitosamente |
| 400 | Bad Request | Datos inválidos, validación fallida |
| 403 | Forbidden | API Key inválida o faltante |
| 500 | Internal Server Error | Error interno del servidor |

### Estructura de Errores

**Todos los errores incluyen:**
```json
{
  "success": false,
  "error": "codigo_error",
  "mensaje": "Descripción legible",
  "errores": [ /* array opcional con detalles */ ]
}
```

### Logging

Todos los errores se registran en logs con:
- Nivel ERROR para errores 500
- Nivel WARNING para errores de validación
- Nivel INFO para requests exitosos
- Prefix: `[Luna API]`

**Ejemplo de log:**
```
ERROR [Luna API] Error creando reserva: Servicio con ID 999 no existe
```

---

## Tests Automatizados

### Scripts de Testing

**Fase 1 - Infraestructura:**
```bash
python scripts/test_luna_api_phase1.py
```

**Fase 2 - Validaciones:**
```bash
python scripts/test_luna_api_phase2.py
```

**Fase 3 - Creación de Reservas:**
```bash
python scripts/test_luna_api_phase3.py
```

### Coverage de Tests

**Fase 1 (6 tests):**
- ✅ Health check público
- ✅ Test de autenticación
- ✅ Rechazo de API Key inválida
- ✅ Listar regiones
- ✅ Placeholder validar disponibilidad
- ✅ Placeholder crear reserva

**Fase 2 (5 tests):**
- ✅ Validación exitosa de disponibilidad
- ✅ Rechazo de servicio inexistente
- ✅ Rechazo de fecha pasada
- ✅ Validación de respuesta completa
- ✅ Rechazo de capacidad excedida

**Fase 3 (4 tests):**
- ✅ Creación exitosa de reserva completa
- ✅ Detección de reserva duplicada (idempotencia)
- ✅ Rechazo de cliente sin nombre
- ✅ Rechazo de request sin idempotency_key

---

## Ejemplos de Uso

### Ejemplo 1: Validar y Crear Reserva Simple

```python
import requests

API_KEY = "wmRL0kJ52oq15VfTW8db0bZuYYHLoKKq3mXzwGXXnms"
BASE_URL = "https://aremko.cl/ventas/api/luna"

headers = {
    "X-Luna-API-Key": API_KEY,
    "Content-Type": "application/json"
}

# 1. Validar disponibilidad
validacion = requests.post(
    f"{BASE_URL}/reservas/validar/",
    headers=headers,
    json={
        "servicios": [{
            "servicio_id": 12,
            "fecha": "2026-04-15",
            "hora": "14:30",
            "cantidad_personas": 4
        }]
    }
)

if validacion.json()["success"]:
    # 2. Crear reserva
    reserva = requests.post(
        f"{BASE_URL}/reservas/create/",
        headers=headers,
        json={
            "idempotency_key": f"luna-{conversation_id}-{timestamp}",
            "cliente": {
                "nombre": "Juan Pérez",
                "email": "juan@example.com",
                "telefono": "+56987654321",
                "region_id": 14,
                "comuna_id": 318
            },
            "servicios": [{
                "servicio_id": 12,
                "fecha": "2026-04-15",
                "hora": "14:30",
                "cantidad_personas": 4
            }],
            "metodo_pago": "pendiente",
            "notas": "Reserva desde WhatsApp"
        }
    )

    if reserva.status_code == 201:
        reserva_data = reserva.json()["reserva"]
        print(f"✅ Reserva creada: {reserva_data['numero']}")
        print(f"💰 Total: ${reserva_data['total']:,.0f}")
```

### Ejemplo 2: Manejo de No Disponibilidad

```python
validacion = requests.post(
    f"{BASE_URL}/reservas/validar/",
    headers=headers,
    json={
        "servicios": [{
            "servicio_id": 12,
            "fecha": "2026-04-15",
            "hora": "14:30",
            "cantidad_personas": 4
        }]
    }
)

response = validacion.json()

if not response["success"]:
    # Mostrar errores al cliente
    for error in response["errores"]:
        if error["error"] == "no_availability":
            print("❌ Ese horario ya está reservado")
            print("💡 Ofrecer horarios alternativos...")
        elif error["error"] == "below_min_capacity":
            print(f"⚠️ {error['mensaje']}")
```

### Ejemplo 3: Aplicar Descuentos Automáticos

```python
# Validar pack (tina + masajes)
validacion = requests.post(
    f"{BASE_URL}/reservas/validar/",
    headers=headers,
    json={
        "servicios": [
            {
                "servicio_id": 12,  # Tina
                "fecha": "2026-04-15",
                "hora": "14:30",
                "cantidad_personas": 2
            },
            {
                "servicio_id": 20,  # Masaje
                "fecha": "2026-04-15",
                "hora": "16:00",
                "cantidad_personas": 2
            }
        ]
    }
)

response = validacion.json()

if response["success"]:
    print(f"Subtotal: ${response['total_estimado']:,.0f}")

    if response["descuentos_aplicables"]:
        for descuento in response["descuentos_aplicables"]:
            print(f"🎉 {descuento['pack_nombre']}: -${descuento['descuento']:,.0f}")

    print(f"💰 Total: ${response['total_con_descuentos']:,.0f}")
```

---

## Seguridad

### Buenas Prácticas

✅ **API Key en variables de entorno:** Nunca hardcodear en código
✅ **HTTPS obligatorio:** Todas las comunicaciones encriptadas
✅ **Logging de intentos fallidos:** Detectar intentos de acceso no autorizado
✅ **Rate limiting:** Implementado a nivel de infraestructura (Render)
✅ **Validación de datos:** Múltiples capas de validación
✅ **Transacciones atómicas:** Garantizar consistencia de datos
✅ **Idempotencia:** Prevenir duplicados maliciosos

### Rotación de API Key

**Cada 3-6 meses o si se compromete:**

1. Generar nueva clave:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

2. Actualizar en Render:
```
Dashboard → Environment → LUNA_API_KEY → Save
```

3. Actualizar en configuración de Luna

4. La clave anterior deja de funcionar inmediatamente

---

## Monitoreo

### Logs en Render

**Buscar en logs:**
```
[Luna API]
```

**Ejemplos de logs:**
```
INFO [Luna API] Cliente creado: Juan Pérez (+56987654321)
INFO [Luna API] VentaReserva creada: ID 5403
INFO [Luna API] Reserva completada: Total $100000 (descuentos: $0)
WARNING [Luna API] Intento de acceso con API Key inválida
ERROR [Luna API] Error creando reserva: Servicio no encontrado
```

### Métricas Clave

- **Tasa de éxito de creación de reservas**
- **Tiempo de respuesta promedio**
- **Errores de validación más comunes**
- **Descuentos aplicados por día**
- **Horarios más solicitados**

---

## Troubleshooting

### Error: "API Key no configurada en el servidor"

**Problema:** Variable `LUNA_API_KEY` no existe en Render

**Solución:**
1. Render Dashboard → Service → Environment
2. Add Environment Variable: `LUNA_API_KEY`
3. Value: `wmRL0kJ52oq15VfTW8db0bZuYYHLoKKq3mXzwGXXnms`
4. Save Changes (autodeploy)

---

### Error: "Servicio no existe o no está activo"

**Problema:** ID de servicio incorrecto o servicio desactivado

**Solución:**
1. Verificar servicios activos:
```bash
python scripts/check_active_services.py
```

2. Usar IDs correctos
3. O activar servicio en Django Admin

---

### Error: "Comuna no pertenece a la región seleccionada"

**Problema:** IDs de región y comuna no coinciden

**Solución:**
1. Listar regiones y comunas:
```bash
python scripts/check_regions.py
```

2. Verificar que `comuna_id` pertenece a `region_id`

**Ejemplo válido:**
- Región 14 (Los Lagos) → Comuna 318 (Puerto Varas) ✅
- Región 14 (Los Lagos) → Comuna 10 (Valparaíso) ❌

---

### Error: "RUT inválido. Dígito verificador incorrecto"

**Problema:** RUT con dígito verificador incorrecto

**Solución:**
- Usar RUT válido con DV correcto
- O omitir el campo `documento_identidad` (es opcional)

**RUTs de prueba válidos:**
- `11111111-1`
- `22222222-2`
- `33333333-3`

---

### Error: Reserva duplicada no detectada

**Problema:** Idempotency key diferente

**Solución:**
- Usar el mismo `idempotency_key` para la misma conversación
- No generar nuevo key en cada reintento
- Formato: `luna-{conversation_id}-{timestamp_inicial}`

---

## Próximas Mejoras (Roadmap)

### Corto Plazo
- [ ] Endpoint para consultar reservas existentes
- [ ] Endpoint para cancelar reservas
- [ ] Webhook para notificar cambios de estado

### Mediano Plazo
- [ ] Integración con Flow.cl para pagos
- [ ] Envío automático de confirmaciones (SMS/Email)
- [ ] Recordatorios automáticos 24h antes

### Largo Plazo
- [ ] Modificación de reservas existentes
- [ ] Sistema de lista de espera
- [ ] Recomendaciones inteligentes de horarios

---

## Soporte

**Contacto técnico:**
- GitHub Issues: https://github.com/nomad3/booking-system-aremko
- Email técnico: dev@aremko.cl

**Contacto Aremko:**
- WhatsApp: +56 9 5336 1647
- Email: reservas@aremko.cl
- Web: www.aremko.cl

---

**Documentación actualizada:** 31 de Marzo, 2026
**Versión API:** 1.0.0
**Status:** ✅ En producción
