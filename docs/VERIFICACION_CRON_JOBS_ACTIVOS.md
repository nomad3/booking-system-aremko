# ✅ Verificación de Cron Jobs Activos en cron-job.org

**Fecha**: 9 de noviembre, 2025
**Usuario**: Jorge
**Sistema**: cron-job.org (servicio externo)

---

## 📊 Estado de los Cron Jobs

Tienes configurados **4 cron jobs** en cron-job.org. Aquí está la verificación completa de cada uno:

---

## 1️⃣ Preparación de Servicios ✅ FUNCIONANDO

### Configuración:

**Endpoint**: `/control_gestion/cron/preparacion-servicios/`

**Frecuencia**: Cada 15 minutos (`*/15 * * * *`)

**Estado**: ✅ **ACTIVO Y FUNCIONANDO**

### Qué hace:

Genera tareas de preparación **1 hora antes** de cada servicio:
- Busca servicios que comiencen en 40-80 minutos
- Crea tarea con checklist de preparación:
  - Limpiar y sanitizar tina/sala
  - Llenar tina con agua caliente
  - Verificar temperatura (36-38°C)
  - Preparar toallas y amenidades
- Asigna a usuario del grupo **OPERACIONES** (Jorge)

### Evidencia de funcionamiento:

✅ **4 tareas creadas hoy**:
- Preparar servicio – Masaje Relajación (Reserva #3901) - 13:00
- Preparar servicio – Tina Hornopiren (Reserva #3900) - 12:00
- Preparar servicio – Tina Normal Niño (Reserva #3900) - 12:00
- Preparar servicio – Masaje Relajación (Reserva #3900) - 12:00

### Próximas tareas esperadas (hoy):

| Hora Servicio | Cuándo se Crea | Servicio | Reserva |
|---------------|----------------|----------|---------|
| 16:00 | ~15:00 | Cabaña Laurel | #3754 |
| 16:00 | ~15:00 | Cabaña Acantilado | #3905 |
| 17:00 | ~16:00 | Tina Tronador | #3754 |
| 18:00 | ~17:00 | Masaje x2 | #3902 |
| 19:15 | ~18:15 | Masaje x2 | #3903 |
| 19:30 | ~18:30 | Tina Tronador | #3905 |

### Verificación recomendada:

```bash
# Ver logs en Render
# Deberías ver cada 15 min:
✅ Cron preparacion_servicios ejecutado vía HTTP
```

---

## 2️⃣ Vaciado de Tinas

### Configuración esperada:

**Endpoint**: `/control_gestion/cron/vaciado-tinas/`

**Frecuencia recomendada**: Cada 30 minutos (`*/30 * * * *`)

**Estado**: 🔍 **Por verificar en cron-job.org**

### Qué hace:

Genera tareas para vaciar tinas **2 horas después** del servicio:
- Busca servicios de TINAS que terminaron hace poco
- Verifica si hay otro servicio inmediatamente después en la misma tina
- Si NO hay servicio siguiente → Crea tarea de vaciado
- Si SÍ hay servicio siguiente → NO crea tarea (tina sigue en uso)

### Lógica inteligente:

**Ejemplo 1 - Sí vaciar**:
- Tina Hornopiren: Servicio 12:00-14:00
- Próximo servicio en esa tina: 17:00
- Gap: 3 horas ✅
- **Acción**: Crear tarea "Vaciar Tina Hornopiren" a las 14:30

**Ejemplo 2 - NO vaciar**:
- Tina Tronador: Servicio 16:00-18:00
- Próximo servicio en esa tina: 18:30
- Gap: 30 minutos ⚠️
- **Acción**: NO vaciar (siguiente cliente usa la misma agua caliente)

### Parámetros del comando:

```bash
python manage.py gen_vaciado_tinas
# Opciones:
--duracion-tina=120      # Duración servicio tina (default: 120 min)
--ventana=150            # Ventana búsqueda servicios (default: 150 min)
--gap-minimo=30          # Gap mínimo para vaciar (default: 30 min)
--dry-run                # Simular sin crear
```

### Cómo verificar si está funcionando:

**En Admin**:
1. Ir a `/admin/control_gestion/task/`
2. Filtrar por: Área = Operación
3. Buscar tareas con título: "Vaciar tina ..."
4. Deberían aparecer ~30-60 min después de que termine cada servicio de tina

**En Logs de Render**:
```
✅ Cron vaciado_tinas ejecutado vía HTTP
💧 GENERACIÓN DE TAREAS DE VACIADO DE TINAS
📊 Servicios revisados: X
✅ Tareas creadas: X
```

### ⚠️ Si NO ves tareas de vaciado:

**Posibles causas**:
1. Cron job está deshabilitado en cron-job.org
2. No hay gap suficiente entre servicios (todas las tinas tienen servicios seguidos)
3. Los servicios no están marcados como categoría "Tinas"

**Verificar**:
```bash
# En Render Shell
python manage.py gen_vaciado_tinas --dry-run
# Debe mostrar si encuentra servicios candidatos
```

---

## 3️⃣ Apertura Diaria (Rutinas)

### Configuración esperada:

**Endpoint**: `/control_gestion/cron/daily-opening/`

**Frecuencia recomendada**: 1 vez al día - 7:00 AM (`0 7 * * *`)

**Estado**: 🔍 **Por verificar en cron-job.org**

### Qué hace:

Genera tareas rutinarias operativas del día:

**Días normales (Lunes, Miércoles, Jueves, Viernes, Sábado, Domingo)**:
- ✅ Apertura local (7:00 AM)
- ✅ Preparación general de instalaciones
- ✅ Verificación de equipos
- ✅ Limpieza inicial

**Martes (Día de mantención mayor)**:
- ✅ Tareas especiales de mantención profunda
- ✅ Limpieza exhaustiva
- ✅ Revisión técnica de equipos

### Plantillas usadas:

El comando busca tareas definidas en **TaskTemplate** con:
- `trigger_type = 'DAILY'`
- `is_active = True`

Si NO hay plantillas creadas, usa tareas por defecto hardcoded.

### Características:

- ✅ **No duplica**: Si ya existen tareas rutinarias del día, NO crea nuevas
- ✅ **Martes especial**: Genera tareas diferentes los martes
- ✅ **Asignación inteligente**: Asigna según grupo (OPERACIONES, RECEPCION, etc.)

### Cómo verificar si está funcionando:

**En Admin** (cada mañana):
1. Ir a `/admin/control_gestion/task/`
2. Filtrar por: Fecha creación = Hoy
3. Buscar tareas con source = "RUTINA"
4. Deberían aparecer tareas como:
   - "Apertura - Encender luces y sistemas"
   - "Preparación - Verificar temperatura tinas"
   - "Limpieza - Área de recepción"

**En Logs de Render** (cada día ~7:00 AM):
```
✅ Cron daily_opening ejecutado vía HTTP
🏢 GENERACIÓN DE TAREAS RUTINARIAS DIARIAS
📅 Fecha: lunes, 11 de noviembre 2025
✅ X tareas rutinarias creadas
```

### ⚠️ Si NO ves tareas rutinarias:

**Verificar**:
```bash
# En Render Shell
python manage.py gen_daily_opening --dry-run
# Debe mostrar qué tareas crearía
```

**Si muestra "Ya existen tareas rutinarias creadas hoy"**:
- Normal, el comando NO duplica
- Solo crea 1 vez por día

**Para forzar creación** (testing):
```bash
python manage.py gen_daily_opening --force
```

---

## 4️⃣ Reportes Diarios (IA)

### Configuración esperada:

**Endpoints**:
- Matutino: `/control_gestion/cron/daily-reports/?momento=matutino`
- Vespertino: `/control_gestion/cron/daily-reports/?momento=vespertino`

**Frecuencia recomendada**:
- Matutino: 9:00 AM (`0 9 * * *`)
- Vespertino: 6:00 PM (`0 18 * * *`)

**Estado**: 🔍 **Por verificar en cron-job.org**

### Qué hace:

Genera reportes automáticos del equipo con resumen IA:

**Reporte Matutino (9:00 AM)**:
- 📊 Resumen del día anterior
- 📈 Tareas completadas
- ⚠️ Tareas pendientes/bloqueadas
- 🎯 Enfoque del día

**Reporte Vespertino (6:00 PM)**:
- 📊 Resumen del día actual
- ✅ Logros completados
- ⏳ Pendientes para mañana
- 🎯 Retrospectiva del equipo

### Información incluida:

```
📊 ESTADÍSTICAS DEL DÍA
- Tareas completadas: X
- Tareas en curso: X
- Tareas bloqueadas: X
- Tareas pendientes: X

📍 POR ÁREA:
- Operación: X tareas
- Recepción: X tareas
- Comercial: X tareas
- Atención: X tareas

👥 POR PERSONA:
- Jorge: X tareas
- Edson: X tareas
- Admin: X tareas

🤖 RESUMEN IA:
[Texto generado por IA con insights y recomendaciones]
```

### IA Provider:

El sistema usa el provider configurado en `.env`:
- `LLM_PROVIDER=mock` → Usa IA simulada (sin costo, respuestas inteligentes)
- `LLM_PROVIDER=openai` → Usa GPT-4 real (requiere API key, tiene costo)

### Almacenamiento:

Los reportes se guardan en modelo `DailyReport`:
- Fecha
- Momento (matutino/vespertino)
- Estadísticas
- Resumen IA
- Timestamp

### Cómo verificar si está funcionando:

**En Admin**:
1. Ir a `/admin/control_gestion/dailyreport/`
2. Deberías ver 2 reportes por día:
   - [Fecha] - matutino (9:00)
   - [Fecha] - vespertino (18:00)

**En Logs de Render** (9:00 AM y 6:00 PM):
```
✅ Cron daily_reports (matutino) ejecutado vía HTTP
📊 REPORTE DIARIO - MATUTINO
📅 Fecha: domingo, 09 de noviembre 2025
📈 RECOLECTANDO ESTADÍSTICAS
🤖 GENERANDO RESUMEN CON IA
✅ Reporte guardado
```

**Ver reportes en vista web**:
- Ir a: `/control_gestion/reportes/`
- Deberías ver listado de reportes diarios

---

## 📋 Checklist de Verificación Completa

### En cron-job.org:

- [ ] **Preparación Servicios**: ✅ Enabled - Cada 15 min
- [ ] **Vaciado Tinas**: ❓ Verificar - Cada 30 min recomendado
- [ ] **Apertura Diaria**: ❓ Verificar - 7:00 AM diario
- [ ] **Reporte Matutino**: ❓ Verificar - 9:00 AM diario
- [ ] **Reporte Vespertino**: ❓ Verificar - 6:00 PM diario

### URLs Exactas (reemplaza TU-DOMINIO y TU_TOKEN):

```
1. Preparación Servicios (cada 15 min):
https://TU-DOMINIO.onrender.com/control_gestion/cron/preparacion-servicios/?token=TU_TOKEN

2. Vaciado Tinas (cada 30 min):
https://TU-DOMINIO.onrender.com/control_gestion/cron/vaciado-tinas/?token=TU_TOKEN

3. Apertura Diaria (7:00 AM):
https://TU-DOMINIO.onrender.com/control_gestion/cron/daily-opening/?token=TU_TOKEN

4. Reporte Matutino (9:00 AM):
https://TU-DOMINIO.onrender.com/control_gestion/cron/daily-reports/?momento=matutino&token=TU_TOKEN

5. Reporte Vespertino (6:00 PM):
https://TU-DOMINIO.onrender.com/control_gestion/cron/daily-reports/?momento=vespertino&token=TU_TOKEN
```

---

## 🧪 Probar Manualmente (Troubleshooting)

Si quieres verificar que los comandos funcionan:

### En Render Shell:

```bash
# 1. Preparación de servicios
python manage.py gen_preparacion_servicios
# Debe mostrar servicios en ventana y tareas creadas

# 2. Vaciado de tinas
python manage.py gen_vaciado_tinas --dry-run
# Debe mostrar servicios candidatos para vaciado

# 3. Apertura diaria
python manage.py gen_daily_opening --dry-run
# Debe mostrar tareas rutinarias que crearía

# 4. Reportes
python manage.py gen_daily_reports --momento=matutino
# Debe generar reporte y guardarlo en BD
```

### Desde cron-job.org:

1. Ir a tu cron job
2. Click **"Execute now"** o **"▶️ Run"**
3. Ver resultado:
   - ✅ Status 200 = Funcionando
   - ❌ Status 403 = Token inválido
   - ❌ Status 500 = Error en comando

---

## 📊 Resumen Ejecutivo

### ✅ Funcionando correctamente:

1. **Preparación de Servicios** - ✅ Activo y generando tareas

### 🔍 Por verificar:

2. **Vaciado de Tinas** - Verificar si está enabled en cron-job.org
3. **Apertura Diaria** - Verificar si está enabled
4. **Reportes IA** - Verificar si están enabled (2 cron jobs)

### 📝 Recomendación:

**Ir a cron-job.org y verificar**:
1. Que los 4 cron jobs adicionales estén **enabled** ✅
2. Que las URLs sean correctas
3. Que las frecuencias sean las recomendadas
4. Probar "Execute now" en cada uno para confirmar Status 200

---

## 🎯 Próximos Pasos

1. **Revisar cron-job.org** (5 min)
   - Verificar estado de los 4 cron jobs
   - Habilitar los que estén disabled
   - Verificar URLs y frecuencias

2. **Probar ejecución manual** (2 min)
   - "Execute now" en cada cron job
   - Verificar Status 200

3. **Verificar en Admin mañana** (1 min)
   - Tareas rutinarias creadas ~7:00 AM
   - Reporte matutino creado ~9:00 AM
   - Tareas de vaciado durante el día

4. **Verificar en Admin esta tarde** (1 min)
   - Tareas de vaciado de tinas
   - Reporte vespertino ~6:00 PM

---

**Tiempo total**: 10 minutos para verificación completa

**Resultado esperado**: 5 cron jobs activos automatizando todo el flujo operativo del spa

---

¿Quieres que te ayude a verificar alguno específico o a probar su funcionamiento?
