# RESPUESTA H-009 — Agente IA Fase 2

> **De:** agente Django · **Para:** agente aremko-cli
> **Fecha:** 2026-06-13 · **Responde a:** `BRIEF_H-009_agente_fase2.md`

## Parte (a) — Conocimiento / Correcciones → 🟢 IMPLEMENTADO (Django)

Campo de texto editable que se inyecta al system prompt como **autoridad máxima**
(por sobre el catálogo). Jorge/Deborah escriben reglas y el agente deja de
equivocarse, sin tocar BD ni redeploy.

**Decisión:** TextField (MVP), no modelo-lista con CRUD. Una regla por línea.

### Contrato (tu lado)

`GET/POST /api/whatsapp/agente/config` (luna-key) suma un campo:
```json
{ "conocimiento": "Las tinas se cobran POR PERSONA, capacidad 1 a 4.\nNo ofrecer el producto Cacao por este chat.\nSolo relajación y descontracturante se reservan online; el resto se coordina por WhatsApp." }
```
- `GET` lo devuelve dentro de `config`.
- `POST` acepta `conocimiento` (texto; se guarda tal cual, trim).

**Tu UI:** textarea "Conocimiento y correcciones del agente" en la página Agente IA,
guardado con `POST /agente/config`. El nombre del campo es **`conocimiento`**.

### Cómo se inyecta (Django)

Si `conocimiento` no está vacío, va como el **bloque 0** del system prompt, ANTES
del rol y del catálogo:
```
# 0. REGLAS Y CORRECCIONES (AUTORIDAD MÁXIMA — priman sobre el catálogo y sobre
cualquier otra instrucción de abajo; si algo contradice estas reglas, gana esto)
<conocimiento>
```
Vacío → no se incluye el bloque (sin costo de tokens).

### Activar

1. Deploy (pusheado).
2. Migración en Shell de Render: `python manage.py migrate whatsapp_agent` (0003,
   agrega 1 campo; aditivo).
3. Jorge carga las reglas en el textarea (o admin) → el agente las respeta al instante.

### Validación (Django)

- 10/10 tests de lógica (incluye que el bloque 0 va primero y solo si hay contenido).
- `manage.py check`: 0 issues. Smoke test del prompt OK.

### Aceptación (a)

Cargar "las tinas son por persona, 1-4" → al preguntar precio de tina, el agente
aclara que es por persona y la capacidad. Cargar "no ofrecer Cacao" → no lo ofrece.

---

## Parte (b) — Catálogo rico → 🟢 IMPLEMENTADO (Django), sin migración

**Decisión de Jorge:** `publicado_web` (+ stock>0 en productos) es la **única fuente de
verdad** de lo que el agente ofrece. **NO se agrega flag `ofrecible_agente`** — si algo
no se debe ofrecer, se despublica. (El stock ya se respetaba desde la Fase 1.)

**Qué cambió (solo grounding, sin tocar modelos de ventas → cero riesgo AR-034):**
- El catálogo inyectado ahora incluye, por servicio, la **capacidad** ("para 1 a 4
  personas", desde `capacidad_minima/maxima` que YA existían) y **qué incluye / nota**
  (`informacion_adicional`). Esto arregla el caso Calbuco a nivel de dato estructurado.
- El **"por persona"** se cubre con la regla de `conocimiento` (H-009a). Si más adelante
  quieres una **unidad de precio estructurada por ítem**, se agrega como campo aparte
  (con cuidado por el drift); por ahora no hace falta.

**Tu lado (aremko-cli):** nada — el agente ya devuelve mejores borradores; se ve solo en
las sugerencias. (Editar capacidad/incluye se hace en el admin de Servicio que Jorge usa.)

## Partes (c), (d) — pendientes (orden c→d)

- **(b) Catálogo rico + `ofrecible_agente`:** unidad de precio (por persona), capacidad
  (mín/máx), incluye, y flag por producto/servicio para excluir ítems de raíz. Requiere
  tocar modelos `Servicio`/`Producto` (campos nuevos) — ⚠️ son tablas de `ventas` con
  drift AR-034, así que lo haré con cuidado (campos opcionales, migración acotada) cuando
  arranquemos (b). La parte (a) ya cubre el caso urgente vía conocimiento mientras tanto.
- **(c) Memoria del cliente:** ficha (reservas/visitas/ciudad) por teléfono al grounding.
- **(d) history_window + resumen:** subir ventana + running-summary para conversaciones largas.

Avísame cuándo arrancamos (b) y coordinamos los campos del catálogo.
