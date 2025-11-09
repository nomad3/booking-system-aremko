# 🎯 Control de Gestión - Aremko

Sistema operativo de gestión de tareas con IA, integrado con el sistema de reservas.

**Estado**: ✅ Etapas 1-5 implementadas (MVP funcional)  
**Rama**: `feature/control-gestion`  
**Versión**: 1.0.0-beta

---

## 📋 ¿Qué es Control de Gestión?

Módulo para ejecutar la metodología:
**Tareas Claras** → **Rendición de Cuentas** → **Priorización por Cola (WIP=1)**

### Características Principales

✅ **Regla WIP=1**: Solo una tarea en curso por persona (máximo enfoque)  
✅ **Priorización automática**: Cliente en sitio → top de cola  
✅ **IA integrada**: Checklist, QA, resúmenes, clasificación  
✅ **Integración con reservas**: Tareas automáticas al check-in/checkout  
✅ **Rutinas automatizadas**: Apertura, monitoreo, cierre  
✅ **Reportes diarios**: Resumen IA 2x día  

---

## 🏗️ Arquitectura

```
control_gestion/
├── models.py              # Task, ChecklistItem, TaskLog, etc.
├── admin.py               # Admin completo con 6 acciones
├── signals.py             # WIP=1 + integración con VentaReserva
├── views.py               # Vistas web + 3 webhooks
├── urls.py                # Rutas configuradas
├── ai_client.py           # Cliente LLM (OpenAI/Mock)
├── ai.py                  # 5 funciones IA de negocio
├── management/commands/
│   ├── gen_daily_opening.py    # Rutinas diarias
│   └── gen_daily_reports.py    # Reportes IA
├── migrations/
│   └── 0001_initial.py    # Migración inicial
├── fixtures/
│   └── control_gestion_seed.json  # Datos semilla
└── tests/
    └── test_control_gestion.py    # 10 tests
```

---

## 🚀 Instalación Rápida

### 1. La app ya está configurada en:
- `settings.py`: `INSTALLED_APPS` ✅
- `urls.py`: `path('control_gestion/', ...)` ✅

### 2. Aplicar migraciones:

```bash
python manage.py migrate control_gestion
```

### 3. Cargar datos semilla:

```bash
python manage.py loaddata control_gestion/fixtures/control_gestion_seed.json
```

### 4. Crear grupos y usuarios:

Ver `docs/CREAR_USUARIOS_GRUPOS.md` para instrucciones detalladas.

Resumen rápido:
```python
python manage.py shell

from django.contrib.auth.models import Group

for nombre in ['OPERACIONES', 'RECEPCION', 'VENTAS', 'ATENCION']:
    Group.objects.get_or_create(name=nombre)
    print(f"✅ {nombre}")
```

### 5. Configurar IA (opcional):

En `.env`:
```env
LLM_PROVIDER=mock  # o "openai" para IA real
LLM_MODEL=gpt-4o-mini
OPENAI_API_KEY=sk-...  # solo si provider=openai
```

---

## 📖 Uso

### Admin de Django

1. Acceder: `http://localhost:8000/admin/control_gestion/task/`

2. **Crear tarea**:
   - Título, descripción, swimlane, responsable
   - Agregar checklist items
   - Asignar prioridad

3. **Acciones disponibles**:
   - Mover arriba/abajo en cola
   - Marcar EN CURSO (valida WIP=1)
   - Marcar HECHA (gatilla QA automático)
   - Generar checklist IA

### Vistas Web

**Mi Día**: `http://localhost:8000/control_gestion/mi-dia/`
- Tus top 3 tareas del día
- Enfoque en lo importante

**Equipo**: `http://localhost:8000/control_gestion/equipo/`
- Snapshot de todo el equipo
- Estadísticas del día

### Integración Automática

Cuando el recepcionista cambia `estado_reserva`:

**Check-in** (`pendiente` → `checkin`):
- ✅ Tarea RECEPCION: Bienvenida
- ⚠️ Tarea(s) OPERACION: Se crean automáticamente 1 hora antes vía `gen_preparacion_servicios`

**Checkout** (`checkin` → `checkout`):
- ✅ Tarea RECEPCION: Checkout completado
- ✅ Tarea ATENCION: NPS post-visita
- ✅ Tarea(s) COMERCIAL: Premio D+3 (programada)

### Comandos Automáticos

```bash
# Rutinas diarias (excepto martes)
python manage.py gen_daily_opening

# Preparación de servicios (cada 15 minutos) ⭐ IMPORTANTE
python manage.py gen_preparacion_servicios

# Reporte diario con IA
python manage.py gen_daily_reports --momento=matutino   # 09:00
python manage.py gen_daily_reports --momento=vespertino  # 18:00

# Vaciado de tinas
python manage.py gen_vaciado_tinas
```

### Webhooks

**Cliente en sitio** (prioridad ALTA):
```bash
curl -X POST http://localhost:8000/control_gestion/webhooks/cliente_en_sitio/ \
  -H "Content-Type: application/json" \
  -d '{
    "pedido": "tabla de quesos y jugos",
    "ubicacion": "TINA_4",
    "responsable_username": "recepcion_user",
    "reserva_id": "3851"
  }'
```

**Mensaje → Tarea (IA)**:
```bash
curl -X POST http://localhost:8000/control_gestion/ai/ingest_message/ \
  -H "Content-Type: application/json" \
  -d '{
    "texto": "Estamos en tina 4, falta café",
    "contexto": {"ubicacion": "TINA_4"}
  }'
```

**Generar checklist (IA)**:
```bash
curl -X POST http://localhost:8000/control_gestion/ai/generate_checklist/ \
  -H "Content-Type: application/json" \
  -d '{
    "swimlane": "OPS",
    "servicio": "TINA_HIDRO",
    "ubicacion": "TINA_4"
  }'
```

---

## 🧪 Testing

```bash
# Ejecutar tests
python manage.py test control_gestion

# Tests incluidos: 10 tests
# - WIP=1 (3 tests)
# - Prioridad (1 test)
# - Logs automáticos (2 tests)
# - QA (2 tests)
# - Checklist (2 tests)
```

---

## 📊 Modelos

### Task (Tarea)
- **Organización**: swimlane, owner, queue_position
- **Estado**: BACKLOG, IN_PROGRESS, BLOCKED, DONE
- **Prioridad**: NORMAL, ALTA (cliente en sitio)
- **Contexto**: reservation_id, customer_phone_last9, segment_tag
- **Ubicación**: location_ref, service_type

### ChecklistItem
- Relación con Task
- Campos: text, done

### TaskLog
- Histórico de acciones
- Campos: when, actor, action, note

### CustomerSegment
- Definición de segmentos
- Campos: name, min_spend, max_spend, benefit

### DailyReport
- Reportes diarios IA
- Campos: date, generated_at, summary

---

## 🔐 Permisos

Grupos necesarios:
- **OPERACIONES**: Tareas operativas (tinas, salas, mantención)
- **RECEPCION**: Check-in, atención inicial
- **VENTAS**: Premios, seguimiento comercial
- **ATENCION**: NPS, encuestas, feedback

Ver `docs/CREAR_USUARIOS_GRUPOS.md` para configurar.

---

## 🤖 IA - Funciones Disponibles

1. **message_to_task()**: Mensaje → tarea estructurada
2. **generate_checklist()**: Checklist 5-9 pasos contextual
3. **summarize_day()**: Resumen diario motivante
4. **classify_priority()**: ALTA/NORMAL automático
5. **qa_task_completion()**: QA inteligente al cerrar

**Modo Mock**: Funciona sin OpenAI (respuestas inteligentes simuladas)  
**Modo OpenAI**: Requiere API key y tiene costo

---

## 📖 Documentación

- `docs/PLAN_CONTROL_GESTION.md`: Plan completo de implementación
- `docs/INFORMACION_SISTEMA_ACTUAL.md`: Info del sistema de reservas
- `docs/INTEGRACION_CONTROL_GESTION_RESERVAS.md`: Cómo funciona la integración
- `docs/CREAR_USUARIOS_GRUPOS.md`: Setup de usuarios y grupos
- `docs/ETAPA1_COMPLETADA.md`: Resumen Etapa 1

---

## 🎯 Estado de Implementación

| Etapa | Estado | Días | Descripción |
|-------|--------|------|-------------|
| 1. MVP Admin | ✅ | 3 | Modelos, admin, WIP=1 |
| 2. IA | ✅ | 2 | Cliente LLM + 5 funciones |
| 3. Integración | ✅ | 3 | Signals con VentaReserva |
| 4. Vistas/Webhooks | ✅ | 2 | Mi día, equipo, 3 webhooks + 4 endpoints cron |
| 5. Comandos | ✅ | 2 | Rutinas + reportes IA + preparación servicios |
| 6. Polish | ⏳ | 2 | UI, permisos, KPIs |
| 7. Testing/Docs | ⏳ | 2 | Tests adicionales, documentación final |
| 8. Producción | ⏳ | 1 | Deploy, monitoreo |

**Progreso**: 71% (12/17 días)

---

## 🚀 Deploy a Producción

### Pre-requisitos:
- [ ] Backup de BD
- [ ] Grupos creados
- [ ] Usuarios asignados
- [ ] Variables env configuradas

### Steps:

```bash
# 1. Merge a main
git checkout main
git merge feature/control-gestion

# 2. Migraciones
python manage.py migrate control_gestion

# 3. Datos semilla
python manage.py loaddata control_gestion/fixtures/control_gestion_seed.json

# 4. Tests
python manage.py test control_gestion

# 5. Restart server
```

### Post-deploy:
- [ ] Verificar admin accesible
- [ ] Crear tarea de prueba
- [ ] Test check-in → verificar tareas automáticas
- [ ] Test comando gen_daily_opening
- [ ] Revisar logs

---

## 🛡️ Garantías

✅ **NO modifica modelos existentes** (Cliente, VentaReserva, etc.)  
✅ **Solo lectura** de datos de ventas  
✅ **Signals propios** (no altera ventas/signals.py)  
✅ **Rollback fácil**: Remover de INSTALLED_APPS  

---

## 📞 Soporte

**Documentación completa**: `docs/`  
**Tests**: `control_gestion/tests/`  
**Ejemplos**: Ver documentos en `docs/`

---

## 📊 Métricas

- **Modelos**: 5
- **Vistas**: 5 (2 web + 3 webhooks)
- **Comandos**: 2
- **Signals**: 5
- **Tests**: 10
- **Acciones Admin**: 6
- **Líneas de código**: ~2,500

---

**Versión**: 1.0.0-beta  
**Autor**: Equipo Aremko  
**Fecha**: Noviembre 2025  
**Licencia**: Propietario

