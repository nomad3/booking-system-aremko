# Pendientes Aremko (backlog vivo)

Lista única de temas pendientes Jorge ↔ Claude. **Uso:** al completar un tema se
ELIMINA de la lista (git guarda la historia); los IDs `P-xx` son estables y no se
reutilizan. Para agregar: "agrega a pendientes: …". Para cerrar: "listo el P-xx".
Claude la revisa al inicio de sesión y en cada wrapup.

_Última revisión: 2026-09-24_

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

43. **P-43 · Equipo de terreno para empresas (Cristián): 3 decisiones de Jorge** —
    El material de venta ya está armado (memoria «Equipo de terreno empresas»).
    Falta: (1) los códigos de atribución de Cristián y su compañero, para saber qué
    venta vino de quién — sin eso la comisión se discute en tres meses; (2) cómo se
    les paga (fijo, comisión o mezcla); (3) la lista de empresas de Puerto Montt
    (salmoneras, clínicas, colegios, retail), que Claude arma cuando Jorge diga.
44. **P-44 · Correo semanal (H-111): falta el lado Datamatic y la primera campaña
    real** — Django está listo desde el 14-09 (endpoint
    `POST /marketing/api/campana-semanal/`, remitente comunicaciones@aremko.cl con
    respuestas a ventas@, baja con un clic en el pie, un lote de 50 cada 5 min).
    Falta que Datamatic llame al endpoint sin `segmento`, muestre `revisar_en` y
    recién ahí `instalar_aremko`; el recordatorio de Google de los jueves tampoco
    tiene endpoint HTTP aún. Cuando llegue la primera campaña: nace en Borrador y
    Jorge/Deborah la pasan a «Lista para envío» en el admin — nada sale solo.

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
16. **P-16 · Boletas electrónicas SII — lo que queda** — 🟢 **En producción desde el
    03-09-2026** (certificación aprobada 02-09, Declaración de Cumplimiento hecha,
    CAF real 69012+, F2 con pregunta al cobrar en la tarjeta, envío al cliente por
    WhatsApp en 3 fases, 3 crons SII en cron-job.org). Historia completa en git y en
    `docs/BRIEF_P-16_boletas_sii.md`. Queda: **(a)** el medio genérico `mercadopago`
    (~$7,8M en 66 pagos por 60 días) está marcado «no boletea» — si son transferencias
    y no links de pago, hay que boletearlos; no se cambió sin decisión de Jorge para no
    duplicar boletas. **(b)** Confirmar con el contador `unidad_sii` y la dirección que
    el SII tiene registrada (solo afecta la impresión). **(c)** Decidir qué hacer con la
    deuda histórica que mostró el listado al encender: 41 pagos por $3.721.000 sin
    boleta. F3 (notas de crédito) NO se construye: van a mano en el sistema gratuito.

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

<!-- P-39 (reserva 6742, pago y boleta 69015 repetidos) CERRADO 2026-09-25 por decisión
     de Jorge: «olvida esta duplicación». La nota de crédito de la 69015 la hizo él en el
     SII; en el sistema quedan como están el pago 8549 y la boleta (la reserva marca $120.000
     pagados sobre $60.000). -->
40. **P-40 · El admin de Django no tiene protección de doble clic** — La tarjeta
    móvil ya tiene las tres capas (21-09: botón bloqueado mientras responde, candado
    consultivo `pg_try_advisory_lock` por reserva, rechazo de un pago idéntico en
    30 s). El admin (`VentaReservaAdmin` con sus inlines de pagos y productos) no
    tiene ninguna: desde ahí todavía se duplica un pago o un producto con dos clics
    en «Guardar». Caso real: reserva 6869 (pagos 8692/8696, 21-09).

## Operación e inventario

37. **P-37 · Stock: 76 productos vendidos sin comanda + 2 extras de giftcard de 2021** —
    (a) 76 líneas de producto de ventas históricas nunca tuvieron comanda, así que su
    stock nunca se descontó (desde el 21-09 toda venta genera comanda: admin, tarjeta
    y agenda). Decidir si se ajusta el inventario a mano o se da por perdido.
    (b) Las 2 comandas con fecha de relleno 02-02-2021 son extras de giftcards sin
    canjear: la prueba del cron del 21-09 las dio por entregadas y descontó su stock.
    Decidir si se devuelve.
38. **P-38 · Correos de clientes por corregir** — De la limpieza del 21-09 (17 correos
    inválidos que trababan las campañas) queda el cliente 2692 (`noemimunoz@live.c`,
    Noemí Muñoz — probablemente `.cl`) y 3 clientes que quedaron SIN correo porque el
    campo tenía un nombre en vez de un correo (2841 Felipe Silva, 20793 Carolina
    Barrientos y uno más; la lista está en el log del job del 21-09). Deborah les pide
    el correo en la próxima visita.

46. **P-46 · Cancelar una reserva hoy es borrarla, sin rastro** — Hallazgo del 22-09
    al cerrar P-41: en toda la base hay UNA venta marcada cancelada (la 6859 de
    prueba); todas las demás cancelaciones se hicieron eliminando la reserva o sus
    servicios desde el admin. No hay botón «Cancelar» ni estado «cancelada» en el
    desplegable (`ESTADO_RESERVA_CHOICES` = pendiente/checkin/checkout) y el registro
    de eliminaciones en `MovimientoCliente` está comentado en `main_signals.py`.
    Efecto: si una clienta pagó y cancela, su pago desaparece del sistema junto con
    la reserva; no se pueden medir cancelaciones ni auditarlas. Qué construir: acción
    «Cancelar reserva» (admin y tarjeta) que marque `estado_reserva='cancelada'`, deje
    nota y usuario, conserve pagos y servicios y devuelva el stock de las comandas no
    entregadas. Desde el 22-09 (commit `2c47a1b1`) los caminos de disponibilidad ya
    respetan esa marca (`ventas/services/ocupacion.py`): una reserva cancelada deja de
    ocupar su hora sin borrarla. Decidir también qué pasa con el pago: devolución,
    giftcard o crédito.

47. **P-47 · El admin acepta cualquier texto como hora de un servicio** — Hallazgo del
    23-09: la reserva 6818 (Booking, Cabaña Laurel 28-09) tiene una línea «Comisión
    Booking» con hora `20900` (se escribió el monto en el campo de la hora) y el
    proceso de tareas de preparación (`gen_preparacion_servicios`, cada 15 min) falla
    en esa reserva desde el 12-09. Hay 40 líneas históricas con horas mal escritas
    ('16.00', '1630', '9:30', '16;30'). Arreglo: validar formato HH:MM al guardar
    `ReservaServicio` (admin y API) y normalizar las 40 existentes. **La 6818 la corrigió
    Jorge el 23-09 (~12:20): el error dejó de aparecer desde la pasada de las 12:30.**
48. **P-48 · El cajón de cotizaciones acepta cualquier RUT** — El 23-09 una cotización
    salió del cajón de la bandeja (repo `aremko-cli`) con el RUT de ejemplo
    `12345678-9` (dígito verificador malo) y el cliente vio «Datos de cliente
    inválidos» al aprobar. Django ya se defiende (commit `0ad036c5`: pide el dato de
    nuevo con el motivo), pero lo ideal es que el cajón avise al escribirlo. Toca el
    front de aremko-cli (validar dígito verificador antes de enviar) y, de paso, el
    endpoint Django que recibe la cotización del cajón podría rechazar un RUT
    inválido con mensaje claro.

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
    **Addendum 2026-09-22:** los tests SÍ corren, con dos shims locales que NO se
    commitean (se recrean cada sesión y se borran antes del commit):
    `aremko_project/test_settings.py` (sqlite en memoria, migraciones desactivadas
    con un dict `_SinMigraciones`, `DEFAULT_FILE_STORAGE`, `STATICFILES_STORAGE`
    plano, hasher MD5) y `aremko_project/test_settings_pg.py` (Postgres del
    docker-compose, para probar concurrencia real con hilos). El drift sigue ahí:
    el shim lo esquiva, no lo arregla. Decidir si se commitean los shims.
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
    arreglar los dos primeros. **Addendum 2026-08-22:** `ventas.tests_checkout_agenda`
    tiene 6 fallas + 1 error PREEXISTENTES bajo el shim sqlite de tests (verificado
    con `git stash` en árbol limpio; 12-13 si se corre después de `whatsapp_agent`,
    por interferencia entre suites). Probablemente verdes bajo Postgres, que es
    contra lo que se escribieron — no atribuirlas a cambios nuevos.
    **Addendum 2026-09-22:** la interferencia entre suites tiene causa conocida:
    `ThreadLocalMiddleware._thread_locals.user` queda seteado por una suite y
    contamina la siguiente. Las suites nuevas limpian en `tearDown`
    (`middleware._thread_locals.user = None`); faltan 5 suites antiguas. Las fallas
    por fecha fija ('2026-09-10') y por cabañas con capacidad 1 contra el filtro ≥2
    se arreglaron el 21-09 (`tests_tarjeta_reserva`, `tests_checkout_agenda`,
    `tests_pago_repetido`).
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

35. **P-35 · La bandeja debe mostrar si el mensaje REALMENTE llegó (status del webhook)** —
    Detectado 2026-08-21 con el caso del error 131042: Deborah estuvo días usando
    "Contactando" viendo "Enviado ✓" mientras Meta descartaba cada plantilla segundos
    después. Causa estructural: un **200 de la Cloud API solo significa "aceptado"**; el
    veredicto real llega asíncrono por webhook (`sent` → `delivered` → `read`, o `failed`
    con su código). Hoy el backend Go solo LOGUEA esos statuses (`handlers/whatsapp.go`,
    desde el commit 1cb2906 con el motivo del fallo incluido) y nadie los ve.
    **Qué construir:** el webhook reenvía el status a Django (endpoint nuevo, keyeado por
    `wa_message_id`, idempotente) → se guarda en el saliente → la bandeja lo muestra
    (✓ enviado / ✓✓ entregado / leído / ⚠️ falló + motivo en español). Beneficia a los
    tres flujos que envían sin humano mirando: Contactando, campañas OVC
    (`run-template-campaign`) y los recordatorios de Luna (H-109). Mínimo viable: marcar
    en rojo los `failed` con el motivo traducido; lo demás es lujo.
    Ver `[[feedback_whatsapp_plantillas_facturacion_131042]]`.

36. **P-36 · SEGURIDAD: cerrar con auth el backend Go (H-110)** — ⚠️ **DIFERIDO POR JORGE
    el 2026-08-31** ("déjalo pendiente y me lo vas recordando en cada sesión"). Verificado
    con curl: **113 de las 116 rutas `/api/v1/*` responden sin credencial desde internet**
    (solo 3 exigen X-API-Key). No es solo lectura de conversaciones —como decía el reporte
    original— sino también **escritura**: `/whatsapp/reply` e `/instagram/reply` permiten
    escribirle a clientes desde el número de Aremko, y `/meta-ads/campaigns/{id}/budget`
    `/pause` `/activate` permiten mover presupuestos de publicidad. Mitigación de hecho (NO
    es seguridad): la URL del backend no es pública ni indexada.
    **Hueco del brief original:** poner la key "en Vercel" NO basta — el dashboard llama al
    backend DESDE EL NAVEGADOR (`NEXT_PUBLIC_API_URL`, 5 archivos del front), así que la
    llave viajaría en el bundle JS.
    **Plan acordado:** proxy server-side en Next.js (BFF) — el navegador llama a una ruta
    del propio Vercel (ya autenticada por next-auth) y el servidor agrega la llave. Deploy
    en 3 pasos sin downtime: (1) el Go acepta la llave pero tolera su ausencia; (2) el front
    pasa al proxy; (3) el Go cierra (único paso con riesgo → hacerlo fuera del horario de
    atención de Deborah y Alda). SIN auth: `/health` y los webhooks de Meta (validan HMAC).
    Env var en el proyecto Vercel `aremko-cli-frontend`, NO en el duplicado `aremko-cli`.
    Brief: `docs/BRIEF_H-110_auth_backend_go.md` · fila H-110 en `docs/HANDOFFS.md`.

42. **P-42 · Borrar el workflow de GitHub «Build and Deploy to GKE»** —
    `.github/workflows/deploy.yml` corre en cada push a `main`/`dev`, intenta desplegar
    a un clúster de Google que nunca existió (placeholders «TODO: update to your
    cluster name») y falla siempre → correo de error a Jorge por cada deploy. Render
    despliega por su cuenta; el archivo sobra. Un commit de borrado.
45. **P-45 · Vigilar la primera semana de los 3 crons creados el 21-09** — En
    cron-job.org: entregas de comandas vencidas 06:30, seguimientos de masaje 10:00,
    boletas pendientes por WhatsApp 11:00. **22-09:** 06:30 ✓ (cerró las 37
    acumuladas; stock intacto, no descontó de nuevo) · 10:00 ✓ (25 seguimientos
    enviados, 0 errores) · 11:00 por ver. Los «Fallido (timeout 30 s)» del panel son
    cosméticos: vale el log de Render («✅ Cron … ejecutado vía HTTP»); ojo con el
    auto-deshabilitado tras fallos. De pasada quedaron suspendidos los 3 crons de
    Render de la rama `dev` (reminders/surveys/reactivation, duplicaban a
    cron-job.org) y apagado «Aremko-Email-Campaign» (drenaba la misma cola dos veces).
    Cerrar este ítem el 28-09 si todo corrió.

<!-- P-49 (Luna «error interno» por clave repetida) CERRADO 2026-09-23, commit 686fd46b:
     whatsapp_agent/idempotencia.py decide antes de crear (reintento → la misma; pedido ya
     convertido en reserva <24 h → «ya está creada»; otro caso → clave libre carrito-N#2).
     De paso revivió «agregar a mi reserva» (H-060), que no había creado NUNCA una propuesta
     por la fila con clave vacía del 19-06. Verificado en prod dentro de transacciones que se
     deshacen. Seguimiento de las primeras adiciones reales en P-51. -->
50. **P-50 · DeepSeek sin saldo (402 Payment Required)** — Desde al menos el 21-09.
    Lo usa `control_gestion/ai_client.py` para los reportes diarios
    (`gen_daily_reports`, 09:05 y 18:00): con la cuenta vacía caen a «modo mock» y
    salen con texto de relleno. Se arregla recargando saldo en platform.deepseek.com
    (Jorge) o cambiando `LLM_PROVIDER`. No afecta a Luna ni a las boletas.
    **23-09 12:45:** Jorge dijo «listo», pero la clave que usa Render (termina en
    …19f2) sigue con saldo −0,72 USD e `is_available: false` (consulta de solo lectura a
    `api.deepseek.com/user/balance`). Revisar que la recarga haya ido a la cuenta dueña
    de esa clave.

51. **P-51 · Vigilar las primeras propuestas de «agregar a una reserva»** — Desde el
    23-09 (P-49) Luna vuelve a poder proponer agregar servicios o productos a una
    reserva ya creada (H-060). Esa propuesta nunca había existido en producción, así que
    su aprobación (`crear_reserva` con `reserva_existente_id` → `agregar_items_a_reserva`)
    tampoco se ha ejecutado nunca con datos reales. Mirar la primera de punta a punta: que
    Deborah la vea bien en la bandeja, que al aprobarla se sume a la reserva correcta con
    el precio correcto, y que el total y el Pase se actualicen. Hipótesis sin confirmar,
    anotada al revisar: si el cliente tiene una cotización pendiente viva y confirma de
    nuevo el carrito CAMBIADO, se le devuelve la cotización vieja (comportamiento previo,
    no tocado por P-49).

52. **P-52 · Gift cards: venta visible y canje sin enredos (pasos 2 y 3)** — Plan
    aprobado por Jorge el 23-09. **Paso 1 EN PROD 24-09 (commit `5fbdee12`):** pagar
    con gift card desde la tarjeta móvil (buscar por código o nombre, verla antes de
    usarla, «Aplicar $X» por lo que falte). **Paso 2 EN PROD 24-09 (commit
    `5b454e26`):** «🎁 Gift cards vendidas» en la tarjeta: ver, copiar código, PDF por
    WhatsApp al comprador (ventana 24 h) o reenvío por email; código oculto hasta que
    la compra esté pagada (decisión de Jorge). **Prueba real OK 24-09 19:28:** el PDF
    de la gift card 314 (reserva 4448) le llegó a Jorge por WhatsApp. De esa prueba
    salieron dos ajustes, ya en prod: una gift card usada o vencida no ofrece reenvío
    (`011e2064`; el PDF la mostraba vigente) y la búsqueda del canje acepta cero por O
    y uno por I (`e971f66e`; la fuente de la carta dibuja la O como cero). **2b EN PROD 25-09 (commit `a895741a`):** el PDF sale solo por
    WhatsApp al registrarse el pago (señal de Pago + webhook de Flow, en on_commit),
    si la venta quedó pagada ENTERA y el comprador conversó en 24 h; una sola vez.
    Falta verlo en una venta real (buscar «enviada sola por WhatsApp» en los logs).
    **(d) RESUELTO 25-09 (commit `ae8d7994`):** el email automático de la gift
    card ahora espera a que la venta quede pagada ENTERA (antes salía con un abono
    parcial). Al aplicarlo no había ninguna venta de gift card a medio pagar. Quedan
    vivas 3 ventas de gift card de nov-2025 NUNCA pagadas (#3987, #4007, #4008; gift
    cards 229, 232, 233, vencen nov-2026): revisar con Deborah si se anulan.
    **Paso 3 · aprobado por Jorge el 25-09 («Dale»), en dos deploys.** Jorge: «normalmente
    el cliente solo manda la foto». Prueba real (68 fotos, 90 días, Gemini 2.5 Flash):
    10/10 códigos exactos, 1 manuscrito con 1 carácter mal (gc 471), 4 vouchers
    «R ####» (= id de la reserva), 34 comprobantes y 19 otras bien descartadas;
    ~2 s y US$0,0007 por foto. Jorge aprobó mandar TODAS las fotos entrantes al lector.
    **Deploy 1 (25-09) · Luna ve la foto:** `whatsapp_agent/lector_giftcard.py` lee las
    fotos del turno sin responder (máx. 3, últimos 7 días; cada una UNA vez, queda en
    `LecturaImagen`); si hay gift card o voucher, la sugerencia pasa a Deborah con la
    tarjeta ya identificada en el motivo («Canje de gift card · Tina para dos · código
    … · lista para usar ($X) · vence …»), sin gastar el borrador; el historial de Luna
    muestra «(foto: …)» en vez de «(image)». Búsqueda compartida con la tarjeta
    (`ventas/services/giftcard_estado.py`): exacto, O=0/I=1, comienzo, y 1–2
    caracteres de diferencia —distintos, de más o de menos, en lecturas de 11 a 13—
    con una sola candidata (la tarjeta avisa «Lo escrito tiene N carácter de
    diferencia»), y «R 5602» avisa que es un voucher antiguo de la reserva #5602.
    Migración `whatsapp_agent 0014` aplicada por Jorge el 25-09. Verificado en prod
    con 17 fotos reales: 16 bien; en la otra el modelo se comió un carácter (gift
    card 389) → ajuste del mismo día: la tolerancia cuenta también el carácter que
    falta o sobra (en prod la 389 queda a 1 y la siguiente de 496, a 8). **Deploy 2 · flujo aprobado por Jorge el 25-09, en dos partes** (sin esperar a Deborah).
    **2a (25-09):** con la foto sola (o con un saludo) de una gift card que se puede usar,
    Luna prepara la bienvenida de texto fijo (saluda como en el prompt, confirma cuál es,
    saldo y vencimiento, y pide el día); con fecha, pregunta, audio, otra foto, reserva
    próxima o gift card usada/vencida/por cobrar, pasa a Deborah como en el deploy 1. Lo
    que el cliente escriba en los 3 días siguientes, mientras la gift card siga sin usarse,
    lo ve Deborah («Canje de gift card en curso · …»): el freno va en el código.
    **2b (25-09, publicado APAGADO):** `whatsapp_agent/canje_giftcard.py`: FICHAS por
    gift card (tipo del motor de alternativas, personas, tina sin/con hidromasaje, días)
    con lo que dice la carta mientras Deborah no responda la tabla (PDF en el Escritorio,
    21 fichas, 12 preguntas); herramienta `horario_canje` (una opción, regla de la casa
    H-081); durante un canje es la ÚNICA herramienta de Luna y el ejecutor rechaza las
    de venta; el código arma «Canje listo · …» al confirmar y deriva si el borrador da la
    reserva por hecha, menciona un precio o el cliente dice «sí» sin confirmar. Monto
    libre y antiguas sin ficha: Deborah. Probado con el modelo real y la agenda real en
    prod (4 conversaciones, todas bien) y **encendido por Jorge el 25-09**
    (`LUNA_CONVERSA_EL_CANJE = True`; con False vuelve al 2a). Pendiente: las respuestas
    de Deborah a la tabla (solo cambian las fichas). Opcionales: botón «Vender gift card» ligado a la reserva
    (reemplaza las reservas con fecha de relleno 02/02, caso 6873).
    **Deudas del modelo encontradas el 24-09 (sin arreglar):** (a) el campo `estado`
    significa dos cosas —«compra sin pagar» (venta por Luna/web) y «vigente con saldo»
    (canje parcial, «Ajustar saldo»)—; la tarjeta ya no lo lee, deriva «¿se pagó?» de
    la venta de origen. (b) La señal `verificar_saldo_giftcard_post_pago` recalcula
    el saldo como «monto inicial − canjes» en CADA canje (su condición de
    inconsistencia es siempre verdadera) y deja «por_cobrar» a toda gift card con
    saldo: pisaría el saldo de una gift card ajustada con «Ajustar saldo» (que sube
    el disponible sin tocar el inicial) y podría dejarlo negativo. Hoy no muerde: las
    496 cuadran. (c) `Pago.save()` llama a `usar()` también al EDITAR un pago con
    gift card ya guardado: editarlo en el admin descuenta el saldo dos veces.

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
