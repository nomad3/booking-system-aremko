# 🚀 Campaña por CSV - Flujo Completo Mejorado

## ✅ Mejoras Implementadas

### 1. **Flujo Web Completo**
- ✅ Formulario web para subir CSV desde tu Mac
- ✅ Campos para asunto y contenido HTML personalizado
- ✅ Email de prueba automático antes del envío masivo
- ✅ Creación automática de clientes si no existen
- ✅ Progreso en tiempo real con estado detallado

### 2. **Envío por Lotes Mejorado**
- ✅ Comando `send_next_campaign_drip` ahora envía **5 emails por ejecución** (en lugar de 1)
- ✅ Usa el asunto y contenido del formulario web (almacenado en cada `CommunicationLog`)
- ✅ Personalización automática con `[Nombre]` → nombre real del contacto
- ✅ Manejo de errores y reintentos

### 3. **Interfaz Mejorada**
- ✅ Dashboard de progreso con métricas claras
- ✅ Estados visuales: Procesando → Cola preparada → Enviando
- ✅ Estimación de tiempo restante
- ✅ Botón de actualización en tiempo real

---

## 🎯 Cómo Usar el Sistema

### **Paso 1: Preparar CSV**
Tu CSV debe tener estas columnas (exactamente):
- `nombre` - Nombre del contacto
- `email` - Email (obligatorio)
- `celular` - Teléfono (opcional)
- `empresa` - Nombre de la empresa
- `rubro` - Sector/industria
- `ciudad` - Ciudad

### **Paso 2: Acceder al Formulario**
1. Ve a Admin → CRM → **"Campaña por CSV (beta)"**
2. Completa:
   - **Asunto**: Línea de asunto del email
   - **Cuerpo (HTML)**: Contenido del email (usa `[Nombre]` para personalizar)
   - **Archivo CSV**: Sube tu archivo
   - **Email de prueba**: Recibirás una muestra antes del envío masivo

### **Paso 3: Envío Automático**
1. Al subir, el sistema:
   - ✅ Envía email de prueba inmediatamente
   - ✅ Crea/actualiza contactos y clientes en la base
   - ✅ Genera cola de `PENDING` en `CommunicationLog`
   - ✅ **Inicia el primer lote automáticamente**

2. El cron continúa enviando **5 emails cada 10 minutos**
3. Puedes ver el progreso actualizando la página

---

## ⚙️ Configuración del Cron (Render)

**IMPORTANTE**: Actualiza tu cron job en Render con este comando:

```bash
python manage.py send_next_campaign_drip --use-stored-content --batch-size 5
```

### **Ventajas del Nuevo Comando:**
- `--use-stored-content`: Usa asunto/contenido del formulario web
- `--batch-size 5`: Envía 5 emails por ejecución (12x más rápido)
- Con 59 emails: ~12 minutos total (en lugar de ~10 horas)

---

## 📊 Ejemplo de Flujo

### **CSV de 59 contactos:**
```csv
nombre,email,celular,empresa,rubro,ciudad
Juan Pérez,juan@empresa.cl,+56912345678,Empresa ABC,Tecnología,Santiago
María García,maria@empresa2.cl,+56987654321,Empresa XYZ,Educación,Puerto Montt
...
```

### **Timeline de Envío:**
- **00:00** - Subes CSV → Email de prueba enviado
- **00:01** - Primer lote (5 emails) enviado automáticamente  
- **00:10** - Segundo lote (5 emails)
- **00:20** - Tercer lote (5 emails)
- **...continúa cada 10 min**
- **~02:00** - ✅ Campaña completada (59 emails enviados)

---

## 🛠️ Características Técnicas

### **Creación Automática de Registros:**
- `Company` → Creada/actualizada por nombre de empresa
- `Contact` → Creado/actualizado por email
- `Cliente` → Creado/actualizado para `CommunicationLog`
- `CommunicationLog` → Status `PENDING` → `SENT`

### **Personalización:**
- `[Nombre]` → Reemplazado por `first_name` del contacto
- Fallback: Si no hay nombre, usa "Hola"
- HTML/texto plano soportado automáticamente

### **Manejo de Errores:**
- Emails inválidos se marcan como `FAILED`
- Duplicados se detectan y evitan
- Errores SMTP se registran en logs

---

## 🎉 Resultado

**Antes:**
- ❌ Solo comando manual en shell de Render
- ❌ 1 email cada 10 min = 10 horas para 59 emails
- ❌ Sin interfaz web
- ❌ Sin progreso visible

**Ahora:**
- ✅ Formulario web completo desde tu Mac
- ✅ 5 emails cada 10 min = ~12 minutos para 59 emails  
- ✅ Email de prueba automático
- ✅ Dashboard de progreso en tiempo real
- ✅ Creación automática de clientes
- ✅ Personalización con nombres reales

**¡Tu campaña por CSV ahora funciona completamente desde la web!** 🚀