# -*- coding: utf-8 -*-
"""Catálogo y venta de artesanías — para el equipo de recepción (staff)."""
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Q, Sum
from django.shortcuts import redirect, render

from .models import ArtesaniaPieza
from .services import ErrorVenta, vender_pieza


def _orden_natural(pieza):
    c = pieza.codigo
    return (0, int(c)) if c.isdigit() else (1, c)


@staff_member_required
def catalogo(request):
    """El reemplazo del papel: buscar, ver, vender y dar de alta."""

    # ── Vender (POST desde la tarjeta de una pieza) ──────────────────────────
    if request.method == 'POST' and request.POST.get('accion') == 'vender':
        try:
            pieza, reserva = vender_pieza(
                request.POST.get('codigo'),
                request.POST.get('reserva_id'),
                monto=(request.POST.get('monto') or '').replace('.', '').strip() or None,
                usuario=request.user.get_username(),
            )
            messages.success(
                request,
                f'✓ {pieza.codigo} · {pieza.nombre} vendida en '
                f'${int(pieza.venta_monto):,} a la reserva #{reserva.id} '
                f'(total reserva: ${int(reserva.total):,})'.replace(',', '.'))
        except ErrorVenta as e:
            messages.error(request, str(e))
        return redirect('artesanias:catalogo')

    # ── Alta rápida ──────────────────────────────────────────────────────────
    if request.method == 'POST' and request.POST.get('accion') == 'alta':
        codigo = (request.POST.get('codigo') or '').strip()
        nombre = (request.POST.get('nombre') or '').strip()
        precio = (request.POST.get('precio') or '').replace('.', '').strip()
        if not codigo or not nombre or not precio.isdigit() or int(precio) <= 0:
            messages.error(request, 'Alta incompleta: código, nombre y precio son obligatorios.')
        elif ArtesaniaPieza.objects.filter(codigo=codigo).exists():
            messages.error(request, f'El código {codigo} ya existe.')
        else:
            pieza = ArtesaniaPieza.objects.create(
                codigo=codigo, nombre=nombre, precio=int(precio),
                estado=request.POST.get('estado') or 'disponible',
                foto=request.FILES.get('foto'))
            messages.success(request, f'✓ Pieza {pieza.codigo} · {pieza.nombre} ingresada.')
        return redirect('artesanias:catalogo')

    # ── Listado ──────────────────────────────────────────────────────────────
    filtro = request.GET.get('estado', 'vivas')
    q = (request.GET.get('q') or '').strip()

    piezas = ArtesaniaPieza.objects.all()
    if filtro == 'vivas':
        piezas = piezas.filter(estado__in=ArtesaniaPieza.VIVOS)
    elif filtro != 'todas':
        piezas = piezas.filter(estado=filtro)
    if q:
        piezas = piezas.filter(Q(codigo__icontains=q) | Q(nombre__icontains=q))

    piezas = sorted(piezas, key=_orden_natural)

    vivas = ArtesaniaPieza.objects.filter(estado__in=ArtesaniaPieza.VIVOS)
    valor_vivo = int(vivas.aggregate(t=Sum('precio'))['t'] or 0)
    resumen = {
        'n_vivas': vivas.count(),
        'valor_vivo': f'${valor_vivo:,}'.replace(',', '.'),
        'n_vendidas': ArtesaniaPieza.objects.filter(estado='vendida').count(),
    }

    return render(request, 'artesanias/catalogo.html', {
        'piezas': piezas,
        'filtro': filtro,
        'q': q,
        'resumen': resumen,
        'sugerencia_codigo': ArtesaniaPieza.siguiente_codigo(),
        'estados': ArtesaniaPieza.ESTADOS,
    })
