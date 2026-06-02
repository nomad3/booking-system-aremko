# Manual de uso — Ficha de Bienestar para Masajes (Aremko)

Versión v1 · 2026-06-01. Sistema para registrar a cada persona que recibe masaje,
recoger sus preferencias de bienestar y dejar el resumen del terapeuta.

> **Lenguaje:** siempre hablamos de **bienestar, preferencias y experiencia**.
> Nunca usamos lenguaje médico (diagnóstico, tratamiento, paciente, ficha clínica).

---

## PARTE A — Para Deborah (ventas y coordinación)

### Acceso
- Entras al panel en **https://www.aremko.cl/admin/** con tu usuario y contraseña.
- Tu grupo es **"Coordinacion Masajes"** (o eres administradora): ves reservas,
  participantes, fichas y puedes enviar enlaces.

### Flujo normal de una reserva de masaje para 2 personas
1. La reserva se crea como siempre (el comprador queda registrado).
2. El sistema **crea automáticamente** los participantes: el comprador y un
   "acompañante" (sin datos todavía).
3. Abre la reserva en el admin → sección **"Participantes de masaje"**. Verás:
   - El **comprador** con sus datos.
   - El **acompañante** con la alerta **"⚠ Falta registrar datos del acompañante"**.
   - **Enlaces** por participante: *Ficha de bienestar* y, en el comprador,
     *Registrar acompañante*.

### Conseguir los datos del acompañante
Tienes 2 formas:
- **Opción rápida:** copia el enlace **"Registrar acompañante"** del comprador y
  envíaselo (por WhatsApp/email). El comprador ingresa nombre + WhatsApp del
  acompañante.
- **Opción automática:** en el listado **"Participantes de masaje"** (menú lateral),
  selecciona al comprador → acción **"Enviar link de registro de acompañante"** →
  se le manda por email.

### Que cada persona complete su ficha de bienestar
- Copia el enlace **"Ficha de bienestar"** de cada participante y compártelo.
- Cuando lo completan, el estado cambia a **"✓ Ficha completada"**.

### Qué NO hacer
- No inventes datos. Si falta el acompañante, usa los enlaces para pedirlos.
- En el resumen del terapeuta, evita lenguaje médico.

---

## PARTE B — Para los masajistas (terapeutas)

### Tu acceso
- Tienes tu **propio usuario y contraseña**. Entra en **https://www.aremko.cl/admin/**.
- **Solo verás "Fichas de bienestar (masajes)"** — nada más del sistema.

### Qué haces tú
1. Entra y abre **"Fichas de bienestar (masajes)"**.
2. Busca la ficha de la persona que atendiste (por nombre o reserva).
3. Arriba verás (solo lectura) sus **preferencias**: objetivo, intensidad
   preferida, zonas de tensión, zonas a evitar y observaciones.
4. Abajo, completa el **"Resumen del terapeuta"**:
   - **Observaciones del terapeuta** (de bienestar, no médicas).
   - **Zonas trabajadas**.
   - **Intensidad aplicada**.
   - **Sugerencia de frecuencia** (cada 15 días / mensual / cada 2 meses / ocasional).
   - **Recomendación** (texto breve de autocuidado/bienestar).
5. Guarda (botón **"Guardar"** abajo).

### Reglas importantes
- **Solo lenguaje de bienestar.** Prohibido: diagnóstico, tratamiento, paciente,
  enfermedad, recomendación médica. Permitido: zonas de tensión, observaciones del
  terapeuta, sugerencia de frecuencia, autocuidado.
- No puedes crear ni borrar fichas, solo completar el resumen. Es lo correcto.

---

## PARTE C — Para el administrador (crear los accesos)

> Esto se hace UNA vez para preparar el sistema, y luego un usuario por masajista.

### 1) Crear los grupos de permisos (una sola vez, en la Render Shell)
```bash
python manage.py setup_masajistas
```
Crea/actualiza:
- **"Masajistas"**: solo ver + editar la Ficha de Bienestar.
- **"Coordinacion Masajes"**: reservas + participantes + fichas + seguimientos (Deborah).

### 2) Crear el usuario de cada masajista (en el admin)
1. Admin → **Usuarios** → **Agregar usuario** → nombre de usuario + contraseña.
2. Guardar y continuar editando.
3. Marca **"Staff status" (is_staff)** = ✓ (sin esto no entra al admin).
4. En **Grupos**, asígnale **"Masajistas"**. (NO marques superusuario.)
5. Guardar. Entrégale su usuario/contraseña.

### 3) Acceso de Deborah
- Igual que arriba, pero asígnale el grupo **"Coordinacion Masajes"** (o déjala como
  administradora si ya lo es).

### Notas
- Con estos grupos, cada quien ve **solo lo que le corresponde**.
- Más adelante (v2) podremos darles un panel propio más simple y el envío por
  WhatsApp Cloud API.
