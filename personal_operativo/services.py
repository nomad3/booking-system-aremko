# -*- coding: utf-8 -*-
"""Lógica de "Luna Interna" (Fase 0): identificar al staff por su número y armar
su briefing del día. Determinístico, en código (el LLM solo lo conversa).

Ver docs/PLAN_LUNA_INTERNA.md y docs/BRIEF_H-037_luna_interna_fase0.md.
"""
from datetime import date, timedelta

from django.utils import timezone


def _solo_digitos(s):
    return ''.join(c for c in (s or '') if c.isdigit())


def buscar_personal(telefono):
    """Devuelve el PersonalOperativo ACTIVO de ese número, o None.

    Hace match exacto y, si no, por los últimos 9 dígitos (tolera +56 / 56 / 9...).
    """
    from .models import PersonalOperativo
    if not telefono:
        return None
    qs = PersonalOperativo.objects.filter(activo=True)
    exacto = qs.filter(telefono=str(telefono).strip()).first()
    if exacto:
        return exacto
    d9 = _solo_digitos(telefono)[-9:]
    if not d9:
        return None
    for cand in qs:
        if _solo_digitos(cand.telefono)[-9:] == d9:
            return cand
    return None


def responde_auto(telefono):
    """True si ese número es staff whitelisted con autonomía (Luna responde sola)."""
    p = buscar_personal(telefono)
    return bool(p and p.responde_auto)


def receptores_avisos_operacion():
    """Personal activo que recibe los avisos de operación/recepción (el/los de turno)."""
    from .models import PersonalOperativo
    return list(PersonalOperativo.objects.filter(activo=True, recibe_avisos_operacion=True))


def texto_alerta_tarea(task):
    """Arma el texto WhatsApp de aviso para una tarea recién creada de control_gestion."""
    area = ''
    try:
        area = task.get_swimlane_display()
    except Exception:
        area = getattr(task, 'swimlane', '') or ''
    lineas = [f'🔔 *Nueva tarea · {area}*', (task.title or '').strip()]
    # Hora límite si la tarea la trae
    due = getattr(task, 'promise_due_at', None)
    if due:
        from django.utils import timezone
        try:
            due_local = timezone.localtime(due)
            lineas.append(f'⏰ Lista antes de las {due_local:%H:%M}')
        except Exception:
            pass
    ref = getattr(task, 'reservation_id', '') or ''
    if ref:
        lineas.append(f'📌 Reserva #{ref}')
    lineas.append('Responde "ok" cuando la tengas controlada.')
    return '\n'.join([l for l in lineas if l])


def encolar_notificacion(telefono, texto, dedup_key, origen='', ref_tipo='', ref_id=''):
    """Encola una notificación saliente (idempotente por dedup_key). Devuelve (obj, creada)."""
    from .models import NotificacionStaff
    return NotificacionStaff.objects.get_or_create(
        dedup_key=dedup_key,
        defaults={
            'telefono': telefono, 'texto': texto, 'origen': origen,
            'ref_tipo': ref_tipo, 'ref_id': str(ref_id),
        },
    )


def _saludo():
    h = timezone.localtime().hour
    if h < 12:
        return 'Buenos días'
    if h < 20:
        return 'Buenas tardes'
    return 'Buenas noches'


def construir_briefing(persona):
    """Arma el texto del briefing del día para un PersonalOperativo.

    Secciones (tolerantes a fallos: si una falla, no rompe el resto):
      - Pagos que vencen ≤7 días + saldos bajos (costos_web)
      - Tareas pendientes del usuario (control_gestion)
      - Comandas pendientes (pulso operativo)
    """
    primer_nombre = (persona.nombre.split()[0] if persona and persona.nombre else '').strip()
    lineas = [f'{_saludo()}, {primer_nombre} 👋'.replace(' 👋', ' 👋').strip()]
    lineas.append('Acá va tu resumen del día:')
    hay_contenido = False

    # --- Pagos y saldos (costos_web) ---
    try:
        from costos_web.models import ServicioWeb
        hoy = date.today()
        limite = hoy + timedelta(days=30)
        vencen = list(ServicioWeb.objects.filter(
            activo=True, proxima_fecha_pago__isnull=False, proxima_fecha_pago__lte=limite
        ).order_by('proxima_fecha_pago'))
        if vencen:
            hay_contenido = True
            lineas.append('\n💳 *Pagos próximos (30 días):*')
            for s in vencen:
                d = (s.proxima_fecha_pago - hoy).days
                cuando = 'VENCIDO' if d < 0 else ('hoy' if d == 0 else f'en {d} días')
                monto = f' · {s.monto:,.0f} {s.moneda}' if s.monto is not None else ''
                tarjeta = f' · ****{s.tarjeta_ultimos4}' if s.tarjeta_ultimos4 else ''
                lineas.append(f'• {s.nombre}: {s.proxima_fecha_pago:%d-%m} ({cuando}){monto}{tarjeta}')

        bajos = [s for s in ServicioWeb.objects.filter(activo=True, modalidad='uso') if s.saldo_bajo]
        if bajos:
            hay_contenido = True
            lineas.append('\n🔴 *Saldos bajos:*')
            for s in bajos:
                lineas.append(f'• {s.nombre}: {s.saldo_actual:,.0f} {s.moneda} '
                              f'(umbral {s.saldo_umbral_alerta:,.0f})')
    except Exception:
        pass

    # --- Tareas pendientes del usuario (control_gestion) ---
    try:
        if persona and persona.usuario_id:
            from control_gestion.models import Tarea
            pend = (Tarea.objects.filter(owner_id=persona.usuario_id)
                    .exclude(state='DONE').order_by('promise_due_at'))
            n = pend.count()
            if n:
                hay_contenido = True
                lineas.append(f'\n✅ *Tus tareas pendientes ({n}):*')
                for t in pend[:5]:
                    lineas.append(f'• {t.title}')
                if n > 5:
                    lineas.append(f'• …y {n - 5} más')
    except Exception:
        pass

    # --- Comandas pendientes (pulso operativo) ---
    try:
        from ventas.models import Comanda
        cp = Comanda.objects.filter(estado='pendiente').count()
        if cp:
            hay_contenido = True
            lineas.append(f'\n📋 Comandas pendientes: {cp}')
    except Exception:
        pass

    if not hay_contenido:
        lineas.append('\n✨ Nada urgente por ahora. ¡Buen turno!')

    return '\n'.join(lineas)
