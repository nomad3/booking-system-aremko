# Pendientes Aremko (backlog vivo)

Lista única de temas pendientes Jorge ↔ Claude. **Uso:** al completar un tema se
ELIMINA de la lista (git guarda la historia); los IDs `P-xx` son estables y no se
reutilizan. Para agregar: "agrega a pendientes: …". Para cerrar: "listo el P-xx".
Claude la revisa al inicio de sesión y en cada wrapup.

_Última revisión: 2026-08-20 (P-33 cerrado; P-34 carta EN PROD, revisar resultados ~27/08)_

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
    **F1 CONSTRUIDA 2026-08-08:** app `finanzas/` (solo superusuario, aislada
    drift-safe): cuentas financieras (6: MP, BancoEstado Cuenta Pro, Scotiabank,
    efectivo, Visa ••••2936, Mach), plan de cuentas mínimo (13 categorías),
    `MovimientoFinanciero` (gasto/traspaso con jerarquía de fuentes api>correo>
    captura>manual e idempotencia por referencia), `SaldoMensual` (ancla del
    cierre: saldo anterior + entradas − salidas), tablero en `/finanzas/tablero/`
    (ingresos leídos DIRECTO de `Pago` — sin duplicar, sin cron; canje giftcard
    excluido del ingreso; meses sin gastos muestran «—», no un resultado
    mentiroso), botón admin "Registrar traspaso" que crea las 2 piernas, y carga
    histórica jun–ago 2026 (211 movs; corte julio decidido 2026-08-08: quedan
    124 desde el 1-jul). Comandos: `sembrar_finanzas` +
    `cargar_historico_finanzas [--aplicar] [--desde]`. **Mapa de dinero cerrado
    2026-08-08:** Flow Y SumUp liquidan a BancoEstado (visto en cartola en
    línea); BCh no es cuenta de Aremko.
    **F2 CONSTRUIDA 2026-08-08:** (A) sección «Verificación Mercado Pago» en el
    tablero — por día, 14 días, Pago vs MovimientoMP excluyendo solo ajenos por
    `MOTIVO_NO_ES_COBRO` (lo ignorado por Deborah SÍ cuenta: es plata que entró);
    (B) compras vía MP (Aremko pagador) → gasto automático `finanzas.services.
    registrar_compras_mp` (por clasificar, fuente api, ref `mp:<id>`, corte
    julio, cuenta según payment_type: account_money→MP, credit_card→Visa),
    enganchado dentro de `traer_pagos_mp` (un fetch, dos consumidores);
    (C) Cron Job «revisar pagos» CREADO y verificado en Render 2026-08-08
    (horario, `0 * * * *`; primera corrida OK: «MP: 17 pagos revisados»).
    **F3 CONSTRUIDA 2026-08-08:** comando `ingerir_correos_finanzas` (IMAP
    solo-lectura a ecolonco, modo lectura default, idempotente por Message-ID)
    parsea los correos MP «Tu transferencia fue enviada» → remuneraciones /
    insumos / traspaso MP→Scotiabank con dos piernas; guardia anti-solape con
    la carga histórica (hist:mp misma fecha+monto). Paraguas cronable
    `auditoria_horaria` = traer_pagos_mp + ingerir_correos (pasos aislados).
    Pendiente de Jorge: App Password de Gmail → env `GMAIL_FINANZAS_APP_PASSWORD`
    en el cron + cambiar el Command del cron a `python manage.py auditoria_horaria`.
    **Datos de Jorge 2026-08-08:** SumUp deposita en la Chequera Electrónica
    BancoEstado (cuenta renombrada en sembrar); el portal BancoEstado SÍ tiene
    botón Exportar → F4 va por CSV/XLS subido, no OCR ni PDF con clave; la
    débito ••••5702 sigue sin dueño confirmado.
    **F4 CONSTRUIDA 2026-08-08 (pasos 2-4):** comisiones MP automáticas por
    cobro (fee_details → gasto 'comisiones', ref mp:fee:<id>; backfill corrido:
    141 por $508.999 desde julio); página /finanzas/cargar-cartola/ que acepta
    el XLSX de BancoEstado Y el .xls de Scotiabank (detección por bytes, cadena
    de saldos verificada, estados nuevo/ya está/en histórico/revisar contra
    dobles conteos, cierres de mes derivados) — cargadas ambas cartolas reales
    (36 + 44 movimientos; anclas julio: BE $15.865.429, Scotia $490.434);
    vista /finanzas/flujo-caja/ día a día desde el 1-ago (hoy hacia atrás):
    entradas/salidas sin traspasos + saldo por cuenta (ancla + acumulado) +
    total, con frescura declarada por fuente y cuentas sin ancla en «—».
    **F6 PLAN DE CUENTAS DE JORGE (2026-08-08 noche):** 14 grupos definidos
    por él (sueldos+imposiciones / masajistas / energía Crell / marketing /
    infra web e IA / admin y financieros / operación e insumos / combustibles /
    impuestos / personales Martín-Alda-Jorge) con categorías y REGLAS por
    beneficiario en finanzas/reglas.py (Nancy-Claudio-Rafael=sueldos;
    Carolina-Sandra-Paul-Sofía=masajistas; Cintia y Javiera=personal Alda;
    Cristian=infraestructura; Martín además presupuesto $300k/mes vía TEF a
    Jorge, se reasigna a mano). Migración 0002 (grupo), comando
    aplicar_plan_cuentas (lectura/--aplicar), categoría editable EN LA LISTA
    del admin (list_editable + filtro por grupo), tablero con subtotales por
    grupo y Resumen con Resultado operacional vs Retiros familia. Retiros Alda
    quedan «por analizar con ella». 4 anclas cargadas (flujo completo con
    detalle expandible por día); barrido 05-08 \$1M repuesto a mano.
    Pendiente: anclas — LISTAS; brecha residual Scotiabank ~\$54.240 (cazar con
    cartola agosto fresca); cartolas se suben a diario (decisión de Jorge:
    revisión diaria manual); combustibles y comercios REDCOMPRA ambiguos se
    asignan a mano; reporte de diferencias en el briefing de Luna Interna.
    **ACCESO ALDA CONSTRUIDO 2026-08-09:** grupo Django «Finanzas colaborador»
    — las 3 vistas (tablero/flujo/cartola) aceptan superusuario O grupo; en
    Movimientos el grupo ve todo y solo edita la categoría (triaje); crear/
    borrar/traspasos siguen solo-dueño; enlaces en cabecera admin para el
    grupo. Alta: `python manage.py configurar_acceso_alda` (usa el usuario
    EXISTENTE de Alda, contraseña intacta; `--usuario X` si hay ambigüedad).
    **F7 SIGUIENTE SESIÓN — cuenta puente Scotiabank Alda:** parser BSA.dat
    (`;`, DDMMYYYY, coma decimal), cuenta fuera del flujo, conversión
    Aremko→Alda a traspaso SOLO con calce en su cartola, cargos default
    personal, vale vista \$558.318→impuestos, pedir estado de la TARJETA
    (65% del gasto) y reenvío de correos de atoloza1970 a ecolonco.
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

23. **P-23 · Preguntarle a Deborah qué significa su "ignorar" en el Conciliador** —
    En julio 2026, de $21,5M que Mercado Pago recibió, **$16.376.500 (140 movimientos,
    76%) terminaron en `ignorado` y solo $1.272.000 en `aplicado`**. Se investigó el
    2026-08-08 pensando que era ruido de la herramienta: se encontró y arregló un bug
    real (el fetch traía también las compras que Aremko hace por MP), pero eran solo
    **19 movimientos de 401, menos del 5%**. La hipótesis del ruido NO explica el 76%.
    **Es una pregunta de operación, no de código:** *"cuando marcas ignorar, ¿estás
    diciendo que ese pago ya lo registraste a mano, o que no sabes qué hacer con él?"*
    Si es lo primero, el Conciliador no está ahorrando trabajo y hay que decidir si
    vale la pena mantenerlo; si es lo segundo, hay pagos de clientes sin aplicar y la
    cola es peor de lo que se ve. **Bloquea saber si P-22 tiene que ocuparse también
    de los ingresos o solo de los egresos.** Detalle en `[[project_aremko_conciliacion_pagos]]`.

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
24. **P-24 · La BD de test no se puede crear (ningún test corre)** — `manage.py test`
    muere aplicando migraciones: `column "tramos_validos" of relation "ventas_premio"
    already exists`. Como la BD de test se crea desde cero, **hoy no corre un solo
    test del repo**: el 2026-08-15 quedaron 26 tests escritos sin ejecutar (check-out
    de la agenda, hora del pedido, y los siete arreglos de gift cards H-099…H-105).
    Reparar drift-safe (`SeparateDatabaseAndState` + `ADD COLUMN IF NOT EXISTS`, ver
    `ventas/migrations/0134`): prod ya tiene la columna, el arreglo debe ser no-op
    contra prod. **OJO:** `makemigrations ventas --check` también reporta drift
    preexistente (índices como `producto_comanda_idx` de la 0082 que el modelo no
    declara) — NO generarlas a ciegas: borrarían índices vivos.
25. **P-25 · El editor «Corregir cotización» no sabe de gift cards** — En la bandeja
    (repo `aremko-cli`) no se puede corregir una cotización de gift card: exige ≥1
    servicio en las tres capas (`CotizacionCajon.tsx`, `luna.go`, `editar_propuesta`
    en Django). **Relajar solo la validación ROMPE la venta**: `recalcular_propuesta`
    recalcula el total con servicios+productos y dejaría las cartas guardadas pero
    invisibles (una cotización de $100.000 quedaría en $20.000). Primero enseñarle a
    `editar_propuesta` a conservar y sumar las gift cards, después destrabar las tres
    capas. Toca 2 repos y 3 deploys (Django, Vercel, backend Go a mano). Mientras
    tanto el camino es pedírselo a Luna por chat, que sí sabe (H-105).
26. **P-26 · El cron de vaciado de tinas falla cada media hora** — `gen_vaciado_tinas`
    tira `value too long for type character varying(16)` procesando el servicio 13913
    (visto 2026-08-15 a las 18:30 y 19:00 UTC): un campo se pasa de largo y esa tarea
    de vaciado no se genera. Nadie se entera porque el cron sigue corriendo.
27. **P-27 · Sincronización iCal con OTAs — pendientes del panel y las otras 4 cabañas** —
    Las DOS fases están operativas para la **Cabaña Torre** (2026-08-16): Fase 1
    verificada (Booking leyó el `.ics` y bloqueó el 21-22 con el 23 libre) y Fase 2 en
    marcha — Cron Job `sincronizar-calendarios-ota` en Render (`*/15 * * * *`, clon de la
    config de «revisar pagos»; primera corrida en verde). El cron espeja, no acumula
    (`ventas/ota_sync.py`); el exportador excluye los bloqueos `[OTA]` para no hacer eco.
    Falta: **(a)** confirmar si «Habitación Doble» de la propiedad Booking 15112726 es
    efectivamente la Torre o agrupa varias cabañas, **antes** de conectar las otras
    cuatro; **(b)** revisar por qué Booking muestra «Cerrado» el 18, 23 y 25 de agosto —
    no salió de Aremko, el 18 y 25 son martes pero el 23 es domingo y no calza con nada;
    **(c)** conectar las otras 4 cabañas cuando (a) esté resuelto (crear su Calendario en
    el admin + pegar URLs en ambas direcciones, mismo flujo que la Torre); **(d)** la
    primera reserva real por Booking será la prueba end-to-end del cron — mirar que el
    bloqueo `[OTA]` aparezca solo. Al cron nuevo le faltan SENDGRID/Redvoiss (hoy
    irrelevante: no manda nada), anotarlo si algún día se le suma alerta de overbooking
    por email. Ver `[[project_aremko_ical_ota_sync]]`.
28. **P-28 · Tests en rojo en main** — Detectados 4 el 2026-08-15 y confirmados como
    preexistentes (aparecen también con mi trabajo guardado en stash). Dos vienen de
    reglas que Jorge pidió ese mismo día y son arreglo trivial: strings que todavía dicen
    "carta" en vez de "Gift Card" en `whatsapp_agent/giftcards.py`, y un `{# … #}` sin
    cerrar en el template de la agenda. Los otros dos son cambios de comportamiento de
    otra sesión — **no tocarlos sin preguntar**. Falta la decisión de Jorge sobre si
    arreglar los dos primeros.
<!-- P-33 (recordatorios de Luna, H-109) CERRADO 2026-08-20: runner Go + migración +
     env + cron recordatorios_luna operativos; 2 recordatorios reales enviados y
     verificados E2E. Detalle en docs/HANDOFFS.md fila H-109. -->
34. **P-34 · Primeras respuestas: medir el efecto de la carta + motivo de rechazo** —
    **HECHO (2026-08-20):** estudio con `estudiar_primeras_respuestas` (369 muertas vs
    255 cotizadas: el separador es la CONCRETUD — horarios 49,6% vs 76,5%; velocidad y
    largo no separan; el 67% de las muertas YA cerraba preguntando) + **carta de precios
    EN PROD** (`whatsapp_agent/carta.py`, commit 67049335): apertura genérica → escalera
    completa $40k→$290k desde el catálogo vivo, sin preguntas de calificación antes.
    Verificada en vivo por Jorge con "servicios" y "precios". **FALTA:**
    **(a) Revisar resultados ~27/08** — antes de mirar, correr
    `python manage.py clasificar_conversaciones --dias 10 --limit 60` (las conversaciones
    nuevas necesitan clasificación para comparar); luego re-correr
    `estudiar_primeras_respuestas` y mirar en el embudo si % cotiza sigue subiendo y si
    `silencio_tras_info` baja su participación entre las clasificadas nuevas.
    **(b) Clasificar motivo de rechazo** (las 37 rechazadas del mes, $3,9M) con el mismo
    pipeline de temas — palanca 2 del análisis, aún sin empezar.
    **(c) Opcional si el drift molesta:** Luna RE-ESCRIBE la carta en vez de pegarla
    (visto 20/08 21:49: le agregó «desde» al Refugio, que es precio plano). Si aparecen
    montos alterados o líneas perdidas, endurecer con respuesta determinista en código
    (patrón ausencia/confirmaciones, modelo='codigo') detectando la apertura genérica
    por regex antes del LLM.

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
