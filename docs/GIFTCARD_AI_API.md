# 🎁 API de GiftCards con IA - Documentación

Sistema de GiftCards personalizadas con mensajes generados por IA usando DeepSeek.

---

## 📋 Índice

1. [Endpoints Disponibles](#endpoints-disponibles)
2. [Flujo de Compra de GiftCard](#flujo-de-compra-de-giftcard)
3. [Ejemplos de Uso](#ejemplos-de-uso)
4. [Tipos de Mensaje Disponibles](#tipos-de-mensaje-disponibles)
5. [Servicios Asociados](#servicios-asociados)
6. [Estados de GiftCard](#estados-de-giftcard)
7. [Testing](#testing)

---

## 🔌 Endpoints Disponibles

### 1. Generar Mensajes con IA

Genera múltiples mensajes personalizados usando DeepSeek AI.

**Endpoint:** `POST /api/giftcard/generar-mensajes/`

**Request Body:**
```json
{
  "tipo_mensaje": "romantico",
  "nombre": "María",
  "relacion": "esposa",
  "detalle": "Celebrando 10 años juntos",
  "cantidad": 3
}
```

**Parámetros:**
- `tipo_mensaje` (string, requerido): Tipo de mensaje ([ver tipos disponibles](#tipos-de-mensaje-disponibles))
- `nombre` (string, requerido): Nombre o apodo del destinatario
- `relacion` (string, requerido): Relación con el comprador (ej: "esposa", "amigo", "madre")
- `detalle` (string, opcional): Detalle especial para enriquecer el mensaje
- `cantidad` (integer, opcional): Cantidad de mensajes a generar (1-5, default: 3)

**Response Exitoso (200):**
```json
{
  "success": true,
  "mensajes": [
    "María, estos 10 años juntos han sido un viaje extraordinario...",
    "Para mi María, celebrando una década de amor y complicidad...",
    "María, amor mío, 10 años no son nada cuando se viven junto a ti..."
  ],
  "cantidad_generada": 3
}
```

**Response Error (400):**
```json
{
  "success": false,
  "error": "Campos requeridos: tipo_mensaje, nombre, relacion"
}
```

---

### 2. Regenerar Mensaje (Diferente)

Genera UN nuevo mensaje diferente a los anteriores.

**Endpoint:** `POST /api/giftcard/regenerar-mensaje/`

**Request Body:**
```json
{
  "tipo_mensaje": "cumpleanos",
  "nombre": "Camila",
  "relacion": "hermana",
  "detalle": "Cumple 30 años",
  "mensajes_previos": [
    "Mensaje 1 que no le gustó...",
    "Mensaje 2 que tampoco..."
  ]
}
```

**Parámetros:**
- `tipo_mensaje` (string, requerido): Tipo de mensaje
- `nombre` (string, requerido): Nombre del destinatario
- `relacion` (string, requerido): Relación con el comprador
- `detalle` (string, opcional): Detalle especial
- `mensajes_previos` (array, opcional): Mensajes a evitar/no repetir

**Response Exitoso (200):**
```json
{
  "success": true,
  "mensaje": "Camila, en tus 30 años brillas más que nunca. Que este regalo sea el inicio de una nueva etapa llena de relax y felicidad..."
}
```

---

### 3. Crear GiftCard

Crea una nueva GiftCard con mensaje personalizado.

**Endpoint:** `POST /api/giftcard/crear/`

**Request Body:**
```json
{
  "monto_inicial": 50000,
  "dias_validez": 180,
  "comprador_nombre": "Juan Pérez",
  "comprador_email": "juan@example.com",
  "comprador_telefono": "+56912345678",
  "destinatario_nombre": "María",
  "destinatario_email": "maria@example.com",
  "destinatario_telefono": "+56987654321",
  "destinatario_relacion": "esposa",
  "detalle_especial": "Celebrando 10 años juntos",
  "tipo_mensaje": "aniversario",
  "mensaje_personalizado": "María, amor mío, estos 10 años han sido extraordinarios...",
  "mensaje_alternativas": [
    "Mensaje alternativo 1...",
    "Mensaje alternativo 2...",
    "Mensaje alternativo 3..."
  ],
  "servicio_asociado": "tinas"
}
```

**Parámetros Requeridos:**
- `monto_inicial` (number): Monto de la giftcard en pesos chilenos
- `comprador_nombre` (string): Nombre completo del comprador
- `destinatario_nombre` (string): Nombre/apodo del destinatario
- `tipo_mensaje` (string): Tipo de mensaje seleccionado
- `mensaje_personalizado` (string): Mensaje final seleccionado por el comprador

**Parámetros Opcionales:**
- `dias_validez` (integer): Días de validez (default: 180)
- `comprador_email` (string): Email del comprador
- `comprador_telefono` (string): Teléfono del comprador
- `destinatario_email` (string): Email del destinatario
- `destinatario_telefono` (string): Teléfono del destinatario
- `destinatario_relacion` (string): Relación con el comprador
- `detalle_especial` (string): Detalle especial usado en generación IA
- `mensaje_alternativas` (array): Mensajes alternativos generados
- `servicio_asociado` (string): Servicio asociado ([ver servicios](#servicios-asociados))

**Response Exitoso (201):**
```json
{
  "success": true,
  "giftcard_id": 123,
  "codigo": "GIFT-A1B2C3D4",
  "monto_inicial": 50000,
  "fecha_vencimiento": "2025-05-15",
  "estado": "por_cobrar"
}
```

**Response Error (400):**
```json
{
  "success": false,
  "error": "Campos requeridos: monto_inicial, comprador_nombre, destinatario_nombre, tipo_mensaje, mensaje_personalizado"
}
```

---

### 4. Consultar GiftCard

Consulta el estado y detalles de una GiftCard por código.

**Endpoint:** `GET /api/giftcard/{codigo}/`

**Parámetros de URL:**
- `codigo` (string): Código de la giftcard (ej: "GIFT-A1B2C3D4")

**Response Exitoso (200):**
```json
{
  "success": true,
  "giftcard": {
    "codigo": "GIFT-A1B2C3D4",
    "monto_inicial": 50000,
    "monto_disponible": 50000,
    "estado": "activo",
    "fecha_emision": "2024-11-15",
    "fecha_vencimiento": "2025-05-15",
    "destinatario_nombre": "María",
    "mensaje_personalizado": "María, amor mío, estos 10 años han sido extraordinarios...",
    "servicio_asociado": "tinas",
    "dias_restantes": 181
  }
}
```

**Response Error (404):**
```json
{
  "success": false,
  "error": "GiftCard no encontrada"
}
```

---

## 🛒 Flujo de Compra de GiftCard

### Paso 1: Seleccionar Servicio/Experiencia
Cliente selecciona qué experiencia quiere regalar (tinas, masajes, etc.)

### Paso 2: Configurar Mensaje Personalizado
1. Cliente ingresa datos del destinatario (nombre, relación)
2. Cliente selecciona tipo de mensaje (romántico, cumpleaños, etc.)
3. Cliente opcionalmente agrega detalles especiales

### Paso 3: Generar Mensajes con IA
```bash
curl -X POST https://aremko.cl/api/giftcard/generar-mensajes/ \
  -H "Content-Type: application/json" \
  -d '{
    "tipo_mensaje": "romantico",
    "nombre": "María",
    "relacion": "esposa",
    "detalle": "Celebrando 10 años juntos",
    "cantidad": 3
  }'
```

### Paso 4: Seleccionar o Regenerar Mensaje
- Cliente revisa los 3 mensajes generados
- Si no le gusta ninguno, puede regenerar:

```bash
curl -X POST https://aremko.cl/api/giftcard/regenerar-mensaje/ \
  -H "Content-Type: application/json" \
  -d '{
    "tipo_mensaje": "romantico",
    "nombre": "María",
    "relacion": "esposa",
    "detalle": "Celebrando 10 años juntos",
    "mensajes_previos": ["Mensaje 1...", "Mensaje 2...", "Mensaje 3..."]
  }'
```

### Paso 5: Crear GiftCard
Una vez seleccionado el mensaje final:

```bash
curl -X POST https://aremko.cl/api/giftcard/crear/ \
  -H "Content-Type: application/json" \
  -d '{
    "monto_inicial": 50000,
    "comprador_nombre": "Juan Pérez",
    "comprador_email": "juan@example.com",
    "destinatario_nombre": "María",
    "tipo_mensaje": "romantico",
    "mensaje_personalizado": "Mensaje seleccionado...",
    "servicio_asociado": "tinas"
  }'
```

### Paso 6: Procesar Pago
- Integrar con Flow/Stripe para procesar pago
- Al confirmar pago, cambiar estado de `por_cobrar` → `cobrado` → `activo`

### Paso 7: Generar y Enviar PDF
- Generar PDF premium con mensaje personalizado
- Enviar por email al comprador y/o destinatario
- Opcionalmente enviar por WhatsApp

---

## 📝 Tipos de Mensaje Disponibles

| Tipo | Descripción | Tono |
|------|-------------|------|
| `romantico` | Mensaje romántico para parejas | Romántico, íntimo y apasionado |
| `cumpleanos` | Felicitación de cumpleaños | Celebrativo, alegre y festivo |
| `aniversario` | Celebración de aniversario | Nostálgico, especial y conmemorativo |
| `celebracion` | Celebración general | Festivo, emocionante y positivo |
| `relajacion` | Regalo de relax y bienestar | Tranquilo, sereno y revitalizante |
| `parejas` | Experiencia para parejas | Romántico, cómplice y especial |
| `agradecimiento` | Gesto de agradecimiento | Agradecido, cálido y sincero |
| `amistad` | Regalo entre amigos | Fraternal, cariñoso y genuino |

---

## 🌟 Servicios Asociados

| Código | Nombre | Descripción |
|--------|--------|-------------|
| `tinas` | Tinas Calientes | Experiencia de tinas calientes junto al río |
| `masajes` | Masajes | Sesión de masajes relajantes |
| `cabanas` | Alojamiento en Cabaña | Estadía en cabaña del spa |
| `ritual_rio` | Ritual del Río | Experiencia completa Ritual del Río |
| `celebracion` | Celebración Especial | Paquete de celebración personalizada |
| `monto_libre` | Monto Libre | El destinatario elige la experiencia |

---

## 🔄 Estados de GiftCard

| Estado | Descripción | Flujo |
|--------|-------------|-------|
| `por_cobrar` | Creada pero pago pendiente | Estado inicial |
| `cobrado` | Pago confirmado, pendiente activación | Tras confirmar pago |
| `activo` | Giftcard activa, lista para usar | Tras envío de PDF |
| `canjeado` | Monto completamente usado | Tras canje total |
| `expirado` | Venció sin ser canjeada | Tras fecha_vencimiento |

---

## 🧪 Testing

### Testing Local

1. **Configurar API Key:**
```python
# En aremko_project/settings.py
DEEPSEEK_API_KEY = 'sk-xxxxxxxxxxxxxxxxxxxxxxxx'
```

2. **Ejecutar Script de Tests:**
```bash
python test_giftcard_ai.py
```

Este script ejecuta 5 tests:
- ✅ Mensajes románticos (3 mensajes)
- ✅ Mensajes de cumpleaños (3 mensajes)
- ✅ Regenerar mensaje único
- ✅ Validación de tipo inválido
- ✅ Todos los tipos de mensaje (8 tipos)

### Testing de Endpoints (Postman/cURL)

**1. Generar Mensajes:**
```bash
curl -X POST http://localhost:8000/api/giftcard/generar-mensajes/ \
  -H "Content-Type: application/json" \
  -d '{
    "tipo_mensaje": "romantico",
    "nombre": "María",
    "relacion": "esposa",
    "cantidad": 3
  }'
```

**2. Regenerar Mensaje:**
```bash
curl -X POST http://localhost:8000/api/giftcard/regenerar-mensaje/ \
  -H "Content-Type: application/json" \
  -d '{
    "tipo_mensaje": "cumpleanos",
    "nombre": "Camila",
    "relacion": "hermana",
    "mensajes_previos": ["Mensaje 1...", "Mensaje 2..."]
  }'
```

**3. Crear GiftCard:**
```bash
curl -X POST http://localhost:8000/api/giftcard/crear/ \
  -H "Content-Type: application/json" \
  -d '{
    "monto_inicial": 30000,
    "comprador_nombre": "Juan Pérez",
    "destinatario_nombre": "María",
    "tipo_mensaje": "romantico",
    "mensaje_personalizado": "María, este regalo es para celebrar nuestro amor..."
  }'
```

**4. Consultar GiftCard:**
```bash
curl http://localhost:8000/api/giftcard/GIFT-A1B2C3D4/
```

---

## 🔐 Seguridad

- **CSRF Protection:** Endpoints marcados con `@csrf_exempt` para permitir llamadas desde frontend externo (WordPress)
- **Validación de Datos:** Todos los campos son validados antes de procesar
- **Rate Limiting:** Considerar implementar rate limiting en producción para evitar abuso de API de IA
- **API Key:** DEEPSEEK_API_KEY debe estar en variables de entorno, NO en código

---

## 📊 Monitoreo y Logs

Todos los endpoints generan logs:

```python
logger.info(f"Mensajes generados exitosamente para {nombre} (tipo: {tipo_mensaje})")
logger.warning(f"Error de validación en generar_mensajes_ai: {str(e)}")
logger.error(f"Error en generar_mensajes_ai: {str(e)}", exc_info=True)
```

Revisar logs en:
- Desarrollo: `./logs/django.log`
- Producción: Render logs o CloudWatch

---

## 🚀 Próximos Pasos

1. **Frontend Wizard** - Implementar interfaz de usuario en WordPress
2. **Generación PDF** - Crear PDFs premium con branding
3. **Integración de Pago** - Conectar con Flow.cl
4. **Envío Automático** - Email/WhatsApp con PDF adjunto
5. **Sistema de Canje** - Página pública para canjear giftcards

---

## 📞 Soporte

Para dudas o problemas con la API:
- **Desarrollador Backend:** Jorge Aguilera
- **Documentación DeepSeek:** https://platform.deepseek.com/api-docs/
- **Logs:** Revisar `/logs/django.log` o Render Dashboard

---

**Última actualización:** 2024-11-15
**Versión API:** 1.0.0
**Modelo IA:** DeepSeek Chat (via OpenAI API)
