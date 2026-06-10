# HANDOFFS — Bitácora de encargos entre agentes (Django ↔ aremko-cli)

> Fuente de verdad del trabajo cruzado entre el **agente Django**
> (`~/dev/booking-system-aremko`) y el **agente aremko-cli**
> (`~/Documents/GitHub/aremko-cli.nosync`). Si se corta la sesión/energía,
> este archivo + `git log` reconstruyen en qué quedamos.

## Tabla de handoffs

| ID | Qué | Implementa | Estado | Última actualización |
|----|-----|-----------|--------|----------------------|
| H-001 | Antiduplicado 48 h + orden gracias→resumen + cron normalizar ciudades (bandeja Conexión-Masajes) | Django → luego aremko-cli (UI) | ✅ IMPLEMENTADO (Django, `a10d1c9`) — falta UI flags/forzar en aremko-cli y agendar cron-job.org | 2026-06-10 (agente Django) |

## Estados

`SOLICITADO` → `EN PROGRESO (lado X)` → `IMPLEMENTADO (esperando al otro lado)` → `INTEGRADO` → `CERRADO`

- **SOLICITADO**: existe el `BRIEF_H-xxx_*.md`, nadie lo tomó aún.
- **EN PROGRESO (lado X)**: el agente X está trabajando. ⚠️ Marcar ANTES de empezar.
- **IMPLEMENTADO**: un lado terminó y publicó su `RESPUESTA_H-xxx_*.md`; falta el otro.
- **INTEGRADO**: ambos lados desplegados, falta validación de Jorge en producción.
- **CERRADO**: validado funcionando.

## Reglas del protocolo (para ambos agentes)

1. **Un ID por encargo cruzado**: serie `H-001`, `H-002`, … (los AR-### siguen
   siendo para bugs/issues internos del booking system). Los documentos llevan
   el ID: `docs/BRIEF_H-002_<tema>.md` y `docs/RESPUESTA_H-002_<tema>.md`.
2. **Commit + push del cambio de estado ANTES de empezar a trabajar** (fila →
   `EN PROGRESO (Django)` o `EN PROGRESO (aremko-cli)`), y de nuevo al terminar.
   El estado vive en git, no en la memoria de la sesión.
3. **Este archivo vive solo en el repo Django** (aquí ya viven los briefs).
   El agente aremko-cli lo lee y edita directamente en
   `~/dev/booking-system-aremko/docs/HANDOFFS.md` y commitea SOLO este archivo
   (y briefs/respuestas) en este repo — nunca código del otro lado.
4. **Tras un corte** (energía, sesión, contexto): leer esta tabla; si hay un
   `EN PROGRESO`, revisar `git log --oneline -10` y `git status` del repo que
   implementa para ver qué alcanzó a commitearse. No re-implementar sin
   verificar primero.
5. **Mensajes de commit de la bitácora**: `docs(handoffs): H-xxx → <estado>`.
6. **Histórico previo al protocolo** (referencia): brief de la bandeja masajes
   (`BRIEF_BANDEJA_MASAJES_AREMKO_CLI.md`), respuesta geo
   (`RESPUESTA_OUTBOX_GEO_AREMKO_CLI.md`) — anteriores a la numeración, no se renombran.
