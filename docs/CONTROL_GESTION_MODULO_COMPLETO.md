# Control de Gestión — Aremko Aguas Calientes & Spa (Django + IA)

> Módulo operativo para ejecutar la metodología **Tareas Claras → Rendición de Cuentas → Priorización por Cola (WIP=1)**, integrado con **Reservas (ventas.VentaReserva)**, **Servicios agendados (ventas.ReservaServicio)**, **Cliente (ventas.Cliente)** y **Tramos (TramoService)**. Incluye **IA** para transformar mensajes en tareas, generar **checklists SOP**, **resumen diario** 09:00/18:00, **clasificar prioridad** y **QA de cierre**.

---

## 0) Estructura propuesta

```
aremko/
├── manage.py
├── aremko/
│   ├── settings.py
│   ├── urls.py
│   └── ...
├── ventas/                      # EXISTENTE: VentaReserva, ReservaServicio, Cliente, TramoService
└── control_gestion/             # 🔹 NUEVO MÓDULO
    ├── __init__.py
    ├── apps.py
    ├── admin.py
    ├── models.py
    ├── signals.py
    ├── views.py
    ├── urls.py
    ├── tasks.py                 # utilidades internas (opcional)
    ├── validators.py
    ├── ai_client.py             # cliente LLM
    ├── ai.py                    # funciones IA de negocio
    ├── management/
    │   └── commands/
    │       ├── gen_daily_opening.py
    │       └── gen_daily_reports.py
    ├── fixtures/
    │   └── control_gestion_seed.json
    └── tests/
        └── test_control_gestion.py
```

---

[CONTENIDO COMPLETO DEL MÓDULO - Ver en el mensaje del usuario para referencia completa]

Este archivo contiene la especificación técnica completa del módulo de Control de Gestión,
incluyendo:

- Modelos (Task, ChecklistItem, TaskLog, CustomerSegment, DailyReport)
- Admin personalizado con acciones
- Capa de IA (LLMClient, funciones de negocio)
- Vistas y webhooks
- Signals de integración con VentaReserva
- Comandos de management (rutinas y reportes)
- Fixtures y tests
- Plan de despliegue por etapas

Para implementación detallada, consultar:
- docs/PLAN_CONTROL_GESTION.md (plan de implementación por etapas)
- docs/INFORMACION_SISTEMA_ACTUAL.md (información del sistema actual)

---

**Última actualización**: Noviembre 2025
**Estado**: ✅ **IMPLEMENTADO** - Etapas 1-5 completadas (MVP funcional)
**Rama**: feature/control-gestion
**Versión**: 1.0.0-beta

---

## 📊 Estado Actual de Implementación

### ✅ Etapas Completadas

| Etapa | Estado | Descripción |
|-------|--------|-------------|
| **1. MVP Admin** | ✅ **100%** | Modelos, Admin completo, WIP=1, Tests |
| **2. IA** | ✅ **100%** | Cliente LLM (OpenAI/Mock), 5 funciones IA |
| **3. Integración Reservas** | ✅ **100%** | Signals con VentaReserva, tareas automáticas |
| **4. Vistas/Webhooks** | ✅ **100%** | Mi día, Equipo, 3 webhooks, endpoints cron |
| **5. Comandos** | ✅ **100%** | Rutinas diarias, reportes IA, preparación servicios |

### ⏳ Etapas Pendientes

| Etapa | Estado | Descripción |
|-------|--------|-------------|
| **6. Polish** | ⏳ **0%** | UI mejorada, permisos por grupo, dashboard KPIs |
| **7. Testing/Docs** | ⏳ **30%** | Tests adicionales, documentación final |
| **8. Producción** | ⏳ **0%** | Deploy, verificación, monitoreo |

**Progreso Total**: ~71% (12/17 días estimados)

---

## 🎯 Funcionalidades Implementadas

### ✅ Modelos y Admin
- 5 modelos: Task, ChecklistItem, TaskLog, CustomerSegment, DailyReport
- 2 modelos adicionales: TaskTemplate, EmpleadoDisponibilidad
- Admin completo con 6 acciones
- Formularios con validación WIP=1

### ✅ Capa de IA
- Cliente LLM con soporte OpenAI, DeepSeek y Mock
- 5 funciones IA: message_to_task, generate_checklist, summarize_day, classify_priority, qa_task_completion
- Modo mock funcional para desarrollo sin costo

### ✅ Integración con Reservas
- Signals que detectan check-in/checkout automáticamente
- Tareas automáticas para RECEPCION, ATENCION, COMERCIAL
- Integración con TramoService para segmentación
- Comando `gen_preparacion_servicios` para tareas 1 hora antes

### ✅ Vistas Web y Webhooks
- Vista "Mi Día" (top 3 tareas del usuario)
- Vista "Equipo" (snapshot del día)
- 3 webhooks: cliente_en_sitio, ai_ingest_message, ai_generate_checklist
- 4 endpoints HTTP para cron externo

### ✅ Comandos Automáticos
- `gen_daily_opening`: Tareas rutinarias diarias (excepto martes)
- `gen_daily_reports`: Reportes diarios con IA (matutino/vespertino)
- `gen_preparacion_servicios`: Tareas 1 hora antes de servicios
- `gen_vaciado_tinas`: Tareas de vaciado programadas

---

## 📝 Notas Importantes

### ⚠️ Cambio en Flujo de Preparación de Servicios

**IMPORTANTE**: Las tareas de preparación de servicios (OPERACION) **NO se crean automáticamente** al hacer check-in. En su lugar, se crean mediante el comando `gen_preparacion_servicios` que debe ejecutarse cada 15 minutos vía cron.

**Razón**: Permite crear las tareas exactamente 1 hora antes del servicio, independientemente de cuándo se haga el check-in.

**Configuración cron recomendada**:
```bash
*/15 * * * * python manage.py gen_preparacion_servicios
```

---

## 📚 Documentación Relacionada

- `docs/PLAN_CONTROL_GESTION.md`: Plan completo de implementación (actualizar checkboxes)
- `docs/INTEGRACION_CONTROL_GESTION_RESERVAS.md`: Cómo funciona la integración
- `control_gestion/README.md`: Guía de uso del módulo
- `docs/ETAPA1_COMPLETADA.md`: Resumen de Etapa 1

