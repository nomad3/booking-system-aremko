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

    lineas = (
        ReservaServicio.objects
        .filter(servicio__tipo_servicio='masaje', fecha_agendamiento=fecha)
        .select_related('servicio', 'proveedor_asignado', 'venta_reserva', 'venta_reserva__cliente')
        .order_by('hora_inicio', 'id')
    )
    masajista_sin_vinculo = False
    if es_masajista:
        if prov:
            lineas = lineas.filter(proveedor_asignado=prov)
        else:
            lineas = lineas.none()
            masajista_sin_vinculo = True

    # UNA fila por MASAJE (línea de servicio) asignado — no por participante.
    # Así el masajista ve exactamente los masajes que tiene asignados.
    filas = []
    for ls in lineas:
        vr = ls.venta_reserva
        if not vr:
            continue
        hora = str(ls.hora_inicio)[:5] if ls.hora_inicio else ''
        masajista = ls.proveedor_asignado.nombre if ls.proveedor_asignado_id else '— sin asignar —'
        cant = ls.cantidad_personas or 1

        # Ficha a abrir: la del comprador si existe; si no, la 1ª con ficha.
        participantes = sorted(
            vr.participantes_masaje.select_related('ficha_bienestar', 'cliente').all(),
            key=lambda p: (0 if p.tipo_participante == 'comprador' else 1, p.id),
        )
        ficha_id = None
        for p in participantes:
            if p.ficha_bienestar_id:
                ficha_id = p.ficha_bienestar_id
                break
        completas = sum(1 for p in participantes if p.ficha_bienestar_id)

        filas.append({
            'hora': hora,
            'reserva_id': vr.id,
            'masajista': masajista,
            'nombre': (vr.cliente.nombre if vr.cliente_id
                       else (participantes[0].nombre if participantes else '—')),
            'cantidad': cant,
            'ficha_id': ficha_id,
            'estado': 'Completada' if completas else 'Pendiente del cliente',
            'fichas_total': len(participantes),
            'fichas_completas': completas,
        })

    filas.sort(key=lambda f: (f['hora'] or '99:99', f['reserva_id']))

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
