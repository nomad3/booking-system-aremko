# MIGRACIÓN M17 → DH · Arranque (para el agente Django)

> **Para:** agente Django (`~/dev/booking-system-aremko`).
> **De:** coordinador de producto (con Jorge).
> **Objetivo:** echar a andar la migración de **M17 (Asistente de Publicaciones)** desde Aremko
> (laboratorio) hacia **Datamatic Hospitality** (producto vendible).
> **Modelo de trabajo NUEVO:** **Django ↔ DH por handoffs directos** entre agentes. El
> coordinador queda en producto/estrategia (escalar ahí lo de negocio, no lo técnico).

## 0. Por qué ahora
**Cabañas Puerto Varas** (cliente de pago de DH) usará M17 **desde DH, sí o sí**. El core
(Fases 1–3: manual + auto-pick + batch) ya está **validado en Aremko** (H-070…H-074). Es
momento de consolidar M17 en DH como **producto**, no de seguir agregando en Aremko.

## 1. El norte de producto (para ti y para el agente DH)
- M17 = **producto standalone "gancho"** + módulo estrella de DH (vende el ecosistema completo).
- Dolor que ataca: costo de un **Community Manager** / trabajo artesanal de redes en pymes.
- **El brief es el motor**; su calidad = **riqueza de fuentes**. Arquitectura **base + enchufes**:
  genera igual con lo que haya (degradación elegante), mejora con cada fuente/módulo conectado.
- Fuentes: **automáticas** (calendario/temporadas/feriados/findes largos, reseñas TripAdvisor/
  Google, SEO, competencia) + **conectables OAuth** (Meta/Google Ads, GA4) + **datos del propio
  DH** (reservas, ads) si el tenant tiene esos módulos.
- **Aprendizaje acumulativo**: mide resultados (ventas / reacciones en redes / campañas) →
  mejora el brief → retención (mientras más usa, más sabe de SU negocio).
- **Onboarding asistido + "medidor de riqueza del brief"**: para que configurar las fuentes NO
  sea una pesadilla — y para que esa fricción **venda** los módulos DH (cada módulo pre-conecta
  fuentes → sube el % de calidad del brief).

## 2. El desenredo (separar 3 cosas que hoy están pegadas)
Hoy, en el laboratorio Aremko, todo vive junto. En DH se separan limpio:
- **MOTOR** (procesa: genera el brief + elige la foto + compone la pieza) → se **reconstruye en
  DH, multi-tenant**.
- **FUENTES** (datos que alimentan el brief) → se vuelven **enchufes por tenant**.
- **CONTENIDO** (catálogo de fotos + material generado) → **por tenant** en DH.

Casos:
- **Cabañas PV:** motor DH + fuentes **de DH** (sus reservas ya están ahí) + su catálogo → todo
  limpio dentro de DH. **Es el caso más simple → por eso va primero.**
- **Aremko** (después, M-3): tenant que **enchufa** sus datos desde `booking-system-aremko`
  (fuente externa vía API) + catálogo migrado. Aremko pasa de "todo pegado" a "un tenant más".

## 3. Secuencia de migración
- **M-1 · Core en DH** (para Cabañas PV): app `apps/publicaciones` multi-tenant + `Clip`/`UsoClip`
  + auto-pick + composer + pantalla de publicaciones + gating; **brief alimentado por datos DH**.
- **M-2 · Piel + Standalone**: home del asistente + **onboarding asistido** + kit de marca por
  tenant + brief con **enchufes externos** (Meta/Google/reseñas/SEO) + **medidor de riqueza** +
  landing + pricing. (Aquí nacen también las **Fases 4–6**: carrusel, chat, video.)
- **M-3 · Migrar Aremko**: contenido de Angélica → DH; Angélica opera como **tenant más**.

## 4. Qué se porta (inventario) y decisiones a PRESERVAR
**Inventario (Aremko → DH):**
- `catalogo_clips`: `Clip`, `UsoClip`, `seleccionar.py` (auto-pick + degradación en cascada),
  `composer.py` (render Cloudinary URL), `tagging.py`, `web_views.py`
  (explorador / ingesta / componer / `generar_lote`) + templates.
- `marketing_briefs`: `PublicacionPlanificada`, segmentos, explode, `criterio_foto`.
- `ventas/services/marketing_brief_generator.py`: generador del brief (`build_copywriter_prompt`,
  `criterio_foto`, saneo `_sanear_criterios_foto`).

**Decisiones de diseño a PRESERVAR (no reinventar):**
- Render **Cloudinary por URL** (cero CPU server; ver `PLAN_M17_PRODUCCION_PIEZAS` §5.9 + trampas
  de sintaxis documentadas).
- **`criterio_foto` estructurado** emitido por el brief (patrón `prompt_imagen_ia` de H-064).
- Auto-pick **100% determinista** (`seleccionar_clip` + degradación en cascada auditable +
  `excluir_ids`); anti-repetición vía `UsoClip`/`ultimo_uso`.
- **Regla de oro: elección de foto = código; el LLM solo conversa.**
- App **aislada / drift-safe** en origen → en DH, respetar su patrón multi-tenant.

## 5. Reglas de DH a respetar (de su `CLAUDE.md`)
Multi-tenant por fila (**FK `tenant`** en todo modelo), gating **`@requires_feature`** +
`apps/entitlements/features.py` (correr `sync_features`), **`unfold.admin`**, **bilingüe ES/EN**
(`gettext`/`{% trans %}`), settings `config.settings.dev|prod`, **commits en español**. App
destino: **`apps/publicaciones`**. Registrar M17 en la **tabla `Modulo`** + `docs/MODULOS.md`.

## 6. Tu primer entregable (para echar a andar la máquina)
1. **Dossier de traspaso M17** — documento técnico que le permita al agente DH **reconstruir** el
   módulo: modelos / servicios / vistas + contratos de datos + dependencias + **qué es portable
   tal cual vs. qué adaptar** a multi-tenant/gating. Apóyate en lo ya escrito: `BRIEF_H-070..074`,
   `CONTRATO_H-070_CATALOGO`, `PLAN_M17_PRODUCCION_PIEZAS`.
2. **Contactar al agente DH** y abrir el canal de **handoffs directos** (mensajería entre
   sesiones). El coordinador hace la presentación inicial si hace falta.
3. **Proponer con el agente DH el plan técnico de M-1** (core en DH para Cabañas PV).

## 7. Roles
- **Django ↔ DH:** handoffs directos entre ustedes para lo técnico de la migración.
- **Coordinador (con Jorge):** producto / estrategia / prioridades. Escálennos lo de negocio.
- Persistan el estado (dossier + plan M-1) en `docs/` (aquí y/o en `datamatic-hospitality/docs/`
  según acuerden con el agente DH).
