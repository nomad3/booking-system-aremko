# 📧 Flujo Completo de Campañas de Email Marketing

## 🎯 Objetivo
Enviar campañas de email personalizadas a clientes segmentados, con control total sobre el contenido y el proceso de envío.

---

## 📋 Flujo Actual (Funcional)

### **Paso 1: Segmentación de Clientes**
1. Ve a: `/ventas/reportes/segmentacion-clientes/`
2. Selecciona el tipo de segmentación:
   - **Por tramo de clientes** (basado en gasto histórico)
   - **Filtro personalizado** (gasto mínimo/máximo, comuna, etc.)
3. Haz clic en "Buscar" para ver los clientes que cumplen los criterios
4. **Selecciona los clientes** que quieres incluir en la campaña (checkboxes)
5. Haz clic en **"Iniciar Campaña"**

### **Paso 2: Crear la Campaña de Email**
**Actualmente**: Se hace manualmente con un comando de Django

```bash
python manage.py crear_campana_prueba --cliente-ids="1,2,3" --nombre-campana="Black Friday 2025"
```

Este comando:
- ✅ Crea una `EmailCampaign` con el nombre especificado
- ✅ Crea un `EmailRecipient` por cada cliente seleccionado
- ✅ Personaliza el contenido con el **primer nombre** del cliente
- ✅ Personaliza el contenido con el **gasto total** del cliente
- ✅ Deja la campaña en estado `draft` para revisión

### **Paso 3: Revisar la Campaña**
1. Ve a: `/admin/ventas/emailcampaign/`
2. Haz clic en la campaña recién creada
3. Revisa:
   - **Template de asunto**: `Hola {nombre_cliente}, tenemos una oferta especial para ti`
   - **Template de cuerpo HTML**: Email completo con diseño profesional
   - **Configuración de envío**: Horarios, lotes, intervalos

### **Paso 4: Revisar los Destinatarios**
1. Ve a: `/admin/ventas/emailrecipient/?campaign__id__exact=<ID>`
2. Haz clic en cada destinatario para ver:
   - **Asunto personalizado**: "Hola Simon, tenemos una oferta especial para ti"
   - **Cuerpo personalizado**: Email con su nombre y gasto total
   - **Estado**: `pending` (listo para enviar)

### **Paso 5: Hacer un Dry-Run (Simulación)**
```bash
python manage.py enviar_campana_email --campaign-id <ID> --dry-run --ignore-schedule
```

Esto muestra:
- ✅ Cuántos emails se enviarían
- ✅ A quién se enviarían
- ✅ El asunto de cada email
- ❌ **NO envía emails reales**

### **Paso 6: Cambiar el Estado a "ready"**
**Opción A: Desde el Admin**
1. Ve a `/admin/ventas/emailcampaign/<ID>/change/`
2. Cambia **Status** de "Borrador" a "Lista para envío"
3. Guarda

**Opción B: Desde el Shell**
```bash
python manage.py shell -c "from ventas.models import EmailCampaign; c = EmailCampaign.objects.get(id=<ID>); c.status = 'ready'; c.save(); print(f'✅ Estado: {c.get_status_display()}')"
```

### **Paso 7: Enviar los Emails Reales**
```bash
python manage.py enviar_campana_email --campaign-id <ID> --ignore-schedule
```

Esto:
- ✅ Envía los emails a través de **SendGrid**
- ✅ Marca los destinatarios como "enviados"
- ✅ Actualiza las estadísticas de la campaña
- ✅ Crea logs de entrega en `EmailDeliveryLog`

### **Paso 8: Monitorear el Envío**
**En el Admin de Django:**
- Ve a `/admin/ventas/emailcampaign/<ID>/change/` para ver estadísticas:
  - Total de destinatarios
  - Emails enviados
  - Emails entregados
  - Emails abiertos
  - Clicks

**En SendGrid Dashboard:**
- Ve a: https://app.sendgrid.com/email_activity
- Filtra por fecha y campaña
- Revisa:
  - Emails entregados
  - Rebotes (bounces)
  - Quejas de spam
  - Aperturas y clicks

---

## 🚀 Flujo Ideal (Propuesto para Mejora)

### **Mejoras Propuestas:**

#### **1. Vista de Selección de Campaña**
Después de seleccionar clientes en la segmentación:
- Mostrar un modal o página con:
  - **Opción A**: Crear nueva campaña
  - **Opción B**: Usar campaña existente (template)
  
#### **2. Editor de Campaña Visual**
- **Editor WYSIWYG** para el cuerpo del email
- **Vista previa en tiempo real** con datos de un cliente de ejemplo
- **Variables disponibles**: `{nombre_cliente}`, `{gasto_total}`, `{ultima_visita}`, etc.
- **Botón "Guardar como borrador"**

#### **3. Vista Previa de Destinatarios**
- Tabla con todos los destinatarios seleccionados
- **Vista previa individual**: Clic en un destinatario para ver su email personalizado
- **Edición individual**: Posibilidad de editar el email de un destinatario específico
- **Excluir destinatarios**: Checkbox para excluir sin eliminar

#### **4. Configuración de Envío**
- **Enviar ahora** vs **Programar envío**
- **Configuración de lotes**:
  - Emails por lote (default: 5)
  - Intervalo entre lotes (default: 6 minutos)
- **Horario de envío**:
  - Hora de inicio (default: 08:00)
  - Hora de fin (default: 21:00)

#### **5. Confirmación y Envío**
- **Resumen final**:
  - Número de destinatarios
  - Horario de envío
  - Vista previa de 3 emails aleatorios
- **Botón "Enviar Campaña"**
- **Barra de progreso en tiempo real**

---

## 🔧 Configuración Técnica

### **Variables de Entorno Necesarias:**
```bash
SENDGRID_API_KEY=<tu_api_key>
DEFAULT_FROM_EMAIL=comunicaciones@aremko.cl
```

### **Modelos Principales:**
- `EmailCampaign`: Campaña de email con templates y configuración
- `EmailRecipient`: Destinatario individual con contenido personalizado
- `EmailDeliveryLog`: Logs de entrega y eventos

### **Comandos Disponibles:**
```bash
# Crear campaña de prueba
python manage.py crear_campana_prueba --cliente-ids="1,2,3" --nombre-campana="Mi Campaña"

# Enviar campaña (dry-run)
python manage.py enviar_campana_email --campaign-id <ID> --dry-run

# Enviar campaña (real)
python manage.py enviar_campana_email --campaign-id <ID>

# Enviar todas las campañas listas (modo automático)
python manage.py enviar_campana_email --auto

# Probar SendGrid
python manage.py test_sendgrid --to=tu_email@gmail.com
```

---

## 📊 Estadísticas y Métricas

### **Métricas Disponibles:**
- **Tasa de entrega**: % de emails entregados vs enviados
- **Tasa de apertura**: % de emails abiertos vs entregados
- **Tasa de clicks**: % de emails con clicks vs entregados
- **Tasa de rebote**: % de emails rebotados vs enviados
- **Quejas de spam**: Número de quejas recibidas

### **Integración con SendGrid:**
- Tracking de aperturas (pixel tracking)
- Tracking de clicks (link tracking)
- Webhooks para eventos en tiempo real
- Dashboard de SendGrid para análisis detallado

---

## ⚠️ Mejores Prácticas

### **1. Segmentación:**
- No enviar a más de 100 clientes por campaña (límite de SendGrid gratuito)
- Segmentar por comportamiento, no solo por gasto
- Excluir clientes que se han desuscrito

### **2. Contenido:**
- Usar solo el **primer nombre** para personalización
- Incluir un **CTA claro** (Call To Action)
- Diseño responsive para móviles
- Texto alternativo para imágenes

### **3. Envío:**
- Respetar horarios (08:00 - 21:00)
- Enviar en lotes pequeños (5-10 emails por lote)
- Intervalo de 3-6 minutos entre lotes
- Evitar días festivos y fines de semana

### **4. Monitoreo:**
- Revisar tasa de rebote (debe ser < 5%)
- Revisar quejas de spam (debe ser < 0.1%)
- Pausar campaña si hay problemas
- Analizar métricas después de 24-48 horas

---

## 🎯 Próximos Pasos para Implementar Flujo Ideal

### **Fase 1: Backend (1-2 días)**
- [ ] Crear vista de selección de campaña
- [ ] Crear API para vista previa de email
- [ ] Crear endpoint para envío programado

### **Fase 2: Frontend (2-3 días)**
- [ ] Crear modal de selección de campaña
- [ ] Crear editor visual de email (TinyMCE o similar)
- [ ] Crear vista previa de destinatarios
- [ ] Crear configuración de envío

### **Fase 3: Testing (1 día)**
- [ ] Probar flujo completo con clientes de prueba
- [ ] Verificar personalización
- [ ] Verificar envío a través de SendGrid
- [ ] Verificar estadísticas

### **Fase 4: Documentación (1 día)**
- [ ] Crear guía de usuario
- [ ] Crear video tutorial
- [ ] Documentar casos de uso

---

## 📞 Soporte

Para cualquier duda o problema:
- **Email**: comunicaciones@aremko.cl
- **SendGrid Dashboard**: https://app.sendgrid.com
- **Documentación SendGrid**: https://docs.sendgrid.com

---

**Última actualización**: 2025-11-23
**Versión**: 1.0
