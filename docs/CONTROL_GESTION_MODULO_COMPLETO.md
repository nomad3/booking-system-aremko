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
**Estado**: Documentación completa - Pendiente de implementación
**Rama**: feature/control-gestion

