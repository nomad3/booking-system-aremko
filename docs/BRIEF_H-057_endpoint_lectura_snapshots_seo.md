# BRIEF H-057 — Endpoint de lectura de snapshots SEO/GA4 (para el loop de mejora continua)

> **De:** agente aremko-cli
> **Para:** agente Django
> **Tipo:** Django expone un endpoint de solo lectura; el loop de SEO (nueva sesión dedicada) lo consume.

## 1. Contexto

Estamos armando 3 "loops" de mejora continua (sesiones dedicadas con `/loop`, agendadas):
- Meta Ads y Google Ads → ya viven en aremko-cli, funcionando ([[project_aremko_luna_interna]] no aplica, ver `docs/LOOP_META_ADS.md`/`LOOP_GOOGLE_ADS.md` en aremko-cli).
- **SEO → va en una sesión dedicada de Django** (aquí), aremko.cl únicamente por ahora (destinopuertovaras.cl queda para después).

Descubrí que **ya existe** el pipeline de datos semanal (`snapshot_weekly_traffic` lunes 9am → `GA4Snapshot`/`SearchConsoleSnapshot`; `generate_weekly_marketing_brief` lunes 10am → email). Jorge decidió que el loop de SEO queda **separado** de ese brief (que sigue igual, informativo general) — el loop es nuevo, específico de SEO accionable, con bitácora y comparación semana a semana (mismo patrón que Meta/Google Ads).

## 2. El problema puntual

Los 2 endpoints que ya existen (`POST /ventas/api/cron/snapshot-weekly-traffic/`, `POST /ventas/api/cron/marketing-brief/`) **generan** datos nuevos, y están protegidos con `X-API-KEY: {AUTOMATION_API_KEY}`. El loop de SEO corre en tu máquina local (una sesión de Claude Code dedicada), **sin ese secreto disponible ahí** — y preferimos NO poner esa clave en un archivo local de prompt (mismo criterio que usamos en H-053: los endpoints que consume un loop/agente automático deben ser públicos de solo-lectura, no requerir secretos).

**No necesitamos generar nada nuevo** — el snapshot semanal ya se genera solo (cron existente). Solo necesitamos **leer** lo que ya quedó guardado en `GA4Snapshot`/`SearchConsoleSnapshot`.

## 3. Lo que pido

Un endpoint nuevo, **público, sin auth**, mismo espíritu que `family-combinations-range` (H-053):

```
GET /ventas/api/aremko-cli/seo-snapshots/?weeks=8
```

Respuesta 200 (ajustá nombres si no calzan exacto con los campos materializados reales — usá los que ya existen en los modelos):
```jsonc
{
  "weeks_requested": 8,
  "ga4": [
    {
      "week_start": "2026-06-15",
      "sessions": 000, "total_users": 000, "conversions": 000,
      "reservation_started": 000, "reservation_completed": 000,
      "whatsapp_clicks": 000, "phone_clicks": 000, "cta_blog_clicks": 000
    }
    // ... una fila por snapshot semanal, más antigua primero
  ],
  "gsc": [
    {
      "week_start": "2026-06-15",
      "clicks": 000, "impressions": 000, "ctr": 0.0, "position": 0.0,
      "top_queries": [ {"query": "masajes puerto varas", "clicks": 0, "impressions": 0, "position": 0.0}, ... ],
      "top_pages": [ {"page": "/", "clicks": 0, "impressions": 0}, ... ]
    }
  ]
}
```
- `weeks` opcional, default 8 (≈2 meses de historia, mismo criterio que usamos para las tablas semanales de ads).
- Si hay menos de N snapshots guardados todavía, devolvé los que haya (no error).
- Sin autenticación — no es dato sensible (tráfico agregado), mismo nivel que `family-combinations-range`.

## 4. Qué hará el loop con esto (para que tengas el contexto completo)

Semanal, sesión dedicada en Django: compara el snapshot de esta semana contra el histórico, cruza contra las **keywords protegidas** de `docs/SEO_BASELINE_HOME.md` (masajes/tinajas/spa puerto varas + marca), y propone 1-3 acciones concretas. A diferencia de los loops de ads, el de SEO puede **redactar** (no solo sugerir texto): puede dejar un `BlogPost` armado con `is_published=False`, o un `SEOContent`/`HomepageConfig` con el texto propuesto SIN guardarlo aún — Nivel 2 sigue siendo "no publica/aplica sin que Jorge lo revise", pero el trabajo de redacción ya queda hecho.

## 5. Avisar cuando esté

Ruta/shape final (avisame si preferís otro nombre) y cualquier campo que no exista tal cual lo puse arriba. ¡Gracias!
