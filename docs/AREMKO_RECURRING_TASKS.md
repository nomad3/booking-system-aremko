# Tareas Recurrentes — Aremko Marketing

**Versión:** v1.0 · **Fecha:** 2026-05-01

Tareas que se repiten en el tiempo. No tienen número de fase porque viven aparte del plan maestro. Todas deben quedar absorbidas eventualmente por el agente programado de los lunes.

**Documento relacionado:** [docs/MARKETING_PLAYBOOK.md](MARKETING_PLAYBOOK.md) (cadencias y voz)

---

## DIARIAS

### D1 — Stories de Instagram (1-2 al día)
- **Quién:** Jorge (o equipo asignado)
- **Tiempo:** 2-5 min/story
- **Cuándo:** mañana (8-10am) y/o tarde (17-19h)
- **Tipos rotativos** (no repetir el mismo tipo 2 días seguidos):
  - **Detrás de escena**: preparación de cabaña, ambientación, masajistas en acción
  - **Naturaleza**: río, bosque, paneles solares, atardecer, animales
  - **Cliente real**: con su consentimiento, mostrando momento (ej. tina humeante)
  - **Datos del día**: temperatura del agua, clima, "hoy llegamos a 38.2°C"
  - **Recordatorios prácticos**: "abrimos hasta medianoche", "domingo a jueves $110k"
  - **Educativo cortito**: "Sabías que la tina fría se llama Yates?"
- **Regla:** todas con sticker link al blog cuando aplique (`?utm_source=instagram&utm_medium=story`)

### D2 — Revisar y responder DMs Instagram
- **Quién:** Jorge (o equipo)
- **Tiempo:** 10-15 min/día
- **Cuándo:** 2 chequeos al día (mañana + tarde)
- **SLA:** responder en menos de 4h
- **Casos especiales:** si DM viene de palabra clave de Reel (`TINAS`, `GARANTÍA`, etc.) → respuesta automática (ManyChat) + seguimiento manual si pregunta más

### D3 — Revisar mensajes Google Business Profile
- **Quién:** Jorge
- **Tiempo:** 2 min/día
- **SLA:** responder en menos de 2h (Google premia respuesta rápida en ranking local)

### D4 — Revisar reviews nuevas (Google + TripAdvisor + Trip.com)
- **Quién:** Jorge
- **Tiempo:** 5 min/día
- **Acción:** responder TODAS las reviews — positivas en 24h, negativas en menos de 12h con tono profesional

---

## SEMANALES

### LUNES

#### L1 — Agente programado entrega brief (10:00 AM Chile)
- **Quién:** Claude (agente)
- **Output:** documento `docs/weekly-briefs/YYYY-MM-DD.md` + notificación Telegram a Jorge
- **Contenido del brief:**
  - Resumen métricas semana anterior (GA4 + GSC)
  - Decisión de la semana (qué amplificar, qué cambiar)
  - Drafts listos para todos los canales (GBP, Reels, carrusel, email engaged)
  - Checklist de publicaciones del día con horarios sugeridos
  - Estado del plan maestro: tareas en 🟡 esta semana

#### L2 — Publicar 1 GBP post (10:30-11:00 AM)
- **Quién:** Jorge
- **Tiempo:** 5 min
- **Contenido:** definido por brief de L1, vinculado al blog post de la semana
- **Recordatorio:** Google premia frecuencia semanal en GBP

#### L3 — Publicar 1 blog post (10:00-12:00 AM)
- **Quién:** Claude (genera) + Jorge (revisa y publica)
- **Tiempo:** 1h
- **Pre-requisito:** skill `/blog-aremko` funcionando (Tarea 2.7 del plan maestro)
- **Cadencia:** lunes de cada semana
- **UTM:** sin UTM en URL canónica, con UTM en links promocionales

#### L4 — Publicar Reel #1 (18:00-20:00, mejor hora IG)
- **Quién:** Jorge graba (script de Claude del brief)
- **Tiempo:** 30 min grabación + 15 min edición
- **Framework:** 5 partes (gancho, contexto, moraleja, solución, CTA palabra clave)
- **Métrica clave:** RI (retención) a las 24h y 48h

---

### MARTES

#### M1 — Boost de Reel ganador semana anterior (si aplica)
- **Quién:** Claude (estrategia) + Jorge (Meta Ads)
- **Tiempo:** 10 min
- **Condición:** si hubo Reel con RI >50% la semana pasada
- **Presupuesto:** $5-10 USD por 3 días, lookalike de followers + geo Sur de Chile

---

### MIÉRCOLES

#### W1 — Publicar 1 carrusel educativo IG (18:00-20:00)
- **Quién:** Jorge publica (asset de Claude del brief)
- **Tiempo:** 15 min
- **Tema:** ligado a contenido del blog de la semana, tono educativo (no viral)
- **Cuando NO publicar:** si la idea no aporta valor — no publicar por publicar

#### W2 — Email a segmento "engaged" (10:00 AM)
- **Quién:** Claude (copy) + Jorge (envío SendGrid)
- **Tiempo:** 30 min
- **Audiencia:** ~500-800 que abrieron último email
- **Contenido:** valor (artículo del blog) o oferta soft (1 de cada 4)
- **Pre-requisito:** Tarea 5.4 del plan maestro

---

### JUEVES

#### J1 — Publicar Reel #2 (18:00-20:00)
- **Quién:** Jorge graba
- **Tiempo:** 30 min grabación + 15 min edición
- **Estrategia:**
  - Si Reel del lunes pasó 50% RI → variación del mismo concepto (Víctor Eras: doblar la apuesta)
  - Si no → idea nueva del backlog del playbook
- **Framework:** mismo de 5 partes

---

### VIERNES

#### V1 — Resumen métricas de la semana
- **Quién:** Claude (automatizado) → Jorge revisa
- **Tiempo:** 10 min revisión
- **Output:** mensaje Telegram con:
  - Visitas blog (vs semana anterior)
  - Top fuente de tráfico
  - RI de los 2 Reels
  - DMs con palabra clave generados
  - Reviews nuevas
  - Reservas atribuidas a marketing digital
  - **Decisiones para próxima semana**

#### V2 — Decidir qué Reel boostear lunes próximo
- **Quién:** Jorge (con recomendación de Claude)
- **Tiempo:** 5 min
- **Output:** anotado en agente programado para que el lunes lo ejecute

---

### SÁBADO Y DOMINGO

> **No hay publicaciones programadas obligatorias** los fines de semana.
>
> **Sí Stories** (D1) — los fines de semana tienen **mayor engagement orgánico** porque la audiencia está descansando.
>
> **Excepción:** si hay evento especial (apertura, ambientación, cliente VIP, naturaleza espectacular) → publicar siempre.

---

## QUINCENALES

### Q1 — Publicar 1 reel testimonial / "case study"
- **Quién:** Jorge graba con cliente real (con consentimiento)
- **Cadencia:** cada 2 semanas
- **Formato:** 30-60s, cliente cuenta su experiencia
- **Pre-requisito:** consentimiento firmado del cliente

---

## MENSUALES

### PRIMER LUNES DEL MES

#### MES1 — Newsletter mensual a full list (3.000 contactos)
- **Quién:** Claude (copy) + Jorge (envío SendGrid)
- **Tiempo:** 2h
- **Audiencia:** todos los 3.000 contactos
- **Contenido:** digest de los 4 posts del mes + oferta destacada del mes (gift cards en mes pre-celebración, pack temporada baja, etc.)

#### MES2 — Revisión global del plan maestro
- **Quién:** Jorge + Claude (agente lo prepara)
- **Tiempo:** 1h
- **Acciones:**
  - Cuántas tareas pasaron a 🟢 el mes pasado
  - Qué se atrasó y por qué
  - Cambios al playbook (lo que aprendimos)
  - Próximas 4 tareas a priorizar
  - Cambios al calendario de eventos locales si vienen fechas relevantes

---

### CUALQUIER DÍA DEL MES

#### MES3 — Análisis de competencia (mensual rotativo)
- **Quién:** Claude (automatizado)
- **Cadencia:** cada mes revisa 1 competidor de los 5 (rotativo)
- **Output:** documento con: nuevas reviews, cambios en web, nuevos servicios, ideas para Aremko

#### MES4 — Email cumpleaños a clientes del mes
- **Quién:** Claude (automatizado, depende de Tarea 5.6)
- **Cadencia:** trigger automático por fecha de nacimiento
- **Contenido:** voucher $20-30k descuento válido 30 días

---

## TRIMESTRALES

### T1 — Análisis profundo y reset estratégico
- **Quién:** Jorge + Claude
- **Tiempo:** 3h
- **Acciones:**
  - Revisión de KPIs vs metas
  - Validación con clientes reales (5-10 entrevistas — Tarea 1.X tipo "Validación")
  - ¿El playbook sigue vigente? Editar si no
  - ¿Las personas de buyer siguen vigentes?
  - Cambio de fase del plan maestro si corresponde

### T2 — Estacionalidad — preparar campañas próximo trimestre
- **Quién:** Claude (estrategia) + Jorge (validación)
- **Tiempo:** 2h
- **Output:** calendario de promociones específicas según temporada (ver eventos en playbook)

---

## REGLAS GENERALES

### Si no se publicó algo programado
- ❌ No "recuperar" publicando 2 al día siguiente — Instagram penaliza picos
- ✅ Saltar y continuar la semana siguiente con cadencia normal
- ✅ Anotar en log el motivo (para el reporte semanal)

### Si una tarea recurrente se vuelve "ruido"
- Si una tarea no se ejecuta 3 semanas seguidas → revisar si tiene sentido mantenerla
- Si nadie ve el output de una tarea → eliminar

### Cuándo agregar una nueva tarea recurrente
- Solo si pasa 4 semanas siendo "tarea ad-hoc repetida" sin frame
- Pasa por revisión: ¿realmente repetir, o fue ruido específico?

---

## Notificaciones

- **Canal preferido del usuario:** WhatsApp y Telegram (no email)
- **Agente programado:** entrega brief por **Telegram** los lunes 10am
- **Reportes semanales (V1):** Telegram los viernes
- **Alertas críticas** (review negativa, sitemap caído, etc.): WhatsApp inmediato
