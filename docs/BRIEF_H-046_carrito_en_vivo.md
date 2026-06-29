# BRIEF H-046 — Carrito EN VIVO en la bandeja (Fase 1: solo lectura)

> **De:** agente Django (`~/dev/booking-system-aremko`)
> **Para:** agente aremko-cli (`~/Documents/GitHub/aremko-cli.nosync`)
> **Estado Django:** ✅ HECHO y vivo en prod. El endpoint de conversación ya devuelve el carrito.
> **Para aremko-cli:** **frontend puro** (el endpoint de conversación es passthrough en Go → el campo nuevo llega solo, sin tocar Go).

---

## 1. La idea (pedido de Jorge, 2026-06-29)

La vista en vivo de la cotización (el cajón que se llena solo cuando el cliente agrega/quita con
Luna) resultó **espectacular** para Deborah. Jorge quiere verla **desde antes**: que el **carrito**
se muestre llenándose en vivo DESDE que el cliente agrega el primer ítem (no recién cuando se
genera la cotización formal).

**Modelo "UNA cosa viva a la vez":**
- **Antes** de que exista la cotización → se muestra el **CARRITO en curso** (`carrito_en_curso`).
- **Después** (Luna o Deborah crea la propuesta) → se muestra la **PROPUESTA** (el cajón actual,
  `propuesta_reserva`). En ese momento `carrito_en_curso` pasa a `null` (no se muestran los dos).

**Fase 1 = SOLO LECTURA** (que Deborah lo VEA llenarse). Editar a mano + "pasar a cotización" es
**Fase 2** (otro brief).

---

## 2. Qué entrega Django (ya en prod)

El endpoint de conversación que ya consumís —`GET /api/whatsapp/conversation/` y los de
Instagram/Messenger en `/api/inbox/conversation/`— ahora trae un campo nuevo **`carrito_en_curso`**
(además de `propuesta_reserva` y `reserva_creada`):

```jsonc
"carrito_en_curso": {
  "servicios": [
    // MISMO shape que propuesta_reserva.servicios → reusá el mismo renderer del cajón
    { "servicio_id": 12, "servicio_nombre": "Tina Hidromasaje Llaima", "fecha": "2026-07-01",
      "hora": "16:30", "cantidad_personas": 2, "subtotal": 60000 },
    { "producto_id": 5, "servicio_nombre": "Jugo Natural de Melón", "fecha": null, "hora": null,
      "cantidad_personas": 1, "subtotal": 3500, "es_producto": true }
  ],
  "total": 63500,
  "editable": false          // Fase 1: solo lectura (Fase 2 lo pondrá en true)
}
```

Reglas que YA aplica Django (no tenés que reimplementarlas):
- `carrito_en_curso` es **`null`** si: no hay carrito con ítems, o el carrito está viejo (tocado
  hace > 24h), o **ya existe una `propuesta_reserva` vigente** (ahí mandás la propuesta, no el carrito).
- Las líneas vienen con el **mismo shape** que `propuesta_reserva.servicios` (servicio con
  `servicio_id`+fecha/hora; producto con `producto_id`, `fecha/hora=null`, `es_producto:true`,
  cantidad en `cantidad_personas`). El descuento de pack: igual que el cajón, calculalo en el front
  como `Σ subtotales − total` y mostralo como línea "Descuento −$X".

---

## 3. Tarea aremko-cli (Fase 1, frontend)

En el componente del cajón (`CotizacionCajon.tsx` o un hermano), agregar el render del
**carrito en curso** cuando llega `carrito_en_curso != null` (y no hay `propuesta_reserva`):

- Panel con look del cajón pero rotulado distinto para que se note que es **borrador en vivo**, ej.
  encabezado **"🛒 Carrito en curso"** (ámbar/gris, NO el amarillo "Cotización lista"), con la lista
  de líneas + total + línea de descuento (si `Σ − total > 0`).
- **Solo lectura** en Fase 1: SIN botón "Poner cotización en el mensaje" ni "Aprobar" (eso es de la
  propuesta). Podés poner un texto chico "Se actualiza en vivo mientras Luna conversa".
- Se refresca con el polling que ya hacés de la conversación (cada ~12s) → Deborah lo ve llenarse.
- `types.ts`: agregá el tipo `CarritoEnCurso { servicios: LineaCotizacion[]; total: number; editable: boolean }`
  y el campo opcional en el tipo de la conversación. Reusá el tipo de línea de la cotización.

**NO toca Go** (los endpoints de conversación son passthrough crudo; el campo nuevo ya pasa).

---

## 4. Criterios de aceptación (Fase 1)
1. Al agregar el primer ítem con Luna, aparece el panel "🛒 Carrito en curso" y se va actualizando
   (agregar/quitar) en cada refresco.
2. Cuando se genera la cotización (propuesta), el panel del carrito **desaparece** y queda el cajón
   "Cotización lista" de siempre (porque Django manda `carrito_en_curso: null`).
3. No aparece en conversaciones sin ítems ni en carritos viejos (>24h).
4. `tsc` 0 + `next build` OK.

## 5. Fase 2 (NO ahora, para que lo tengas en mente)
Editar el carrito a mano + botón **"Pasar a cotización"** (crea la propuesta desde el carrito y la
manda al cajón). Reusará la maquinaria de edición de H-042 + un endpoint Django nuevo
("crear propuesta desde el carrito"). Cuando lleguemos, Django pondrá `editable: true`.

## 6. Gotcha aremko-cli
- **Deploy NO automático** del backend (`feedback_aremko_cli_deploy_manual`) — pero Fase 1 es solo
  frontend (Vercel auto-deploya en push). Igual confirmá que quedó vivo.
