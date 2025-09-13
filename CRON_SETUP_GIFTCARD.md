# 🕐 Configuración del Cron Job para Campaña Giftcard

## 📋 Configuración del Cron Job

### **Comando a ejecutar:**
```bash
python manage.py enviar_campana_giftcard --batch-size 2
```

### **Frecuencia:**
- **Cada 6 minutos** durante horario laboral (8:00 - 18:00 Chile)
- **2 emails por ejecución** para evitar spam

### **Configuración en Render:**

1. **Crear nuevo Cron Job:**
   - Ve a tu dashboard de Render
   - Clic en "New" → "Cron Job"
   - Nombre: `Campaña Giftcard - 6min`

2. **Configuración del servicio:**
   - **Command:** `python manage.py enviar_campana_giftcard --batch-size 2`
   - **Schedule:** `*/6 * * * *` (cada 6 minutos)
   - **Environment:** `Web` (mismo que tu app principal)

3. **Variables de entorno:**
   - Copia TODAS las variables de entorno de tu servicio web principal
   - Especialmente: `DATABASE_URL`, `EMAIL_HOST_*`, `VENTAS_FROM_EMAIL`

### **Horario de Funcionamiento:**
- **Lunes a Viernes:** 8:00 AM - 6:00 PM (Chile)
- **Sábados y Domingos:** 8:00 AM - 6:00 PM (Chile)
- **Fuera de horario:** No envía emails (respeta horario laboral)

### **Características del Envío:**

#### **📊 Control de Lotes:**
- **2 emails por ejecución** (configurable)
- **Prioridad:** Por fecha de creación y prioridad asignada
- **Filtro:** Solo emails de campaña giftcard

#### **📧 Información de Contacto:**
- **Teléfono:** +56 9 5790 2525
- **Dirección:** Río Pescado Km 4, Puerto Varas
- **Email:** ventas@aremko.cl

#### **🔄 Copias Automáticas:**
- **BCC:** aremkospa@gmail.com
- **BCC:** ventas@aremko.cl

### **📈 Monitoreo:**

#### **Logs del Cron:**
```bash
# Ver logs en tiempo real
render logs --service=campana-giftcard-6min --follow
```

#### **Estados de Email:**
- **PENDIENTE:** En cola para envío
- **ENVIADO:** Enviado exitosamente
- **FALLIDO:** Error en el envío

#### **Dashboard Web:**
- Accede a: `https://tu-dominio.com/admin/section/crm/giftcard-campaign/`
- Ve estadísticas en tiempo real
- Configura mes/año y monto de giftcard

### **🚀 Comandos de Prueba:**

#### **Probar envío inmediato:**
```bash
python manage.py enviar_campana_giftcard --batch-size 2 --ignore-schedule
```

#### **Ver emails pendientes:**
```bash
python manage.py shell
>>> from ventas.models import MailParaEnviar
>>> MailParaEnviar.objects.filter(estado='PENDIENTE', asunto__icontains='giftcard').count()
```

#### **Crear campaña de prueba:**
```bash
python manage.py segment_january_clients --year 2025 --month 1 --giftcard-amount 15000 --create-campaign
```

### **⚠️ Consideraciones Importantes:**

1. **Límite de Emails:**
   - 2 emails cada 6 minutos = máximo 20 emails por hora
   - Máximo 120 emails por día (6 horas laborales)

2. **Horario Chile:**
   - El sistema respeta automáticamente el horario de Chile
   - No envía emails fuera de 8:00-18:00

3. **Personalización:**
   - Cada email incluye el nombre del cliente
   - Monto de giftcard personalizable por campaña
   - Información de contacto actualizada

4. **Monitoreo:**
   - Revisa logs regularmente
   - Verifica que no haya emails fallidos
   - Ajusta batch-size si es necesario

### **🔧 Troubleshooting:**

#### **Si no se envían emails:**
1. Verificar que el cron esté activo en Render
2. Revisar logs del cron job
3. Verificar variables de entorno
4. Comprobar que hay emails pendientes

#### **Si hay errores de envío:**
1. Revisar configuración de email en settings
2. Verificar que los emails de destino sean válidos
3. Comprobar límites del proveedor de email

#### **Para pausar temporalmente:**
1. Desactivar el cron job en Render
2. O cambiar el schedule a `0 0 0 0 0` (nunca)