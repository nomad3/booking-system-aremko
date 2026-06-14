# BRIEF H-012 — Automatizar la salida de la Bandeja WhatsApp con plantillas

- **Solicita:** agente aremko-cli (a pedido de Jorge)
- **Implementa:** Django (segmentación → envíos de plantilla + aprobación) + aremko-cli (UI de aprobación)
- **Fecha:** 2026-06-14
- **Estado:** SOLICITADO

## Problema / contexto

La "Bandeja WhatsApp" (OVC) era una **lista de trabajo**: Django decía a quién contactar + sugería el
mensaje, y Deborah lo enviaba **manual desde su WhatsApp** (`marcar-enviado` solo REGISTRA). Al migrar
el número a **Cloud API**, eso se rompió: para **iniciar** conversación (fuera de la ventana de 24h)
Meta **exige una plantilla aprobada**; ya no se puede texto libre ni mandar desde el celular.

**Objetivo:** automatizar esa salida con **plantillas aprobadas**, reusando el motor que ya existe.

## Reusa lo ya construido (no reinventar)

- `run-template-campaign` (Go aremko-cli) ya envía plantillas vía Cloud API leyendo de Django.
- `pending-template-sends` (Django) ya alimenta ese motor; `mark-template-sent`/`-failed` existen.
- 28 plantillas "Vuelta a Casa" (`vac_*`) **aprobadas**.

## Flujo propuesto

1. La **segmentación de la Bandeja** (a quién contactar y por qué motivo) — que ya existe en Django —
   en vez de "sugerir texto para que Deborah copie", **genera un envío de plantilla pendiente** por
   cliente: `{phone/cliente, plantilla aprobada según el motivo, variables (nombre, etc.), motivo}`.
2. **Aprobación (arrancamos por acá):** esos envíos quedan en estado **"por aprobar"**. Deborah los
   revisa en aremko-cli y **aprueba/descarta** (individual o **por lote**).
3. Los aprobados → `run-template-campaign` los **envía** por Cloud API.
4. 🔗 La plantilla **invita a responder** → al contestar el cliente se abre la **ventana de 24h** →
   ahí entra el **agente IA** (H-007) a atender, orientar y resolver. La plantilla abre la puerta.

**Modo:** **empezar por aprobación** (human-in-the-loop, mismo criterio que el agente); madurar a
**automático con tope diario** cuando veamos que la calidad/tier se mantiene sana.

## Restricciones de Meta a respetar (SÍ o SÍ)

- **Plantilla aprobada** obligatoria para iniciar; personalización solo por **variables**.
- **Categorías + costo:** reactivación = MARKETING (la más cara); Meta cobra por mensaje de plantilla.
- **Calidad y límites:** el número tiene **tier** (1k/10k/100k clientes únicos/día) y **calidad**
  (verde→amarillo→rojo). Bloqueos/reportes la bajan → Meta puede **limitar/pausar/suspender**.
  Mal hecho, **quema el número**. → volumen bajo al inicio, segmentar fino.
- **Límite de marketing por usuario** (anti-spam de Meta) + **opt-out** (respetarlo siempre).
- Reusar la **anti-saturación** que ya existe en el sistema (no recontactar al mismo cliente muy seguido).

## Reparto

**Django:**
- Mapear cada **motivo** de contacto de la Bandeja → **plantilla aprobada** (crear las que falten y
  mandarlas a aprobar). Hoy hay `vac_*` (reactivación); si la Bandeja contacta por otros motivos
  (cumpleaños/celebración, seguimiento), definir esas plantillas con Jorge.
- Generar los envíos pendientes desde la segmentación (estado `por_aprobar`), respetando
  anti-saturación + opt-out + límites.
- Endpoints (luna-key), p. ej.: `GET /api/whatsapp/bandeja-envios?estado=por_aprobar`;
  `POST .../<id>/aprobar` (pasa a listo para `run-template-campaign`); `POST .../<id>/descartar`;
  acción de lote ("aprobar todos los del motivo X"). Nombres a tu criterio → me avisas y calzo.

**aremko-cli (yo):**
- UI "Envíos de plantilla por aprobar": lista por motivo con **cliente, plantilla, preview del texto
  renderizado**, y **Aprobar / Descartar** (individual + por lote) + **"Enviar aprobados"** (dispara
  `run-template-campaign`). Proxies Go a los endpoints.

## Decisiones a definir (con Jorge)

- **Qué motivos contacta la Bandeja hoy** y **qué plantilla aprobada** usa cada uno (mapeo). Crear las
  que falten.
- Tope diario para cuando pasemos a automático.

## Aceptación

- Deborah ve la lista de "por aprobar" (cliente + plantilla + preview), aprueba un lote → se envían por
  Cloud API → el cliente recibe la plantilla → si responde, lo atiende el agente.
- Se respeta anti-saturación/opt-out; volumen controlado para no dañar la calidad del número.

## Punteros
- Motor de envío: `run-template-campaign` (Go) + `pending-template-sends` (Django).
- Segmentación actual: endpoints OVC `bandeja-whatsapp/siguiente|del-dia` y su lógica en Django.
- Plantillas: `vac_*` (Vuelta a Casa) + las que se creen para otros motivos.
