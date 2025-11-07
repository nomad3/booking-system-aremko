# 📋 Plan de Implementación: Módulo Control de Gestión Aremko

**Rama de Desarrollo**: `feature/control-gestion`  
**Fecha de Inicio**: Noviembre 2025  
**Sistema Base**: Booking System Aremko  
**Estrategia**: Módulo complementario SIN modificar modelos existentes

---

## 🎯 Objetivo

Implementar un sistema operativo de **Control de Gestión** que aplique la metodología:
- **Tareas Claras** → **Rendición de Cuentas** → **Priorización por Cola (WIP=1)**

Integrado con el sistema de reservas existente (`ventas.VentaReserva`, `ventas.ReservaServicio`, `ventas.Cliente`) mediante **signals**, con capa de IA para automatización.

---

## 📊 Análisis de Compatibilidad con Sistema Actual

### ✅ Componentes Existentes que se Integran

| Componente Actual | Uso en Control de Gestión | Método de Integración |
|------------------|---------------------------|----------------------|
| `ventas.VentaReserva` | Detectar check-in/checkout | **Signals** (pre_save/post_save) |
| `ventas.ReservaServicio` | Obtener servicios agendados | Lectura (ForeignKey relations) |
| `ventas.Cliente` | Identificar cliente y tramo | Lectura + TramoService |
| `TramoService` | Calcular segmento/tramo | Llamadas a servicio existente |
| `ventas.models.Cliente.telefono` | Identificador de cliente | Campo normalizado existente |
| Sistema de permisos | Usuarios y roles | `User` y `Groups` de Django |

### 🔒 Garantías de No-Invasión

✅ **NO se modifican modelos existentes** (Cliente, VentaReserva, ReservaServicio)  
✅ **NO se alteran migraciones existentes** de app `ventas`  
✅ **NO se modifican signals existentes** en `ventas/signals.py`  
✅ El módulo `control_gestion` es **completamente independiente**  
✅ Integración mediante **signals propios** y **lectura de modelos** existentes

---

## 🏗️ Arquitectura del Nuevo Módulo

```
control_gestion/                    # Nueva app Django (independiente)
├── models.py                       # Modelos NUEVOS (Task, ChecklistItem, TaskLog, etc.)
├── signals.py                      # Signals NUEVOS (engancha con ventas.VentaReserva)
├── admin.py                        # Admin personalizado para tareas
├── views.py                        # Vistas web + webhooks
├── urls.py                         # URLs del módulo
├── ai_client.py                    # Cliente LLM (OpenAI/Mock)
├── ai.py                           # Funciones IA de negocio
├── management/commands/            # Comandos cron
│   ├── gen_daily_opening.py        # Rutinas diarias
│   └── gen_daily_reports.py        # Reportes IA
└── tests/                          # Tests unitarios
```

### Modelos Nuevos (NO tocan ventas)

1. **Task**: Tarea operativa con swimlane, owner, estado, prioridad, cola
2. **ChecklistItem**: Ítems de checklist por tarea
3. **TaskLog**: Histórico de acciones sobre tareas
4. **CustomerSegment**: Definición de segmentos (complementa TramoService)
5. **DailyReport**: Reportes diarios generados por IA

---

## 📅 Plan de Implementación por Etapas

### ✅ Pre-requisitos (ANTES de empezar)

- [x] Documento de información del sistema actual creado (`docs/INFORMACION_SISTEMA_ACTUAL.md`)
- [x] Rama `feature/control-gestion` creada
- [ ] Backup completo de base de datos de producción
- [ ] Ambiente de desarrollo local configurado
- [ ] Variables de entorno de IA configuradas (opcional, puede ser mock)

---

## 🚀 ETAPA 1: MVP en Admin (Sprint 1 - 3 días)

**Objetivo**: Crear estructura básica del módulo con admin funcional y regla WIP=1

### 1.1 Crear App y Estructura Base (Día 1 - Mañana)

- [ ] Crear app: `python manage.py startapp control_gestion`
- [ ] Agregar a `INSTALLED_APPS` en `settings.py`
- [ ] Crear estructura de carpetas (`management/commands`, `tests`, `fixtures`)
- [ ] Configurar `urls.py` del módulo
- [ ] Incluir en `aremko_project/urls.py`: `path("control_gestion/", include("control_gestion.urls"))`

**Checkpoint**: ✅ App registrada y accesible

### 1.2 Modelos Básicos (Día 1 - Tarde)

**Archivo**: `control_gestion/models.py`

- [ ] Crear enums: `Swimlane`, `TaskState`, `Priority`, `TaskSource`, `LocationRef`
- [ ] Modelo `Task` con todos los campos según documento
- [ ] Modelo `ChecklistItem` (relación con Task)
- [ ] Modelo `TaskLog` (relación con Task)
- [ ] Modelo `CustomerSegment` (definición de segmentos)
- [ ] Modelo `DailyReport` (reportes diarios)

**Validaciones**:
- [ ] Revisar que NO hay ForeignKey a modelos de `ventas` (solo lectura en signals)
- [ ] `Task.reservation_id` es CharField (no ForeignKey)
- [ ] `Task.customer_phone_last9` es CharField (no ForeignKey)

**Checkpoint**: ✅ Modelos creados sin errores

### 1.3 Migraciones (Día 1 - Final)

```bash
python manage.py makemigrations control_gestion
python manage.py migrate control_gestion
```

- [ ] Verificar que migraciones se crean correctamente
- [ ] Verificar que NO se generan migraciones en app `ventas`
- [ ] Commit: `git commit -m "feat: Create control_gestion models"`

**Checkpoint**: ✅ Migraciones aplicadas, tablas creadas

---

### 1.4 Admin Básico (Día 2 - Mañana)

**Archivo**: `control_gestion/admin.py`

- [ ] Registrar `CustomerSegment` y `DailyReport` (simple)
- [ ] Crear `ChecklistInline` (TabularInline)
- [ ] Crear `TaskLogInline` (TabularInline, readonly)
- [ ] Registrar `TaskAdmin` con:
  - list_display, list_filter, search_fields
  - inlines (ChecklistInline, TaskLogInline)
  - readonly_fields (created_at, updated_at)

**Checkpoint**: ✅ Admin básico funcional

### 1.5 Acciones Admin (Día 2 - Tarde)

**Archivo**: `control_gestion/admin.py`

- [ ] Acción: `move_up` (mover arriba en cola)
- [ ] Acción: `move_down` (mover abajo en cola)
- [ ] Acción: `mark_in_progress` (cambiar a EN CURSO)
- [ ] Acción: `mark_done` (cambiar a HECHA)
- [ ] Acción: `ai_generate_checklist_action` (placeholder, sin IA aún)

**Checkpoint**: ✅ Acciones disponibles en admin

### 1.6 Signals de Reglas Internas (Día 2 - Final)

**Archivo**: `control_gestion/signals.py`

- [ ] Signal `enforce_rules` (pre_save Task):
  - Validar WIP=1 por owner
  - Si priority=ALTA → queue_position=1
- [ ] Signal `create_log` (post_save Task):
  - Crear TaskLog automático (CREATED/UPDATED)
- [ ] Registrar signals en `control_gestion/apps.py` (ready method)

**Checkpoint**: ✅ Regla WIP=1 funcionando

### 1.7 Testing WIP=1 (Día 3 - Mañana)

**Archivo**: `control_gestion/tests/test_control_gestion.py`

- [ ] Test: Crear tarea, marcar EN CURSO, intentar crear otra EN CURSO → debe fallar
- [ ] Test: Priority ALTA debe poner queue_position=1
- [ ] Ejecutar: `python manage.py test control_gestion`

**Checkpoint**: ✅ Tests pasando, WIP=1 validado

### 1.8 Fixtures y Datos Semilla (Día 3 - Tarde)

**Archivo**: `control_gestion/fixtures/control_gestion_seed.json`

- [ ] Crear 5 CustomerSegment de ejemplo (Tramo 1, 2, 5-8, VIP, ELITE)
- [ ] Cargar: `python manage.py loaddata control_gestion/fixtures/control_gestion_seed.json`

**Checkpoint**: ✅ Datos semilla cargados

---

### ✅ Entregables Etapa 1

- [x] App `control_gestion` creada y registrada
- [ ] Modelos Task, ChecklistItem, TaskLog, CustomerSegment, DailyReport
- [ ] Migraciones aplicadas
- [ ] Admin funcional con acciones
- [ ] Regla WIP=1 implementada y probada
- [ ] Tests básicos pasando
- [ ] Datos semilla cargados

**Criterios de Aceptación**:
1. En Admin, crear una tarea para un usuario
2. Marcarla "EN CURSO"
3. Intentar marcar otra tarea del mismo usuario "EN CURSO" → debe mostrar error
4. Crear tarea con prioridad ALTA → debe aparecer con queue_position=1

---

## 🤖 ETAPA 2: Capa de IA (Sprint 2 - 2 días)

**Objetivo**: Implementar funciones de IA para automatización de tareas

### 2.1 Cliente LLM (Día 4 - Mañana)

**Archivo**: `control_gestion/ai_client.py`

- [ ] Clase `LLMClient` con soporte OpenAI/Mock
- [ ] Leer `LLM_PROVIDER`, `OPENAI_API_KEY`, `LLM_MODEL` de env
- [ ] Método `complete(system, user)` → str
- [ ] Fallback a mock si no hay credenciales

**Variables de entorno** (agregar a `.env.example`):
```env
# Control de Gestión - IA (opcional)
LLM_PROVIDER=openai  # o "mock" para desarrollo sin costo
OPENAI_API_KEY=sk-...
LLM_MODEL=gpt-4o-mini
```

**Checkpoint**: ✅ Cliente LLM funcionando (mock o real)

### 2.2 Funciones IA de Negocio (Día 4 - Tarde)

**Archivo**: `control_gestion/ai.py`

- [ ] `message_to_task(msg)` → Dict (título, descripción, checklist, prioridad, etc.)
- [ ] `generate_checklist(ctx)` → List[str] (5-9 pasos)
- [ ] `summarize_day(stats)` → str (resumen diario)
- [ ] `classify_priority(txt)` → Dict (ALTA/NORMAL + razón)
- [ ] `qa_task_completion(task, evidence)` → Dict (status, motivo, siguiente_acción)

**Checkpoint**: ✅ Funciones IA implementadas

### 2.3 Integrar IA en Admin (Día 4 - Final)

**Archivo**: `control_gestion/admin.py`

- [ ] Actualizar `ai_generate_checklist_action` para usar `ai.generate_checklist()`
- [ ] Probarlo desde admin: seleccionar tarea → "Generar checklist IA"

**Checkpoint**: ✅ Acción de IA funcionando en admin

### 2.4 Signal QA al Cerrar (Día 5 - Mañana)

**Archivo**: `control_gestion/signals.py`

- [ ] Signal `qa_on_done` (post_save Task cuando state=DONE):
  - Llamar `ai.qa_task_completion()`
  - Crear TaskLog con resultado QA

**Checkpoint**: ✅ QA automático al cerrar tarea

### 2.5 Testing IA (Día 5 - Tarde)

- [ ] Test manual: crear tarea, agregar checklist IA, cerrar tarea
- [ ] Verificar que se crea TaskLog con QA_RESULT
- [ ] Probar con y sin OpenAI (mock vs real)

**Checkpoint**: ✅ IA funcionando end-to-end

---

### ✅ Entregables Etapa 2

- [ ] Cliente LLM implementado (OpenAI + Mock)
- [ ] 5 funciones IA de negocio
- [ ] Acción admin "Generar checklist IA"
- [ ] QA automático al cerrar tarea
- [ ] Tests manuales exitosos

**Criterios de Aceptación**:
1. Crear tarea en admin
2. Acción → "Generar checklist IA" → checklist se llena
3. Marcar tarea como HECHA → se crea log con QA

---

## 🔌 ETAPA 3: Integración con Reservas (Sprint 3 - 3 días)

**Objetivo**: Enganchar con `ventas.VentaReserva` para detectar check-in/checkout

### 3.1 Crear Usuarios y Grupos (Día 6 - Mañana)

**Desde Django Admin**:

- [ ] Crear grupos: `OPERACIONES`, `RECEPCION`, `VENTAS`, `ATENCION`, `MUCAMA`, `SUPERVISION`
- [ ] Crear usuarios de prueba:
  - `ops_user` (grupo OPERACIONES)
  - `recepcion_user` (grupo RECEPCION)
  - `ventas_user` (grupo VENTAS)
  - `atencion_user` (grupo ATENCION)

**Checkpoint**: ✅ Usuarios y grupos creados

### 3.2 Signals de Integración (Día 6 - Tarde)

**Archivo**: `control_gestion/signals.py`

**IMPORTANTE**: Estos signals NO modifican modelos de `ventas`, solo LEEN

- [ ] Signal `capture_old_estado` (pre_save):
  - Detectar modelo `ventas.VentaReserva`
  - Guardar `old.estado_reserva` en caché
  
- [ ] Signal `react_to_reserva_change` (post_save):
  - Detectar transición a `checkin`:
    - Crear Task para RECEPCION (check-in confirmado)
    - Crear Task(s) para OPERACION (preparar servicios)
  - Detectar transición a `checkout`:
    - Crear Task para ATENCION (NPS post-visita)
    - Crear Task(s) para VENTAS (premio D+3 con promise_due_at)

**Estructura del signal**:
```python
from ventas.models import VentaReserva, ReservaServicio

@receiver(post_save, sender=VentaReserva)
def react_to_reserva_change(sender, instance, created, **kwargs):
    # Leer estado anterior
    # Detectar transiciones
    # Crear Task según corresponda
```

**Checkpoint**: ✅ Signals de integración implementados

### 3.3 Testing de Integración (Día 7 - Mañana)

**Pruebas manuales en Admin de Django**:

1. **Test Check-in**:
   - [ ] Crear VentaReserva en estado 'pendiente'
   - [ ] Agregar ReservaServicio con fecha_agendamiento
   - [ ] Cambiar estado_reserva a 'checkin'
   - [ ] Verificar que se crearon tareas:
     - Recepción: "Check-in confirmado"
     - Operación: "Preparar servicio [nombre]"

2. **Test Check-out**:
   - [ ] Cambiar estado_reserva a 'checkout'
   - [ ] Verificar que se crearon tareas:
     - Atención: "NPS post-visita"
     - Ventas: "Verificar premio D+3" (con promise_due_at = fecha_agendamiento + 3 días)

**Checkpoint**: ✅ Integración funcionando

### 3.4 Integrar Tramo del Cliente (Día 7 - Tarde)

**Archivo**: `control_gestion/signals.py`

En `react_to_reserva_change`, al crear Task:

```python
try:
    from ventas.services.tramo_service import TramoService
    gasto_total = TramoService.calcular_gasto_cliente(instance.cliente)
    tramo_actual = TramoService.calcular_tramo(float(gasto_total))
    segment_tag = f"Tramo {tramo_actual}"
except Exception:
    segment_tag = ""

# Usar segment_tag al crear Task
Task.objects.create(
    # ... otros campos ...
    segment_tag=segment_tag
)
```

- [ ] Actualizar signal para incluir segment_tag
- [ ] Probar que el tramo se guarda correctamente

**Checkpoint**: ✅ Tramo integrado en tareas

### 3.5 Documentación de Integración (Día 8)

**Archivo**: `docs/INTEGRACION_CONTROL_GESTION_RESERVAS.md`

- [ ] Documentar cómo funciona la integración
- [ ] Diagrama de flujo: Reserva → Check-in → Tareas
- [ ] Ejemplos de tareas generadas
- [ ] Troubleshooting común

**Checkpoint**: ✅ Documentación completa

---

### ✅ Entregables Etapa 3

- [ ] Usuarios y grupos creados
- [ ] Signals de integración con VentaReserva
- [ ] Tareas automáticas al check-in/checkout
- [ ] Integración con TramoService
- [ ] Tests de integración exitosos
- [ ] Documentación de integración

**Criterios de Aceptación**:
1. Cambiar estado_reserva de una reserva a 'checkin'
2. Verificar que se crean tareas automáticas en Admin
3. Tareas deben tener segment_tag con tramo del cliente
4. Premio D+3 debe tener promise_due_at correcta

---

## 🌐 ETAPA 4: Vistas Web y Webhooks (Sprint 4 - 2 días)

**Objetivo**: Crear interfaces web para operadores y webhooks para integraciones

### 4.1 Templates Base (Día 9 - Mañana)

**Directorio**: `control_gestion/templates/control_gestion/`

- [ ] Crear `base_control.html` (hereda de admin/base_site.html)
- [ ] Crear `mi_dia.html` (vista mis tareas del día)
- [ ] Crear `equipo.html` (snapshot del equipo)

**Checkpoint**: ✅ Templates creados

### 4.2 Vistas (Día 9 - Tarde)

**Archivo**: `control_gestion/views.py`

- [ ] Vista `mi_dia(request)`:
  - Filtrar tareas del usuario logueado
  - Excluir DONE
  - Ordenar por swimlane, queue_position, promise_due_at
  - Limitar a 3 tareas top
  
- [ ] Vista `equipo_snapshot(request)`:
  - Tareas del día (updated_at__date=today)
  - Mostrar todas las áreas

**Checkpoint**: ✅ Vistas implementadas

### 4.3 Webhooks (Día 10 - Mañana)

**Archivo**: `control_gestion/views.py`

- [ ] `webhook_cliente_en_sitio`:
  - Recibir POST con pedido, ubicación, responsable
  - Crear Task con prioridad ALTA
  - Clasificar prioridad con IA
  
- [ ] `ai_ingest_message`:
  - Recibir mensaje de cliente
  - Convertir a tarea con IA
  - Retornar sugerencia JSON
  
- [ ] `ai_generate_checklist`:
  - Recibir contexto
  - Generar checklist con IA
  - Retornar lista JSON

**Checkpoint**: ✅ Webhooks implementados

### 4.4 URLs (Día 10 - Tarde)

**Archivo**: `control_gestion/urls.py`

```python
urlpatterns = [
    path("mi-dia/", views.mi_dia, name="mi_dia"),
    path("equipo/", views.equipo_snapshot, name="equipo"),
    path("webhooks/cliente_en_sitio/", views.webhook_cliente_en_sitio, name="webhook_cliente_en_sitio"),
    path("ai/ingest_message/", views.ai_ingest_message, name="ai_ingest_message"),
    path("ai/generate_checklist/", views.ai_generate_checklist, name="ai_generate_checklist"),
]
```

**Checkpoint**: ✅ URLs configuradas

### 4.5 Testing Webhooks (Día 10 - Final)

**Pruebas con curl**:

```bash
# Cliente en sitio
curl -X POST http://localhost:8000/control_gestion/webhooks/cliente_en_sitio/ \
  -H "Content-Type: application/json" \
  -d '{"pedido":"tabla y jugos","ubicacion":"TINA_4","responsable_username":"recepcion_user","reserva_id":"1234"}'

# Mensaje a tarea
curl -X POST http://localhost:8000/control_gestion/ai/ingest_message/ \
  -H "Content-Type: application/json" \
  -d '{"texto":"Hola, estamos en tina 4, falta café","contexto":{"ubicacion":"TINA_4"}}'

# Generar checklist
curl -X POST http://localhost:8000/control_gestion/ai/generate_checklist/ \
  -H "Content-Type: application/json" \
  -d '{"swimlane":"OPS","servicio":"TINA_HIDRO","ubicacion":"TINA_4"}'
```

- [ ] Probar cada webhook
- [ ] Verificar respuestas JSON
- [ ] Verificar tareas creadas en admin

**Checkpoint**: ✅ Webhooks funcionando

---

### ✅ Entregables Etapa 4

- [ ] Templates para vistas web
- [ ] Vista "Mi día" funcional
- [ ] Vista "Equipo" funcional
- [ ] 3 webhooks implementados y probados
- [ ] URLs configuradas

**Criterios de Aceptación**:
1. Acceder a `/control_gestion/mi-dia/` → ver mis tareas
2. Llamar webhook cliente_en_sitio → crear tarea ALTA en admin
3. Llamar ai_ingest_message → recibir sugerencia de tarea

---

## ⏰ ETAPA 5: Comandos y Rutinas (Sprint 5 - 2 días)

**Objetivo**: Automatizar generación de tareas rutinarias y reportes

### 5.1 Comando Rutinas Diarias (Día 11 - Mañana)

**Archivo**: `control_gestion/management/commands/gen_daily_opening.py`

- [ ] Leer día de la semana
- [ ] Si es martes → solo mensaje (sin rutinas)
- [ ] Si no es martes:
  - Crear tarea OPERACION: "Apertura AM"
  - Crear tarea OPERACION: "Monitoreo °C"
  - Crear tarea OPERACION: "Cierre PM"
  - Crear tarea RECEPCION: "Recepción lista 15:30"
  
- [ ] Asignar owners según grupos
- [ ] Ejecutar: `python manage.py gen_daily_opening`

**Checkpoint**: ✅ Comando de rutinas funcionando

### 5.2 Comando Reporte Diario (Día 11 - Tarde)

**Archivo**: `control_gestion/management/commands/gen_daily_reports.py`

- [ ] Recolectar estadísticas del día:
  - Tareas hechas
  - Tareas en curso
  - Tareas bloqueadas
  - Por área (swimlane)
  
- [ ] Llamar `ai.summarize_day(stats)`
- [ ] Crear DailyReport
- [ ] Mostrar resumen en consola
- [ ] Ejecutar: `python manage.py gen_daily_reports`

**Checkpoint**: ✅ Comando de reportes funcionando

### 5.3 Configurar Cron (Día 12 - Mañana)

**Archivo**: `docs/CRON_CONTROL_GESTION.md`

Documentar configuración cron:

```cron
# Rutinas diarias (09:00 AM)
0 9 * * * cd /path/to/proyecto && python manage.py gen_daily_opening

# Reporte matutino (09:00 AM)
5 9 * * * cd /path/to/proyecto && python manage.py gen_daily_reports

# Reporte vespertino (18:00 PM)
0 18 * * * cd /path/to/proyecto && python manage.py gen_daily_reports
```

- [ ] Documentar cron jobs
- [ ] Incluir instrucciones para Render/producción

**Checkpoint**: ✅ Cron documentado

### 5.4 Integración con n8n (Día 12 - Tarde)

**Archivo**: `docs/N8N_CONTROL_GESTION.md`

- [ ] Documentar workflow n8n para:
  - Leer DailyReport
  - Enviar por WhatsApp (Manychat/Twilio)
  - Enviar por Email
  
- [ ] Incluir JSON de workflow ejemplo

**Checkpoint**: ✅ Integración n8n documentada

---

### ✅ Entregables Etapa 5

- [ ] Comando gen_daily_opening
- [ ] Comando gen_daily_reports
- [ ] Documentación cron
- [ ] Documentación integración n8n
- [ ] Tests manuales de comandos

**Criterios de Aceptación**:
1. Ejecutar gen_daily_opening → crear 4 tareas rutinarias
2. Ejecutar gen_daily_reports → crear DailyReport con resumen IA
3. Cron configurado y probado en desarrollo

---

## 🎨 ETAPA 6: Polish y Permisos (Sprint 6 - 2 días)

**Objetivo**: Refinar UI, agregar permisos por rol, métricas

### 6.1 Mejorar Templates (Día 13 - Mañana)

- [ ] Agregar CSS/Bootstrap a templates
- [ ] Vista mi_dia: agregar botones de acción rápida
- [ ] Vista equipo: agregar filtros por área
- [ ] Agregar favicon/branding

**Checkpoint**: ✅ UI mejorada

### 6.2 Permisos por Grupo (Día 13 - Tarde)

**Archivo**: `control_gestion/admin.py`

- [ ] Personalizar `has_view_permission`
- [ ] Personalizar `has_change_permission`
- [ ] Solo owner puede cambiar estado de su tarea
- [ ] SUPERVISION puede ver todas
- [ ] ADMIN puede todo

**Checkpoint**: ✅ Permisos implementados

### 6.3 Vista Indicadores (Día 14 - Mañana)

**Archivo**: `control_gestion/views.py`

Nueva vista `indicadores(request)`:

- [ ] KPI por persona: tareas hechas/bloqueadas/promedio días
- [ ] KPI por área: eficiencia, bloqueos >24h
- [ ] Promesas cumplidas vs vencidas
- [ ] Gráficos (Chart.js o similar)

**Checkpoint**: ✅ Dashboard de indicadores

### 6.4 Exportación (Día 14 - Tarde)

**Archivo**: `control_gestion/admin.py`

- [ ] Acción admin: "Exportar a CSV"
- [ ] Acción admin: "Exportar a Excel"
- [ ] Incluir fechas, estados, owners

**Checkpoint**: ✅ Exportación funcionando

---

### ✅ Entregables Etapa 6

- [ ] UI pulida con CSS
- [ ] Permisos por grupo
- [ ] Dashboard de indicadores
- [ ] Exportación CSV/Excel
- [ ] Tests de permisos

**Criterios de Aceptación**:
1. Usuario OPERACIONES solo ve sus tareas
2. Usuario SUPERVISION ve todas las tareas
3. Dashboard muestra KPIs correctos
4. Exportar tareas a CSV funciona

---

## 🧪 ETAPA 7: Testing y Documentación Final (Sprint 7 - 2 días)

**Objetivo**: Pruebas completas, documentación, preparar para producción

### 7.1 Tests Completos (Día 15 - Mañana)

**Archivo**: `control_gestion/tests/`

- [ ] Tests de modelos (WIP=1, priority, queue)
- [ ] Tests de signals (integración con VentaReserva)
- [ ] Tests de vistas (mi_dia, equipo)
- [ ] Tests de webhooks
- [ ] Tests de comandos
- [ ] Tests de permisos

```bash
python manage.py test control_gestion --verbosity=2
```

**Checkpoint**: ✅ Coverage > 80%

### 7.2 Documentación Final (Día 15 - Tarde)

**Archivos**:

- [ ] `docs/CONTROL_GESTION_README.md` (guía completa)
- [ ] `docs/CONTROL_GESTION_OPERACIONES.md` (manual operador)
- [ ] `docs/CONTROL_GESTION_ADMIN.md` (manual administrador)
- [ ] `docs/CONTROL_GESTION_API.md` (API webhooks)
- [ ] Actualizar `README.md` principal

**Checkpoint**: ✅ Documentación completa

### 7.3 Preparar Producción (Día 16 - Mañana)

- [ ] Actualizar `requirements.txt` si agregaste deps
- [ ] Actualizar `.env.example` con vars de IA
- [ ] Verificar que fixtures están actualizados
- [ ] Crear script de migración para producción
- [ ] Documentar rollback plan

**Checkpoint**: ✅ Listo para deploy

### 7.4 Deploy a Staging (Día 16 - Tarde)

- [ ] Merge a rama `staging`
- [ ] Deploy en ambiente de pruebas
- [ ] Smoke tests en staging
- [ ] Validar con usuarios reales

**Checkpoint**: ✅ Staging funcionando

---

### ✅ Entregables Etapa 7

- [ ] Suite completa de tests (>80% coverage)
- [ ] Documentación completa (5 docs)
- [ ] Script de deploy
- [ ] Deploy a staging exitoso
- [ ] Validación de usuarios

**Criterios de Aceptación**:
1. Todos los tests pasando
2. Documentación revisada y aprobada
3. Staging funcionando sin errores
4. Usuarios de prueba validan funcionalidad

---

## 🚀 ETAPA 8: Deploy a Producción (Sprint 8 - 1 día)

**Objetivo**: Llevar módulo a producción de forma segura

### 8.1 Pre-Deploy Checklist (Día 17 - Mañana)

- [ ] Backup completo de BD de producción
- [ ] Verificar que no hay migraciones pendientes en `ventas`
- [ ] Confirmar que signals NO modifican datos existentes
- [ ] Revisar logs de staging últimos 3 días

**Checkpoint**: ✅ Pre-deploy OK

### 8.2 Deploy (Día 17 - Mediodía)

```bash
# En producción
git checkout main
git merge feature/control-gestion
python manage.py migrate control_gestion
python manage.py loaddata control_gestion/fixtures/control_gestion_seed.json
python manage.py collectstatic --noinput
# Restart server
```

- [ ] Ejecutar migraciones
- [ ] Cargar fixtures
- [ ] Collectstatic
- [ ] Restart

**Checkpoint**: ✅ Deploy exitoso

### 8.3 Post-Deploy Verification (Día 17 - Tarde)

- [ ] Verificar que admin carga sin errores
- [ ] Crear tarea de prueba
- [ ] Cambiar estado de reserva → verificar tareas automáticas
- [ ] Ejecutar comando gen_daily_opening
- [ ] Revisar logs por errores

**Checkpoint**: ✅ Producción funcionando

### 8.4 Monitoreo (Primera Semana)

- [ ] Revisar logs diarios
- [ ] Monitorear uso de API LLM (costos)
- [ ] Recolectar feedback de usuarios
- [ ] Ajustar según necesidad

**Checkpoint**: ✅ Sistema estable

---

### ✅ Entregables Etapa 8

- [ ] Módulo en producción
- [ ] Sin errores en logs
- [ ] Usuarios operando con nuevo módulo
- [ ] Monitoreo activo
- [ ] Plan de soporte

**Criterios de Aceptación**:
1. Admin de control de gestión accesible
2. Tareas automáticas al check-in/checkout funcionando
3. Comandos cron ejecutándose
4. Sin errores críticos en 48 horas

---

## 📊 Resumen de Entregables por Etapa

| Etapa | Días | Entregables Clave |
|-------|------|-------------------|
| 1. MVP Admin | 3 | Modelos, Admin, WIP=1, Tests |
| 2. IA | 2 | Cliente LLM, 5 funciones IA, QA automático |
| 3. Integración Reservas | 3 | Signals, Tareas automáticas, TramoService |
| 4. Vistas/Webhooks | 2 | Mi día, Equipo, 3 webhooks |
| 5. Comandos | 2 | Rutinas diarias, Reportes IA, Cron |
| 6. Polish | 2 | UI, Permisos, Indicadores, Exportación |
| 7. Testing/Docs | 2 | Tests, Documentación, Staging |
| 8. Producción | 1 | Deploy, Verificación, Monitoreo |
| **TOTAL** | **17 días** | **Módulo completo en producción** |

---

## 🔍 Checklist de Validación Global

### Antes de Merge a Main

- [ ] Todos los tests pasando (`python manage.py test control_gestion`)
- [ ] NO hay migraciones en app `ventas` (solo en `control_gestion`)
- [ ] Signals NO modifican modelos de `ventas`, solo leen
- [ ] Regla WIP=1 funcionando
- [ ] Tareas automáticas al check-in/checkout funcionando
- [ ] Comandos gen_daily_opening y gen_daily_reports funcionando
- [ ] Webhooks probados con curl
- [ ] IA funcionando (al menos en modo mock)
- [ ] Documentación completa
- [ ] Code review aprobado
- [ ] Staging validado por usuarios
- [ ] Backup de producción listo

### Después de Deploy a Producción

- [ ] Sin errores en logs (primeras 24h)
- [ ] Tareas automáticas creándose correctamente
- [ ] Comandos cron ejecutándose sin fallos
- [ ] Usuarios pueden acceder a admin de control_gestion
- [ ] Regla WIP=1 activa y respetada
- [ ] QA automático al cerrar tareas funcionando
- [ ] Webhooks respondiendo correctamente
- [ ] Monitoreo de costos IA (si aplica)

---

## 🛡️ Garantías de Seguridad

### ✅ NO se modificará:

1. Modelos de `ventas`:
   - `Cliente`
   - `VentaReserva`
   - `ReservaServicio`
   - `Servicio`
   - `Premio`, `ClientePremio`, `HistorialTramo`

2. Signals existentes en `ventas/signals.py`

3. Vistas existentes en `ventas/views/`

4. Migraciones existentes

### ✅ Integración SOLO por:

1. **Lectura**: Acceso read-only a modelos de `ventas`
2. **Signals propios**: `control_gestion/signals.py` escucha cambios en `VentaReserva`
3. **Servicios**: Llamadas a `TramoService` (read-only)

### ✅ Rollback Plan:

Si algo falla en producción:

```bash
# Deshabilitar signals
python manage.py shell
>>> from control_gestion import signals
>>> # Desconectar signals manualmente

# O simplemente remover de INSTALLED_APPS
# en settings.py:
INSTALLED_APPS.remove('control_gestion')

# Restart server
```

No se perderán datos de `ventas` porque el módulo NO los modifica.

---

## 📞 Soporte y Contacto

**Desarrollador Principal**: (Tu nombre)  
**Rama**: `feature/control-gestion`  
**Documentos Clave**:
- `docs/INFORMACION_SISTEMA_ACTUAL.md`
- `docs/PLAN_CONTROL_GESTION.md` (este documento)
- `docs/INTEGRACION_CONTROL_GESTION_RESERVAS.md` (crear en Etapa 3)

**Última actualización**: Noviembre 2025

---

## 🎯 Próximos Pasos Inmediatos

1. **Revisar este plan** con el equipo
2. **Confirmar usuarios y grupos** necesarios
3. **Definir variables de entorno** de IA (OpenAI vs Mock)
4. **Iniciar Etapa 1** (crear app y modelos)
5. **Commit frecuente** en rama `feature/control-gestion`

---

**¡Listo para empezar! 🚀**

