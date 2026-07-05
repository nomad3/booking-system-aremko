# Propuesta: GiftCards — "Regala una experiencia junto al río"

> v1 (2026-07-05) — análisis crítico de /ventas/giftcards/ + propuesta. Investigación:
> mapa completo del sistema interno (modelos/wizard/PDF/signals/campañas) + benchmark
> de gifting en 10 operadores (Peninsula Hot Springs, AIRE Ancient Baths, Blue Lagoon,
> The NOW Massage, Kamalaya, Six Senses, COMO, Aro Hā + vara chilena: The Secret Spa,
> +Mund). Objetivo de Jorge: que los regalos sean un tema relevante en las ventas;
> la página debe reflejar las experiencias nuevas, no una lista de servicios.

## 1. Diagnóstico crítico de la página actual

### Lo que está BIEN (el motor — mejor de lo esperado)
- **Wizard de 5 pasos con mensajes IA** (8 tonos, 3 opciones generadas, regenerar) —
  feature que NINGÚN spa del benchmark mundial tiene.
- **`GiftCardExperiencia` administrable** (nombre, imagen, descripción corta +
  narrativa para la tarjeta, precio fijo o montos sugeridos, orden, activo) — las
  experiencias regalables son DATOS, no código.
- Wizard con pre-selección (`?exp=ID&skip_step1=true`) → cada card puede entrar
  directo con la experiencia elegida.
- **PDF + email automático** post-pago (signal sobre Pago) con imagen y descripción
  de la experiencia + código de 12 caracteres + vista móvil.
- **Validez 1 año** (la vara chilena es 1-6 meses: Secret Spa 3 meses, +Mund 90 días,
  Aquanatura 30 días) y **uso parcial del saldo** (monto_disponible).
- **Dashboard de campañas de email de giftcards** ya construido en el admin (para la
  idea de campañas de mail/WhatsApp).
- Estructura de página completa: cómo funciona, ocasiones, testimonios, FAQ.

### Lo que está MAL (la vitrina — exactamente lo que dijo Jorge)
1. **Las 4 experiencias insignia NO EXISTEN en la página.** La Pausa junto al río
   está de incógnito como "Tina + Masajes (Dom-Jue) $110.000"; la Noche de Aguas
   Calientes como "Alojamiento + Tinas". El Ritual del Río y el Refugio no aparecen.
   Toda la inversión de marca (landings, Luna, campañas Meta/Google) se corta justo
   en la página donde el ticket es más alto y la decisión más emocional.
2. **Arquitectura de inventario, no de regalo**: tabs por categoría de servicio
   (Tinas/Masajes/Alojamientos/Monto) con 16 opciones sin jerarquía. El benchmark es
   unánime: pocas experiencias curadas con nombre + monto libre secundario
   (Peninsula: 5 curadas + "Freedom Gifts"; Blue Lagoon: elección binaria
   experiencia/monto; AIRE: solo experiencias).
3. **El "para dos" no está en los nombres** — siendo el 98% del negocio. Peninsula y
   Blue Lagoon lo ponen EN el título del regalo ("Reset Bathing for Two", "Retreat
   Spa experience for two").
4. **El regalo no se VE.** Cards con foto chica de servicio. AIRE muestra un demo
   clickeable de lo que recibirá el regalado ANTES de comprar ("See what it looks
   like") — el comprador necesita saber que va a quedar bien.
5. **El precio dual dom-jue/vie-sáb partido en DOS productos** ("Tina + Masajes
   (Dom-Jue)" y "(Vie-Sáb)") — un regalo con restricción de calendario en el título
   es anti-regalo: el que regala no sabe qué día irá el regalado.
6. **"Paquete Romántico Completo $150.000"** no corresponde a ningún programa actual
   (¿reliquia pre-Ritual con precio viejo?) — confusión y riesgo operativo.
7. **Ocasiones desconectadas de las experiencias**: San Valentín → "Paquete
   Romántico"; Aniversario → "Tina + Masajes Fin de Semana". Deberían apuntar a las
   insignia con nombre.

## 2. Lo que hacen los mejores (síntesis del benchmark)

- **El patrón dominante**: la experiencia con nombre + precio cerrado + "for two" en
  el título es el héroe; el monto libre es la opción secundaria de "libertad"
  (Peninsula la llama "Freedom Gifts — Gift the freedom to choose"). Solo el
  ultra-lujo genérico (Six Senses/COMO) vende puro monto porque su catálogo es
  inabarcable.
- **El regalo se presenta como la experiencia, nunca como un voucher**: foto
  lifestyle grande, 2-3 líneas aspiracionales, jamás un mockup de tarjeta.
- **AIRE, estado del arte del regalo digital**: gift box física que se descubre por
  pasos + gift card digital "inmersiva" con preview visible antes de comprar,
  entrega inmediata o PROGRAMADA a fecha, por email o WhatsApp, dedicatoria
  personal. Validez 9 años, transferible, upgrade a experiencia superior pagando
  diferencia (nunca hacia abajo).
- **Blue Lagoon**: gift card como parte de pago (la diferencia se paga con tarjeta);
  elección binaria limpia experiencia/monto.
- **The NOW Massage**: bonus card estacional — "compra $100 de regalo, recibe $20
  para ti" canjeables SOLO en ventana posterior (llena temporada baja + segunda
  visita). Copy de ocasión: "Gift Mom the Escape She Deserves".
- **Kamalaya**: day passes con nombre regalables + fecha preferida de uso en el form.
- **La vara chilena es bajísima**: PDF en 24 horas, plástico por courier en 5-10
  días, vigencias de 30-90 días, cero puesta en escena. Cualquier cosa a la altura
  de Peninsula/AIRE deja a Aremko solo en su categoría en Chile.

## 3. La propuesta

### Concepto rector: **"Regala una experiencia junto al río"**
La página deja de ser un catálogo con tabs y pasa a ser una vitrina de 4 regalos con
nombre y alma + 1 "regalo libre". El comprador no elige entre 16 servicios: elige
entre 4 historias (y si duda, regala la libertad).

### FASE 1 — La vitrina (sin tocar el motor; contenido + template)

**A. Crear las 4 experiencias insignia en `GiftCardExperiencia`** (admin, sin código):

| id_experiencia | Nombre del regalo | Precio único | Incluye |
|---|---|---|---|
| `pausa_junto_al_rio` | Pausa junto al río · para dos | $130.000 | Tina privada + masaje en pareja, la misma tarde |
| `noche_aguas_calientes` | Noche de Aguas Calientes · para dos | $160.000 | Cabaña boutique + tina caliente + desayuno |
| `ritual_del_rio` | Ritual del Río · para dos | $240.000 | Cabaña + tina + masaje en pareja + desayuno |
| `refugio_aremko` | Refugio Aremko · dos noches para dos | $290.000 | 2 noches, misma cabaña, tina + masaje |

**Decisión de precio único (a confirmar con Jorge)**: el regalo se vende al valor
"cualquier día" (= precio vie-sáb). Un regalo no puede decirle al regalado cuándo
ir. Y el sistema ya soporta el uso parcial: **si el regalado va de domingo a jueves,
le queda saldo a favor** (ej. Pausa: $130.000 − $110.000 = $20.000) **que se gasta
en la comanda** (tabla, jugos, decoración). Se convierte en argumento de venta:
"¿Van entre semana? El saldo les queda para celebrar con una tabla junto a la tina."
Nadie pierde, Aremko vende productos extra, y el copy es honesto.

- `descripcion_giftcard` narrativa por experiencia (el texto que va EN la tarjeta
  que recibe el regalado — borradores en §5).
- Fotos: reutilizar las de las landings (tina humeante, domo, cabañas).
- Desactivar los duplicados actuales ("Tina + Masajes (Dom-Jue)"/"(Vie-Sáb)",
  "Alojamiento + Tinas" x2) y el "Paquete Romántico Completo" (o confirmarlo con
  Jorge: ¿qué es? precio no cuadra con ningún programa).

**B. Rediseñar `giftcard_menu.html`** (mismo patrón visual boutique de las landings):
1. **Hero**: "Regala una experiencia junto al río" + sub "Momentos que no se
   envuelven: agua caliente, bosque, manos expertas y el sonido del río Pescado.
   Entrega digital en minutos, válida por 1 año." CTAs: "Ver las experiencias"
   (ancla) + "Crear mi GiftCard".
2. **Las 4 experiencias** (cards grandes, foto lifestyle, nombre con "para dos", 1
   línea sensorial, "incluye", precio, CTA "Regalar esta experiencia" → wizard
   pre-seleccionado). Badges: Ritual = "⭐ El regalo estrella"; Pausa = "La más
   regalada".
3. **La GiftCard de Libertad** (monto libre, estilo "Freedom Gift"): "¿No sabes cuál
   elegir? Regala la libertad — ellos eligen su experiencia." Montos sugeridos
   alineados a la escalera: $50.000 / $80.000 / $130.000 / $240.000.
4. **"Así se ve tu regalo"** (idea AIRE): preview real del regalo digital — mockup
   de la vista móvil que recibirá el regalado (imagen + mensaje + código) con un
   ejemplo precioso. El cierre de venta más fuerte del gifting digital.
5. **Ocasiones reapuntadas a las insignia**: San Valentín → Ritual del Río ·
   Aniversario → Ritual o Refugio · Día de la Madre → Pausa · Cumpleaños → Pausa o
   Noche · Corporativo → GiftCard de Libertad · Grupo de amigos → pack grupal.
6. **Mensajes IA** (sección existente, se mantiene — es única en el mercado; subirla
   de protagonismo en el copy: "El mensaje lo escribes tú... o nuestra IA te propone
   tres").
7. **Más regalos** (compacto, sin tabs): masaje para dos $80.000 (con la narrativa
   de los 5 sentidos), masajes individuales, tinas, packs grupales.
8. Cómo funciona / testimonios / FAQ / CTA final (se mantienen, FAQ actualizado con
   la política de saldo a favor y el upgrade).

**C. Políticas visibles (costo cero, puro copy)**:
- "Válida por 1 año — tienen 12 meses para vivirla" (vs 30-90 días de la
  competencia: hacerlo ARGUMENTO).
- "¿Quieren subir de experiencia? La GiftCard vale como parte de pago: pagan solo
  la diferencia" (escalera Pausa → Ritual → Refugio; patrón AIRE/Blue Lagoon —
  el motor de saldo ya lo permite).
- "Transferible: la puede usar quien ustedes quieran."

### FASE 2 — El flujo de entrega (features de motor, orden sugerido)

1. **Entrega programada a fecha** ("que llegue el día del cumpleaños"): campo
   `fecha_envio_programada` en GiftCard + el signal respeta la fecha (cron diario
   existente puede despachar). AIRE/Blue Lagoon lo tienen; nadie en Chile.
2. **Página "Tengo una GiftCard"** (canje formal): código → muestra la experiencia
   + botón "Agendar por WhatsApp" prellenado con el código → cae a Luna, que ya
   sabe crear propuestas de reserva. (Hoy el canje es "escribe al WhatsApp".)
3. **Preview interactivo del regalo** antes de comprar (la vista móvil ya existe:
   `giftcard_mobile_view` — exponer un ejemplo demo).
4. **Envío directo al regalado por WhatsApp**: BLOQUEADO por App Review de Meta
   (plantillas para iniciar conversación). Mientras tanto, el flujo honesto: el
   comprador recibe el regalo listo para reenviar por SU WhatsApp — documentarlo
   como feature ("te llega listo para reenviar con un toque").
5. **Bonus card estacional** (The NOW) para las campañas: "Regala un Ritual y
   recibe $20.000 para tu propia visita" — canjeable solo dom-jue de temporada baja
   (marzo-junio). Conecta con el dashboard de campañas existente y llena semana.

### FASE 3 — Campañas (la idea de Jorge, con la base ya construida)
- El dashboard de campañas de email de giftcards YA existe en el admin → definir
  calendario comercial (San Valentín, Día de la Madre/Padre, Navidad, aniversario
  del cliente) y conectar con las insignia + bonus card.
- Luna: enseñarle a ofrecer GiftCards cuando alguien pregunta por regalos
  ("¿es para regalar? te armo una GiftCard con mensaje personalizado") — tool nueva
  o link directo a la página. (Fase aparte, no bloquea nada.)

## 4. Decisiones TOMADAS por Jorge (2026-07-05)
1. **Precio único cualquier día AL PRECIO DE DÍA DE SEMANA** (no vie-sáb como
   proponía el borrador): Pausa $110.000 · Noche $130.000 · Ritual $210.000 ·
   Refugio $290.000. Razón de Jorge: "es más conveniente comprar una giftcard para
   el fin de semana que un servicio por reserva normal" — incentivo estructural
   deliberado al canal regalo. La GiftCard es la forma más conveniente de ir un
   fin de semana.
2. **"Paquete Romántico Completo": ELIMINADO.**
3. **Ritual = "⭐ el regalo estrella"; Pausa = "la más regalada".** Confirmado.
4. **Fase 1 primero: GO.**
5. **DECISIÓN RADICAL: solo se regalan EXPERIENCIAS.** No tinas sueltas, no masajes
   sueltos. El catálogo por categorías (tabs con 16 opciones) DESAPARECE completo de
   la página; el command desactiva todas las GiftCardExperiencia que no sean las 4
   insignia. (Interpretación aplicada, avisada a Jorge: la GiftCard de monto libre
   se mantiene como opción discreta reformulada — "Regala la libertad: ellos eligen
   su experiencia" — porque cubre el caso corporativo/indeciso y sigue siendo
   regalar una experiencia, elegida por el regalado. Si Jorge quiere ser 100%
   radical, se desactiva también y quedan solo las 4.)

## 5. Borradores de `descripcion_giftcard` (el texto EN la tarjeta)

- **Pausa junto al río**: "Una tarde entera para los dos: tina caliente privada
  junto al río Pescado y masaje en pareja en un domo de madera entre el bosque.
  Con infusión de hierbas preparada por tu masajista y un mirador donde el río
  suena más fuerte que todo lo demás."
- **Noche de Aguas Calientes**: "Una noche en cabaña boutique junto al río, con
  tina caliente privada esperando bajo las estrellas y desayuno sin apuro a la
  mañana siguiente. Para llegar de noche y no querer irse."
- **Ritual del Río**: "La experiencia completa: cabaña boutique, tina caliente
  junto al río, masaje en pareja en el domo y desayuno al despertar. Una noche
  que se recuerda por años — el regalo estrella de Aremko."
- **Refugio Aremko**: "Dos noches, la misma cabaña, cero apuro: tina caliente,
  masaje en pareja y el río de fondo todo el fin de semana. Para desconectar de
  verdad."

## 6. Archivos que tocaría la Fase 1
- `ventas/templates/ventas/giftcard_menu.html` — rediseño de la vitrina (hero, 4
  insignia, libertad, preview, ocasiones; conserva wizard/IA/FAQ/testimonios).
- Datos en admin: 4 registros nuevos en GiftCardExperiencia + desactivar
  duplicados/reliquia (sin código; puedo dejar un management command de carga con
  --aplicar como el de las descripciones de masajes).
- `ventas/views/giftcard_views.py::giftcard_menu` — pasar las insignia destacadas
  (por id_experiencia conocido) separadas del resto; sin migraciones.
- Sin cambios de modelo en Fase 1. (Fase 2.1 sí: campo fecha_envio_programada —
  migración a mano como siempre.)
