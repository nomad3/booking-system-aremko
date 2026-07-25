# BRIEF H-071 · Catálogo de Clips (M17) — Fase B1: Explorador web (para el CM)

> **Para:** agente Django (`~/dev/booking-system-aremko`).
> **Continúa:** H-070 (Fase A: modelo `Clip` + API `/marketing/api/catalogo/` + **89 keepers
> ya sembrados** en Cloudinary/prod). Contrato: `docs/CONTRATO_H-070_CATALOGO.md`.
> **Alcance de este handoff: SOLO B1** (explorador de **lectura**). NO incluye render/
> composición de la pieza (B2), ni auto-pick brief→foto (B3), ni ingesta web.

## Contexto y decisión de arquitectura (leer)
Fase A dejó el modelo y `GET /marketing/api/catalogo/` con **todos los filtros** ya listos.
El plan M17 completo: el **Community Manager** (Angélica en Aremko) entra a una pantalla web,
**ve el catálogo**, luego el agente **arma la historia** (B2) y **la elige solo desde el brief**
(B3).

**Decisión 2026-07-25 (cambia la nota de H-070):** el front del catálogo se construye como
**vista Django server-rendered en ESTE repo**, NO en el dashboard Next de aremko-cli. Razones:
1. **M17 es módulo de DH, que es Django** → lo server-side se porta casi directo a multi-tenant;
   lo que se hiciera en el Next de aremko-cli habría que rehacerlo.
2. Jorge eligió **render en el servidor** (B2) → conviene que explorador + preview + render
   vivan en el **mismo lugar** (misma sesión/deploy).
3. Una **URL dedicada y protegida** para el CM, sin acoplarla al dashboard de bandeja.

El `GET /marketing/api/catalogo/` (API REST con `X-API-KEY`) **sigue vivo** para consumidores
externos y el auto-pick futuro; esta vista NO lo reemplaza.

## Objetivo B1
Que el CM entre a una URL protegida y **vea, filtre y busque** el catálogo (las 89 keepers +
lo que se agregue), con **miniaturas desde Cloudinary** y su taxonomía. Es **solo lectura**:
responder "¿con qué fotos cuento para publicar?".

## 1. Ruta + vista
- Ruta sugerida: `GET /marketing/catalogo/` (el agente elige el namespace coherente con
  cómo montó `catalogo_clips`). Página HTML, **server-rendered** (template Django).
- Protección: **`@staff_member_required`** (NO superuser — el CM no es admin). Idealmente un
  grupo `Community Manager` con permiso a esta vista.
- Datos: **consultar el ORM directo** del modelo `Clip` (es el mismo proyecto; no pasar por
  la API con `X-API-KEY`). La API REST queda intacta para externos.

## 2. Galería
- Grid responsive de cards, **foco en la foto** (es una herramienta de trabajo de contenido).
- Miniatura: **derivar del `cloud_url` una versión chica** insertando transformación en
  `/upload/` (ej. `…/upload/w_400,c_fill,ar_4:5,f_auto,q_auto/…`) — **no** servir la de 1440
  en el grid.
- Cada card: miniatura + `area` + `nombre_comercial` + badges: ⭐ `keeper`, 💨 `vapor`,
  🌙/☀️ `momento`, 🎀 `decoracion=con`. Distinguir visualmente `estado=revisar`.

## 3. Filtros + búsqueda
- Barra/sidebar con: `area, nombre_comercial, momento, estacion, vapor, decoracion, keeper,
  estado` + caja de texto `q` (busca en archivo/nombre/descripcion/nota).
- Poblar los dropdowns desde la taxonomía real (`.values_list(...).distinct()` para
  `area`/`nombre_comercial`; el resto son enums conocidos).
- **Filtrado server-side** (querystring → queryset) + **paginación** (Django `Paginator`,
  ~48/pág). Vista inicial: `estado != descartado` (toggle "ver todas").
- Mostrar contador arriba: "89 fotos · N tinas · N cabañas · N masajes · …".

## 4. Detalle
- Click en card → modal o página `/marketing/catalogo/<id>/` con **imagen grande** + toda la
  taxonomía (área, nombre, momento, estación, vapor, decoración, personas, permiso, calidad,
  etiquetas, apto_para, nota).
- Dejar el **hueco de B2**: un botón **"Usar en historia →" deshabilitado** (o placeholder).
  NO implementar la acción aún — solo reservar el lugar.

## 5. Acceso del CM (Angélica)
- Requiere user con `is_staff=True`. **Documentar** el paso (Jorge le crea el usuario a
  Angélica, o el grupo `Community Manager`). La vista NO debe exigir superuser.

## Fuera de alcance B1 (explícito)
- **Render/composición** de la historia (B2, va en el **servidor** — próximo handoff).
- **Auto-pick** brief→foto (B3).
- **Ingesta web** (subir foto nueva desde el navegador) — hoy la hace Jorge con `/catalogar`;
  se evaluará como B1.5/B2.
- **Edición** de taxonomía desde esta vista (ya está en el admin Django + `PATCH` API).
- **Video** · **multi-tenant real** (mono-tenant Aremko; mantener el modelo port-friendly).

## Checklist de cierre
- [ ] Ruta `/marketing/catalogo/` + vista protegida (staff, no superuser) + template galería.
- [ ] Miniaturas Cloudinary chicas (no servir la de 1440 en el grid).
- [ ] Filtros server-side (`area, nombre_comercial, momento, estacion, vapor, decoracion,
      keeper, estado, q`) + paginación + contador.
- [ ] Detalle con taxonomía completa + placeholder "Usar en historia" (deshabilitado).
- [ ] Doc breve de acceso para el CM (cómo se crea el usuario de Angélica).
- [ ] `check` + prueba en prod: un user staff entra y ve las 89 keepers, filtrables por
      área/tina/momento, con miniatura y detalle.
