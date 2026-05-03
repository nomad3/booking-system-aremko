# Plan: Agente Recepcionista Aremko

**Versión:** v1.0 · **Fecha:** 2026-05-02 · **Estado:** ⚪ pendiente (no iniciado)

Asistente IA interno para el rol de recepción de Aremko Spa Boutique. Resuelve 3 dolores principales:
1. Recepcionistas nuevos o reemplazos no saben qué hacer al llegar
2. Tareas operativas se olvidan o se traspapelan en el día
3. El conocimiento tribal (procedimientos, casos especiales, preferencias de clientes recurrentes) se pierde con la rotación de personal

**Documentos relacionados:**
- [docs/AREMKO_MARKETING_PLAN.md](AREMKO_MARKETING_PLAN.md) — plan maestro de marketing (separado, no relacionado con este)
- [docs/MARKETING_PLAYBOOK.md](MARKETING_PLAYBOOK.md) — voz Aremko (referencia para tono del agente)

---

## Visión

Un chat interno dentro del sistema de Aremko (probablemente en `/admin/recepcion/asistente/`) donde el recepcionista pregunta cosas en lenguaje natural y obtiene:
- Resumen de tareas del día priorizadas por hora
- Estado de cada cabaña, tina, comanda
- Saldos pendientes por cobrar
- Procedimientos operativos cuando los necesita
- Capacidad de marcar cosas como hechas sin salir del chat

El agente no reemplaza el sistema actual. Lo **complementa como capa conversacional sobre los datos que ya viven en BD**, más un **playbook de conocimiento tribal** editable.

---

## Estados del plan

| Emoji | Estado |
|---|---|
| ⚪ | Pendiente |
| 🟡 | Procesando |
| 🟠 | Parcialmente terminada |
| 🟢 | Terminada |
| 🔴 | Bloqueada |

---

## Fase 0 — Discovery y decisiones (semana 1)

> Antes de codear, resolver las preguntas abiertas para que el alcance quede claro.

### 0.1 Mapear sistema actual
- **Estado:** ⚪
- **Responsable:** Claude (con guía de Jorge)
- **Tiempo:** 2-3h
- **Tareas:**
  - [ ] Revisar `control_gestion` (modelos, vistas, swimlanes) — entender cómo funciona la agenda operativa actual
  - [ ] Revisar modelo `Comanda` y flujo de pedidos de productos
  - [ ] Listar lo que YA existe en BD: VentaReserva, ReservaServicio, Pago, Cliente, ServicioBloqueo, etc.
  - [ ] Identificar gaps: ¿hay tracking de estado de cabaña? ¿estado de tina? ¿lavado de ropa?

### 0.2 Decisiones de alcance (validación con Jorge)
- **Estado:** ⚪
- **Tiempo:** 30 min de conversación con Jorge
- **Decisiones a tomar:**
  - [ ] **Escrituras sí/no en MVP**: arrancar read-only, o desde el día 1 puede marcar tareas/registrar pagos?
  - [ ] **Otros roles**: solo recepción o también masajistas / encargado cabañas / cocina?
  - [ ] **Voice input**: solo texto en MVP, o desde el día 1 también voz (para manos ocupadas)?
  - [ ] **¿Es solo interno** o eventualmente también responde a huéspedes vía WhatsApp?
  - [ ] **Modelo LLM**: Claude Haiku (~$5-15/mes) vs Sonnet ($30-50/mes). Recomendación: Sonnet por calidad
  - [ ] **Idioma del agente**: 100% español Chile (no neutro)

### 0.3 Capturar conocimiento tribal inicial
- **Estado:** ⚪
- **Responsable:** Jorge + recepcionista actual
- **Tiempo:** 2-3h sentados juntos
- **Output:** primer borrador de [docs/PLAYBOOK_RECEPCIONISTA.md](PLAYBOOK_RECEPCIONISTA.md) con:
  - [ ] Protocolo de preparación de tinas (1h antes, calibración temperatura, etc.)
  - [ ] Procedimiento de check-in / check-out
  - [ ] Cómo manejar pedidos especiales (jugos, ambientaciones)
  - [ ] Quién hace qué en cada turno (mañana/tarde, días de semana)
  - [ ] Casos comunes y respuestas templated
  - [ ] Contactos del equipo (masajistas, mantención, proveedores)

---

## Fase 1 — MVP Read-only (semanas 2-3)

> Un agente que escucha, lee BD + playbook, responde. Sin escrituras todavía.

### 1.1 Modelo de conversación + UI chat
- **Estado:** ⚪
- **Responsable:** Claude
- **Tiempo:** 4-6h
- **Componentes:**
  - [ ] Modelo `ConversacionAgente` (usuario, mensajes, fecha, contexto)
  - [ ] Modelo `MensajeAgente` (rol: user/assistant/tool, contenido, tools_used, tokens)
  - [ ] Migración (manual en Render shell)
  - [ ] Vista admin `/admin/recepcion/asistente/` con UI tipo chat (mensaje + respuesta scroll-down)
  - [ ] CSS responsive (recepción puede usar tablet o celular)
  - [ ] Permisos: solo grupo "Recepción" + superuser

### 1.2 Servicio agente con OpenRouter + tool calling
- **Estado:** ⚪
- **Responsable:** Claude
- **Tiempo:** 4-6h
- **Componentes:**
  - [ ] `ventas/services/agente_recepcionista.py`
  - [ ] System prompt con contexto Aremko + voz
  - [ ] Tools (read-only) implementados:
    - `obtener_reservas_del_dia(fecha=None)` → ReservaServicio + VentaReserva
    - `obtener_reservas_proximas(horas=2)` → próximas N horas
    - `obtener_saldo_pendiente(reserva_id)` → calcula deuda
    - `obtener_comandas_pendientes()` → pedidos de productos no completados
    - `obtener_tareas_recepcion()` → desde control_gestion
    - `consultar_cliente(busqueda)` → Cliente + historial reservas
    - `obtener_resumen_dia(fecha=None)` → totales: cuántos checkouts, tinas, masajes, ingreso esperado
  - [ ] Streaming response (mejor UX con LLM)
  - [ ] Logging de tools llamadas para debugging

### 1.3 Playbook como context dinámico
- **Estado:** ⚪
- **Responsable:** Jorge (contenido) + Claude (integración)
- **Tiempo:** 1-2h integración
- **Tareas:**
  - [ ] Cargar `docs/PLAYBOOK_RECEPCIONISTA.md` en system prompt
  - [ ] Si el playbook >5000 tokens, segmentar y usar tool `consultar_playbook(seccion)` en vez de cargar todo
  - [ ] UI admin para editar el playbook desde Django sin tocar código

### 1.4 Endpoint API + integración con cron-job.org si aplica
- **Estado:** ⚪
- **Responsable:** Claude
- **Tiempo:** 1-2h
- **Decisión pendiente Fase 0:** ¿hay alertas proactivas? Ej. "10 min antes de cada tina mandar mensaje al chat avisando que hay que prepararla"

### 1.5 Validación con recepcionista actual
- **Estado:** ⚪
- **Responsable:** Jorge + recepcionista
- **Tiempo:** 1 día de uso
- **Criterio de éxito:**
  - 5+ preguntas respondidas correctamente
  - Recepcionista dice "esto me sirve"
  - Cero respuestas alucinadas (datos inventados)

---

## Fase 2 — Escrituras (semanas 4-5)

> El agente puede actuar en el sistema, no solo informar.

### 2.1 Tools de escritura con validación
- **Estado:** ⚪
- **Tiempo:** 4-6h
- **Tools nuevos:**
  - [ ] `marcar_tarea_completada(tarea_id, notas)` → control_gestion
  - [ ] `registrar_pago(reserva_id, monto, metodo)` → crea Pago
  - [ ] `crear_tarea_recepcion(descripcion, hora_objetivo)` → tarea ad-hoc
  - [ ] `agregar_nota_cliente(cliente_id, nota)` → para preferencias futuras
  - [ ] `marcar_comanda_lista(comanda_id)` → si aplica
- **Reglas:**
  - [ ] Confirmación explícita del recepcionista antes de cada escritura
  - [ ] Logging de quién ejecutó cada acción
  - [ ] Reversible cuando sea posible

### 2.2 Manejo de errores y casos límite
- **Estado:** ⚪
- **Tiempo:** 2h
- **Tareas:**
  - [ ] Qué hace el agente si el monto del pago no cuadra con la deuda
  - [ ] Qué hace si la tarea ya estaba marcada como completada
  - [ ] Qué hace si el cliente buscado tiene 5 matches por nombre

---

## Fase 3 — Estados operativos en BD (semanas 6-8)

> Modelar lo que hoy vive en cabeza/papel para que el agente lo conozca.

### 3.1 Modelo EstadoCabana
- **Estado:** ⚪
- **Tiempo:** 4-6h
- **Modelo:**
  - cabana FK
  - estado (lista | ocupada | sucia_pendiente | en_limpieza | lista_para_uso | mantenimiento)
  - timestamps de transición
  - quien_actualizo (User FK)
- **UI:**
  - [ ] Vista admin para que recepción/cabañas actualicen estado en 1 click
  - [ ] Auto-transición ocupada → sucia_pendiente al checkout
- **Migración manual en Render**

### 3.2 Modelo EstadoTina
- **Estado:** ⚪
- **Tiempo:** 3-4h
- **Modelo similar** + temperatura medida (cuando se calibra antes de uso)

### 3.3 Tools nuevos del agente
- **Estado:** ⚪
- **Tools:**
  - `obtener_estado_cabanas()` → matriz de estados
  - `marcar_cabana_lista(cabana_id)`
  - `registrar_temperatura_tina(tina_id, temperatura)`

---

## Fase 4 — Conocimiento tribal estructurado (semanas 9-12)

> Capturar todo el know-how no escrito en formato consultable.

### 4.1 Captura masiva de conocimiento
- **Estado:** ⚪
- **Tiempo:** 8-15h distribuidas en sesiones de 1-2h con Jorge y recepcionista
- **Approach:** sesiones grabadas de "preguntas frecuentes que recibe el recepcionista" → procesar con IA → estructurar
- **Output:** Playbook v2 con secciones organizadas:
  - Operaciones diarias
  - Casos especiales por servicio
  - Preferencias de clientes recurrentes (sincronizado con notas en Cliente)
  - Procedimientos de emergencia
  - Contactos críticos

### 4.2 FAQ con respuestas templated
- **Estado:** ⚪
- **Tiempo:** 3-4h
- **Componente:** Tool `obtener_respuesta_faq(pregunta)` busca semánticamente en una base de FAQs

---

## Fase 5 — Escalabilidad y otros roles (mes 4+)

### 5.1 Roles adicionales
- **Estado:** ⚪
- **Posibilidades:**
  - [ ] Agente para masajistas (su agenda + notas de clientes que atendieron)
  - [ ] Agente para cabañas (lista de limpiezas pendientes, prioridades)
  - [ ] Agente para cocina si aplica (comandas en tiempo real)

### 5.2 Voice input (Whisper)
- **Estado:** ⚪
- **Beneficio:** recepción puede consultar al agente con manos ocupadas

### 5.3 Notificaciones proactivas
- **Estado:** ⚪
- **Ejemplos:**
  - 1h antes de tina: aviso al chat "preparar tina Calbuco para 14:30"
  - Al detectar saldo no cobrado al final del día
  - Al detectar comanda pendiente de hace >2h

---

## Fase 6 — Externo / Conserje virtual (futuro, mes 6+)

> Si funciona internamente, abrir variante para huéspedes.

- Agente vía WhatsApp para consultas pre-visita ("a qué hora me esperan", "qué llevo")
- Agente vía web para consultas pre-reserva
- Limitado en alcance: NO toma reservas (esas pasan por el flujo actual)

---

## Stack técnico propuesto

| Componente | Tecnología |
|---|---|
| LLM | OpenRouter con `anthropic/claude-sonnet-4.6` (mismo provider que análisis IA) |
| Streaming | SSE (Server-Sent Events) o WebSocket Django Channels |
| UI | Template Django + Alpine.js o htmx (sin React, mantener stack simple) |
| Persistencia conversaciones | Modelos Django `ConversacionAgente` + `MensajeAgente` |
| Auth | Django auth con grupo "Recepción" |
| Logging | Standard Python logging + tabla de auditoría |
| Costo estimado | $30-50 USD/mes con Sonnet (30 conversaciones/día × ~1000 tokens) |

---

## Métricas de éxito

| Métrica | Cómo se mide | Meta 3 meses |
|---|---|---|
| Adopción | % de turnos donde se usa el agente | >70% |
| Tiempo de "ramp up" de reemplazos | Encuesta a reemplazos | <2h vs ~2 días actual |
| Tareas olvidadas | Reporte semanal de pendientes no marcados | -50% vs baseline |
| Satisfacción equipo | Encuesta interna trimestral | >7/10 |

---

## Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Recepcionista no adopta porque "más rápido en cabeza" | Empezar con MVP minimalista validado con recepcionista actual antes de invertir más |
| Alucinaciones del LLM (datos inventados) | Tool calling estricto + system prompt anti-alucinación + monitor logs |
| Costo LLM se dispara | Cache de respuestas comunes + monitoreo mensual de tokens |
| Conocimiento tribal nunca se captura porque "no hay tiempo" | Sesiones cortas y frecuentes (30 min/semana) en vez de una sola larga |
| Datos sensibles del cliente expuestos en logs | Sanitización antes de logging + retención limitada |

---

## Cómo trabajamos este plan

1. **Fase 0 obligatoria** antes de cualquier código — resolver las preguntas pendientes
2. **Una fase a la vez**, validar con Jorge antes de pasar a la siguiente
3. **Cualquier idea nueva** que surja se evalúa: ¿entra como nueva tarea o se descarta? No improvisar
4. **Migraciones SIEMPRE manuales** en Render shell (regla del proyecto)
