# Plan de Trabajo — Área "Conexión-Masajes"

> **Documento vivo.** Se actualiza al cerrar cada fase. Es un PLAN, no implementación.
> Creado: 2026-06-01 · Owner: Jorge Aguilera · Responsable técnico: Claude Code

## 🎯 Objetivo
Módulo **"Ficha de Bienestar para Masajes"**: registrar a **cada persona** que recibe masaje (no solo al comprador), crear/actualizar su **ficha de cliente**, enviarle un **formulario breve por WhatsApp** antes del servicio, y **automatizar correos** de seguimiento de bienestar y comerciales — siempre con **lenguaje de bienestar, nunca médico/clínico**.

## ⚖️ Reglas no negociables (cumplimiento)
- **Lenguaje permitido:** ficha de bienestar, experiencia de masaje, preferencias, zonas de tensión, observaciones del terapeuta, sugerencia de frecuencia, autocuidado, bienestar general.
- **Lenguaje PROHIBIDO:** diagnóstico, tratamiento, prescripción, paciente, ficha clínica, enfermedad, recomendación médica. (Validar en templates, help_texts, emails y admin.)
- **Consentimientos separados:** (1) uso de datos para adaptar la experiencia — *obligatorio*; (2) marketing/comunicaciones — *opcional*. Registrar **fecha + texto exacto** aceptado.
- **Datos sensibles:** nunca obligatorios. `condiciones_declaradas` siempre opcional, con help_text: *"Esta información se usa solo para adaptar la experiencia de bienestar. No constituye evaluación médica ni diagnóstico."*
- **Marketing solo si `consentimiento_marketing = True`.** Los emails transaccionales de la visita pueden ir aunque sea False, pero **sin promociones**.

---

## 🔗 Integración con el sistema actual (nombres REALES verificados)
| Concepto del prompt | En el proyecto real | Nota |
|---|---|---|
| Cliente (identificador) | `ventas.models.Cliente` — `telefono` es **`unique`** | Usar teléfono como identidad (ya lo es). Reusar `ClienteService.buscar_cliente_por_telefono` + normalización. |
| Reserva | `ventas.models.VentaReserva` | El comprador es `VentaReserva.cliente`. |
| "detalle de servicio" | `ventas.models.ReservaServicio` (`venta_reserva`, `servicio`, `cantidad_personas`, `fecha_agendamiento`, `hora_inicio`) | `servicio_reservado` → FK a **`ReservaServicio`**. |
| Identificar masaje | `Servicio.tipo_servicio == 'masaje'` | Ya existe el choice. Cantidad en `ReservaServicio.cantidad_personas`. |
| Token público | Patrón ya usado: `secrets.token_urlsafe(32)` + `reverse()` (ver `token_acceso` de comandas) | Reusar el patrón, no inventar. |
| Enviar WhatsApp | Existe `neonize_service/` (gateway) + `ventas/services/whatsapp_message_service.py` (genera contenido) + bandeja/webhooks | **Verificar en F0 la ruta de ENVÍO real** y envolverla en un único `send_whatsapp_message(phone, message)`. NO crear proveedor nuevo. |
| Emails + cron | `ventas/services/communication_service.py`, comando `send_communication_triggers` (cron central), modelo `EncuestaSatisfaccion` (encuesta D+1 ya existe), `CommunicationLog` | **Extender** el cron y reusar logging/anti-spam existentes. No duplicar el motor de envío. |
| Seguimiento post-visita | Ya hay encuesta D+1 (`EncuestaSatisfaccion`) y triggers de reactivación | Alinear `SeguimientoBienestarMasaje` con lo existente para no duplicar correos. |

> ⚠️ **Migraciones = MANUALES en Render** (regla del proyecto: `migrate` está desactivado en `entrypoint.sh`). Cada fase con modelos nuevos requiere correr `migrate` a mano en la Render Shell, con respaldo previo de BD. Usar el patrón zero-downtime (columna/tabla primero) si aplica.

---

## 🗂️ FASES

### F0 — Descubrimiento y diseño (sin código)
- [ ] Mapear la ruta de **envío real** de WhatsApp (¿neonize gateway directo? ¿webhook a n8n/ManyChat?). Definir la firma única `send_whatsapp_message(phone, message)` que la envuelva.
- [ ] Confirmar cómo se relaciona el comprador y si hoy se guarda algún acompañante (creemos que no).
- [ ] Revisar `EncuestaSatisfaccion` y los triggers actuales para **evitar correos duplicados** (encuesta D+1 ya existe).
- [ ] Validar con Jorge: textos legales/consentimiento, remitente, y si el seguimiento comercial reemplaza o convive con los emails actuales.
- **Entregable:** mini-doc de decisiones + diagrama del flujo. **Sin migración.**

### F1 — Modelos + migraciones ✅ HECHO (commit local, sin desplegar aún)
- [x] `BienestarMasajeFicha` (con resumen del terapeuta integrado como campos: `obs_terapeuta`, `zonas_trabajadas`, `intensidad_aplicada`, `sugerencia_frecuencia`, `recomendacion_texto`; + consentimientos con `fecha_consentimiento` y `consentimiento_texto`).
- [x] `ParticipanteMasajeReserva` (token `secrets.token_urlsafe`; campos email-neutrales: `estado_contacto=email_enviado`, `fecha_envio`).
- [x] `SeguimientoBienestarMasaje` (scaffolding v2; tabla creada, envío de emails se implementa en v2).
- [x] Migración `0118_conexion_masajes_ficha_bienestar` (3 tablas NUEVAS). **Validada con Django real** (migrate sqlite OK + `makemigrations --check` sin drift).
- **PENDIENTE deploy:** correr `migrate ventas` MANUAL en Render cuando se despliegue v1. Tablas nuevas → no rompen nada al desplegar el código antes del migrate.

### F2 — Servicio: generación de participantes
- [ ] Servicio `generar_participantes_masaje(venta_reserva)`: cuando una `ReservaServicio` con `servicio.tipo_servicio=='masaje'` tiene `cantidad_personas > 1`, crear N participantes; el **comprador** queda como 1er participante (`tipo_participante='comprador'`).
- [ ] Disparador: signal post_save de `VentaReserva`/`ReservaServicio` o llamada explícita en el flujo de creación (decidir en F0 para no romper el checkout actual).
- [ ] Idempotente (no duplicar participantes al re-guardar).
- **Entregable:** servicio + tests. Sin migración nueva.

### F3 — Formularios públicos con token (responsive, mobile-first)
- [ ] Vista pública **"registrar acompañante"** (token del comprador): nombre, WhatsApp, email opcional, confirmación de autorización. Crea/actualiza `Cliente` por teléfono y el 2º `ParticipanteMasajeReserva`.
- [ ] Vista pública **"ficha de bienestar individual"** (token por participante): los campos de la ficha + ambos consentimientos. Reusa template base mobile.
- [ ] Seguridad: validar token + estado; completar **una sola vez** (salvo edición admin); no exponer IDs internos; registrar consentimiento (fecha+texto).
- [ ] Enlazar a la **Política de Privacidad** (`/privacidad/`, ya existe).
- **Entregable:** vistas + templates + tokens. Sin migración nueva.

### F4 — Integración en el Admin
- [ ] Inline **"Participantes de masaje"** en `VentaReservaAdmin`: nombre, teléfono, tipo, estado ficha, **botón reenviar WhatsApp**, link copiar formulario, estado consentimiento marketing.
- [ ] **Alerta** cuando falte el acompañante: *"Falta registrar datos del acompañante para enviar ficha de bienestar."*
- [ ] Acción admin: enviar al comprador el link de registro de acompañante.
- [ ] Vista/admin **resumen post-masaje** del terapeuta con advertencia: *"Evitar lenguaje médico. Registrar solo observaciones de bienestar y experiencia."*
- **Entregable:** admin. Sin migración nueva.

### F5 — Servicio WhatsApp (envolver el existente)
- [ ] `send_whatsapp_message(phone, message)` único, que envuelve el gateway real (neonize/n8n/ManyChat — según F0). Manejo de errores + log.
- [ ] Plantillas de los 2 mensajes (comprador y acompañante) con variables `{{nombre}}`, `{{cantidad}}`, `{{link_acompañante}}`, `{{nombre_comprador}}`, `{{fecha_reserva}}`, `{{link_ficha}}`.
- **Entregable:** servicio + templates de mensaje. Sin migración.

### F6 — Programación de emails de seguimiento
- [ ] Al completar la ficha, **programar** los `SeguimientoBienestarMasaje`: 24h (gracias+encuesta), 7d, 30d, 60d, 90d.
- [ ] Despachar desde el cron existente (`send_communication_triggers`) o un comando nuevo `send_seguimiento_masajes` — decidir en F0 para no chocar con triggers actuales.
- [ ] **Gating:** solo comerciales si `consentimiento_marketing=True`; transaccionales sin promo permitidos.
- [ ] Cancelar seguimiento desde admin. Reusar `CommunicationLog` + límites anti-spam existentes.
- **Entregable:** scheduler + templates email. Sin migración (si SeguimientoBienestarMasaje ya está en F1).

### F7 — Email "resumen de bienestar" post-masaje
- [ ] Email con asunto *"Tu resumen de bienestar en Aremko"* y cuerpo base no-médico; incluye objetivo declarado, intensidad aplicada, zonas trabajadas, sugerencia de frecuencia, link para reservar.
- **Entregable:** template + trigger. Sin migración.

### F8 — Tests
- [ ] reserva con masaje para 2 → crea 2 participantes
- [ ] completar ficha → crea/actualiza Cliente (por teléfono)
- [ ] acompañante recibe token único
- [ ] NO se envía marketing sin consentimiento
- [ ] token inválido → falla
- [ ] ficha completada → cambia estado
- **Entregable:** suite de tests.

### F9 — Documentación para recepción
- [ ] Guía breve: cómo registrar acompañante, reenviar WhatsApp, leer fichas, registrar resumen del terapeuta, y qué lenguaje usar/evitar.

---

## ✅ Decisiones tomadas (F0)
- **Canal v1 = EMAIL.** Toda la comunicación (formulario al acompañante, ficha, seguimiento) se hace por **email** usando la infra existente (`communication_service` + `send_communication_triggers`).
- **WhatsApp = PENDIENTE.** Se construye la abstracción `send_whatsapp_message(phone, message)` como stub (log/cola, no envía aún). En unos días se conectará a la **WhatsApp Cloud API** (NO al gateway neonize). Los links `wa.me` click-to-chat sí se pueden usar como CTA, pero el envío automatizado va por email por ahora.
- **Identidad técnica confirmada:** gateway de envío saliente actual = `neonize_service` (`POST /send` `{jid,text}`), pero NO se usa para este módulo (se reserva para cuando llegue Cloud API si se decide).

## ❓ Preguntas abiertas para Jorge (resolver en F0)
1. ~~Envío WhatsApp~~ → **RESUELTO: email ahora, WhatsApp Cloud API después (stub).**
2. **Seguimiento vs. lo actual:** ¿estos correos de masaje **reemplazan** o **conviven** con la encuesta D+1 y los triggers de reactivación ya existentes? (evitar duplicados).
3. **Resumen del terapeuta:** ¿quién lo llena (recepción/terapeuta) y desde dónde (admin Django o una vista simple)?
4. **Textos legales/consentimiento:** confirmar redacción final de los 2 checkboxes y remitente del email.
5. **Alcance v1:** ¿lanzamos primero solo la **captura de acompañante + ficha** (F1-F4) y dejamos la automatización de emails (F6-F7) para una v2?

## 📌 Bitácora
| Fecha | Fase | Avance | Aprobado |
|---|---|---|---|
| 2026-06-01 | — | Creación del plan (grounded en modelos reales) | — |
| 2026-06-01 | F0 | Decisiones: canal=email; WhatsApp stub (Cloud API después); v1=F1-F4; emails masaje reemplazan; resumen terapeuta en admin. | Jorge |
| 2026-06-01 | F1-F4 | **v1 code-complete** (4 commits locales, NO desplegado): modelos+migración 0118 (validada con Django real), servicio+signal defensivo, formularios públicos con token, admin (inline+alerta+resumen terapeuta+acción email). | pendiente deploy |
| 2026-06-03 | F2 | **Cubrir masaje individual:** el signal/servicio ahora generan participante+ficha para masajes de **1 o más** personas (antes solo `>1`). 1 persona → solo comprador (su ficha); 2+ → comprador + acompañantes. Inline oculta "Registrar acompañante" si no hay acompañante. Sin migración. | Jorge |
| 2026-06-03 | Admin | **Card "Masajes" en el dashboard** de inicio (hub): Fichas + Participantes + Seguimientos + Pagos masajistas + Servicios + Horarios. No mueve nada de su lugar; masajistas conservan su vista simplificada. | Jorge |
| 2026-06-03 | F6 | **Motor de seguimientos comerciales:** al completar la ficha se PROGRAMAN los SeguimientoBienestarMasaje (gracias 24h transaccional; 7/30/60/90 d comerciales = solo con consentimiento_marketing). Comando `enviar_seguimientos_masaje` (enganchado a send_communication_triggers) envía los vencidos. **APAGADO por defecto** (`MASAJE_SEGUIMIENTOS_ACTIVOS=false`) hasta revisar textos. Copys borrador en `masaje_seguimiento_service.py`. Sin migración. | pendiente revisar textos + activar |
| 2026-06-03 | F7 | **Email "resumen de bienestar":** signal post_save en BienestarMasajeFicha → cuando la masajista completa su resumen (obs/zonas/intensidad/frecuencia/recomendación) se programa un SeguimientoBienestarMasaje tipo `resumen_bienestar` (inmediato, transaccional, idempotente 1×/participante) armado con esos datos + CTA reservar. Respeta el mismo flag de envío. Nuevo choice (sin migración de BD). | pendiente revisar textos + activar |
| 2026-06-03 | Privacidad | **Masajista no ve datos de contacto:** la vista de la ficha para el grupo Masajistas muestra solo nombre + N° reserva + fecha/hora del servicio + preferencias + su resumen; oculta teléfono/email/consentimientos (también list_display/search). | Jorge |
| 2026-06-03 | Asignación | **Ficha por masajista asignado:** `Proveedor.usuario` (OneToOne a User, **migración 0122 REQUIERE migrate manual**) vincula el login del masajista; la ficha sale a todos pero solo el masajista **asignado** (`ReservaServicio.proveedor_asignado`) puede editar el resumen — los demás la ven en solo lectura con aviso "no asignada a ti". Fallback: si no hay vínculo usuario, matchea por email. Admin de Proveedor expone el campo `usuario` (raw_id). | pendiente migrate + vincular usuarios |
| 2026-06-03 | F8 | **Tests** `ventas/tests_masaje_conexion.py`: generación 1 persona (solo comprador) / 2 (comprador+acompañante), idempotencia, completar ficha (crea Cliente+ficha+estado), token único/ inválido (404), no-completar-2×, gating seguimientos por consentimiento (solo gracias sin mkt; +4 comerciales con mkt), resumen terapeuta programa email idempotente. Correr: `python manage.py test ventas.tests_masaje_conexion`. | pendiente correr |

> **v1 DEPLOY pendiente:** push a main + **`migrate ventas` MANUAL en Render**. ⚠️ Correr migrate **pronto tras el deploy**: el admin de VentaReserva tiene el inline de participantes que consulta la tabla nueva; hasta correr migrate, abrir una reserva en el admin daría error 500 (el sitio público NO se afecta — el signal es defensivo).
> **Pendiente post-v1:** F8 tests, F9 docs recepción; v2 = emails de seguimiento (F6-F7) + envío real WhatsApp (Cloud API).
