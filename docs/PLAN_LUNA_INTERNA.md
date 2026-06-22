# Plan — Luna Interna: IA como asistente personal para la gestión operativa de Aremko

> **Estado:** Propuesta (v1, 2026-06-22). Pendiente: arrancar Fase 0 (piloto con Jorge).
> **Origen:** Visión de Jorge — pasar de "Luna copiloto de ventas" a "IA al servicio de la
> gestión operativa", donde cada trabajador tiene un asistente personal por WhatsApp que le
> indica sus labores, controla que se cumplan y escala lo que no puede resolver.

---

## 1. Resumen ejecutivo

Hoy Luna es un **copiloto de ventas** que atiende clientes en modo borrador (Deborah aprueba
antes de enviar). Este plan la convierte, **primero hacia adentro**, en el **asistente operativo
de cada trabajador de Aremko**: el empleado escribe "empezando el día" al WhatsApp de la empresa,
Luna lo reconoce por su número, abre su sesión de turno, le entrega sus labores (de la agenda
operativa y las comandas), controla el avance y escala a Deborah/Jorge lo que no resuelve.

La clave estratégica: **el staff es un universo finito y conocido**, lo que permite **soltarle la
autonomía a Luna solo con ellos** (responde automático, sin aprobación), manteniendo a los clientes
en modo seguro. Es el sandbox ideal para graduar a Luna de copiloto a piloto.

El piloto (Fase 0) es **Jorge mismo**: "empezando el día" → Luna le da su briefing (pagos que
vencen, agenda, comandas). De paso resuelve el pedido del resumen diario por WhatsApp a las 11:00.

---

## 2. El problema / la oportunidad

- La operación de Aremko se reparte entre varias personas (masajistas, recepción, mantención,
  Deborah, Ernesto, Jorge) con labores operativas y comerciales que hoy se coordinan a mano.
- Ya existe el dato estructurado (tareas, comandas, agenda) pero **falta la capa que lo lleve a la
  persona correcta, en el momento correcto, y controle que se cumpla.**
- WhatsApp es donde el equipo ya vive todo el día → es el canal natural para esa capa.
- Luna ya sabe conversar y ejecutar herramientas → es el motor.

**Oportunidad:** una IA que colabora con análisis en el trabajo de cada cual, como asistente
personal, y que en conjunto funciona como **control de gestión interno**.

---

## 3. Visión

> Cada trabajador de Aremko inicia su turno escribiendo al WhatsApp de la empresa. Luna lo saluda
> por su nombre, le dice qué tiene que hacer hoy según su rol, lo acompaña durante el turno
> (recordatorios, confirmaciones, dudas) y deja registrado el avance. Lo que excede su libreto, lo
> deriva a un humano. Jorge y Deborah ven el pulso de la operación sin perseguir a nadie.

---

## 4. Principio rector: **adentro antes que afuera** (inside-out)

Luna está en "modo borrador" para clientes **porque el público es infinito y riesgoso**. El staff
es lo contrario: **finito, identificable y con tolerancia interna al error**. Por eso:

> **La whitelist de números de staff es el interruptor de autonomía.** Solo los teléfonos del
> equipo (en la BD) reciben respuesta automática; los clientes siguen en modo borrador. Una sola
> condición — "¿este número es staff?" — decide el modo de operación.

Esto **desacopla** dos cosas que hoy van juntas: "Luna puede actuar sola" y "Luna es segura con el
público". Adentro soltamos la primera sin arriesgar la segunda. Lo que aprendamos con el staff se
gradúa después a clientes.

---

## 5. Metodología (principios de ejecución)

1. **Whitelist = autonomía.** El modo (auto vs borrador) lo decide si el número es staff.
2. **Adentro antes que afuera.** El staff es el campo de pruebas; lo validado se gradúa a clientes.
3. **Determinismo en código, no en el LLM.** Identificar el número, mapear número→rol→tareas y
   cambiar estados (comandas/agenda) van en código; Luna pone conversación y seguimiento. (Lección
   repetida con el modelo liviano: lo crítico se blinda en código.)
4. **Reusar, no reinventar.** Luna es la capa conversacional sobre control_gestion + comandas +
   agenda, que ya existen.
5. **Sesión de turno.** "Empezando el día" abre contexto (quién, rol, turno) y personaliza todo.
6. **Escalamiento humano.** Lo que Luna no resuelve va a Deborah/Jorge (reusa el flujo de
   asistencia humana que ya existe para clientes, pero al revés).
7. **Iterar con un piloto real (Jorge)** antes de sumar gente.

---

## 6. Arquitectura

- **Django (cerebro/datos):** identidad de staff (número→usuario→rol→turno), las herramientas
  internas de Luna (mi_agenda, mis_tareas, mis_comandas, marcar_tarea, etc.), la decisión de modo
  (auto si es staff), y el contenido del briefing. Reusa whatsapp_agent (tool-calling) +
  control_gestion + comandas + agenda.
- **aremko-cli (canal/envío):** la bandeja, el envío por la Cloud API (tiene el token) y el routing.
  Para staff: modo auto (sin pasar por el cajón de aprobación de Deborah).
- **Disparador del saludo:** cuando un número de staff escribe, Django detecta staff → Luna
  auto-saluda + abre sesión. El cron de las 11:00 (o el "empezando el día") es el gatillo.

> Nota: Luna vive en ambos lados, así que cada fase es un trabajo conjunto Django + aremko-cli
> (handoffs H-0xx).

---

## 7. Modelo de identidad del staff (la pieza nueva — primera tarea técnica)

Antes de codear, **confirmar/definir** cómo se modela el staff:
- Teléfono del trabajador (normalizado +56) como campo identificable.
- Rol / área (¿grupos de Django como "Masajistas"? ¿un campo cargo? ¿swimlane de control_gestion?).
- Turno (mañana/tarde) para el saludo y la entrega de labores.
- La **whitelist**: qué define que un número es "staff con auto-respuesta".

Piezas que probablemente ya sirven: usuarios del sistema con teléfono, grupo "Masajistas",
`Proveedor.usuario`, `control_gestion.Tarea.asignado_a`. **A confirmar en Fase 1.**

---

## 8. Roadmap por fases

### Fase 0 — Piloto con Jorge (primer paso, chico y 100% interno)
- "Empezando el día" → Luna reconoce a Jorge por su número, lo saluda y entrega su **briefing**:
  pagos que vencen (tablero de costos), agenda del día, comandas pendientes.
- Valida: identidad-por-número + respuesta automática a un número whitelisted + entrega de reporte.
- **Funde el pedido del resumen diario por WhatsApp a las 11:00.**

### Fase 1 — Identidad y roles
- Modelo de identidad de staff (sección 7). Saludo por turno. Whitelist de auto-respuesta.
- Switch de modo: número staff → Luna responde sola; resto → borrador (sin cambios).

### Fase 2 — Entrega de labores
- Al iniciar turno, según rol, Luna entrega las tareas del día:
  masajista → sus masajes + fichas; recepción → check-ins; mantención → sus tareas; etc.
- Fuente: agenda operativa + control_gestion + comandas.

### Fase 3 — Control de gestión
- El trabajador marca avance por WhatsApp ("listo el masaje de las 16:00", "comanda 123 entregada")
  → Luna actualiza el estado en el sistema y hace seguimiento de lo pendiente.
- Jorge/Deborah ven el pulso (lo no hecho, lo atrasado).

### Fase 4 — Escalamiento y asistencia
- Lo que Luna no resuelve automáticamente → a Deborah/Jorge, con contexto.
- Luna aprende los casos recurrentes.

---

## 9. Lo que YA existe (mapa de reuso)

| Pieza | App | Sirve para |
|---|---|---|
| Tareas por swimlane/área, asignadas, con vencimiento, WIP=1 | `control_gestion` | El backbone de labores |
| Comandas (tickets de pedidos, estados) | `ventas` | Labores comerciales/pedidos |
| Agenda operativa del día | (interna) | Servicios/horarios del día |
| Luna (tool-calling, modo borrador/auto) | `whatsapp_agent` | El motor conversacional |
| Bandeja omnicanal (identifica por teléfono) | `inbox_omnicanal` + aremko-cli | El canal |
| Fichas de masajes (las masajistas las ven/completan) | `ventas` | Caso de uso por rol |

~70% de la infraestructura está. Falta la **capa de identidad de staff** + conectar Luna a esos datos.

---

## 10. Guardrails y riesgos

- Luna interna **lee y actualiza estados** (tareas/agenda/comandas). **No** hace acciones
  destructivas ni toca pagos/plata.
- Autonomía **solo** para números en la whitelist; clientes sin cambios.
- Lo crítico (identidad, permisos, de quién es cada tarea) en código, no en el prompt.
- **Ventana de 24h de WhatsApp:** como el staff inicia la conversación, la ventana suele estar
  abierta; si se requiere enviar fuera de ventana (recordatorio proactivo), usar plantilla aprobada
  o fallback a otro canal.
- Privacidad: data interna de staff; sin exponer datos sensibles de clientes en el canal interno.

---

## 11. Reparto Django / aremko-cli (por fase = handoff)

- **Django:** identidad de staff, herramientas internas de Luna, decisión de modo, contenido del
  briefing, lógica de estados.
- **aremko-cli:** envío por WhatsApp (token), routing staff→auto, cron del gatillo, UI si aplica.

Cada fase se abre como handoff H-0xx en `docs/HANDOFFS.md`.

---

## 12. Métricas de éxito

- % de turnos iniciados vía "empezando el día".
- % de tareas/comandas marcadas como hechas por WhatsApp (vs. perseguir a mano).
- Tiempo de respuesta de Luna a un trabajador; % resuelto sin escalar.
- Reducción de coordinación manual de Deborah/Jorge.

---

## 13. Próximos pasos

1. **Confirmar el modelo de identidad del staff** (sección 7) — exploración técnica.
2. **Arrancar Fase 0 con Jorge** ("empezando el día" → briefing), como handoff Django + aremko-cli.
3. Validado el piloto, sumar 1 rol (ej. masajistas) en Fase 2.
