# 📋 Guía: Configurar Cron Job para Atención de Clientes

Esta guía te ayudará a configurar el cron job que genera automáticamente tareas de atención a clientes 20 minutos después del check-in.

---

## 📌 Requisitos Previos

1. ✅ Deploy completado en Render
2. ✅ Variable de entorno `CRON_TOKEN` configurada en Render
3. ✅ Cuenta en cron-job.org (gratuita)
4. ✅ TaskOwnerConfig creado en Django Admin

---

## 🔐 Paso 1: Obtener/Configurar CRON_TOKEN

### **¿Qué es CRON_TOKEN?**
Es un token secreto que protege tus endpoints de cron para que solo cron-job.org pueda ejecutarlos.

### **Verificar si ya existe**

1. Ve a **Render Dashboard**
2. Click en tu aplicación → **Environment**
3. Busca `CRON_TOKEN`

### **Si NO existe, créalo:**

1. Genera un token aleatorio (32+ caracteres):
   ```bash
   # En tu terminal local
   openssl rand -base64 32
   ```

   Ejemplo de resultado: `xK9mP2vQ8nR5tL7wY4zC1aB6dE3fG0hJ`

2. En **Render Dashboard** → Environment → **Add Environment Variable**:
   ```
   Key:   CRON_TOKEN
   Value: xK9mP2vQ8nR5tL7wY4zC1aB6dE3fG0hJ
   ```

3. Click **Save Changes** → Render hará redeploy automático

---

## 🤖 Paso 2: Configurar TaskOwnerConfig en Django Admin

Antes de que el cron job funcione, necesitas configurar quién será responsable de las tareas.

### **Ir a Django Admin**

```
https://tu-dominio.onrender.com/admin/
```

### **Crear configuración**

1. **Control Gestion** → **Task Owner Configs** → **Agregar Task Owner Config**

2. Completar formulario:

| Campo | Valor |
|-------|-------|
| **Tipo de Tarea** | Atención de Clientes en Servicio (20 min después check-in) |
| **Asignar a Usuario** | Deborah |
| **Asignar a Grupo** | VENTAS |
| **Usuario Fallback** | (opcional, dejar vacío) |
| **Activo** | ✓ Sí |
| **Notas** | Tarea para atender clientes 20 min después del check-in en tinas y cabañas |

3. Click **Guardar**

---

## 🌐 Paso 3: Configurar Cron Job en cron-job.org

### **1. Iniciar sesión en cron-job.org**

Ve a: https://cron-job.org/en/
- Login con tu cuenta existente

### **2. Crear nuevo cron job**

Click en **"Create cronjob"**

### **3. Configurar detalles del job**

#### **General Settings:**

| Campo | Valor |
|-------|-------|
| **Title** | Atención Clientes - Aremko |
| **URL** | `https://booking-system-aremko.onrender.com/cron/gen-atencion-clientes/?token=TU_TOKEN_AQUI` |
| **Request method** | GET |
| **Request timeout** | 30 seconds |

**⚠️ IMPORTANTE**: Reemplaza `TU_TOKEN_AQUI` con el valor real de tu `CRON_TOKEN`

**Ejemplo de URL completa:**
```
https://booking-system-aremko.onrender.com/cron/gen-atencion-clientes/?token=xK9mP2vQ8nR5tL7wY4zC1aB6dE3fG0hJ
```

#### **Schedule Settings:**

| Campo | Valor |
|-------|-------|
| **Schedule** | Every 15 minutes |
| **Cron expression** | `*/15 * * * *` |

**Esto significa:**
- Se ejecuta cada 15 minutos
- Todos los días
- Todo el año

#### **Advanced Settings (opcional):**

| Campo | Valor |
|-------|-------|
| **Enable notifications** | ✓ (para recibir alertas si falla) |
| **Notification email** | tu-email@ejemplo.com |
| **Failed executions threshold** | 3 (te notifica después de 3 fallos seguidos) |

### **4. Guardar**

Click en **"Create cronjob"**

---

## ✅ Paso 4: Testing

### **Probar manualmente (antes de esperar 15 min)**

1. En cron-job.org, en tu nuevo cron job, click en **"Run now"**

2. Espera 5-10 segundos

3. Click en **"Execution history"** o **"View logs"**

4. Deberías ver:
   ```json
   {
     "ok": true,
     "message": "Generación de tareas de atención a clientes ejecutada",
     "command": "gen_atencion_clientes",
     "output": "..."
   }
   ```

### **Verificar en Django Admin**

1. Ve a **Control Gestion** → **Tasks**

2. Busca tareas con título: `"Atención de clientes –"`

3. Si hay reservas con check-in hace 20 min, deberías ver nuevas tareas

---

## 🔍 Troubleshooting

### **❌ Error: "Token inválido"**

**Problema**: El token en la URL no coincide con `CRON_TOKEN` en Render

**Solución**:
1. Verifica que `CRON_TOKEN` está configurado en Render
2. Verifica que la URL en cron-job.org tiene el token correcto
3. NO debe haber espacios en el token

---

### **❌ Error 500**

**Problema**: Error en el servidor

**Solución**:
1. Ve a Render → Logs
2. Busca errores recientes
3. Verifica que el comando existe: `python manage.py gen_atencion_clientes --dry-run`

---

### **✅ OK pero no se crean tareas**

**Problema**: El comando ejecuta correctamente pero no genera tareas

**Posibles causas**:

1. **No hay reservas con check-in hace 20 min**
   - Es normal si no hay servicios activos
   - Espera a que haya check-ins reales

2. **TaskOwnerConfig no configurado**
   - Verifica en Django Admin que existe la configuración
   - Verifica que está **Activo**: ✓

3. **Solo servicios de masajes**
   - El comando solo crea tareas para TINAS y CABAÑAS
   - NO crea tareas para masajes

4. **Servicio "Descuento_Servicios"**
   - Este servicio virtual está excluido

---

## 📊 Monitoreo

### **Ver historial de ejecuciones**

En cron-job.org:
1. Click en tu cron job
2. Click en **"Execution history"**
3. Verás todas las ejecuciones con timestamps

### **Ver tareas generadas**

En Django Admin:
1. **Control Gestion** → **Tasks**
2. Filtrar por:
   - **State**: Por Ejecutar
   - **Source**: Sistema
   - **Swimlane**: Atención Cliente

---

## 📈 Ejemplo de Flujo Completo

```
14:00 - Cliente llega al spa
14:01 - Recepción hace check-in (estado_reserva = 'checkin')
14:01 - Cliente ingresa a Tina Hornopiren

14:15 - Cron ejecuta (1ra vez)
      → Servicio comenzó hace 15 min
      → Aún no es tiempo (necesita 20 min)
      → No crea tarea

14:30 - Cron ejecuta (2da vez)
      → Servicio comenzó hace 30 min
      → Ya pasaron los 20 min necesarios
      → ✅ CREA TAREA: "Atención de clientes – Tina Hornopiren"

14:32 - Deborah ve tarea en su backlog
14:35 - Deborah atiende al cliente
        • Pregunta si está cómodo
        • Ofrece bebidas
        • Verifica temperatura
14:40 - Deborah marca tarea como completada
```

---

## ⚙️ Configuración Final

Una vez configurado, tu cron job:

✅ Se ejecutará **cada 15 minutos** automáticamente
✅ Detectará reservas con check-in hace **20 minutos**
✅ Creará tareas solo para **TINAS y CABAÑAS**
✅ Asignará tareas a **Deborah** (o quien configures)
✅ Incluirá **checklist de atención** en cada tarea
✅ Enviará **notificaciones** si algo falla

---

## 📞 Soporte

Si tienes problemas:

1. Revisa esta guía completa
2. Verifica los logs en Render
3. Verifica historial en cron-job.org
4. Ejecuta manualmente: `python manage.py gen_atencion_clientes --dry-run`

---

**¡Listo!** Tu sistema de atención automática a clientes está configurado. 🎉
