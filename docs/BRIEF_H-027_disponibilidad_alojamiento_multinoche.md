# BRIEF H-027 — Disponibilidad de alojamiento multi-noche para Luna (agente)

**Pedido de Jorge (2026-06-18).** Continuación de H-011 (disponibilidad del agente).
Hoy Luna responde disponibilidad de servicios de un día (tina/masaje y cabaña como
1 noche). Falta que responda **alojamiento de varias noches** correctamente.

Diseñado con el agente aremko-cli + Jorge. Alcance de esta fase: **solo Luna (chat)**.
La reserva web multi-noche queda para después.

## Requisitos de negocio (cerrados por Jorge)
1. Alojamiento = **máximo 2 personas** por cabaña.
2. **Misma cabaña toda la estadía** (no Torre una noche y Laurel la siguiente).
3. **Precio**: el cálculo se mantiene como hoy → `precio_por_persona × personas × nº_noches`.
   PERO **Luna NUNCA debe mostrar el valor por persona**; solo el **total por noche** y el
   **total de la estadía**. (Tarifa plana: todas las noches valen igual → total_por_noche
   constante.)
4. El **martes cerrado NO aplica al alojamiento** (solo a tinas/masajes/spa): una estadía
   puede llegar, quedarse y cruzar la noche del martes sin problema.

## Flujo del agente (prompt)
1. Cliente pide alojamiento con fechas (ej. "cabaña para el 23 y 24").
2. **Luna desambigua ANTES de consultar** cuando el nº de noches no es explícito:
   > "¿1 noche (entras el 23, sales el 24) o 2 noches (entras el 23, sales el 25)?"
   Si el cliente ya dijo las noches ("2 noches desde el 23"), salta este paso.
3. Luna necesita: **fecha de llegada, fecha de salida** (o nº de noches) y **personas (1–2)**.
4. Con eso, llama a la herramienta de disponibilidad de alojamiento.
5. Muestra las cabañas libres TODA la estadía + total por noche + total estadía.
   - Si piden 3+ personas → aclarar que las cabañas son para máx 2 (combinar 2 cabañas = futuro).
   - Si ninguna cabaña está libre toda la estadía → decirlo (ofrecer alternativas = futuro).

## Herramienta sugerida (tool-calling)
`consultar_disponibilidad_alojamiento(fecha_llegada, fecha_salida, personas)`
- `noches_ocupadas` = desde `fecha_llegada` hasta `fecha_salida` − 1 día
  (ej. llegada 23 / salida 25 → noches del 23 y 24 = 2 noches).
- Para cada `Servicio tipo_servicio='cabana'`, `publicado_web=True`/`activo=True`, **excluido de
  complementos** (igual que el grounding de H-011): califica solo si está **libre en TODAS** las
  noches ocupadas. Reusar el motor del calendario por noche e **intersectar** la disponibilidad.
- Respuesta por cabaña: `{ nombre, total_por_noche, noches, total_estadia }`.
  **NO incluir el precio por persona en la respuesta del tool** (para que el LLM no lo muestre ni
  haga aritmética). `total_por_noche = precio_por_persona × personas`; `total_estadia = total_por_noche × noches`.
- La noche de martes NO se descarta para cabañas (a diferencia de tinas/masajes).

## Preguntas para el lado Django (de su modelo, confírmenlo)
1. **¿Cómo se almacena hoy la ocupación de una cabaña por noche?** ¿una `ReservaServicio` por
   noche, o una que abarca el rango de fechas? Eso define cómo leer la disponibilidad multi-noche
   (la herramienta debe detectar la cabaña ocupada en cualquiera de las noches del rango).
2. ¿El motor actual (`extraer_slots_para_fecha`/`verificar_disponibilidad`) sirve por-noche para
   cabañas, o conviene una consulta directa de ocupación por (cabaña, fecha)?
3. Sin migración esperada (es read-only + presentación). Confirmar.

## Front (aremko-cli)
Nada nuevo por ahora: Luna ya responde en la bandeja; esto es lógica del agente + tool en Django.
Validación: probar en Shell de Render (`probar_disponibilidad` / `probar_agente_wa`) y luego un DM real.

**Mirror/contexto:** H-011 (disponibilidad agente, por persona) + [[memoria cabaña/tina nivel 2]].
