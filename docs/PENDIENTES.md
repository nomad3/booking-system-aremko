# Pendientes Aremko (backlog vivo)

Lista única de temas pendientes Jorge ↔ Claude. **Uso:** al completar un tema se
ELIMINA de la lista (git guarda la historia); los IDs `P-xx` son estables y no se
reutilizan. Para agregar: "agrega a pendientes: …". Para cerrar: "listo el P-xx".
Claude la revisa al inicio de sesión y en cada wrapup.

_Última revisión: 2026-08-06_

## Web y marketing

2. **P-02 · Fotos definitivas a carruseles GiftCards** — Reemplazar fotos provisorias
   de las 4 experiencias insignia. Hay 80 fotos optimizadas en `*/_web/` del disco
   JAguilera.
4. **P-04 · Menú/navegación limpia site-wide** — La home boutique ya tiene menú
   limpio; falta extenderlo al resto del sitio.
5. **P-05 · Campañas Ritual + Pausa en Meta y Google** — Arrancar verificando los
   paneles (plan 2026-06-26). El material de Pausa (keywords, RSA, anuncios) quedó
   listo en aremko-cli.
6. **P-06 · GiftCards F2/F3** — Entrega programada, canje conversacional con Luna,
   bonus estacional y campañas de email de giftcards.

## Pagos y conciliador

7. **P-07 · Activar auto-aplicar del Conciliador** — Tras ~2 semanas de calibración
   supervisada (desde 2026-07-06 → revisar ~2026-07-20): matches únicos se aplican
   solos, Deborah solo mira los "revisar".
8. **P-08 · Limpiar tanda histórica del Conciliador** — Deborah marca "Ignorar" los
   movimientos antiguos ya registrados a mano, para dejar la cola en cero.
9. **P-09 · Decisión Flow → MP en el checkout web** — Hoy conviven; definir si el
   carrito público migra a Mercado Pago (cuotas también en la web).
10. **P-10 · Reserva de prueba #6221** — Anular/reembolsar desde el panel MP los
    $2.500 reales del test de cuotas, para no ensuciar métricas.
16. **P-16 · Boletas electrónicas SII automáticas** — **F1 DESPLEGADA 2026-07-11**
    (criterio giftcard aclarado: la venta de giftcard es un producto más — boletea
    según el medio de pago de la compra; el canje nunca boletea)
    (app `facturacion/` en ambiente simulado: MedioPago con switch genera_boleta,
    emisor idempotente vía SimpleAPI, acción "Emitir boleta" en Pagos, página
    pública /boletas/consulta/, diagnóstico --smoke). Detalle y runbook completo:
    `docs/BRIEF_P-16_boletas_sii.md`. **Pasos de Jorge COMPLETADOS 2026-07-12**:
    API key SimpleAPI ✓, certificado .pfx en Render ✓ (verificado con
    `--exigir-credenciales`), certificado instalado en Llavero ✓, POSTULACIÓN
    ACEPTADA en el SII (solo Boleta Electrónica afecta; software "AREMKO BOOKING
    SYSTEM") ✓, set de pruebas descargado ✓ (5 casos —
    `docs/certificacion_sii/Set_Prueba_BE.txt`; multi-ítem, ítem exento en
    CASO-4, unidad Kg en CASO-5, referencia SET/CASO-N obligatoria).
    El SII CONFIRMÓ la exclusividad: al AUTORIZARSE se pierde el sistema
    gratuito (solo al final; antes del switch: respaldar documentos del portal
    + OK del contador). **CERTIFICACIÓN 2026-07-12 PM**: CAF cert 1-50 cargado
    vía API + las 5 BOLETAS DEL SET TIMBRADAS (folios 1-5, exento y Kg OK).
    Pendiente SOLO el envío del sobre: SII cert responde 500 (4 intentos,
    sábado; reintento nocturno programado; comando idempotente
    `ejecutar_set_pruebas` reutiliza lo timbrado). Bitácora en admin (caso
    __LOG__). Si persiste → soporte SimpleAPI. Después: declarar avance +
    muestras impresas → declaración de cumplimiento (Jorge) → switch
    producción. F2 (cola automática) y F3 (notas de crédito) tras el switch.
    F1: app `facturacion/` + tabla `MedioPago` con flag `genera_boleta` (siembra de
    los 21 métodos, editable en admin; pedido por Jorge para evitar dobles boleteos)
    + botón manual. F2: señal post_save(Pago) + cola (patrón conciliador) + candado
    1-a-1 boleta↔pago. F3: notas de crédito + cuadratura mensual.

22. **P-22 · Jornada de orden contable: plan de cuentas + registro mensual de
    ingresos y gastos** — Pedido de Jorge 2026-08-06 tras el diagnóstico de correos.
    **Diagnóstico:** las bandejas están descuidadas (miles de correos sin leer, avisos
    de pago y de servicios enterrados) y no existe un registro consolidado de gastos
    ni de ingresos; la conciliación cubre solo Mercado Pago. Nadie tiene hoy el número
    de "cuánto gastó Aremko este mes" ni "de dónde entró la plata".
    **Alcance de la jornada (bloque de trabajo dedicado, no incremental):**
    (a) definir un **plan de cuentas** simple para Aremko — categorías de ingreso por
    canal (Flow, Mercado Pago, transferencias, giftcards) y de gasto (infraestructura
    web, publicidad, remuneraciones, impuestos, insumos, servicios básicos, seguros);
    (b) decidir **dónde vive el registro** (extender `costos_web`, app nueva, o
    planilla) y cómo se alimenta desde el correo — ver el diseño de `EventoCosto`
    conversado el 2026-08-06;
    (c) **cerrar los circuitos de plata** ya mapeados: MP recauda → barre a Scotiabank
    → de Scotiabank salen sueldos, SII y contador (Patricio Rubio → Previred);
    (d) **cuadratura mensual** de ingresos vs. lo que registra el sistema de reservas.
    **Insumo ya listo:** el mapa de las 4 casillas y sus remitentes de cobro está en la
    memoria `reference_correos_jorge_mapa`, y desde el 2026-08-06 hay filtros que
    reenvían lo relevante de `ecolonco1`, `aremkospa` y `abonosaremko` a `ecolonco`.
    **Punto ciego conocido:** Scotiabank no avisa por correo los abonos entrantes
    (Banco de Chile y MP sí) → pedir a la ejecutiva que active esos avisos.

## Infraestructura y Luna

11. **P-11 · Logging de errores 500 en Render** — Agregar handler para el logger
    `django.request` (hoy los 500 no dejan traceback; se diagnostican con
    `diagnosticar_admin_add --url`).
12. **P-12 · Luna FASE 3 y 4** — Cron de seguimiento de propuestas + combos en el
    carrito.
13. **P-13 · Máquina de reseñas Google** — Pedir reseña post-visita vía Luna
    (diseñada en plan, no iniciada).
14. **P-14 · Tina Calbuco para grupos de 3** — Configurar `capacidad_minima=3`
    ($75.000 para 3 personas) en el admin.
15. **P-15 · WhatsApp Cloud API / Meta** — Destrabar App Review (decidir App propio
    vs BSP) y rotar el APP_SECRET de la bandeja de Instagram.

## Asistente de Publicaciones (community manager)

> Este módulo (cola semanal + revisión IA de material + publicar en un clic) se
> está perfilando como **producto vendible por sí mismo** — encaja con el M17
> "Asistente de Publicaciones" del catálogo Datamatic Hospitality. Diseñar
> multi-tenant desde ya (los destinos GBP/IG y la ficha ya salen de constantes
> aisladas, pensadas para mover a config del tenant). Ver `[[project_datamatic_hospitality_modulos]]`.

<!-- P-18 (revisión de reels/videos) cerrado 2026-07-19 como H-065/H-066-F2: subida
     de video + fotogramas por URL Cloudinary + revisor IA por clip, verificado en
     vivo. Pendiente solo el front de aremko-cli (ya tiene el contrato). -->

## Veladas & Celebraciones (experiencias-regalo)

19. **P-19 · Plan Veladas (V-01…V-23)** — Convertir la Experiencia Romántica en un
    negocio de experiencias-regalo que venda todo el año (aniversarios/cumpleaños
    evergreen + bengalas estacionales), abrir **tinas grupales** (despedidas de
    soltera/o, gender reveal reusando el color, escapadas de amigas) y el **segmento
    empresas** (giftcards corporativas, incentivos, convenios). Backlog completo en
    `docs/PLAN_VELADAS.md`. **Tablero interno OCULTO** (estado vivo, se actualiza a
    medida que avanzamos): ruta `panel-veladas-09c7c72cd1/` en `aremko_project/urls.py`
    → `ventas/views/plan_veladas_view.py` (editar `estado` de cada V-xx y desplegar).
    Base ya construida y LIVE: configurador + invitación + taxonomía + F2-B/F2-C
    bebidas + chocolates. Ver `[[project_aremko_experiencia_romantica]]`.

20. **P-20 · La Ficha como app + upsell (F-01…F-10)** — Convertir la Ficha de Reserva
    del cliente (`/reserva/<token>/`) en una mini-app: que la abran, la entiendan y
    **compren más desde ahí** (tina→masaje, masaje→noche, 1 noche→2 noches). Problema =
    adopción, no información; dos embudos (abrir / activar), hoy ciegos en aperturas.
    Fases: **Abrir** (F-01 medir, F-02 reencuadrar mensaje "Tu Aremko", F-03 onboarding) ·
    **Vender** (F-04 upsell contextual, F-05 sumar a un toque, F-06 medir conversión) ·
    **Volver** (F-07 nudges Luna, F-08 QR físico) · **App** (F-09 guardar en pantalla,
    F-10 avisos). Backlog en `docs/PLAN_FICHA.md`. Empezar por F-01 + F-02 (medir +
    reencuadrar) antes de tocar la ficha. Ver `[[project_aremko_ficha_reserva_digital]]`.

21. **P-21 · Notas de producción se cuelan literales en el compositor de historias** —
    El texto del brief a veces trae anotaciones entre corchetes (ej. "[Sticker link a
    wa.me/…]", placeholders "[X]°C") que hoy salen TAL CUAL sobre la imagen compuesta
    (H-073/B2-A) en vez de tratarse como instrucción para quien redacta/publica.
    Detectado 2026-07-25 en la validación e2e de H-073 (sábado 25/07 · Historia 3).
    Opciones a evaluar: separar en el brief texto-visible de nota-de-producción (dos
    campos), que el compositor filtre/oculte lo que va entre corchetes antes de
    renderizar, o dejarlo como paso manual de Angélica (editar antes de generar). NO
    bloqueante — no toca la selección de foto, que funcionó bien. Ver `docs/HANDOFFS.md`
    fila H-073.
