"""Agenda de Masajes por fecha (Conexión-Masajes).

Selector de fecha (por defecto hoy, solo de hoy en adelante) → lista los masajes
de esa fecha con cliente, hora, masajista asignado y estado de la ficha, con
acceso directo a la ficha.

Visibilidad:
- Masajista (grupo "Masajistas", no superuser): ve SOLO sus masajes asignados
  (ReservaServicio.proveedor_asignado == su Proveedor, vía Proveedor.usuario o
  email coincidente).
- Deborah / admin: ven TODOS los masajes de la fecha.
"""

from datetime import datetime

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.utils import timezone

from ..models import ReservaServicio, Proveedor


def _proveedor_de_usuario(user):
    prov = Proveedor.objects.filter(usuario=user).first()
    if not prov and getattr(user, 'email', ''):
        prov = Proveedor.objects.filter(email__iexact=user.email).first()
    return prov


def _es_masajista(user):
    return (not user.is_superuser) and user.groups.filter(name='Masajistas').exists()


@staff_member_required
def agenda_masajes(request):
    hoy = timezone.localtime(timezone.now()).date()

    fecha = hoy
    fecha_str = request.GET.get('fecha')
    if fecha_str:
        try:
            fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        except ValueError:
            fecha = hoy
    if fecha < hoy:
        fecha = hoy  # solo hoy en adelante

    es_masajista = _es_masajista(request.user)
    prov = _proveedor_de_usuario(request.user) if es_masajista else None

    masajista_sin_vinculo = es_masajista and not prov

    # Reservas con masaje en la fecha.
    lineas = (
        ReservaServicio.objects
        .filter(servicio__tipo_servicio='masaje', fecha_agendamiento=fecha)
        .select_related('proveedor_asignado', 'venta_reserva', 'venta_reserva__cliente')
    )
    reservas_ids = list(lineas.values_list('venta_reserva_id', flat=True).distinct())

    from .. import models as _m
    from ..services.masaje_participantes_service import mapear_participante_a_linea

    # UNA fila por PERSONA (participante), atendida por el masajista de SU línea.
    filas = []
    if not masajista_sin_vinculo:
        reservas = _m.VentaReserva.objects.filter(id__in=reservas_ids).select_related('cliente')
        for vr in reservas:
            mapeo = mapear_participante_a_linea(vr)  # {participante_id: ReservaServicio|None}
            participantes = sorted(
                vr.participantes_masaje.select_related('ficha_bienestar', 'cliente').all(),
                key=lambda p: (0 if p.tipo_participante == 'comprador' else 1, p.id),
            )
            for p in participantes:
                ls = mapeo.get(p.id)
                # Solo personas cuya línea de masaje es de ESTA fecha.
                if not ls or ls.fecha_agendamiento != fecha:
                    continue
                masajista_prov = ls.proveedor_asignado if ls.proveedor_asignado_id else None
                # El masajista solo ve a SUS personas.
                if es_masajista and not (masajista_prov and masajista_prov.id == prov.id):
                    continue
                filas.append({
                    'hora': str(ls.hora_inicio)[:5] if (ls and ls.hora_inicio) else '',
                    'reserva_id': vr.id,
                    'masajista': masajista_prov.nombre if masajista_prov else '— sin asignar —',
                    'nombre': p.nombre or (vr.cliente.nombre if vr.cliente_id else '—'),
                    'tipo': p.get_tipo_participante_display(),
                    'ficha_id': p.ficha_bienestar_id,
                    'estado': 'Completada' if p.ficha_bienestar_id else 'Pendiente del cliente',
                })

    filas.sort(key=lambda f: (f['hora'] or '99:99', f['reserva_id'], f['nombre']))

    from datetime import timedelta
    fecha_next = fecha + timedelta(days=1)
    fecha_prev = fecha - timedelta(days=1)

    ctx = {
        'fecha': fecha,
        'fecha_iso': fecha.strftime('%Y-%m-%d'),
        'hoy_iso': hoy.strftime('%Y-%m-%d'),
        'fecha_next_iso': fecha_next.strftime('%Y-%m-%d'),
        'fecha_prev_iso': (fecha_prev.strftime('%Y-%m-%d') if fecha_prev >= hoy else None),
        'es_hoy': fecha == hoy,
        'filas': filas,
        'total': len(filas),
        'es_masajista': es_masajista,
        'masajista_sin_vinculo': masajista_sin_vinculo,
    }
    return render(request, 'ventas/agenda_masajes.html', ctx)
