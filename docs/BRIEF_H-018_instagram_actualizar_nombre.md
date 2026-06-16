# BRIEF H-018 — Actualizar el nombre del cliente en conversaciones de Instagram

**Pedido por:** Jorge (vía agente aremko-cli) · 2026-06-16
**Lado que implementa:** Django (app `inbox_omnicanal`)
**Tamaño:** chico (1 cambio en el inbound de Instagram)

## Síntoma
En la bandeja, varias conversaciones de Instagram muestran el **IGSID crudo**
(ej. `854589897056982`) en vez del nombre del cliente. Solo algunas muestran el
nombre/@usuario (las creadas después de que aremko-cli empezó a resolverlo).

## Causa
aremko-cli **ya resuelve** el nombre del cliente (display name; si no hay, el
`@usuario`) vía la Graph API de Instagram y lo manda en `contact_name` en **cada**
inbound no-eco (`POST /api/instagram/inbound`). Pero el `contact_name` parece
guardarse **solo al crear** la conversación/contacto: las conversaciones creadas
antes (cuando aremko-cli mandaba `contact_name` vacío) se quedaron sin nombre y no
se actualizan aunque el cliente siga escribiendo.

## Pedido (alcance acotado — Jorge eligió "solo A", SIN backfill)
En el handler del inbound de Instagram (`inbox_omnicanal`): cuando llega un inbound
con **`contact_name` no vacío**, **ACTUALIZAR** el nombre del contacto/conversación
(no solo setearlo en la creación). Así las conversaciones que hoy muestran el IGSID
se **llenan solas** cuando el cliente vuelve a escribir.

Detalles:
- Solo actualizar si el `contact_name` entrante es no vacío (no pisar un nombre con
  vacío).
- Aplica al **contacto del cliente** (el IGSID que NO es la cuenta `17841400756478364`),
  igual que la lógica de keyeo del inbound.
- Si más adelante hay edición manual de nombre (como el `editar-nombre` de WhatsApp),
  esa debería tener prioridad; por ahora no existe para IG, así que basta con
  actualizar `contact_name`.

## NO incluye
- **Backfill** de las conversaciones existentes (Jorge lo descartó por ahora). Si se
  quisiera después, requeriría que aremko-cli resuelva los nombres (tiene el token) y
  un endpoint Django para setear `contact_name` por `(canal, external_id)` — queda
  para un H-019 si se decide.

## aremko-cli
Nada nuevo: ya manda `contact_name` en cada inbound (y ya prefiere el display name
sobre el @usuario, commit `a8eb2cc`). Solo espera que Django actualice el campo.

## Resultado esperado
En la bandeja, las conversaciones de Instagram muestran el nombre del cliente
(display name o @usuario) en cuanto el cliente manda un mensaje nuevo, en vez del
IGSID. (Algunos usuarios no exponen su perfil por privacidad → ahí seguirá el IGSID;
probablemente se destrabe con App Review.)
