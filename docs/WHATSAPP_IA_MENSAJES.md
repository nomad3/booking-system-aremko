# 📱 Sistema de Mensajes WhatsApp Personalizados con IA (GPT-4o)

## 🎯 Descripción

Sistema avanzado que genera mensajes de WhatsApp personalizados usando **OpenAI GPT-4o**, analizando el perfil 360° del cliente para crear comunicaciones contextualizadas y naturales.

---

## ✨ Características Principales

### 1. **Segmentación Inteligente de Clientes**
Identifica automáticamente 6 perfiles distintos basados en:
- Servicios históricos (2014-2024)
- Servicios actuales (2025+)
- Gasto total y frecuencia
- Días desde última visita
- Segmento RFM (Recency, Frequency, Monetary)

### 2. **Generación de Mensajes con IA**
- Usa **GPT-4o** (modelo más avanzado de OpenAI)
- Mensajes cálidos, naturales y profesionales
- Tono chileno amigable
- Contextualizados según historial del cliente

### 3. **Interfaz Intuitiva**
- Botón "Iniciar Conversación" en perfil 360°
- Modal con preview del mensaje
- Opciones: Copiar, Regenerar, Abrir WhatsApp
- Muestra perfil detectado del cliente

---

## 👥 Perfiles de Clientes

### 1. Cliente Completamente Nuevo 🆕
**Criterios:**
- No existe en base de datos
- Primera vez que contacta

**Ejemplo de Mensaje:**
```
¡Hola! 👋

¡Bienvenido/a a Aremko Spa! 🌿

Somos especialistas en tinas de hidromasaje, cabañas y masajes
terapéuticos.

¿En qué podemos ayudarte hoy?
```

---

### 2. Cliente con Primera Reserva 🌱
**Criterios:**
- 1-3 servicios en sistema actual
- Sin servicios históricos
- Cliente hace menos de 30 días

**Ejemplo de Mensaje:**
```
¡Hola María! 😊

Veo que tienes tu primera visita agendada para el 15 de nov.
¡Estamos emocionados de recibirte!

Tu reserva incluye:
• Tina Hornopiren
• Cabaña Laurel

💡 Tip: Llega 10 minutos antes para aprovechar al máximo.

¿Tienes alguna pregunta?
```

---

### 3. Cliente Recurrente Activo ⭐
**Criterios:**
- 2-10 servicios totales
- Solo en base de datos actual
- Última visita hace menos de 90 días

**Ejemplo de Mensaje:**
```
¡Hola Carlos! 😊

Qué gusto saber de ti. Veo que has venido 5 veces y te encantan
las tinas de hidromasaje 🌟

¿Vienes por tu favorita o quieres probar algo nuevo? Te puedo
recomendar la nueva Tina Premium.

¿En qué te puedo ayudar hoy?
```

---

### 4. Cliente Antiguo Reactivado 🔄
**Criterios:**
- Tiene servicios históricos (2014-2024)
- Regresó después de más de 1 año inactivo
- Primera reserva reciente en sistema actual

**Ejemplo de Mensaje:**
```
¡Ana! 🤗

¡Qué alegría verte de vuelta después de 3 años!

Veo que fuiste cliente entre 2018 y 2021. Tu última visita
disfrutaste de las cabañas.

Hemos renovado todo: nuevas tinas premium, cabañas remodeladas
y servicios ampliados.

¿Te gustaría conocer las novedades?

¡Bienvenida de vuelta a la familia Aremko! 💚
```

---

### 5. Cliente VIP / Champions 👑
**Criterios:**
- Más de 10 servicios
- Gasto total > $500,000
- Segmento RFM: Champions, VIP, Loyal Customers

**Ejemplo de Mensaje:**
```
¡Roberto! ✨

Es un placer saber de ti.

Como uno de nuestros clientes más especiales (15 visitas, cliente
desde 2019), queremos asegurarnos de brindarte la mejor experiencia.

Tu historial con nosotros:
💎 15 servicios
💰 Categorías favoritas: Tinas, Cabañas
📅 Última visita: hace 2 semanas

¿Necesitas una reserva prioritaria, algo especial o tienes alguna
solicitud VIP?

Estamos aquí para ti. 👑
```

---

### 6. Cliente En Riesgo ⚠️
**Criterios:**
- Fue cliente frecuente (> 5 servicios)
- Última visita hace más de 180 días
- Segmento RFM: At Risk, Hibernating

**Ejemplo de Mensaje:**
```
¡Hola Laura! 😊

¡Te extrañamos mucho en Aremko! 💙

Veo que tu última visita fue hace 8 meses, cuando disfrutaste
de la Tina Tronador.

Hemos agregado nuevas experiencias que creo te encantarían:
✨ Tina Premium con vista panorámica
✨ Masajes terapéuticos con aromaterapia

Además, tenemos una sorpresa especial para clientes como tú.

¿Te gustaría volver a visitarnos? 🌿
```

---

## 🛠️ Instalación y Configuración

### 1. Instalar OpenAI SDK
```bash
pip install openai
```

### 2. Configurar API Key

#### Opción A: Variable de Entorno (Recomendado)
```bash
# En Render.com Dashboard > Environment Variables
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

#### Opción B: En settings.py
```python
# settings.py
OPENAI_API_KEY = 'sk-proj-xxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
```

### 3. Verificar Instalación
```bash
python manage.py shell
>>> from ventas.services.whatsapp_message_service import WhatsAppMessageService
>>> resultado = WhatsAppMessageService.generar_mensaje_whatsapp(cliente_id=123)
>>> print(resultado)
```

---

## 📖 Uso

### Desde la Interfaz Web

1. **Navegar al Perfil 360° del Cliente**
   - CRM > Buscar Cliente > Seleccionar Cliente

2. **Generar Mensaje**
   - Click en botón **"🤖 Iniciar Conversación"** (verde oscuro)
   - El sistema analiza automáticamente el perfil del cliente

3. **Preview del Mensaje**
   - Modal muestra:
     - Perfil detectado
     - Mensaje generado
     - Info del cliente

4. **Acciones Disponibles**
   - **Copiar Mensaje**: Copia al portapapeles
   - **Regenerar**: Genera un mensaje nuevo con IA
   - **Abrir WhatsApp**: Abre WhatsApp con mensaje prellenado

### Desde Python/Shell

```python
from ventas.services.whatsapp_message_service import WhatsAppMessageService

# Generar mensaje para cliente existente
resultado = WhatsAppMessageService.generar_mensaje_whatsapp(cliente_id=123)

if resultado['success']:
    print(f"Perfil: {resultado['perfil_nombre']}")
    print(f"Mensaje: {resultado['mensaje']}")
    print(f"URL WhatsApp: {resultado['whatsapp_url']}")
else:
    print(f"Error: {resultado['error']}")

# Generar mensaje para cliente nuevo (no en BD)
resultado = WhatsAppMessageService.generar_mensaje_cliente_nuevo_sin_bd(
    telefono='+56912345678',
    nombre='Juan Pérez'
)
```

---

## 🎨 Personalización de Prompts

Los prompts de IA están definidos en:
```
ventas/services/whatsapp_message_service.py
Método: _generar_prompt_ia()
```

### Estructura del Prompt

```python
base_context = f"""
Eres un asistente para Aremko Spa...

INFORMACIÓN DEL CLIENTE:
- Nombre: {cliente['nombre']}
- Total servicios: {metricas['total_servicios']}
- Gasto total: ${metricas['gasto_total']:,.0f}
...

PERFIL IDENTIFICADO: {perfil_cliente}
"""

instrucciones_especificas = """
OBJETIVO: ...
TONO: ...
LONGITUD: ...
ESTRUCTURA SUGERIDA:
1. ...
2. ...
"""
```

### Modificar Tono o Estilo

Edita las instrucciones en el diccionario `instrucciones_por_perfil`:

```python
instrucciones_por_perfil = {
    cls.CLIENTE_NUEVO: """
OBJETIVO: Dar bienvenida cálida...
TONO: Acogedor, informativo  # ← Modificar aquí
LONGITUD: 3-4 líneas
    """,
    # ...
}
```

---

## 🔧 API Endpoints

### POST /ventas/crm/cliente/<id>/whatsapp-ia/
Genera mensaje WhatsApp con IA para un cliente.

**Request:**
```bash
POST /ventas/crm/cliente/123/whatsapp-ia/
Headers:
  X-CSRFToken: <token>
```

**Response (Success):**
```json
{
  "success": true,
  "mensaje": "¡Hola Roberto! ✨...",
  "perfil": "VIP",
  "perfil_nombre": "Cliente VIP / Champions 👑",
  "telefono": "+56912345678",
  "telefono_limpio": "56912345678",
  "whatsapp_url": "https://wa.me/56912345678?text=...",
  "nombre_cliente": "Roberto González"
}
```

**Response (Error):**
```json
{
  "success": false,
  "error": "OPENAI_API_KEY no configurada"
}
```

---

## 📊 Lógica de Segmentación

### Algoritmo de Detección de Perfil

```python
def determinar_perfil_cliente(datos_360):
    # 1. Cliente Nuevo (sin servicios)
    if total_servicios == 0:
        return CLIENTE_NUEVO

    # 2. Primera Reserva (servicios actuales <= 3, sin históricos, < 30 días)
    if servicios_actuales <= 3 and servicios_historicos == 0 and dias_cliente < 30:
        return PRIMERA_RESERVA

    # 3. VIP (segmento Champions/VIP o gasto > $500K)
    if segmento_rfm in ['Champions', 'VIP'] or gasto_total > 500000:
        return VIP

    # 4. En Riesgo (segmento At Risk/Hibernating y > 180 días sin venir)
    if segmento_rfm in ['At Risk', 'Hibernating'] and dias_desde_ultima > 180:
        return EN_RIESGO

    # 5. Reactivado (tiene históricos, servicios actuales <= 3)
    if servicios_historicos > 0 and servicios_actuales <= 3:
        return REACTIVADO

    # 6. Recurrente Activo (default)
    return RECURRENTE_ACTIVO
```

### Variables Utilizadas

| Variable | Fuente | Descripción |
|----------|--------|-------------|
| `total_servicios` | CRMService | Históricos + Actuales |
| `servicios_historicos` | ServiceHistory (2014-2024) | Servicios antiguos |
| `servicios_actuales` | VentaReserva (2025+) | Servicios nuevos |
| `gasto_total` | Suma de ambas fuentes | Total gastado |
| `dias_como_cliente` | Desde primer servicio | Antigüedad |
| `dias_desde_ultima` | Desde último servicio | Recencia |
| `segmento_rfm` | CRMService | Champions, VIP, At Risk, etc. |

---

## 🚨 Troubleshooting

### Error: "OpenAI no está instalado"
```bash
pip install openai
```

### Error: "OPENAI_API_KEY no configurada"
1. Ir a Render Dashboard
2. Environment Variables
3. Agregar: `OPENAI_API_KEY=sk-proj-...`
4. Redeploy

### Error: "Rate limit exceeded"
Estás excediendo el límite de tokens de OpenAI.

**Solución:**
- Esperar unos minutos
- Verificar plan de OpenAI (https://platform.openai.com/usage)
- Considerar upgrade a plan con más cuota

### Mensaje Generado es Muy Formal/Informal
Ajusta el parámetro `temperature` en el código:

```python
response = client.chat.completions.create(
    model="gpt-4o",
    temperature=0.7,  # ← Ajustar entre 0.5 (formal) y 0.9 (creativo)
    ...
)
```

### Mensaje Muy Largo/Corto
Modifica la instrucción `LONGITUD` en el prompt:

```python
LONGITUD: 3-4 líneas máximo  # ← Cambiar aquí
```

---

## 💰 Costos

### OpenAI GPT-4o Pricing (2025)

| Modelo | Input | Output |
|--------|-------|--------|
| GPT-4o | $2.50 / 1M tokens | $10.00 / 1M tokens |

### Estimación de Costos

**Por Mensaje:**
- Input: ~800 tokens (datos del cliente + prompt) = $0.002
- Output: ~150 tokens (mensaje generado) = $0.0015
- **Total por mensaje: ~$0.0035 USD**

**Por 1,000 Mensajes:**
- ~$3.50 USD

**Por 10,000 Mensajes/Mes:**
- ~$35 USD/mes

---

## 📁 Archivos del Sistema

```
ventas/
├── services/
│   ├── whatsapp_message_service.py  # Servicio principal con IA
│   └── crm_service.py               # Datos perfil 360°
├── views/
│   └── crm_views.py                 # Vistas y endpoints
├── templates/
│   └── ventas/crm/
│       ├── cliente_detalle.html     # Perfil 360° (botón agregado)
│       └── whatsapp_modal.html      # Modal preview mensaje
└── urls.py                          # Rutas del sistema
```

---

## 🎓 Mejores Prácticas

### 1. **Usar en Contexto Adecuado**
- ✅ Iniciar conversaciones nuevas
- ✅ Reactivar clientes inactivos
- ✅ Responder contactos nuevos
- ❌ NO usar para respuestas automatizadas en masa

### 2. **Personalizar Siempre**
- Revisar mensaje generado antes de enviar
- Ajustar si es necesario (botón Regenerar)
- Agregar detalles específicos manualmente si corresponde

### 3. **Monitorear Uso**
- Revisar costos en OpenAI Platform
- Configurar alertas de usage
- Considerar cache para clientes frecuentes (implementar si es necesario)

### 4. **Privacidad de Datos**
- OpenAI NO almacena datos enviados vía API (según política)
- Los prompts NO se usan para entrenar modelos
- Cumple con políticas de privacidad de Aremko

---

## 🔮 Mejoras Futuras

### Planeadas
- [ ] Cache de mensajes recientes (evitar regenerar para mismo cliente)
- [ ] A/B testing de prompts (medir conversión)
- [ ] Métricas de engagement (tracking de respuestas)
- [ ] Integración directa con WhatsApp Business API
- [ ] Personalización de emojis según preferencias del cliente

### Ideas
- Detección de sentimiento en mensajes recibidos
- Sugerencia automática de ofertas basadas en perfil
- Multi-idioma (inglés para turistas)

---

## 📞 Soporte

**Desarrollado por:** Equipo Aremko + Claude Code
**Fecha:** Noviembre 2025
**Versión:** 1.0.0

Para soporte técnico:
- Revisar logs: `ventas/services/whatsapp_message_service.py`
- Logger: `logger.info()`, `logger.error()`

---

## 📄 Licencia

Uso interno de Aremko Spa.
Basado en OpenAI GPT-4o (licencia OpenAI).

---

**🤖 Generado con Claude Code**
https://claude.com/claude-code

