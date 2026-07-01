# BRIEF H-056 — Briefing de Luna Interna: info financiera por perfil + Agenda del día para todos

> **De:** agente aremko-cli (análisis; el cambio de código es 100% Django)
> **Para:** agente Django (`~/dev/booking-system-aremko`)
> **Contexto:** al sumar a Ernesto (jefe de Operaciones) como segundo receptor de "empezando el día"
> (ver [[project_aremko_luna_interna]] / H-037), Jorge notó que su briefing incluía la sección de
> Pagos próximos / Saldos bajos — información financiera que Ernesto no debería ver. Función:
> `construir_briefing(persona)` en `personal_operativo/services.py`.

## 1. Por qué (decidido con Jorge, 2026-07-01)

Jorge aclaró el criterio exacto tras varias vueltas — dejarlo explícito para no reinterpretarlo:

- **Pagos próximos / Saldos bajos (`costos_web`):** SOLO para Jorge y Alda (mismo perfil que Jorge,
  la va a crear él mismo en el admin). El resto (Ernesto, y futuros) NO debe verla.
- **"Tus tareas de hoy" (`control_gestion`, ya filtrado por `owner_id=persona.usuario_id`) y
  "Comandas pendientes":** sin cambios — ya varían naturalmente por persona, es exactamente el
  "cada uno ve según su perfil" que pidió Jorge.
- **Nueva sección "Agenda del día"** (primera tina, primer masaje, cabañas del día): para **TODOS**
  los que reciben briefing, sin excepción — Jorge: *"el resumen de inicio del día para todos"*.
  Es solo lectura de datos que ya existen cada día (`ReservaServicio`), no requiere nada nuevo del
  lado de datos.

## 2. Cambio 1 — Interruptor de visibilidad financiera (requiere migración chica)

**Por qué hace falta un campo nuevo:** hoy Jorge y Ernesto tienen el mismo `rol` ("Jefatura /
Administración"), así que `rol` no alcanza para distinguir quién ve finanzas. Se necesita un dato
explícito, igual patrón que `responde_auto` / `recibe_avisos_operacion` (mismo modelo, mismo estilo
de fieldset con descripción).

**Modelo** (`personal_operativo/models.py`, clase `PersonalOperativo`):
```python
recibe_info_financiera = models.BooleanField(
    default=False,
    help_text='💰 Incluye en su briefing los pagos próximos y saldos bajos (costos_web). '
              'Actívalo solo para quien deba ver información financiera/administrativa '
              '(ej. Jorge, Alda). Por defecto NO se muestra.')
```
Migración puramente aditiva (1 columna booleana, default False) — mismo patrón ya usado varias
veces en este proyecto (ver `feedback_makemigrations_drift_safe`).

**Admin** (`personal_operativo/admin.py`): agregar a `fieldsets` un bloque nuevo (estilo igual a
"Avisos de operación"):
```python
('Información financiera', {
    'fields': ('recibe_info_financiera',),
    'description': '💰 Si está activo, su briefing incluye pagos próximos y saldos bajos '
                   '(costos_web). Dejar apagado salvo para quien deba ver esta información '
                   '(dueño/administración).'
}),
```
Opcional pero recomendable: sumar a `list_display`/`list_filter` un badge corto (mismo estilo que
`avisos_col`/`auto_col`), para verlo de un vistazo en la lista.

**Lógica** (`personal_operativo/services.py`, función `construir_briefing`): la sección actual
- --- Pagos y saldos (costos_web) --- se ejecuta HOY sin condición. Envolverla en:
```python
if persona and persona.recibe_info_financiera:
    # ... (todo el bloque de pagos + saldos bajos, sin cambios internos)
```
Si `False`, la sección simplemente no se agrega (no rompe `hay_contenido`, que ya lo maneja el resto
de secciones).

**⚠️ Paso de datos post-deploy (Jorge, en el admin, después de correr la migración):** el campo
nace en `False` para TODOS, incluidas las filas que YA existen. Hay que entrar a Personal Operativo
y activar `recibe_info_financiera` manualmente en la fila de **Jorge** (y en la de **Alda** cuando
la cree) — si no, Jorge deja de ver sus propios pagos. Dejarlo anotado en el mensaje de vuelta para
que no se pierda este paso.

## 3. Cambio 2 — Nueva sección "Agenda del día" (sin migración, solo lectura)

Agregar una sección nueva a `construir_briefing`, **incondicional** (para cualquier persona,
sin gate), después de "Tus tareas de hoy" o donde encaje mejor en el orden. Usa `ReservaServicio`
del día — mismo patrón de exclusión que el resto del proyecto (`excluir estado_pago='cancelado'`):

```python
# --- Agenda del día (tinas, masajes, cabañas) — TODOS la reciben ---
try:
    from ventas.models import ReservaServicio
    hoy = date.today()
    base_qs = ReservaServicio.objects.filter(
        fecha_agendamiento=hoy
    ).exclude(
        venta_reserva__estado_pago='cancelado'
    ).select_related('servicio')

    primera_tina = base_qs.filter(servicio__tipo_servicio='tina').order_by('hora_inicio').first()
    primer_masaje = base_qs.filter(servicio__tipo_servicio='masaje').order_by('hora_inicio').first()
    cabanas_hoy = list(
        base_qs.filter(servicio__tipo_servicio='cabana')
        .order_by('hora_inicio')
        .values_list('servicio__nombre', flat=True)
    )

    hay_contenido = True  # esta sección siempre se muestra, aunque esté vacía
    lineas.append('\n📅 *Agenda del día:*')
    lineas.append(f'🛁 Primera tina: {primera_tina.hora_inicio} · {primera_tina.servicio.nombre}'
                  if primera_tina else '🛁 Sin tinas agendadas hoy')
    lineas.append(f'💆 Primer masaje: {primer_masaje.hora_inicio} · {primer_masaje.servicio.nombre}'
                  if primer_masaje else '💆 Sin masajes agendados hoy')
    if cabanas_hoy:
        lineas.append(f'🏡 Cabañas arrendadas hoy ({len(cabanas_hoy)}): {", ".join(cabanas_hoy)}')
    else:
        lineas.append('🏡 Sin cabañas arrendadas hoy')
except Exception:
    pass
```
(Pseudocódigo orientativo — ajustar a la convención exacta del archivo; ya importa `date` arriba.)

**Nota de diseño:** "primera tina"/"primer masaje" = la más temprana del día (no todo el listado);
"cabañas" = TODAS las de hoy con su nombre (Jorge pidió "cuántas y cuáles", no solo la primera). Así
lo pidió explícitamente.

## 4. Qué NO cambia

- "Tus tareas de hoy" y "Comandas pendientes": intactas.
- El mecanismo de avisos de operación (`NotificacionStaff`, H-038): intacto, no relacionado.
- Nadie más pierde acceso a nada — el único campo nuevo nace en `False` (nadie ve MENOS de lo que
  ve hoy salvo Jorge mismo, que hay que reactivarlo a mano tras el deploy — ver sección 2).

## 5. Avisar cuando esté

Con el deploy hecho + migración corrida, avisame la ruta/nombre final del campo si lo cambiaste, y
recuérdale a Jorge activar `recibe_info_financiera` en su fila (y en la de Alda). ¡Gracias!
