# BRIEF H-026 — Borrador de IA (Luna) en Messenger

**Pedido de Jorge (2026-06-18):** que el agente Luna sugiera un borrador de respuesta
en las conversaciones de **Messenger**, igual que ya lo hace en Instagram (H-019) y
WhatsApp (H-007).

**Mirror exacto de H-019 (Instagram).** El agente (`whatsapp_agent._producir_borrador`)
es agnóstico del canal: solo necesita el mensaje entrante + el historial. Hoy la rama
`canal == 'messenger'` de `inbox_omnicanal/views.py::conversation()` (líneas ~668-692)
**NO** incluye `sugerencia_agente`; la de Instagram sí.

## Lo que pide (lado Django)

En `inbox_omnicanal/views.py`:

1. **`_historial_messenger(external_id, antes_de_ts, window)`** — idéntico a
   `_historial_instagram` pero `canal='messenger'`.
2. **`_contexto_saludo_messenger(external_id, entrante_timestamp)`** — idéntico a
   `_contexto_saludo_instagram` pero `canal='messenger'`.
3. **`_sugerencia_messenger(external_id)`** — idéntico a `_sugerencia_instagram` pero
   filtrando `canal='messenger'` y usando los helpers de arriba.
4. En la rama `canal == 'messenger'` de `conversation()`, agregar al JSON:
   ```python
   'sugerencia_agente': (
       _sugerencia_messenger(external_id)
       if _truthy(request.GET.get('sugerencia', '0')) else None
   ),
   ```
   (mismo patrón lazy / opt-in `&sugerencia=1` que Instagram).

Sin migración (no toca modelos). Mismo shape de `sugerencia_agente` que IG/WhatsApp.

## Front (aremko-cli) — ya construido

El componente de conversación es compartido (IG + Messenger). Ya lo ajusté para que
pida `&sugerencia=1` también en Messenger y muestre el banner "✨ Borrador sugerido por
IA" con el acento azul del canal. Tolera `sugerencia_agente: null` (no muestra nada)
mientras este endpoint no lo provea → se enciende solo cuando desplieguen.

**Mirror de:** H-019 (Instagram) + H-007 (agente WhatsApp).
