# Contrato H-067 — `PublicacionPlanificada.metricas` (v1)

**Autor:** agente aremko-cli · 2026-07-18 · Estado: v1 vigente
**Productor:** cosecha Go en aremko-cli (`GET /api/v1/cron/publicaciones-metricas`, cron viernes AM)
**Consumidores:** Django (`publicacion_actualizar` guarda; brief lee), front aremko-cli (card de métricas), futuro port M17 multi-tenant y capa `Leccion` (PLAN_M17 §9 en datamatic-hospitality).

Este documento es la fuente de verdad del esquema. Si el esquema cambia, se
incrementa `v` y se anota acá — los consumidores no deben asumir campos no
listados, y deben tolerar `v` mayores ignorando campos desconocidos.

## Flujo

1. La cosecha corre viernes AM (cron-job.org → endpoint Go, token `REPORTE_CRON_TOKEN`). Dry-run por defecto; `apply=1` escribe.
2. Busca `PublicacionPlanificada` con `estado='publicada'` y `published_url` de Instagram en las últimas 4 semanas (`?semanas=`, tope 8).
3. Matchea contra la media propia de la cuenta por **shortcode** del permalink (tolera `/p/` vs `/reel/`, query params, mayúsculas, trailing slash). La URL que pega Angélica basta; no se guarda media-id por adelantado.
4. Pide insights SOLO de las matcheadas y arma el objeto `metricas` completo (merge del historial client-side).
5. `POST publicacion_actualizar {"metricas": {...}}` → **Django hace REPLACE simple del campo** (el merge ya viene hecho). La cosecha verifica en la respuesta serializada que el campo se persistió.

## Esquema v1

```json
{
  "v": 1,
  "fuente": "instagram_graph",
  "fetched_at": "2026-07-18",
  "media_id": "17895695668004550",
  "permalink": "https://www.instagram.com/reel/ABC123xyz/",
  "media_type": "REELS",
  "caption_publicado": "texto completo del caption tal como quedó publicado…",
  "snapshots": [
    {
      "fetched_at": "2026-07-18",
      "reach": 1234,
      "saves": 21,
      "shares": 9,
      "views": 4567,
      "likes": 87,
      "comments": 6
    }
  ],
  "tasas": {
    "valiosa": 0.0243,
    "interaccion": 0.0754
  }
}
```

### Semántica de campos

| Campo | Notas |
|---|---|
| `v` | Versión del esquema. Hoy `1`. |
| `fuente` | `"instagram_graph"` (cosecha automática). Reservado: `"manual"` para cuando Angélica pegue números a mano (TikTok/GBP/email, fuera de F3-a) — en ese caso solo se garantiza `v`, `fuente`, `snapshots` parciales. |
| `fetched_at` | Fecha (YYYY-MM-DD) de la última cosecha que tocó este objeto. |
| `caption_publicado` | Caption REAL del post en IG. Insumo del **% publicado-sin-editar**: Django lo compara contra el caption generado en `copy_json`. ⚠️ Comparación TOLERANTE (pedido Datamatic): normalizar trim/espacios múltiples/saltos de línea y usar similitud (ratio ≥ 0.95 = sin_editar), NO igualdad exacta — si no, la meta-métrica nace sesgada. |
| `snapshots[]` | Historial semanal, orden cronológico, **tope 12** (~3 meses). Una re-corrida el MISMO día reemplaza el último snapshot (no duplica). `0` en una métrica = no disponible para ese media_type (p.ej. `shares`/`views` no existen en todos los tipos; la cosecha degrada a `reach,saved` si Graph rechaza el set completo — puede venir además `insights_error` informativo en el snapshot). |
| `tasas.valiosa` | `(saves + shares) / reach` del último snapshot. La métrica de ranking mientras no exista atribución de consultas/ventas (jerarquía de Jorge: consultas/ventas > guardados/compartidos > alcance > likes). |
| `tasas.interaccion` | `(likes + comments) / reach` del último snapshot. Secundaria — los likes NUNCA como métrica principal. |

### Reglas para consumidores

- **Django/brief:** rankear top/bottom por `tasas.valiosa` (desempate: `reach`); no comparar publicaciones de semanas distintas sin considerar que los snapshots más viejos tienen más días de acumulación. La sección "Decisiones de la semana" (persistir/abandonar/re-enfocar) se arma con las últimas 2-4 semanas.
- **Front aremko-cli:** mostrar último snapshot + badge con `tasas.valiosa`; si `metricas` está vacío o sin `v`, no mostrar nada (pieza aún sin cosechar).
- **Consultas/ventas:** NO están en v1 (sin fuente de atribución todavía). Cuando existan, entrarán como campos nuevos con bump de versión — no inventar proxies mientras tanto.

## Pendiente del lado Django (para cerrar el ciclo)

1. `publicacion_actualizar` acepta `metricas` (dict completo, replace).
2. Sección "Decisiones de la semana" en el brief (pasada 1).
3. % publicado-sin-editar con la comparación tolerante de captions descrita arriba.
