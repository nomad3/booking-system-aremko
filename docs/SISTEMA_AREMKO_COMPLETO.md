# Sistema Aremko Spa Boutique — Documento Funcional y Técnico Completo

**Versión:** 1.0
**Fecha:** 20 de mayo de 2026
**Audiencia:** ejecutivos, equipos técnicos, agentes IA, equipos comerciales

---

## Resumen Ejecutivo

### Qué es el Sistema Aremko

El **Sistema Aremko** es una plataforma de gestión integral hecha a medida para Aremko Spa Boutique (Puerto Varas, Chile), construida en torno a tres ejes que rara vez conviven en un mismo sistema:

1. **Operación**: reservas online, gestión de servicios (tinas, masajes, cabañas), comandas de productos, agenda diaria, control de gestión interno (task management con swimlanes para 4 áreas operativas).
2. **Comercial**: CRM con 4.400+ clientes segmentados, programa de fidelización por tramos con premios automáticos, cotizaciones empresariales formales, gift cards digitales con PDF generado, sistema VoC (Voz del Cliente) con encuestas nativas + análisis IA.
3. **Marketing inteligente**: brief semanal generado por IA (Claude Sonnet vía OpenRouter), tracking server-side de conversiones a Meta (Pixel + CAPI con deduplicación), snapshots semanales de GA4, Search Console, Instagram, Facebook y competidores; generador de contenido y análisis cruzado de señales.

El producto se vende como una **suite de dos componentes que trabajan juntos**:

- **aremko-booking** (este sistema, backend Django + frontend público en aremko.cl): núcleo operativo, base de datos, lógica de negocio, integraciones con pasarelas de pago, mensajería, redes sociales y analytics.
- **aremko-cli** (Next.js + Go, hosting separado en Vercel + Render): capa de visualización por rol con dashboards diferenciados para CEO, equipo comercial y operaciones. Consume APIs de aremko-booking y agrega su propia capa de análisis con IA.

### Problema que resuelve

Pequeñas y medianas empresas turísticas y de bienestar enfrentan tres problemas crónicos:

1. **Fragmentación**: sistemas de reservas no hablan con marketing, marketing no habla con CRM, operaciones usa planillas. El sistema Aremko unifica todo en una base de datos coherente, con eventos automáticos que conectan las áreas.
2. **Falta de inteligencia accionable**: tienen GA4, Meta Ads, encuestas, pero ningún lugar donde se correlacionen. El brief semanal automático lee todas las fuentes y produce diagnóstico ejecutivo + plan accionable.
3. **Costo de implementación de buenas prácticas**: tracking server-side, anti-spam de comunicaciones, deduplicación de eventos, scraping de competidores con detección anti-bot, generación de PDFs profesionales — todas técnicas avanzadas que normalmente requieren consultores externos. Aquí están integradas.

### Pilares funcionales (vista de alto nivel)

| Pilar | Capacidades |
|---|---|
| **Reservas y disponibilidad** | Calendario en tiempo real, prevención de doble-booking, slots configurables por servicio, bloqueos por día y por horario, lógica especial para cabañas (check-in 16:00 fijo) y ambientaciones (heredan slot de tina) |
| **Pagos** | Flow.cl (gateway chileno), transferencia, Mercado Pago, gift cards como medio de pago combinable. Webhook de Flow con materialización transaccional, prevención de slot perdido durante el pago |
| **CRM y fidelización** | 4.400+ clientes con segmentación frecuencia/gasto/actividad, sistema de tramos con premios automáticos por hito (5, 10, 15, 20 visitas), historial completo, normalización de teléfonos chilenos, deduplicación de clientes |
| **Comunicaciones** | SMS (Redvoiss), Email (SendGrid), WhatsApp (cola interna). Anti-spam con límites diarios/semanales/mensuales por cliente, respeto de horario preferido, plantillas activas por tipo |
| **Marketing inteligente** | Meta Pixel + Conversions API con deduplicación, GA4 + Search Console snapshots semanales, MetaSnapshot (FB + IG + Ads), brief semanal con IA que correlaciona todas las fuentes |
| **Operaciones** | Sistema de comandas (productos vendidos en venta de servicios), agenda operativa por hora, control de gestión interno con tareas y swimlanes para 4 áreas |
| **Cotizaciones empresariales** | Módulo nuevo (mayo 2026) para emitir documentos formales numerados desde 321, con texto editable, PDF descargable, estados (borrador/enviada/aceptada/rechazada/expirada) |
| **Gift Cards** | Compra online, generación de PDF con código único, envío automático por email, redención como medio de pago, validación de vencimientos |
| **Voz del Cliente** | Encuesta nativa post-visita (D+1), NPS calculado, análisis IA semanal de encuestas, follow-ups pendientes con sugerencia WhatsApp generada por IA |
| **Análisis de competencia** | Scraping web con BeautifulSoup, detección anti-bot, lectura de JSON-LD para precios, snapshots de Reviews TripAdvisor + Google, exposición de errores claros |
| **APIs para agentes externos** | Endpoints diseñados para que aremko-cli y otros consumidores (incluido un LLM con function-calling) consulten ventas detalladas, tendencias semanales, contexto operativo |
| **Catálogo turístico paralelo (DPV)** | Destino Puerto Varas: catálogo de lugares, circuitos turísticos, recomendaciones IA, captura de leads, conversación con agente IA |

### Stack técnico y escala

- **Backend**: Django 4.2.30 sobre Python 3.9 (en transición a 3.10+ pendiente), PostgreSQL, Gunicorn + WhiteNoise.
- **Despliegue**: Render (Docker container con WeasyPrint + libcairo/libpango para PDFs), región Oregon.
- **Almacenamiento de media**: Cloudinary (primario) + Google Cloud Storage (fallback).
- **Frontend público**: templates Django + JavaScript vanilla, Bootstrap 5, ~109 templates.
- **Integraciones externas activas**: Flow.cl, Mercado Pago, SendGrid, Redvoiss (SMS chileno), Meta Graph API v21.0 (Pixel + CAPI), Google Analytics Data API (GA4), Google Search Console API, OpenAI + OpenRouter (Claude Sonnet 4.6 para análisis), Cloudinary, Google Cloud Storage, NotebookLM (vía CLI).

**Métricas de escala (mayo 2026):**

- 75 modelos de datos en la app principal.
- 4.400+ clientes activos.
- ~600 sesiones web/semana, ~43 conversiones medidas, ~5 reservaciones-web-completas/semana (la mayor parte de las ventas se cierra por WhatsApp post-lead).
- 30 servicios disponibles + ~50 productos en catálogo.
- 97 management commands (comandos administrativos + cron jobs disparables vía HTTP).
- 30 servicios de negocio (capas de lógica entre views y modelos).
- 109 templates HTML públicos/internos.
- 38 módulos de views distintos.

### Valor diferenciador

Comparado con soluciones genéricas (un Booking.com / un Bsale / un Mailchimp aislado), el Sistema Aremko ofrece:

1. **Una sola base de datos para todo el negocio** — desde la primera visita a la web hasta el follow-up post-visita, todo deja huella en el mismo PostgreSQL, con relaciones formales que permiten reportes cruzados sin ETL.
2. **Tracking server-side de conversiones reales** — Meta CAPI con deduplicación garantiza que cada venta llegue a Meta incluso si el cliente cerró el navegador antes de volver del pago. Las campañas se optimizan sobre eventos reales, no sobre estimaciones.
3. **Brief semanal generado por IA con TODAS las fuentes correlacionadas** — el lunes 10:00 hora Chile, un proceso automático integra ventas internas, GA4, Meta, reviews externas, encuestas VoC, calendario chileno (feriados/temporadas) y produce un documento con diagnóstico ejecutivo, alertas accionables y drafts de contenido. Esto reemplaza el rol de un analista de marketing dedicado.
4. **Anti-fragilidad operativa** — el sistema persiste snapshots en BD aunque las APIs externas fallen parcialmente, deduplica eventos automáticamente, valida slots antes de cobrar, materializa transaccionalmente con rollback si algo falla mid-checkout.
5. **Extensible para agentes IA** — endpoints diseñados para consumo por LLMs con function-calling (filtros NL sobre ventas, contexto operativo en markdown, generación de PDFs vía URL). Aremko-cli es solo el primer consumidor; cualquier agente externo puede conectarse.

### Lo que distingue al Sistema Aremko de un "MVP construido sobre stack moderno"

Muchos sistemas pequeños empiezan con Django + Postgres y un buen scaffold, pero el Sistema Aremko incorpora prácticas que solo aparecen tras 18+ meses de iteración con uso real:

- Manejo de **slots concurrentes** durante el flujo de pago Flow.cl (revalidación en webhook confirmación con marcado de slot perdido para reembolso manual).
- **Deduplicación de eventos** entre Pixel client-side y CAPI server-side con `event_id` determinístico.
- **Reglas de negocio sobreescritas server-side** que previenen manipulación cliente (precios planos para tinas/cabañas, hora de check-in forzada, ambientaciones que requieren tina previa).
- **Auto-mapeo de servicios** (Desayuno genérico → Desayuno específico de la cabaña reservada, con distribución cíclica si hay múltiples cabañas).
- **Sistema VoC nativo + análisis IA semanal** con persistencia de resultados y alertas operativas accionables.
- **Memoria persistente del sistema** (`ContextoOperativo`) auto-introspectada e inyectable como markdown al system prompt de cualquier LLM consumidor, para que las recomendaciones de IA se construyan sobre lo que ya existe en lugar de proponer cosas implementadas hace 6 meses.

---

# Parte 1 — Arquitectura técnica

## 1.1 Stack tecnológico

### Lenguaje y framework

- **Python 3.9** (en transición a 3.10+; google.auth y google.api_core ya marcan deprecación para 3.9, planificada actualización).
- **Django 4.2.30** (LTS, con todos los CVEs críticos parcheados a la fecha).
- **PostgreSQL** vía `psycopg2-binary 2.9.9+`.

### Servidor web y assets

- **Gunicorn 22+** como servidor WSGI de producción (configurado para 1 worker con timeout de 120s — adecuado para el volumen actual).
- **WhiteNoise 6.8+** sirve archivos estáticos con compresión y cache headers.
- **Cloudinary** como almacenamiento primario de imágenes (logos, fotos de servicios, imágenes de blog).
- **Google Cloud Storage** como fallback histórico (mantenido por compatibilidad con migraciones).

### Generación de documentos

- **WeasyPrint 62.3+** para PDFs (cotizaciones, gift cards, reportes). Requiere Cairo, Pango, GDK-Pixbuf instaladas en el container Docker.
- **python-docx 1.1+** para generar reportes operativos en formato Word (follow-ups VoC con sugerencia IA por cliente).
- **openpyxl 3.1+** y **xlwt 1.3** para Excel (importación masiva de clientes, exportación de reportes históricos).

### APIs HTTP

- **requests 2.32+** como cliente HTTP síncrono.
- **httpx 0.27+** para clientes asíncronos donde aplica.

### Email, SMS y mensajería

- **django-anymail[sendgrid] 10.3+** abstrae SendGrid para envíos transaccionales y de campaña.
- **redvoiss-service.py** (módulo propio) integra Redvoiss, proveedor chileno de SMS.
- **smtplib** (stdlib) como fallback para SMTP directo desde macOS local (workaround para problemas SSL de urllib).

### Servicios IA

- **OpenAI Python SDK 1.57+** apuntado a **OpenRouter** (`https://openrouter.ai/api/v1`) para acceder a Claude Sonnet 4.6 a costo controlado.
- Modelo por default: `anthropic/claude-sonnet-4.6`.
- Otros modelos disponibles vía OpenRouter para análisis específicos (Deepseek para variaciones de copy, etc.).

### Google APIs

- **google-api-python-client 2.150+** y **google-auth 2.35+** para autenticación.
- **google-analytics-data 0.18+** para GA4 Reporting API.
- **googleapiclient** para Google Search Console API.
- Service Account dedicada: `aremko-reader@aremko-e51ae.iam.gserviceaccount.com`.

### Meta (Facebook + Instagram + Ads)

- Cliente Meta Graph API v21.0 implementado en módulos propios (`meta_reporter.py`, `meta_analyzer.py`, `meta_capi_service.py`).
- System User token con acceso a 3 cuentas publicitarias + 1 página Facebook + 1 cuenta Instagram Business.

### Procesamiento de datos y scraping

- **BeautifulSoup 4.12+** para scraping de competencia.
- **phonenumbers 8.13+** para validación/normalización de teléfonos chilenos (+56 prefix).
- **python-dateutil 2.9+** y **pytz 2024.1** para zonas horarias (timezone Chile).

### Frontend (templates Django)

- **Bootstrap 5** (CDN).
- **JavaScript vanilla** + Fetch API.
- **109 templates HTML** distribuidos por dominio.
- **Templatetags personalizados** para lógica de presentación (cabana_display, social_proof, badges).

### Configuración y singletons

- **django-solo 2.3+** para modelos singleton (HomepageConfig, ConfiguracionResumen, ConfiguracionTips, ContextoOperativo).
- **django-cors-headers 4.6+** para CORS (necesario por consumo desde aremko-cli en otro dominio).

### Despliegue

- **Docker** (Dockerfile basado en `python:3.9-slim`).
- **Render.com** región Oregon como host de aplicación + base de datos PostgreSQL.
- **cron-job.org** plan free como scheduler externo (timeout 30s por job, mitigado con threads fire-and-forget).
- **GitHub** (`nomad3/booking-system-aremko`) para versionamiento y trigger de auto-deploy.

### Observabilidad

- Logging estándar de Django a stdout (captado por Render).
- `print()` strategic en webhooks de pago para trace de transacciones.
- Métricas de cobertura de tracking via Meta Events Manager + GA4 Realtime.

## 1.2 Arquitectura de aplicaciones internas

El proyecto Django se divide en **6 apps principales** y varias auxiliares:

### `ventas/` — Core de negocio (la app más grande)

Concentra el 80% del valor del sistema. Tiene su propia estructura interna:

```
ventas/
├── models.py            (75 modelos en un solo archivo, ~6.000 líneas)
├── views/               (38 módulos por dominio)
├── services/            (30 módulos de lógica de negocio)
├── signals/             (3 archivos con signals Django)
├── management/commands/ (97 comandos administrativos y cron)
├── templates/ventas/    (109 plantillas HTML)
├── static/              (CSS, JS, imágenes propias)
├── migrations/          (93 migraciones acumuladas)
├── api_aremko_cli.py    (endpoints específicos para aremko-cli)
├── contexto_operativo.py (generador del Contexto Operativo IA)
└── urls.py              (~220 rutas)
```

### `control_gestion/` — Gestión interna operativa

Sistema de tareas con swimlanes para 4 áreas: ventas, operaciones, marketing, mantenimiento.

Modelos principales:
- `Task`: tarea con estado (Pending, InProgress, Done, Cancelled), prioridad, dueño asignado, swimlane, criticidad temporal, fuente (manual, automática, recurrente).
- `ChecklistItem`: items de checklist anidados a tareas.
- `TaskLog`: bitácora de cambios de estado y comentarios.
- `DailyReport`: reportes diarios consolidados.
- `CustomerSegment`: segmentos de clientes para campañas.
- `TaskOwnerConfig`: configuración de dueños por defecto por swimlane.

### `api/` — Luna AI Assistant

API REST para Luna, asistente conversacional interno. Modelos vacíos (lógica de conversación pasa por views y serializers).

### `destino_puerto_varas/` (DPV)

Proyecto paralelo: catálogo turístico, motor de recomendación de circuitos y agente conversacional para captura de leads.

15 modelos incluidos:
- `Place`, `PlaceEnrichmentDraft`, `PlacePhoto`
- `Circuit`, `CircuitDay`, `CircuitPlace`, `CircuitNarrativeDraft`, `CircuitCompositionDraft`
- `DurationCase` (catálogo de duraciones típicas de viaje)
- `RecommendationRule`, `AremkoRecommendation`, `TravelTip`
- `LeadConversation`, `ConversationMessage`, `AgentPromptTemplate`

### `aremko_blog/` — Blog editorial

App aislada (portable) para `aremko.cl/blog/`. Categorías por cluster temático (`BlogCluster`), publicación markdown→HTML con `markdown 3.6+`.

### `kits/` — Productos compuestos (Bill of Materials)

- `Kit`: producto compuesto vendible.
- `KitComponente`: ingredientes/componentes del kit con cantidades.

### `aremko_project/` — Configuración Django

Settings, root URLs, middleware personalizado de routing por host (permite múltiples dominios apuntando al mismo Django).

## 1.3 Modelo de datos — entidades principales

Las 75 entidades de `ventas/models.py` pueden agruparse en 10 dominios. Las relaciones principales:

### Dominio Reservas

```
Cliente (4.400+)
  └─ VentaReserva (cabecera de la transacción)
       ├─ ReservaServicio (1 línea por servicio, con fecha+hora+proveedor)
       │    └─ Servicio (catálogo)
       │         └─ CategoriaServicio
       │         └─ Proveedor (masajistas)
       ├─ ReservaProducto (productos vendidos junto al servicio)
       │    └─ Producto
       └─ Pago (puede tener varios: ej. parcial + cierre)
            └─ GiftCard (si se pagó con gift card)
```

Modelos auxiliares:
- `PendingReservation`: reserva tentativa creada antes de pagar con Flow (TTL configurable). Si el pago no confirma en X tiempo, expira automáticamente sin tomar el slot.
- `ServicioBloqueo`, `ServicioSlotBloqueo`: bloqueos a nivel día o nivel horario específico.
- `MovimientoCliente`: bitácora de cambios visibles para el cliente.
- `Comanda`, `DetalleComanda`: productos consumidos durante la visita (separados de los pre-reservados).

### Dominio Pagos

- `Pago`: cada pago individual asociado a una `VentaReserva`. Múltiples pagos posibles (pago parcial + pago final).
- `GiftCard`: instrumento de pago interno (compra/redención).
- `GiftCardExperiencia`: experiencias específicas vendibles como gift card (tinas, masajes, etc.).
- `PagoMasajista`, `DetalleServicioPago`: liquidación de comisiones a proveedores externos (40% default configurable).

### Dominio CRM

- `Lead`, `Company`, `Contact`, `Deal`, `Activity`: pipeline B2B clásico (para leads corporativos).
- `Campaign`, `CampaignInteraction`, `CampaignSendLog`: campañas activas y bitácora.
- `EmailCampaign`, `EmailRecipient`, `EmailDeliveryLog`, `EmailBlacklist`: motor de email marketing con tracking.
- `NewsletterSubscriber`: lista pública (registro voluntario en la web).
- `EncuestaSatisfaccion`: encuestas VoC con NPS y comentarios.
- `ClientPreferences`, `CommunicationLog`, `CommunicationLimit`, `MailParaEnviar`: cola y límites anti-spam.
- `Premio`, `ClientePremio`, `HistorialTramo`: programa de fidelización por hito.

### Dominio Marketing

- `MetaSnapshot`: snapshot de Facebook + Instagram + Ads cada lunes (28 días retrospectiva).
- `GA4Snapshot`, `SearchConsoleSnapshot`: persistencia semanal de GA4 y GSC para series históricas.
- `ReviewSnapshot`, `Review`: reviews externas (Google + TripAdvisor) en snapshot semanal y registros individuales.
- `CompetitorSnapshot`, `Competitor`, `CompetitorSocialMedia`: análisis de competencia.
- `WeeklyObjective`: objetivo semanal definido por Jorge para incluir en el brief.
- `WeeklySurveyAnalysis`: cache del análisis IA de encuestas (corre lunes 09:00).

### Dominio Cotizaciones

- `CotizacionEmpresa`: formulario de solicitud desde landing `/empresas/`.
- `CotizacionFormal`, `CotizacionItem`: documentos numerados (321 en adelante) para envío formal.
- `ContextoOperativo`: singleton con markdown auto-generado + manual para inyectar al system prompt de LLMs.

### Dominio Comunicaciones

- `SMSTemplate`, `EmailTemplate`, `EmailSubjectTemplate`, `EmailContentTemplate`: plantillas con variables.
- `CampaignEmailTemplate`, `EmailCampaignTemplate`: plantillas específicas para campañas masivas.

### Dominio Configuración

- `HomepageConfig`, `HomepageSettings`, `ConfiguracionResumen`, `ConfiguracionTips`: singletons editables desde admin Django.
- `SEOContent`: contenido SEO por página.

### Dominio Locación

- `Region`, `Comuna`: catálogo geográfico chileno completo.
- `Cliente.region`, `Cliente.comuna`: vinculación FK para reportes geográficos.

### Dominio Operaciones

- `SalaServicio`: salas físicas donde ocurren servicios (limita disponibilidad por sala).
- `MasajistaEspecialidad`, `HorarioMasajista`: catálogo de especialidades y horarios laborales de masajistas.
- `ServiceHistory`: historial agregado de servicios por cliente (para reportes y análisis IA).

## 1.4 Integraciones externas

### Pasarela de pago Flow.cl (gateway chileno principal)

- API HMAC-SHA256 signed.
- Flujo: `create_flow_payment` (POST) → cliente paga en Flow → Flow llama webhook `flow_confirmation` (server-to-server) → cliente vuelve a `flow_return` (browser).
- Anti-doble-procesamiento: validación de signature + check de estado en cada llamada.
- Anti-slot-perdido: revalidación de disponibilidad en el webhook con marcado `slot_perdido` para reembolso manual si el slot se tomó durante el pago.
- Estados: 1 (pendiente), 2 (pagado), 3 (rechazado), 4 (cancelado).
- Endpoints `urlConfirmation` y `urlReturn` configurables vía env vars; en prod apuntan a `https://aremko.cl/payment/...`.

### Mercado Pago

- Integración secundaria para pagos directos (no como gateway principal).
- Link maestro: `https://link.mercadopago.cl/aremko` (cuenta Aremko Hotel Spa).
- Servicio `mercadopago_service.py` para crear órdenes vía API.

### SendGrid (Email)

- Plan **Essentials 50K** (50.000 emails/mes).
- Dominio autenticado: `aremko.cl` (SPF + DKIM + DMARC configurados).
- Integración vía `django-anymail` (abstrae backend, fácil cambio futuro).
- Reglas de cadencia: emails masivos respetan `email_weekly_limit_per_client=1` y `email_monthly_limit_per_client=4`.
- Bitácora completa: `CommunicationLog`, `EmailDeliveryLog` con tracking de envío/apertura/clic/bounce/spam.

### Redvoiss (SMS Chile)

- Proveedor chileno especializado.
- Endpoint API HTTP simple con username/password.
- Cliente: `redvoiss_service.py` con plantillas y formato chileno (+56...).
- Costo: ~CLP 12 por SMS, monitoreado en `CommunicationLog.costo`.
- Reglas: `sms_daily_limit_per_client=2`, `sms_monthly_limit_per_client=8`.

### Meta Graph API v21.0

**Para análisis (lectura):**
- 3 cuentas publicitarias accesibles: `act_455070225054110` (BM principal), `act_43311853` (legacy USD), `act_323860814935576` (Daniela Almonacid, gestiona promociones Instagram).
- 1 página Facebook: `555157687911449` (~53K fans).
- 1 cuenta Instagram Business: `17841400756478364` (@aremkospa, ~59K seguidores).
- Servicio: `meta_reporter.py` consulta insights, posts, engagement.
- Snapshot persistido: `MetaSnapshot` con 28 días de retrospectiva.

**Para tracking server-side (escritura, Conversions API):**
- Pixel ID: `478226496113915`.
- Token: System User Access Token sin expiración.
- Eventos enviados: `Purchase` (desde webhook Flow + signal post_save VentaReserva), `Lead` (desde creación de PendingReservation).
- Deduplicación con Pixel client-side via `event_id` determinístico (`purchase_<venta_id>`, `lead_<pending_id>`).
- PII hasheada SHA-256 antes de salir del servidor.
- Cobertura: 100% de ventas (Flow + transferencia + admin/WhatsApp) llegan a Meta.

### Google APIs

**GA4 Reporting:**
- Property ID `535461209` (sitio aremko.cl).
- Measurement ID `G-T3K4CTD3HJ`.
- Custom events implementados: `whatsapp_click`, `phone_click`, `cta_blog_click`, `reservation_started`, `reservation_completed`.

**Search Console:**
- Propiedad `sc-domain:aremko.cl`.
- Permisos: pendiente al SA por bug de propagación Google (Estado mayo 2026: bloqueado, reintento manual cada 24-48h).

**Google Cloud Storage:**
- Bucket histórico para media (en transición a Cloudinary).

### Cloudinary

- Cuenta dedicada para imágenes de servicios, productos, blog, gift cards.
- URL: `cloudinary://key:secret@cloud_name` (vía env var).
- Transformaciones automáticas para optimización.

### OpenAI / OpenRouter

- Acceso a Claude Sonnet 4.6 (default).
- Otros modelos disponibles para casos específicos (Deepseek para variación de copy anti-spam).
- Token cap por análisis: configurable, default 32000 tokens (brief largo).
- Costo controlado vía OpenRouter (paga-por-uso real, sin compromisos).

### NotebookLM (Google)

- Notebook "Jorge's AI Brain" como memoria de largo plazo.
- Acceso programático vía CLI `notebooklm-py`.
- Sesiones se suben automáticamente al final del wrapup.

### cron-job.org

- Scheduler externo (plan free).
- Llama endpoints HTTP del sistema con header `X-API-KEY`.
- Endpoints actuales:
  - Lunes 10:00 — `/ventas/api/cron/marketing-brief/` (brief semanal)
  - Lunes 09:00 — `/ventas/api/cron/snapshot-weekly-traffic/` (GA4 + GSC snapshot)
  - Lunes 09:00 — `/ventas/api/cron/analyze-surveys-weekly/` (análisis VoC IA)
- Timeout 30s plan free → mitigado con threads fire-and-forget en el servidor.

## 1.5 Despliegue y entornos

### Producción (Render)

- Container Docker basado en `python:3.9-slim`.
- Build incluye dependencias del sistema: `libcairo2`, `libpango-1.0-0`, `libpangocairo-1.0-0`, `libgdk-pixbuf-xlib-2.0-dev`, `libxml2-dev`, `libxslt1-dev` (para WeasyPrint), `libpq-dev` (PostgreSQL), `netcat-openbsd` (health checks).
- Entrypoint `entrypoint.sh`:
  1. Espera a que la BD esté disponible (parseo de `DATABASE_URL` con Python).
  2. NO ejecuta `migrate` automáticamente (regla del proyecto: migraciones manuales para evitar sorpresas en producción).
  3. Crea superusuario si no existe.
  4. Colecta archivos estáticos con `whitenoise`.
  5. Inicia Gunicorn con 1 worker, timeout 120s.
- Auto-deploy en push a `main` de GitHub.
- BD PostgreSQL gestionada por Render en la misma región.

### Desarrollo local

- Docker Compose con web + postgres + pgAdmin.
- Ports: 8002 (Django), 5435 (Postgres), 5052 (pgAdmin).
- Hot reload con bind mount del código.

### Variables de entorno críticas

Más de 50 env vars documentadas en `CLAUDE.md`. Las más importantes:

- `DATABASE_URL`: conexión Postgres completa.
- `SECRET_KEY`: clave Django.
- `ALLOWED_HOSTS`: hosts permitidos.
- `FLOW_API_KEY`, `FLOW_SECRET_KEY`: credenciales Flow.cl.
- `SENDGRID_API_KEY`: SendGrid.
- `REDVOISS_USERNAME`, `REDVOISS_PASSWORD`: Redvoiss.
- `META_SYSTEM_USER_TOKEN`, `META_CAPI_ACCESS_TOKEN`, `META_PIXEL_ID`: Meta.
- `GOOGLE_SERVICE_ACCOUNT_JSON`: credencial GA4/GSC.
- `OPENROUTER_API_KEY`: IA.
- `CLOUDINARY_URL`: media storage.
- `AUTOMATION_API_KEY`: protección de endpoints cron.
- `SMS_DAILY_LIMIT_PER_CLIENT`, `EMAIL_WEEKLY_LIMIT_PER_CLIENT`, etc.: anti-spam.

### Backups

- Backup automático diario de la BD Postgres por Render (retención según plan).
- Comando manual `backup_database` para snapshot puntual.
- Backups locales en `/backups/` antes de migraciones grandes.

---

# Parte 2 — Funcionalidades por dominio

## 2.1 Dominio Reservas y Disponibilidad

### Flujo público de reserva (cliente final)

1. **Landing**: cliente entra a `aremko.cl/` (homepage), `/tinas/`, `/masajes/`, `/alojamientos/`, `/productos/` o categorías detalladas.
2. **Selección de servicio**: cards visuales con precio, fotos, descripción. Botón "Reservar ahora" abre un modal con selector de fecha + hora + cantidad de personas.
3. **Calendario en tiempo real**: el modal consulta `/api/disponibilidad/` y muestra slots libres. La lógica del slot considera:
   - `Servicio.horario_apertura`, `horario_cierre`, `slots_disponibles` (JSON con horarios discretos).
   - `Servicio.capacidad_minima` y `capacidad_maxima`.
   - `Servicio.max_servicios_simultaneos` (ej: 2 masajes en paralelo si hay sala doble).
   - `ServicioBloqueo` y `ServicioSlotBloqueo` activos para la fecha.
   - Reservas existentes (`ReservaServicio`) en el mismo slot.
   - Disponibilidad de masajista (`HorarioMasajista`).
4. **Carrito**: el cliente puede agregar varios servicios + productos. El carrito se persiste en sesión Django (cookies). Lógica especial:
   - **Cabañas con check-in fijo 16:00**: cualquier hora seleccionada por el cliente se normaliza server-side a las 16:00 (`add_to_cart` línea 132-139).
   - **Ambientaciones requieren tina previa**: si el cliente quiere una ambientación pero no hay tina en el carrito, el servidor rechaza con mensaje "Primero agrega una tina a tu carrito" (línea 150-167).
   - **Ambientaciones heredan slot de tina**: si hay tina, la ambientación toma su fecha+hora automáticamente.
   - **Desayuno auto-mapeo**: si el cliente agrega "Desayuno" (genérico), el servidor lo reemplaza por "Desayuno Torre", "Desayuno Laurel", etc. según las cabañas en el carrito (distribución cíclica entre múltiples cabañas).
   - **Precios planos por unidad**: cabañas y tinas en lista hardcoded (`TINAS_PRECIO_PLANO = {Calbuco, Osorno, Tronador, Hornopirén, Llaima, Puntiagudo, Puyehue, Villarrica}`) se cobran SIEMPRE por `capacidad_maxima` completa, ignorando el `cantidad_personas` del cliente (previene manipulación vía DevTools).
5. **Checkout**: formulario con datos del cliente (autocompleta si el teléfono ya existe en BD), elección de método de pago.
6. **Métodos de pago disponibles**:
   - **Flow.cl**: redirige a la pasarela. Crea `PendingReservation` (NO `VentaReserva` aún) con TTL 60 minutos.
   - **Transferencia bancaria**: crea `VentaReserva` con estado `pendiente`. El equipo confirma manualmente al recibir comprobante.
   - **Gift Card**: combinable con otros métodos. Valida saldo disponible y vencimiento.
7. **Confirmación**: email automático con detalles + (si Flow) link de pago + (si transferencia) datos bancarios + texto de cortesías y políticas de cancelación.

### Flujo de pago Flow.cl en detalle

```
Cliente da click "Pagar con Flow"
  └─ POST /ventas/api/flow/create/ {pending_id: X}
       └─ Crea PendingReservation (estado=iniciado, TTL 60min)
       └─ POST a Flow.cl con monto + commerceOrder=P<id>
       └─ Flow retorna URL de pago
       └─ Cliente redirigido a flow.cl
  ↓ (cliente paga en Flow)
  ↓
Flow webhook POST a /payment/confirmation/?pending_id=X
  ├─ Verifica signature HMAC-SHA256
  ├─ Consulta estado a Flow getStatus
  ├─ Si estado=2 (pagado):
  │   └─ Materializa PendingReservation → VentaReserva (revalida slots)
  │   ├─ Si slot perdido (otro cliente lo tomó): marca PendingReservation con notas + REQUIERE_REEMBOLSO_MANUAL
  │   └─ Si OK: crea VentaReserva + ReservaServicio + ReservaProducto + Pago
  │       ├─ Dispara CAPI Purchase a Meta (event_id=purchase_<id>)
  │       ├─ Envía GiftCards generadas si las hay (PDF + email)
  │       └─ Dispara signal post_save VentaReserva
  │           ├─ Actualiza tramo del cliente (puede generar Premio si hito)
  │           ├─ Registra movimiento de auditoría
  │           └─ Otros signals encadenados
  └─ Si estado=3,4: marca PendingReservation rechazado/cancelado

Cliente vuelve a /payment/return/?pending_id=X (browser)
  ├─ Si ya materializado: muestra "Pago Exitoso" + número de reserva
  ├─ Si pendiente: muestra "Verificando..." con autorefresh
  └─ Si rechazado: muestra "Pago Rechazado"
```

### Materialización transaccional

El proceso `materializar_venta_desde_carrito` (en `reservation_service.py`) es atómico:
- `transaction.atomic()` envuelve todo.
- Crea VentaReserva, sus ReservaServicio, ReservaProducto, Pago en orden.
- Revalida disponibilidad de slots ANTES de comprometer.
- Si cualquier paso falla, rollback completo (no quedan datos inconsistentes).

### Bloqueos administrativos

Desde el admin Django:
- `ServicioBloqueo`: bloquea un servicio para una fecha entera (ej: cabaña cerrada por mantención el 15-jun).
- `ServicioSlotBloqueo`: bloquea solo un horario específico (ej: tina Tronador el 12-may a las 15:00 por evento privado).
- Estos bloqueos se verifican en `add_to_cart` antes de aceptar.

### Edge cases manejados

- Cliente intenta reservar slot que se tomó durante el pago → marcado para reembolso manual con alerta clara.
- Cliente cierra navegador antes de volver del pago → CAPI server-side garantiza que Meta se entere.
- Cliente intenta crear 2 reservas del mismo masaje en el mismo slot → bloqueado por validación de capacity.
- Cliente intenta editar precios via DevTools → server-side override en `add_to_cart`.

## 2.2 Dominio Pagos

### Múltiples métodos combinables

Una `VentaReserva` puede tener múltiples `Pago` asociados. Casos típicos:

1. **Pago único Flow**: cliente paga 100% online → 1 Pago.
2. **Pago parcial + cierre**: cliente paga 50% transferencia anticipo + 50% al check-out con tarjeta → 2 Pagos.
3. **Gift Card + complemento**: cliente tiene gift card de $50.000 pero el total es $80.000 → 1 Pago giftcard + 1 Pago efectivo/tarjeta.
4. **Descuento aplicado**: para descuentos, se usa el método "descuento" con monto negativo y el servicio especial `Descuento_Servicios` (actualmente migrado a su propia categoría para no contaminar reportes de Tinas).

### Estados de pago

`VentaReserva.estado_pago`:
- `pendiente`: nada pagado.
- `parcial`: algo pagado pero saldo > 0.
- `pagado`: saldo = 0.
- `cancelado`: venta anulada (no se cuenta en reportes).

### Cálculo automático

Cada vez que se crea o borra un `Pago`, se llama a `VentaReserva.calcular_total()` que a su vez llama `actualizar_saldo()`:
- Suma `precio_unitario_venta × cantidad_personas` de todos los servicios.
- Suma productos.
- Suma gift cards vendidas en la misma reserva (cuando aplica).
- Resta `Pago.monto` excluyendo método `descuento`.
- Setea `estado_pago` según el saldo resultante.

### Comisiones a masajistas

- Cada `Proveedor` tiene `porcentaje_comision` (default 40%).
- `PagoMasajista` agrupa los servicios de un masajista en un período.
- `DetalleServicioPago` desglosa qué servicios incluye y por qué monto.
- Comando `diagnosticar_pagos_masajista` audita inconsistencias.

### Cobertura Meta CAPI

Como detallado en sección 1.4 (Integraciones Meta), cada `VentaReserva` que transita a `estado_pago='pagado'` (por cualquier vía) dispara automáticamente un evento `Purchase` a Meta vía CAPI, con deduplicación contra el Pixel client-side.

Esto significa que **TODAS las ventas llegan a Meta**:
- Ventas Flow (vía webhook directo)
- Ventas transferencia (vía signal post_save al confirmar)
- Ventas creadas desde admin (vía signal post_save)
- Ventas por WhatsApp registradas por el equipo (vía signal post_save)

## 2.3 Dominio CRM y Fidelización

### Segmentación de clientes

Cada `Cliente` se clasifica automáticamente en 3 ejes:

1. **Frecuencia**: nuevo (0-1 visitas), regular (2-4), VIP (5+).
2. **Spending**: low (<100K CLP histórico), medium (100-300K), high (300K+).
3. **Actividad**: campo `last_visit_date` actualizado por signal.

### Sistema de tramos (fidelización)

Implementado en `tramo_service.py`. Cada cliente avanza de tramo según número de visitas pagadas:

- **Tramo 1**: 1 visita (bienvenida).
- **Tramo 5**: hito (genera Premio automático).
- **Tramo 10**: hito mayor.
- **Tramo 15**, **Tramo 20**: hitos VIP.

Cuando un cliente alcanza un hito, se crea automáticamente un `ClientePremio` con un beneficio configurado (descuento, regalo, etc.). El historial queda en `HistorialTramo`.

**Premios bienvenida** se generan con delay de 3 días post check-in (no inmediatamente al crear la reserva), ejecutados por `procesar_premios_bienvenida`.

### Pipeline B2B

Para leads corporativos:
- `Lead`: contacto inicial.
- `Company`: empresa asociada.
- `Contact`: personas en la empresa.
- `Deal`: oportunidad de negocio.
- `Activity`: tareas/notas/llamadas asociadas.

### Normalización y deduplicación

- `normalize_client_phones`: convierte todos los teléfonos a formato chileno estándar (+56...).
- `normalize_and_merge_clients`: detecta duplicados (mismo teléfono o email) y los fusiona conservando historial.
- Útil tras importación masiva de clientes desde planillas antiguas.

### Importación masiva

- Comando `importar_emails_csv`: carga emails desde planilla.
- Comando `import_contacts`, `import_companies`: para CRM B2B.
- Comando `import_historical_services`: carga histórico de servicios pre-sistema.
- Validación con `phonenumbers` library.

### Bitácora de movimientos

`MovimientoCliente` registra cambios visibles para el cliente (pagos, premios, comunicaciones). Endpoint `/auditoria-movimientos/` permite ver el historial completo.

## 2.4 Dominio Comunicaciones (SMS + Email + WhatsApp)

### Anti-spam multinivel

Cada comunicación pasa por validación contra:
1. **Permisos del cliente**: `permite_sms`, `permite_email` (configurables).
2. **Horario preferido**: `horario_preferido_inicio` y `horario_preferido_fin` (default 09:00-21:00).
3. **Límites diarios**: `sms_daily_limit_per_client` (default 2).
4. **Límites mensuales**: `sms_monthly_limit_per_client` (default 8), `email_monthly_limit_per_client` (default 4).
5. **Límites semanales**: `email_weekly_limit_per_client` (default 1).
6. **Blacklist**: `EmailBlacklist` para emails que pidieron unsubscribe o que bouncearon.
7. **Plantilla activa**: `SMSTemplate.is_active` y `EmailTemplate.is_active`.

### Triggers automáticos

`send_communication_triggers` es el comando central, disparado vía cron diario, que ejecuta:

| Trigger | Cuándo | Canal |
|---|---|---|
| Confirmación de reserva | Inmediato al crear o confirmar pago | Email |
| Pago confirmado | Al detectar 100% pagado | Email + SMS |
| Recordatorio 24h antes | Cron diario a las 09:00 | SMS |
| Encuesta post-visita NPS | D+1 después del servicio | SMS con link a encuesta |
| Reactivación | 90 días sin actividad | Email + SMS |
| Cumpleaños | Anual, día del cumpleaños | Email + SMS |
| Newsletter segmentado | Según segmento y configuración | Email |

### Plantillas con variables

`SMSTemplate.content` y `EmailTemplate.body_html` soportan variables: `{nombre}`, `{servicio}`, `{fecha}`, `{hora}`, `{telefono}`, etc. El método `render_message` substituye en tiempo real.

### Bitácora completa

Cada envío queda en `CommunicationLog`:
- Cliente, canal, plantilla usada.
- Contenido renderizado (para auditoría).
- Estado: sent, delivered, opened (email), clicked (email), bounced, spam.
- Costo (para SMS).
- Errores si fallan.

Para email específicamente, `EmailDeliveryLog` extiende con eventos del webhook de SendGrid.

### Variaciones IA anti-spam

`ai_service.py` ofrece variaciones automáticas del contenido para evitar que Gmail/Yahoo identifiquen patrones repetitivos en envíos masivos:
- Sinónimos en frases clave.
- Reordenamiento de oraciones.
- Insertos de elementos personalizados.
- Configurable: `AI_VARIATION_ENABLED=true` y `AI_ANTI_SPAM_ENABLED=true` (env vars).

### Newsletter segmentado

- `NewsletterSubscriber`: lista pública con `email`, `is_active`, `unsubscribe_token`.
- Suscripción voluntaria desde footer del sitio (`subscribe_view`).
- Unsubscribe con un solo click (`unsubscribe_view`, requirement legal anti-spam).
- Segmentos definidos en `crm_service.py` (engaged, dormidos, VIP, etc.).
- Comando `send_segmented_newsletter` envía con respeto total de anti-spam.

### WhatsApp (cola interna)

- `MailParaEnviar` actúa como cola unificada para mensajes (email + WhatsApp).
- WhatsApp no se envía automáticamente: se exporta como `.docx` con sugerencia IA para que Deborah copie-pegue manualmente.
- `report_pending_followups` genera el .docx con todos los follow-ups VoC pendientes + sugerencia de mensaje personalizada por IA.

## 2.5 Dominio Marketing Inteligente

### Brief semanal automatizado

**Disparo**: cron-job.org → `/ventas/api/cron/marketing-brief/` los lunes 10:00 hora Chile.

**Fuentes consumidas** (en una sola corrida):
1. **Marketing Playbook v1.0** (10K chars): voz, personas (3 maletas/parejas/familias), diferenciadores, cadencia por canal.
2. **Recurring Tasks** (3.5K chars): qué se publica cada día por convención.
3. **Calendario Chile** (6K chars): feriados + fechas comerciales + temporadas turísticas Puerto Varas.
4. **Frases de clientes promotores** (NPS≥9, últimos 30 días): cited textually.
5. **Análisis IA encuestas** semana anterior (`WeeklySurveyAnalysis`).
6. **Reviews externas** (TripAdvisor + Google).
7. **Pipeline interno** completo: ventas última semana, comparativa mes-vs-mes-anterior, mezcla por familia, métodos de pago, packs detectados, top recurrentes, anticipación promedio, disponibilidad próxima semana.
8. **GA4 snapshot** últimos 7 días vs 7 anteriores: sesiones, fuentes, top páginas, eventos custom.
9. **Search Console**: clicks, impresiones, top queries, top páginas.
10. **MetaSnapshot** completo: FB + IG + Ads (28 días).
11. **Análisis IA Meta pre-procesado** (de `meta_analyzer.py`): alertas + oportunidades.
12. **Blog posts recientes** (no repetir temas).
13. **Tendencias históricas** (sub-fase 2C, mayo 2026): series semanales de GA4/Meta/VoC con dirección de tendencia.
14. **Objetivo de la semana** (definido por Jorge en `WeeklyObjective`).
15. **Contexto Operativo** (lo que ya está implementado): para evitar que la IA proponga cosas ya hechas.

**LLM**: Claude Sonnet 4.6 vía OpenRouter, max_tokens=32000.

**Output**: JSON estricto con secciones:
- `resumen_ejecutivo` (headline + 4-6 bullets críticos + alerta crítica)
- `fechas_clave_proximas_4_semanas`
- `diagnostico_meta` (FB + IG + Ads con acciones por responsable)
- `diagnostico_trafico` (GA4 + GSC)
- `diagnostico_comercial` (pipeline)
- `diagnostico_voc` (NPS + reviews + encuestas)
- `tendencias_observadas`
- `plan_semanal_contenido` (drafts por día y canal)
- `recomendaciones_priorizadas`

**Distribución**: email a Jorge + Angélica + equipo. Render guarda el resultado en BD.

### Snapshots semanales

Tres modelos persistidos cada lunes (sub-fase 2A + Meta):

1. **`MetaSnapshot`**: FB fans, IG followers, alcance, engagement rate, ads spend, top posts. Snapshot con `period_days=28` (mes móvil).
2. **`GA4Snapshot`**: sessions, users, conversions, eventos custom, fuentes de tráfico, top páginas. Snapshot de 7 días.
3. **`SearchConsoleSnapshot`**: clicks, impressions, CTR, posición promedio.

Las series semanales acumuladas permiten al brief detectar tendencias semana-vs-semana (mejora/mantiene/empeora) y 4w-vs-4w (más estable, suaviza ruido).

### Tracking server-side (Meta CAPI)

Detallado en 1.4 y 2.2. Resumen: 100% cobertura de conversiones, dedup automática, PII hasheada.

### Análisis IA de Meta

`meta_analyzer.py` corre paralelo al snapshot Meta. Procesa el JSON crudo y produce:
- Alertas: campañas con CPM creciendo >50% en 7 días, posts con engagement <5%, gastos sin retorno.
- Oportunidades: posts virales (engagement >15% del promedio) replicables, audiencias con CTR alto.
- Acciones recomendadas con responsable asignado (Jorge / Daniela).

### Análisis IA de encuestas (VoC)

`survey_ai_analyzer.py` corre los lunes 09:00 sobre las encuestas de la semana:
- Categorización de comentarios (positivos/negativos/sugerencias).
- Detección de temas recurrentes (ej: temperatura tina, atención recepción, mantenimiento).
- Alertas operativas con criticidad (Tarea 1.10: malla antideslizante pasarelas).
- Top promotores con cita textual (para reutilizar en marketing).
- Top detractores con motivo para follow-up.

Persistido en `WeeklySurveyAnalysis`. Consumido por el brief.

## 2.6 Dominio Operaciones

### Sistema de comandas

`Comanda` representa productos consumidos durante la visita (separados de los pre-reservados). Workflow:
1. Cliente reserva (eventualmente con productos pre-pagados).
2. En el momento de la visita, equipo puede agregar más productos vía admin.
3. Comanda se asocia a la `VentaReserva` y aparece en la agenda operativa del día.
4. Estados: `pendiente` → `en_progreso` → `completado`.

### Agenda operativa

`agenda_operativa_view.py` genera vista por hora del día actual:
- Servicios reservados con cliente, slot, masajista asignado, estado de pago.
- Preparaciones requeridas (desayunos para el día siguiente, etc.).
- Alertas: reservas sin masajista asignado, slots con conflicto, comandas atrasadas.
- Filtro por área (recepción, masajistas, cocina, mantenimiento).

### Control de gestión interno

App `control_gestion/`:
- Tareas con swimlane (área), prioridad, dueño, criticidad temporal, fuente.
- Checklist anidado dentro de cada tarea.
- Bitácora de cambios.
- Reportes diarios.

Útil para gestionar:
- Mantenimiento de instalaciones.
- Follow-ups de VoC.
- Compras (stock de productos).
- Tareas comerciales (campañas, contactos).

## 2.7 Dominio Cotizaciones Empresariales (módulo nuevo, mayo 2026)

Implementado para venta B2B (grupos corporativos, retiros de equipo, eventos privados).

### Modelo de datos

- `CotizacionFormal`: documento numerado desde 321 (calculado como `id + 320`).
- `CotizacionItem`: línea individual con servicio o producto + cantidad + precio (snapshot al momento de cotizar).
- Estados: `borrador`, `enviada`, `aceptada`, `rechazada`, `expirada`.
- Datos empresa: razón social, RUT, giro, contacto (nombre/email/teléfono).
- Validez configurable (default 30 días).
- Tracking de estados con timestamps automáticos.

### Generación del documento formal

URL: `/ventas/cotizacion/<numero>/` (staff-only).

Template HTML con look corporativo:
- Header "Aremko Spa Boutique" con número de cotización destacado.
- Datos del destinatario.
- Tabla de ítems con cantidades, precio unitario, subtotal.
- Total destacado.
- Frase de beneficios personalizable (default: "Invertir en el bienestar del equipo es una de las mejores decisiones...").
- Términos y condiciones (validez, forma de pago, RUT, cuenta Mercado Pago).
- Cierre formal.

### Tres botones de acción

1. **Copiar como texto**: copia versión texto plano (monospace, alineada) lista para pegar en WhatsApp o email.
2. **Descargar PDF**: genera PDF tamaño Letter con WeasyPrint, descarga automática a la carpeta Descargas con nombre `Cotizacion_<numero>_<empresa>.pdf`.
3. **Imprimir**: abre el diálogo del navegador.

### Admin Django

- Inline editor de ítems con autocomplete de servicios y productos.
- Auto-completado de `precio_unitario` desde catálogo si se deja vacío.
- Total auto-calculado.
- Badge de estado con colores.
- Botón "Ver documento formal" en cada cotización.
- Acciones masivas: marcar enviada/aceptada/rechazada con timestamps automáticos.

### Configuración global editable

En `ConfiguracionResumen` (singleton), tres campos editables desde admin:
- `cotizacion_frase_beneficios`
- `cotizacion_terminos`
- `cotizacion_cierre`

Si están vacíos, se usa el default del código. Cada cotización también puede override su `frase_beneficios` individualmente.

## 2.8 Dominio Gift Cards

### Compra online

Cliente puede comprar gift cards desde `/giftcards/`:
- Elige monto o experiencia específica (`GiftCardExperiencia`).
- Llena datos del destinatario.
- Personaliza mensaje.
- Paga con Flow.cl o transferencia.

### Generación de PDF

`giftcard_pdf_service.py` usa WeasyPrint:
- Template HTML estilizado con logo, imagen de la experiencia, código único.
- Mensaje personalizado del comprador.
- Fecha de vencimiento.
- Instrucciones de uso.

### Envío automático

Al confirmar pago:
- Email automático al destinatario con el PDF adjunto.
- Email al comprador con confirmación de compra.

### Redención

Al checkout, cliente puede pagar con gift card:
- Ingresa código.
- Sistema valida: existencia, no usada, no vencida, saldo suficiente.
- Crea un `Pago` con `metodo_pago='giftcard'` vinculado al saldo.
- Actualiza `GiftCard.monto_disponible` y `estado`.

### Auditoría

- `GiftCard` mantiene historial de usos.
- Comando `corregir_saldos_giftcards` audita inconsistencias.

## 2.9 Dominio Voz del Cliente (VoC)

### Encuesta nativa post-visita

Implementación interna (sin SurveyMonkey ni Typeform):
- D+1 después del servicio, el cliente recibe SMS con link a `/encuesta-satisfaccion/?token=<unique>`.
- Formulario con escala NPS (0-10), preguntas específicas (calidad/precio, atención, instalaciones, limpieza), comentarios libres.
- Token único por cliente y servicio evita responder dos veces.
- Almacenado en `EncuestaSatisfaccion`.

### Métricas baseline (mayo 2026)

- NPS promedio: **79.8** (alto).
- Calidad-precio: **3.51/5** (área a mejorar, mencionado en análisis IA).
- Encuestas/semana: ~25-40 respuestas activas.

### Análisis IA semanal

`survey_ai_analyzer.py`:
- Categoriza comentarios (positivo/negativo/sugerencia).
- Detecta temas recurrentes con palabras clave + LLM.
- Genera alertas operativas con criticidad.
- Identifica top promotores y top detractores.
- Persiste en `WeeklySurveyAnalysis` para consumo del brief.

### Follow-ups operativos

Para cada cliente que dejó NPS≤6 o comentario negativo:
- Aparece como follow-up pendiente.
- `report_pending_followups` genera `.docx` con sugerencia personalizada por IA del mensaje a enviar por WhatsApp.
- Deborah copia-pega y contacta al cliente.
- Al resolver, marca el follow-up como completado en admin.

## 2.10 Dominio Reviews Externas

### Snapshot semanal

`review_snapshot_service.py` consulta cada lunes:
- **TripAdvisor**: 4.4 estrellas con 258 reviews (mayo 2026), ranking #1 de 14 en Puerto Varas, Travellers' Choice 2024.
- **Google Reviews**: 4.5 con 660 reviews.

`ReviewSnapshot` persiste rating, total, URL, deltas vs semana anterior.

### Reviews individuales

`Review` almacena cada review nueva detectada (autor, fecha, texto, puntaje). Útil para:
- Replicar testimoniales en marketing (con consentimiento implícito).
- Detectar reviews negativas rápido para responder.

### Integración con brief

El brief incluye:
- Status actual (estrellas + total).
- Delta semanal.
- Reviews nuevas notables (positivas y negativas).
- Sugerencia de acción ante reviews negativas.

## 2.11 Dominio Análisis de Competencia

### Modelo

- `Competitor`: nombre + URL.
- `CompetitorSnapshot`: foto semanal con precios, servicios detectados, horarios, promociones, meta description.
- `CompetitorSocialMedia`: métricas IG/FB de competidores (pendiente implementación scraper).

### Scraper

`scrape_competitors` (management command):
- User-Agent Chrome 120 realista + Accept-Language es-CL.
- Regex de precios soporta formatos $24.000, CLP 24.000, 24.000 CLP, 24.000 pesos.
- Lector JSON-LD (schema.org) prioritario antes que regex en HTML.
- Detección de respuestas vacías (<500 bytes) como probable anti-bot.
- Persiste snapshots fallidos con `error_mensaje` claro (no oculta el problema).

### Endpoint para aremko-cli

`GET /ventas/api/competitors-summary/`:
- Lista de competidores con último snapshot exitoso o `last_scrape_error`.
- Comparativa de precios contra precio referencia Aremko (configurable o calculado como promedio de tinas activas).

### Estado por competidor (mayo 2026)

| Competidor | Estado | Detalles |
|---|---|---|
| Termas del Sol | ✅ OK | $24.000, 3 servicios detectados |
| Termas Cochamó | ✅ OK | $5.000 mínimo, 3 servicios + promociones |
| Cancagua | ⚠️ Parcial | Servicios + meta description, precio no en HTML |
| Alma Lemu | ❌ Bloqueado | Anti-bot bloquea IPs de Render (Cloudflare). Requiere Playwright/proxy |

### Sub-fase 2B planificada

Migrar scraper a **Playwright CLI** para sitios JS-heavy y con anti-bot agresivo. Pendiente de implementación.

## 2.12 Dominio Catálogo Turístico Paralelo (DPV)

App `destino_puerto_varas/`: proyecto independiente que comparte infraestructura con Aremko.

### Catálogo

- `Place`: lugares turísticos (cascadas, miradores, restaurantes, etc.).
- `PlacePhoto`: galería con metadatos.
- `Circuit`: circuitos turísticos sugeridos.
- `CircuitDay`, `CircuitPlace`: estructura día-a-día.
- `DurationCase`: catálogo de duraciones típicas (1 día, 2 días, fin de semana, etc.).

### Motor de recomendación

- `RecommendationRule`: reglas de matching (perfil viajero → circuito).
- `AremkoRecommendation`: tarjeta de recomendación con CTA a Aremko.
- `TravelTip`: tips de viaje útiles.

### Agente IA conversacional

- `LeadConversation`: conversación de un visitante con el agente.
- `ConversationMessage`: cada mensaje del histórico.
- `AgentPromptTemplate`: prompts del LLM para distintas etapas.
- Captura leads y los deriva a Aremko cuando aplica.

### Sitio público

- `/dpv/` muestra preview en infra Aremko.
- A futuro: dominio propio `destinopuertovaras.cl`.

## 2.13 Blog Editorial (aremko_blog)

App aislada y portable:
- `BlogPost` con `body_md` (markdown → HTML al render).
- `BlogCluster` (TextChoices) para agrupar por tema SEO.
- Templates editoriales propios.
- Sitemap automático para SEO.
- Sistema de skill `blog-aremko` (Claude Code) genera posts como management commands.

URL pública: `aremko.cl/blog/`.

## 2.14 APIs para aremko-cli y agentes externos

Endpoints diseñados específicamente para consumo programático:

### `/ventas/api/aremko-cli/` (read-only)

- `health/` — health check.
- `bookings/stats/` — estadísticas básicas en rango.
- `bookings/daily/` — desglose diario.
- `bookings/by-family/` — agrupado por familia (Tinas/Masajes/Cabañas/Otros) con comparativas mes-anterior y año-anterior.
- `bookings/by-family-mtd/` — Month-to-Date (1ro del mes hasta ayer) con comparativas.
- `bookings/weekly-breakdown/` — 12 semanas hacia atrás, matriz familia × clientes nuevos/recurrentes + summary con trend.
- `bookings/detalle/` — fila por fila, con filtros (familia, servicio, proveedor, cliente) y agrupado inteligente para evitar duplicados aparentes.
- `bookings/by-payment-method/` — agrupado por método de pago.
- `clients/stats/` — clientes únicos/nuevos/recurrentes en rango.
- `operating-context/` — markdown del Contexto Operativo (sección automática + manual).

### `/ventas/api/cron/` (con header X-API-KEY)

- `marketing-brief/` — dispara el brief semanal.
- `snapshot-weekly-traffic/` — dispara snapshots GA4/GSC.
- `analyze-surveys-weekly/` — dispara análisis IA VoC.

### `/ventas/api/competitors-summary/` (público read-only)

- Resumen de competidores con último snapshot o error.

### `/ventas/api/reviews-summary/` (público read-only)

- Resumen consolidado de reviews TripAdvisor + Google.

### Auth y CORS

- Endpoints `cron/` requieren header `X-API-KEY` con valor `AUTOMATION_API_KEY`.
- Endpoints públicos open sin auth (read-only, datos no sensibles).
- CORS configurado para permitir `aremko-cli-frontend.vercel.app` y dominios autorizados.

### Performance

- Cache HTTP de 1h en endpoints estables (`operating-context`).
- `select_related` y `prefetch_related` en queries con JOINs.
- `statement_timeout=8s` en queries de detalle para protección.
- Hard cap de 500 filas en endpoints detallados.

## 2.15 Contexto Operativo para Agentes IA

`ContextoOperativo` (singleton, modelo creado mayo 2026): permite inyectar al system prompt de cualquier LLM consumidor un markdown actualizado con todo lo que ya está activo en Aremko.

### Sección automática

Auto-descubierta del código y BD cada hora:
- Triggers de comunicación activos.
- Plantillas SMS / Email activas con tipo y contenido resumido.
- Packs de descuento vigentes con descripción y vigencia.
- Gift cards activas (resumen agregado).
- Campañas en curso.
- Cron jobs conocidos en cron-job.org (con schedule y descripción).
- Reglas de negocio hardcoded (anti-spam, cabaña 16:00, desayuno auto-mapeo, ambientaciones, precios planos AR-014).

### Sección manual

Editable por Jorge desde admin Django: información que NO está en código (campañas de marketing externas, alianzas vigentes, decisiones de management, iniciativas).

### Uso

Cualquier agente IA externo (aremko-cli, Luna, otro) consume el endpoint `/ventas/api/aremko-cli/operating-context/` antes de analizar y inyecta el markdown como bloque "## Contexto Operativo Aremko" en su system prompt. Esto evita que el LLM proponga acciones ya implementadas.

---

# Parte 3 — Automatizaciones e Inteligencia Artificial

## 3.1 Calendario de cron jobs activos

Disparados por cron-job.org externo, hitting endpoints HTTP con `X-API-KEY`:

| Día y hora (Chile) | Job | Acción |
|---|---|---|
| Lunes 09:00 | `snapshot_weekly_traffic` | Persiste GA4 + GSC + reviews semanales |
| Lunes 09:00 | `analyze_surveys_weekly` | Análisis IA de encuestas, persiste en `WeeklySurveyAnalysis` |
| Lunes 10:00 | `generate_weekly_marketing_brief` | Genera y envía brief consolidado |
| Diario varios | `send_communication_triggers` | Disparador central de comunicaciones (recordatorios, post-visita, etc.) |
| Cada 30 min | `cleanup_pending_reservations` (sugerido) | Expira PendingReservation sin pago |
| Diario | `report_pending_followups` | Reporte VoC con sugerencias IA |
| Semanal | `scrape_competitors` (sugerido) | Refresca CompetitorSnapshot |

## 3.2 Signals Django activos

`ventas/signals/main_signals.py` contiene los signals principales:

1. **`update_lead_status_on_activity`** (`post_save Activity`): Lead pasa a "Contacted" en primera actividad.
2. **`actualizar_tramo_y_premios_on_pago`** (`post_save VentaReserva`): cuando estado_pago = pagado → actualiza tramo del cliente. Si llega a hito (5, 10, 15, 20 visitas) → crea `ClientePremio`.
3. **`_track_estado_pago_anterior`** (`pre_save VentaReserva`): registra estado previo en instance attr para detección de transición.
4. **`disparar_meta_capi_purchase_on_pago`** (`post_save VentaReserva`): cuando transita a pagado, dispara CAPI Purchase con event_id determinístico. Cubre Flow + transferencia + admin + WhatsApp.
5. **Signals de inventario** (`post_save ReservaProducto`): decrementa stock automáticamente.
6. **Signals de auditoría** (`post_save Cliente`): registra cambios en `MovimientoCliente`.
7. **Signals de Comanda** (`post_save Comanda`): actualiza totales de la venta vinculada.
8. **Signals de Pago** (`post_save Pago`): recalcula `VentaReserva.calcular_total` que a su vez actualiza `estado_pago`.

`ventas/signals/giftcard_signals.py` maneja la lógica específica de gift cards (creación automática al detectar venta de gift card en `ReservaProducto`).

## 3.3 Sistemas IA implementados

| Sistema | Modelo LLM | Trigger | Output |
|---|---|---|---|
| Brief semanal de marketing | Claude Sonnet 4.6 (OpenRouter) | Lunes 10:00 | JSON con 8 secciones + drafts de contenido |
| Análisis Meta | Claude Sonnet 4.6 | Junto al brief | Alertas + oportunidades + acciones por responsable |
| Análisis encuestas VoC | Claude Sonnet 4.6 | Lunes 09:00 | Categorización + alertas operativas + top promotores/detractores |
| Sugerencias WhatsApp para follow-ups | Claude Sonnet 4.6 | Bajo demanda | Mensaje personalizado por cliente con NPS bajo |
| Variaciones anti-spam en email | Deepseek vía OpenRouter | Cada envío masivo (opcional) | Variaciones del mismo contenido |
| Generación de propuestas comerciales | Claude Sonnet 4.6 | Bajo demanda | `ai_proposal_service.py` |
| Agente DPV conversacional | OpenAI GPT (modelo configurable) | Cada mensaje del visitante | Respuesta + captura de datos |
| Generación de blog posts | Claude (vía skill `blog-aremko`) | Bajo demanda | Management commands con posts completos |

## 3.4 Memoria persistente para agentes

Tres niveles de memoria:

1. **Memoria del proyecto Claude Code** (en `~/.claude/projects/.../memory/`): notas de sesión, decisiones, preferencias del usuario.
2. **`ContextoOperativo` en BD**: estado vivo del sistema, inyectable al system prompt.
3. **NotebookLM "Jorge's AI Brain"**: resúmenes de sesión históricos, fuentes de documentación, queryable en NL.

---

# Parte 4 — Capacidades para futuras integraciones y extensiones

## 4.1 APIs públicas disponibles

Resumen ya cubierto en sección 2.14. Pueden ser consumidas por:

- **aremko-cli** (Next.js + Go).
- **Agentes LLM con function-calling** (Luna, ChatGPT custom GPTs, Claude apps).
- **Sistemas externos** (BI tools, sistemas contables, ERPs).
- **Apps móviles** (futuras, no implementadas).

## 4.2 Extensibilidad por código

### Patrón "services + signals + commands"

Para agregar una nueva funcionalidad típica:
1. Definir el modelo en `ventas/models.py`.
2. Crear migración manual (regla del proyecto: no `makemigrations` automático en prod).
3. Implementar lógica de negocio en `ventas/services/<dominio>_service.py`.
4. Conectar a eventos automáticos via signals en `ventas/signals/main_signals.py`.
5. Exponer al usuario via view en `ventas/views/`.
6. Registrar URL en `ventas/urls.py`.
7. (Si requiere admin Django) Registrar en `ventas/admin.py`.
8. (Si requiere consumo desde aremko-cli) Agregar endpoint en `ventas/api_aremko_cli.py`.
9. (Si requiere análisis IA) Inyectar al `ContextoOperativo` para que los LLMs sepan que existe.

### Convenciones del proyecto

- Migraciones manuales en Render shell (NO auto-migrate).
- Comandos largos via Render Cron Jobs o cron-job.org (NO subprocess.Popen).
- Español latinoamericano en UI (tuteo, NO voseo).
- Env vars con línea explícita en `settings.py` para garantizar carga.
- Documentar memoria en `~/.claude/projects/.../memory/`.

## 4.3 Casos de uso para próximas iteraciones

Documentados en el plan integral marketing (en memoria del proyecto):

1. **Sub-fase 2B** — Playwright CLI para scrapers (competidores anti-bot, TripAdvisor, Booking, etc.).
2. **Sub-fase 2C** — Brief con tendencias semana-vs-semana (parcialmente implementado).
3. **Vistas multi-usuario en aremko-cli** — dashboards diferenciados por rol (CEO, comercial, operaciones).
4. **Agente Recepcionista** — asistente IA para front office (6 fases planificadas).
5. **Generador de plan semanal de contenido automatizado con drafts** (extiende el brief).
6. **Cobranza automatizada** (recordatorios escalonados para pagos pendientes).
7. **Programa de referidos** (incentivos cliente-referido).

---

# Parte 5 — Información de contacto y soporte

## 5.1 Equipo Aremko

- **Jorge Aguilera** (ecolonco@gmail.com): CEO, decisiones estratégicas, configuración Meta/Google/Render.
- **Angélica**: gerencia general.
- **Daniela Almonacid**: marketing y redes sociales (Instagram, boosts).
- **Deborah**: ventas WhatsApp y follow-ups.
- **Ernesto**: operaciones.

## 5.2 Cuentas Aremko Spa Boutique

- Dominio principal: `aremko.cl` (sitio + Sistema Aremko).
- Email comercial: `ventas@aremko.cl`.
- Email comunicaciones: `comunicaciones@aremko.cl`.
- Ubicación: Puerto Varas, Región de Los Lagos, Chile.
- WhatsApp: +56 9 7666 8080.
- Instagram: @aremkospa.
- Facebook: Aremko Spa Boutique.

## 5.3 Tecnología y proveedores

- Hosting aplicación: Render (Oregon, USA).
- Hosting BD: Render PostgreSQL.
- Pasarela de pago: Flow.cl.
- Email: SendGrid.
- SMS: Redvoiss (Chile).
- Media: Cloudinary.
- IA: OpenRouter (Claude Sonnet 4.6).
- Scheduler: cron-job.org.
- Analytics: Google (GA4, Search Console).
- Pixel: Meta Business Manager.

## 5.4 Documentación adicional

Documentación viva del sistema en el repositorio:
- `CLAUDE.md` — guía técnica para agentes IA.
- `docs/MARKETING_PLAYBOOK.md` — playbook de marketing (voz, personas, diferenciadores).
- `docs/AREMKO_RECURRING_TASKS.md` — cadencia operativa por día.
- `docs/SISTEMA_AREMKO_COMPLETO.md` — este documento.
- `docs/MASTER_PLAN.md` — plan maestro de evolución del sistema.

---

**Fin del documento.**

_Última actualización: 20 de mayo de 2026._
_Versión 1.0._
_Generado para Aremko Spa Boutique — Puerto Varas, Chile._
