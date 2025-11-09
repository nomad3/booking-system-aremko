# ⏰ Configurar cron-job.org para Tareas Automáticas

**Fecha**: 9 de noviembre, 2025
**Servicio**: cron-job.org (cron externo via HTTP)
**Estado**: ✅ Endpoints listos - Solo falta configurar en cron-job.org

---

## 📊 Estado Actual

### ✅ Lo que YA está configurado:

- ✅ Endpoints HTTP para cron externo (`/control_gestion/cron/...`)
- ✅ Comando `gen_preparacion_servicios` funcionando
- ✅ Validación de token `CRON_TOKEN`
- ✅ Logging de ejecuciones

### ⚠️ Lo que FALTA configurar:

- ❌ Cron Job en cron-job.org para **preparación de servicios** (cada 15 minutos)
- ⚠️ Verificar que otros cron jobs estén activos

---

## 🎯 Solución: Configurar Cron Job de Preparación

### Endpoint a Configurar:

**URL**: `https://TU-DOMINIO.com/control_gestion/cron/preparacion-servicios/`

**Parámetros**:
- `token=TU_CRON_TOKEN` (si está configurado en Render)

**Método**: GET o POST

**Frecuencia**: **Cada 15 minutos** (*/15 * * * *)

---

## 🔧 Pasos para Configurar en cron-job.org

### 1. Acceder a cron-job.org

1. Ir a: https://cron-job.org
2. Login con tu cuenta
3. Click en **"Cronjobs"** en el menú

### 2. Crear Nuevo Cron Job

Click en **"Create cronjob"**

### 3. Configuración del Cron Job

#### **Title** (Nombre):
```
Preparación de Servicios - Aremko
```

#### **URL**:
```
https://TU-DOMINIO-RENDER.onrender.com/control_gestion/cron/preparacion-servicios/?token=TU_TOKEN
```

**Importante**: Reemplazar:
- `TU-DOMINIO-RENDER` por tu dominio real en Render
- `TU_TOKEN` por el valor de `CRON_TOKEN` configurado en Render

**Si NO tienes CRON_TOKEN configurado**, la URL es simplemente:
```
https://TU-DOMINIO-RENDER.onrender.com/control_gestion/cron/preparacion-servicios/
```

#### **Schedule** (Frecuencia):

**Opción recomendada - Cada 15 minutos**:
- Type: **Every 15 minutes**
- O usar expresión cron: `*/15 * * * *`

**Por qué cada 15 minutos**:
- Cubre todos los horarios posibles (14:00, 14:15, 14:30, 14:45, 15:00, etc.)
- Detecta servicios en ventana de 40-80 minutos antes
- No duplica tareas (el comando verifica si ya existe la tarea)

**Alternativas** (menos óptimas):
- Cada 30 minutos: `*/30 * * * *`
- Cada hora: `0 * * * *`

#### **Request Method**:
```
GET
```

#### **Request Timeout**:
```
30 seconds
```

#### **Enable**:
✅ Activado

#### **Notifications** (opcional):
- Email on failure: ✅ Activado
- Tu email para recibir notificaciones si falla

### 4. Guardar

Click en **"Create cronjob"** o **"Save"**

---

## 🧪 Probar la Configuración

### Test 1: Ejecutar Manualmente desde cron-job.org

1. En cron-job.org → Tu cron job
2. Click en **"Execute now"** o **"▶️ Run"**
3. Ver resultado:
   - ✅ Status 200 = Éxito
   - ❌ Status 403 = Token inválido
   - ❌ Status 500 = Error en servidor

### Test 2: Ver Logs en Render

1. Ir a Render Dashboard
2. Tu Web Service → **Logs**
3. Filtrar por: `Cron preparacion_servicios`
4. Deberías ver:
   ```
   ✅ Cron preparacion_servicios ejecutado vía HTTP
   ```

### Test 3: Verificar Tareas Creadas

Después de 15-20 minutos:

1. Ir a `/admin/control_gestion/task/`
2. Filtrar por:
   - **Área**: Operación
   - **Fecha creación**: Hoy
3. Deberías ver tareas como:
   ```
   Preparar servicio – Tina Hidromasaje (Reserva #1234)
   ```

---

## 📋 Otros Cron Jobs Recomendados

Además del de preparación, deberías configurar:

### 1. Vaciado de Tinas (cada 30 min)

**URL**:
```
https://TU-DOMINIO.onrender.com/control_gestion/cron/vaciado-tinas/?token=TU_TOKEN
```

**Schedule**: `*/30 * * * *` (cada 30 minutos)

**Qué hace**: Crea tareas para vaciar tinas 30 minutos después de que termine el servicio

---

### 2. Apertura Diaria (1 vez al día - 7:00 AM)

**URL**:
```
https://TU-DOMINIO.onrender.com/control_gestion/cron/daily-opening/?token=TU_TOKEN
```

**Schedule**: `0 7 * * *` (7:00 AM todos los días)

**Qué hace**: Crea tareas de apertura/preparación del local

---

### 3. Reporte Matutino (9:00 AM)

**URL**:
```
https://TU-DOMINIO.onrender.com/control_gestion/cron/daily-reports/?momento=matutino&token=TU_TOKEN
```

**Schedule**: `0 9 * * *` (9:00 AM)

**Qué hace**: Genera reporte diario con resumen IA

---

### 4. Reporte Vespertino (6:00 PM)

**URL**:
```
https://TU-DOMINIO.onrender.com/control_gestion/cron/daily-reports/?momento=vespertino&token=TU_TOKEN
```

**Schedule**: `0 18 * * *` (6:00 PM)

**Qué hace**: Genera reporte de cierre del día

---

## 🔒 Configurar CRON_TOKEN (Seguridad)

Para proteger tus endpoints de acceso no autorizado:

### 1. Generar Token Seguro

```bash
# En tu terminal local
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Ejemplo de output:
```
a8f4j2k9d3m5n7p1q6r8s2t4u9v3w7x1
```

### 2. Configurar en Render

1. Render Dashboard → Web Service
2. **Environment** → **Environment Variables**
3. Agregar nueva variable:
   - **Key**: `CRON_TOKEN`
   - **Value**: `a8f4j2k9d3m5n7p1q6r8s2t4u9v3w7x1` (tu token generado)
4. **Save Changes**
5. Esperar redeploy automático (1-2 minutos)

### 3. Actualizar URLs en cron-job.org

Agregar `?token=TU_TOKEN` a todas las URLs:

```
https://TU-DOMINIO.onrender.com/control_gestion/cron/preparacion-servicios/?token=a8f4j2k9d3m5n7p1q6r8s2t4u9v3w7x1
```

---

## 🔍 Verificar que Todo Funciona

### Checklist completo:

#### 1. Verificar Endpoint Funciona (sin cron)

```bash
# Desde tu terminal o navegador
curl "https://TU-DOMINIO.onrender.com/control_gestion/cron/preparacion-servicios/?token=TU_TOKEN"
```

Debería retornar:
```json
{
  "ok": true,
  "message": "Comando ejecutado exitosamente",
  "output": "🔔 GENERACIÓN DE TAREAS DE PREPARACIÓN..."
}
```

#### 2. Verificar Cron Job en cron-job.org

- Estado: ✅ Enabled
- Última ejecución: Hace menos de 15 minutos
- Último resultado: Success (200)

#### 3. Verificar Logs en Render

Render Dashboard → Logs:
```
[timestamp] ✅ Cron preparacion_servicios ejecutado vía HTTP
```

#### 4. Verificar Tareas en Admin

`/admin/control_gestion/task/` muestra tareas nuevas de preparación

#### 5. Ejecutar Diagnóstico

En Render Shell:
```bash
python manage.py diagnostico_tareas
```

Debería mostrar:
- ✅ Grupo OPERACIONES existe
- ✅ Hay usuarios asignados
- ✅ Tareas de preparación creadas hoy
- ✅ No se detectaron problemas

---

## 🚨 Troubleshooting

### Problema 1: Cron Job falla con 403 Forbidden

**Causa**: Token inválido o faltante

**Solución**:
1. Verificar que `CRON_TOKEN` esté configurado en Render
2. Verificar que la URL en cron-job.org incluya `?token=...`
3. Token debe coincidir exactamente (case-sensitive)

---

### Problema 2: Cron Job falla con 500 Internal Server Error

**Causa**: Error en el comando Django

**Solución**:
1. Ver logs en Render Dashboard
2. Ejecutar manualmente en Render Shell:
   ```bash
   python manage.py gen_preparacion_servicios
   ```
3. Ver error específico y corregir

**Errores comunes**:
- Grupo OPERACIONES no existe
- No hay reservas en BD
- Problema con hora_inicio de servicios

---

### Problema 3: Cron ejecuta pero no crea tareas

**Causa**: No hay servicios en ventana de tiempo

**Solución**:
1. Ejecutar diagnóstico:
   ```bash
   python manage.py diagnostico_tareas
   ```
2. Verificar sección "4️⃣ VENTANA DE TIEMPO"
3. Verificar que hay reservas con servicios en próximos 40-80 minutos

---

### Problema 4: Se crean tareas duplicadas

**Causa**: Múltiples cron jobs ejecutando el mismo comando

**Solución**:
1. Verificar en cron-job.org que solo haya 1 cron job para preparación
2. Verificar que no haya también Cron Job en Render
3. El comando tiene protección anti-duplicados, pero mejor tener 1 solo cron

---

## 📊 Resumen de URLs

| Cron Job | URL | Frecuencia | Qué hace |
|----------|-----|------------|----------|
| **Preparación Servicios** | `/cron/preparacion-servicios/` | **Cada 15 min** | Crea tareas 1h antes de servicios |
| Vaciado Tinas | `/cron/vaciado-tinas/` | Cada 30 min | Tareas para vaciar tinas después de uso |
| Apertura Diaria | `/cron/daily-opening/` | 7:00 AM | Rutinas de apertura del local |
| Reporte Matutino | `/cron/daily-reports/?momento=matutino` | 9:00 AM | Resumen IA del día |
| Reporte Vespertino | `/cron/daily-reports/?momento=vespertino` | 6:00 PM | Reporte de cierre |

---

## 📚 Documentos Relacionados

- `docs/SOLUCION_TAREAS_NO_SE_GENERAN.md` - Diagnóstico general
- `control_gestion/README.md` - Manual del módulo
- `control_gestion/management/commands/diagnostico_tareas.py` - Comando diagnóstico

---

## 🎯 Próximos Pasos

1. **Configurar cron en cron-job.org** (5 minutos)
   - Crear cron job de preparación
   - URL: `https://TU-DOMINIO.onrender.com/control_gestion/cron/preparacion-servicios/`
   - Frecuencia: Cada 15 minutos

2. **Probar ejecución manual** (1 minuto)
   - Click "Execute now" en cron-job.org
   - Verificar status 200

3. **Esperar 15-20 minutos** y verificar:
   - Logs en Render
   - Tareas en Admin
   - Ejecutar `diagnostico_tareas`

4. **Configurar otros cron jobs** (opcional - 10 minutos)
   - Vaciado de tinas
   - Apertura diaria
   - Reportes

---

**Tiempo total estimado**: 10-15 minutos

**Resultado esperado**: Tareas de preparación generándose automáticamente cada 15 minutos

---

## ✅ Checklist Final

- [ ] Cron job creado en cron-job.org
- [ ] URL configurada correctamente (con token si aplica)
- [ ] Frecuencia: Cada 15 minutos
- [ ] Probado manualmente - Status 200
- [ ] Logs en Render muestran ejecución
- [ ] Tareas aparecen en `/admin/control_gestion/task/`
- [ ] `diagnostico_tareas` no muestra errores

---

**¡Listo!** Una vez configurado, las tareas se generarán automáticamente para todos los servicios programados.
