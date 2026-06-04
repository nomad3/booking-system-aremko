"""Ficha de bienestar — vista mobile-first para la masajista.

Pensada para el celular: muestra los datos mínimos + preferencias (solo lectura)
y un formulario simple para completar el "Resumen del terapeuta". Al guardar,
dispara el email de resumen (signal post_save de BienestarMasajeFicha).

Acceso: solo el masajista ASIGNADO al masaje (Proveedor.usuario / email) o
admin/coordinación. Cualquier otro → 404.
"""

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from ..models import BienestarMasajeFicha, Proveedor


def _proveedor_de_usuario(user):
    prov = Proveedor.objects.filter(usuario=user).first()
    if not prov and getattr(user, 'email', ''):
        prov = Proveedor.objects.filter(email__iexact=user.email).first()
    return prov


def _es_masajista(user):
    return (not user.is_superuser) and user.groups.filter(name='Masajistas').exists()


@staff_member_required
def ficha_masajista(request, ficha_id):
    ficha = get_object_or_404(
        BienestarMasajeFicha.objects.select_related('reserva', 'cliente'), id=ficha_id
    )

    # ---- Control de acceso ----
    if _es_masajista(request.user):
        prov = _proveedor_de_usuario(request.user)
        asignado = bool(prov and ficha.reserva_id and ficha.reserva.reservaservicios.filter(
            servicio__tipo_servicio='masaje', proveedor_asignado=prov,
        ).exists())
        if not asignado:
            raise Http404("Ficha no disponible.")
    # admin / coordinación: acceso completo

    # ---- Guardar resumen ----
    if request.method == 'POST':
        ficha.obs_terapeuta = (request.POST.get('obs_terapeuta') or '')[:5000]
        ficha.zonas_trabajadas = (request.POST.get('zonas_trabajadas') or '')[:255]
        ficha.intensidad_aplicada = (request.POST.get('intensidad_aplicada') or '')[:10]
        ficha.sugerencia_frecuencia = (request.POST.get('sugerencia_frecuencia') or '')[:15]
        ficha.recomendacion_texto = (request.POST.get('recomendacion_texto') or '')[:5000]
        ficha.save()  # dispara el signal que programa el email de resumen
        messages.success(request, '✓ Resumen guardado.')
        return redirect('ventas:ficha_masajista', ficha_id=ficha.id)

    rs = None
    if ficha.reserva_id:
        rs = (ficha.reserva.reservaservicios
              .filter(servicio__tipo_servicio='masaje')
              .order_by('fecha_agendamiento', 'hora_inicio').first())

    ctx = {
        'ficha': ficha,
        'cliente_nombre': ficha.nombre_completo or (ficha.cliente.nombre if ficha.cliente_id else '—'),
        'reserva_id': ficha.reserva_id,
        'fecha_servicio': rs.fecha_agendamiento if rs else None,
        'hora_servicio': str(rs.hora_inicio)[:5] if (rs and rs.hora_inicio) else '',
        'masajista': rs.proveedor_asignado.nombre if (rs and rs.proveedor_asignado_id) else '— sin asignar —',
        'intensidades': BienestarMasajeFicha.INTENSIDAD_CHOICES,
        'frecuencias': BienestarMasajeFicha.FRECUENCIA_CHOICES,
    }
    return render(request, 'ventas/ficha_masajista.html', ctx)
