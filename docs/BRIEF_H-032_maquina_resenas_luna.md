# BRIEF H-032 — Máquina de reseñas: pedido de reseña Google vía Luna (post-visita)

**Contexto:** Plan estratégico de Aremko ("Plan Río", iniciativa PR-02). La máquina de reseñas YA está ~70% construida; esto la AMPLIFICA moviendo el pedido al canal de mayor engagement (Luna/WhatsApp). NO reconstruir lo existente.

## Lo que YA existe (reusar, no tocar)
- **EncuestaSatisfaccion** (post-visita D+1 email): NPS (`nps_categoria`), `cal_experiencia_general`, ratings, `califica_para_review_publico` (≥4⭐ o NPS≥7), `evaluar_followup`/`requiere_followup` (detractores).
- **Funnel web a Google Reviews** en la página de "Gracias" (solo a contentos). Se MANTIENE en paralelo.
- **send_communication_triggers** (cron) que ya dispara la encuesta D+1.

## Outcome (lo nuevo)
Post-visita, **Luna pide la reseña de Google por WhatsApp SOLO a clientes contentos**, con link directo; los detractores van a **recovery** (bandeja, contacto personal de Deborah).

## Decisiones de Jorge (firmes)
- Canal: **Luna/WhatsApp + funnel web** (ambos).
- Política: **solo contentos** (mantener gating actual; NO pedir a detractores).
- Timing: "glow" post-visita (esa tarde/noche o mañana siguiente).
- ⚠️ **No incentivar** reseñas (política Google).

## Flujo
1. **Trigger** post-visita (reusar `send_communication_triggers` o un trigger nuevo — a tu criterio).
2. **Atajo:** si el cliente ya respondió la encuesta como promotor (`califica_para_review_publico=True`) → Luna va **directo a pedir reseña** (no re-preguntar). Evitar doble pedido.
3. **Si no respondió la encuesta:** Luna pregunta cálido "¿cómo lo pasaron?" → gating:
   - Claramente positivo → **pedir reseña** con link directo.
   - No positivo / ambiguo → **recovery** (marcar `requiere_followup` / mandar a la bandeja para Deborah). **DEFAULT SEGURO: ante la duda, NO pedir reseña.**
4. ⚠️ **Gating robusto:** el gateo es crítico (no pedir reseña a un detractor). Como el modelo de Luna es liviano (gemini-2.5-flash), recomiendo gatear de forma **determinística**: micro-NPS por WhatsApp ("¿qué tan probable es que nos recomiendes? responde un número del 0 al 10") → ≥9 promotor = link; ≤6 = recovery; 7-8 = agradecer. Alternativa: clasificación de sentimiento con default seguro a recovery. Decisión tuya — ver patrón en el repo de memoria sobre determinismo de modelos livianos.

## Mensajes (borrador, editables)
- **Saludo:** "Hola [nombre] 🌿 ¿Cómo lo pasaron en Aremko? Nos encanta saber cómo estuvo su experiencia junto al río."
- **Pide reseña:** "¡Qué alegría leer eso! 🌿 Si nos regalan un minuto, una reseña en Google ayuda muchísimo a que más personas descubran este rincón junto al río 🙏 → https://maps.app.goo.gl/zSoVC4kFjS87Lfez7 ¡Gracias de corazón!"
- **Recovery:** "Lamento mucho que no haya sido lo que esperaban 🙏 ¿me cuentan qué pasó? Quiero ayudarles."

## Link de reseña
`https://maps.app.goo.gl/zSoVC4kFjS87Lfez7` (ficha Aremko Aguas Calientes Puerto Varas, CID 0xff605279b5c18ab2). Jorge confirma que abre el cuadro de escribir; quizá se cambie luego por el `g.page/r/…/review` (más directo).

## Fuera de alcance de H-032
- Responder reseñas automáticamente / borrador IA → futuro.
- Automatizar ReviewSnapshot vía Google API → futuro.

## Preguntas abiertas para django
1. ¿Reusar `send_communication_triggers` para el trigger post-visita o uno nuevo?
2. ¿Gating por micro-NPS (número, determinístico) o por sentimiento del LLM con default seguro?
3. ¿Cómo evitar doble pedido si ya respondió la encuesta?
4. ¿Dónde/cómo marca al detractor para que caiga en la bandeja de recovery de Deborah?
