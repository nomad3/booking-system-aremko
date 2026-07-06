# Mensaje para Simón — acceso de escritura de AgentProvision al repo Django

**Contexto:** dejamos armado un buzón de coordinación directa entre el agente Django
(este repo) y el agente AgentProvision, en `docs/AP_MENSAJES.md` +
`docs/HANDOFFS_AGENTPROVISION.md`. Hoy AgentProvision solo tiene **lectura** sobre
`nomad3/booking-system-aremko` — por eso cada actualización de su lado (ej. el reporte
F0 de AP-002) la tengo que registrar yo "en su nombre" a partir de lo que Jorge relaya,
en vez de que el propio agente commitee su entrada.

**Lo que se necesita:** que agregues como colaborador con permiso de **escritura**
(Write) al repo `nomad3/booking-system-aremko` la cuenta/bot con la que AgentProvision
hace commits (la que uses para que corra sus propios `git push`). Con eso el agente AP
puede escribir directo su entrada en `docs/AP_MENSAJES.md` y actualizar el Estado de sus
filas `AP-0xx` en `docs/HANDOFFS_AGENTPROVISION.md`, sin pasar por Jorge como relay.

**Protocolo ya definido (para que AP lo siga al escribir):**
- `git pull` antes de cualquier `git push` (evita pisarse).
- Una entrada nueva = un commit chico, agregada arriba del log en `AP_MENSAJES.md`.
- Si el mensaje avisa que terminó un trabajo, además actualiza el Estado de su fila
  `AP-0xx` correspondiente en `HANDOFFS_AGENTPROVISION.md`.
- Edita solo lo suyo (sus propias entradas/filas), nunca lo que escribió el agente Django.

No es urgente para que AP-002 avance en sí (correr el F0 real con `AUTOMATION_API_KEY`
no depende de esto) — es solo para que la comunicación entre los dos agentes deje de
pasar por Jorge como intermediario.
