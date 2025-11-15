# 🚀 Guía de Configuración - GiftCards con IA en Producción

Pasos para activar el sistema de GiftCards personalizadas con IA en el servidor de producción.

---

## 📋 Pre-requisitos

- ✅ Código ya deployado en rama `dev`
- ✅ Cuenta activa de DeepSeek con API key
- ✅ Acceso a Render Shell o servidor de producción
- ✅ Biblioteca `openai>=1.0.0` instalada

---

## 🔧 Paso 1: Configurar API Key de DeepSeek

### Opción A: Variable de Entorno (RECOMENDADO)

**En Render Dashboard:**
1. Ir a tu servicio web en Render
2. Clic en "Environment" en el menú lateral
3. Agregar nueva variable de entorno:
   - **Key:** `DEEPSEEK_API_KEY`
   - **Value:** `sk-xxxxxxxxxxxxxxxxxxxxxxxx` (tu API key real)
4. Clic en "Save Changes"
5. El servicio se reiniciará automáticamente

**Verificar en Render Shell:**
```bash
echo $DEEPSEEK_API_KEY
# Debe mostrar: sk-xxxxxxxxxxxxxxxxxxxxxxxx
```

### Opción B: Hardcodear en settings.py (NO RECOMENDADO)

```python
# En aremko_project/settings.py
DEEPSEEK_API_KEY = 'sk-xxxxxxxxxxxxxxxxxxxxxxxx'
```

⚠️ **IMPORTANTE:** NO commitear la API key al repositorio.

---

## 📦 Paso 2: Instalar Dependencia OpenAI

Verificar que `openai` esté en `requirements.txt`:

```bash
# En Render Shell
cat requirements.txt | grep openai
```

Si NO está, agregarlo:

```bash
# Agregar a requirements.txt
echo "openai>=1.0.0" >> requirements.txt

# Reinstalar dependencias
pip install -r requirements.txt
```

---

## 🗄️ Paso 3: Ejecutar Migración de Base de Datos

Esta migración agrega 25 campos nuevos al modelo `GiftCard`.

```bash
# En Render Shell
python manage.py migrate ventas
```

**Salida esperada:**
```
Running migrations:
  Applying ventas.0060_giftcard_ai_personalization... OK
```

**Verificar que se aplicó:**
```bash
python manage.py showmigrations ventas
```

Debe mostrar:
```
ventas
 ...
 [X] 0059_add_tramos_validos
 [X] 0060_giftcard_ai_personalization  ← NUEVA
```

---

## 🧪 Paso 4: Testing del Servicio de IA

Ejecutar el script de prueba para verificar que DeepSeek funciona:

```bash
# En Render Shell
python test_giftcard_ai.py
```

**Salida esperada:**

```
████████████████████████████████████████████████████████████████████████████████
█                                                                              █
█                    TESTS DE GIFTCARD AI SERVICE                             █
█                                                                              █
████████████████████████████████████████████████████████████████████████████████

================================================================================
TEST 1: Generar 3 mensajes románticos
================================================================================

✅ Se generaron 3 mensajes exitosamente:

1. María, estos 10 años juntos han sido un viaje extraordinario...

2. Para mi María, celebrando una década de amor y complicidad...

3. María, amor mío, 10 años no son nada cuando se viven junto a ti...

...

████████████████████████████████████████████████████████████████████████████████
█                                                                              █
█                            RESUMEN DE TESTS                                  █
█                                                                              █
████████████████████████████████████████████████████████████████████████████████

✅ Mensajes románticos: EXITOSO
✅ Mensajes de cumpleaños: EXITOSO
✅ Regenerar mensaje único: EXITOSO
✅ Validación tipo inválido: EXITOSO
✅ Todos los tipos de mensaje: EXITOSO

================================================================================
TOTAL: 5/5 tests exitosos (100%)
================================================================================
```

Si todos los tests pasan ✅, el servicio de IA está funcionando correctamente.

---

## 🔌 Paso 5: Testing de Endpoints API

### Test 1: Generar Mensajes con IA

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

**Respuesta esperada:**
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

### Test 2: Crear GiftCard

```bash
curl -X POST https://aremko.cl/api/giftcard/crear/ \
  -H "Content-Type: application/json" \
  -d '{
    "monto_inicial": 30000,
    "comprador_nombre": "Juan Pérez",
    "comprador_email": "juan@test.com",
    "destinatario_nombre": "María",
    "tipo_mensaje": "romantico",
    "mensaje_personalizado": "María, este regalo es para celebrar nuestro amor..."
  }'
```

**Respuesta esperada:**
```json
{
  "success": true,
  "giftcard_id": 123,
  "codigo": "GIFT-A1B2C3D4",
  "monto_inicial": 30000.0,
  "fecha_vencimiento": "2025-05-15",
  "estado": "por_cobrar"
}
```

### Test 3: Consultar GiftCard

```bash
curl https://aremko.cl/api/giftcard/GIFT-A1B2C3D4/
```

**Respuesta esperada:**
```json
{
  "success": true,
  "giftcard": {
    "codigo": "GIFT-A1B2C3D4",
    "monto_inicial": 30000.0,
    "monto_disponible": 30000.0,
    "estado": "por_cobrar",
    "fecha_emision": "2024-11-15",
    "fecha_vencimiento": "2025-05-15",
    "destinatario_nombre": "María",
    "mensaje_personalizado": "María, este regalo es para celebrar nuestro amor...",
    "servicio_asociado": "",
    "dias_restantes": 181
  }
}
```

---

## ✅ Paso 6: Verificación Final

### Checklist de Validación

- [ ] Variable `DEEPSEEK_API_KEY` configurada en Render
- [ ] Biblioteca `openai>=1.0.0` instalada
- [ ] Migración `0060_giftcard_ai_personalization` aplicada
- [ ] Test script pasa 5/5 tests exitosamente
- [ ] Endpoint `generar-mensajes` retorna 3 mensajes
- [ ] Endpoint `crear` crea GiftCard correctamente
- [ ] Endpoint `consultar` retorna detalles de GiftCard
- [ ] Logs no muestran errores de IA

### Verificar Logs

```bash
# En Render Shell o Render Dashboard > Logs
tail -f logs/django.log

# Buscar logs de IA
grep "DeepSeek" logs/django.log
grep "Mensajes generados" logs/django.log
```

**Logs esperados:**
```
INFO Generando 3 mensajes de tipo 'romantico' para María usando DeepSeek
INFO Mensajes generados exitosamente: 3
```

---

## 🐛 Troubleshooting

### Error: "DEEPSEEK_API_KEY no configurada"

**Causa:** Variable de entorno no está configurada.

**Solución:**
```bash
# Verificar que existe
echo $DEEPSEEK_API_KEY

# Si no existe, agregarla en Render Dashboard > Environment
```

### Error: "No module named 'openai'"

**Causa:** Biblioteca `openai` no instalada.

**Solución:**
```bash
pip install openai>=1.0.0
```

### Error: "relation ventas_giftcard does not exist"

**Causa:** Migración no ejecutada.

**Solución:**
```bash
python manage.py migrate ventas
```

### Error: "Invalid API key"

**Causa:** API key de DeepSeek incorrecta o expirada.

**Solución:**
1. Verificar API key en https://platform.deepseek.com/api_keys
2. Regenerar API key si es necesario
3. Actualizar variable de entorno en Render

### Error: "Error al generar mensajes con IA"

**Posibles causas:**
- Rate limiting de DeepSeek (demasiadas solicitudes)
- Problema de conectividad con API de DeepSeek
- Prompt demasiado largo

**Solución:**
```bash
# Revisar logs detallados
tail -100 logs/django.log | grep ERROR

# Intentar manualmente
python test_giftcard_ai.py
```

---

## 📊 Monitoreo en Producción

### Revisar Uso de API de DeepSeek

1. Ir a https://platform.deepseek.com/usage
2. Verificar:
   - Requests por día
   - Tokens consumidos
   - Costos acumulados

### Establecer Alertas

**Crear alerta si:**
- Costo diario > $X USD
- Tasa de error > 5%
- Latencia > 5 segundos

---

## 🔒 Seguridad

### Best Practices

✅ **Usar variable de entorno** para API key
✅ **NO commitear** API keys al repositorio
✅ **Rotar API keys** periódicamente
✅ **Implementar rate limiting** en endpoints públicos
✅ **Monitorear costos** de API de DeepSeek

### Rate Limiting (Opcional)

Agregar en `giftcard_views.py`:

```python
from django_ratelimit.decorators import ratelimit

@ratelimit(key='ip', rate='10/m', method='POST')
@csrf_exempt
@require_http_methods(["POST"])
def generar_mensajes_ai(request):
    # ... código existente
```

---

## 📈 Métricas a Monitorear

1. **Cantidad de GiftCards creadas por día**
2. **Tasa de regeneración de mensajes** (usuarios insatisfechos)
3. **Tipos de mensaje más populares**
4. **Costos de API de DeepSeek**
5. **Latencia de generación de mensajes**
6. **Tasa de error de IA**

### Queries de Monitoreo

```python
# En Django Shell
from ventas.models import GiftCard
from django.utils import timezone
from datetime import timedelta

# GiftCards creadas hoy
hoy = timezone.now().date()
giftcards_hoy = GiftCard.objects.filter(fecha_emision=hoy).count()

# Por tipo de mensaje (últimos 30 días)
hace_30_dias = timezone.now().date() - timedelta(days=30)
from django.db.models import Count
tipos_populares = GiftCard.objects.filter(
    fecha_emision__gte=hace_30_dias
).values('tipo_mensaje').annotate(
    cantidad=Count('id')
).order_by('-cantidad')

print(tipos_populares)
```

---

## 🎯 Próximos Pasos Técnicos

1. **Frontend Wizard** - Implementar wizard de 6 pasos en WordPress
2. **Generación PDF** - Crear PDFs premium con branding de Aremko
3. **Integración Flow.cl** - Procesar pagos con Flow
4. **Email Automation** - Enviar PDFs por email automáticamente
5. **WhatsApp Integration** - Enviar giftcards por WhatsApp
6. **Página de Canje** - Interfaz pública para canjear códigos
7. **Dashboard Admin** - Vista de gestión de giftcards

---

## 📞 Soporte

**Si tienes problemas:**
1. Revisar logs en Render Dashboard
2. Ejecutar `python test_giftcard_ai.py`
3. Revisar documentación: `docs/GIFTCARD_AI_API.md`
4. Contactar al desarrollador: Jorge Aguilera

---

**Última actualización:** 2024-11-15
**Versión:** 1.0.0
**Modelo IA:** DeepSeek Chat
**Servidor:** Render
**Rama:** dev
