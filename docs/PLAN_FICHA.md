# PLAN_FICHA.md — "La Ficha como app + upsell" (IDs F-xx)

Plan para convertir la **Ficha de Reserva del cliente** (`/reserva/<token>/`, el link
tokenizado que el cliente recibe por WhatsApp) en lo que ya casi es: **una mini-app de
Aremko en el bolsillo del cliente** — que la abran, la entiendan y **compren más desde
ahí**. Se implementa **de a un F-xx a la vez**. Registrado como **P-20** en
`docs/PENDIENTES.md`. Relacionado con [[project_aremko_ficha_reserva_digital]],
[[project_aremko_bandeja_omnicanal]], [[project_aremko_luna_interna]].

## El problema (reencuadre)

Los clientes reciben el link pero **no entienden qué pueden hacer con la ficha** — y ahí
se pierde tanto la información como el **upsell**. Es un problema de **adopción de
producto** (una app que nadie abre), no de información. Son **dos embudos**:

1. **¿La abren?** (adopción)
2. **Si la abren, ¿hacen algo?** (activación / upsell)

Hoy estamos **ciegos en el embudo 1** (no medimos aperturas). Por eso el paso 0 es medir.

**La escalera de upsell** (el oro que hoy no se cobra): tina → **masaje** · tina+masaje →
**una noche** · 1 noche → **2 noches** · + bebidas, ambientación, gift card. La ficha es
el vehículo ideal (ya confían en ella, es personal, sabe qué reservaron), pero es el
último eslabón: primero abrir y entender.

Tipos: **[BUILD]** código · **[MKT]** copy/ops · **[B2B]** — .

---

## Fase 1 · ABRIR (que la abran y entiendan)

- **F-01 · Medir aperturas** **[BUILD]** — registrar cuándo el cliente abre la ficha
  (evento) + tasa de apertura, y mostrar **"✓ abrió la ficha"** en la bandeja de
  aremko-cli para Deborah. *Paso 0: sin esto no sabemos si el cuello es abrir o activar.*
  Esfuerzo bajo.
- **F-02 · Reencuadrar el envío** **[BUILD/MKT]** — cambiar el copy del mensaje que manda
  la ficha (bandeja aremko-cli + Luna): de *"tu comprobante/detalles"* a **"Tu Aremko —
  tu panel de la experiencia"** (ve todo · personaliza tu velada · suma un masaje · pide
  tus bebidas). Darle nombre. Probablemente lo que más mueve la apertura. Esfuerzo bajo.
- **F-03 · Onboarding al abrir** **[BUILD]** — al primer abrir, un "¿Qué puedes hacer
  acá?" de 3 íconos, para que capten al toque que es un panel, no un recibo. Esfuerzo bajo.

## Fase 2 · VENDER (upsell — el motor de plata)

- **F-04 · Sección de upsell contextual** **[BUILD]** — en la ficha, ofertas **según lo
  reservado**: tina → masaje · tina+masaje → una noche · 1 noche → 2 noches (+ bebidas,
  ambientación, gift card). La lógica de "qué ofrecer" a partir del carrito de la reserva.
  **El corazón del plan.** Esfuerzo medio.
- **F-05 · Sumar a un toque** **[BUILD]** — el cliente agrega el upsell desde la ficha:
  suma el servicio y **paga la diferencia online** (reusa checkout/MP), o lo deja pedido
  para que Deborah lo confirme. Esfuerzo medio.
- **F-06 · Medir conversión del upsell** **[BUILD]** — cuánto suma la ficha (upsell
  vendido / aperturas). El KPI que prueba que el instrumento cobra. Esfuerzo bajo.

## Fase 3 · VOLVER (lifecycle — razones para reabrir)

- **F-07 · Nudges por WhatsApp en 3 momentos** **[BUILD]** — Luna manda, anclado a la
  fecha de la visita: al reservar (*personaliza + primer upsell*), unos días antes (*qué
  llevar + súmale masaje*), el día (*deja tus bebidas listas*). Cada nudge reabre la ficha
  con un fin. Esfuerzo medio. Conecta con V-07 del plan Veladas.
- **F-08 · Puente físico (QR)** **[MKT/BUILD]** — QR en recepción / en la cabaña que abre
  la ficha del cliente. Los pilla en el momento de máxima intención (ya están ahí,
  relajados, con ganas de sumar). Esfuerzo bajo.

## Fase 4 · APP (retención — que se sienta app)

- **F-09 · Guardar en pantalla (app-like / PWA)** **[BUILD]** — que puedan agregar Aremko
  a la pantalla de inicio: ícono persistente, no un link perdido en el scroll de WhatsApp.
  Esfuerzo medio.
- **F-10 · Recordatorios / avisos** **[BUILD, opcional]** — notificaciones suaves
  (post-visita: reseña; próximo aniversario). Conecta con la máquina de reseñas y con V-07.

---

## Orden sugerido

1. **F-01** (medir) — dimensiona el problema real.
2. **F-02** (reencuadrar el mensaje) — casi sin código, mueve la apertura.
3. **F-04 → F-05** (upsell contextual + sumar a un toque) — el motor de ingresos.
4. **F-07** (nudges) — reabre la ficha con propósito, expone el upsell.
5. Resto (onboarding, QR, app-like) según lo que muestre la medición.

## Notas
- La ficha YA tiene: ver reserva, tips, comanda digital, pagar saldo online, personalizar
  bebida (F2-C) e invitación sorpresa. F-04 le agrega el **upsell** encima.
- F-01 + F-02 primero: con la medición sabremos si atacar **apertura** (mensaje/nudges) o
  **activación** (la ficha). No disparar a ciegas.
- El upsell reusa el checkout / Mercado Pago existentes (sin motor de pago nuevo).
- Se manda desde la bandeja omnicanal de aremko-cli; los nudges salen por Luna.
