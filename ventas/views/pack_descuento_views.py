"""
Vistas para gestión de Packs de Descuento
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from ..models import PackDescuento, Servicio
from ..forms.pack_descuento_form import PackDescuentoForm


@login_required
def pack_list_view(request):
    """Lista todos los packs de descuento"""
    packs = PackDescuento.objects.all().order_by('-activo', '-prioridad', 'nombre')

    # Agregar información de servicios para cada pack
    for pack in packs:
        if pack.usa_servicios_especificos:
            pack.servicios_display = ", ".join([s.nombre for s in pack.servicios_especificos.all()])
        else:
            pack.servicios_display = ", ".join(pack.get_servicios_requeridos_display())

    context = {
        'packs': packs,
        'title': 'Gestión de Packs de Descuento'
    }
    return render(request, 'ventas/pack_descuento/list.html', context)


@login_required
def pack_create_view(request):
    """Crear nuevo pack de descuento"""
    if request.method == 'POST':
        form = PackDescuentoForm(request.POST)
        if form.is_valid():
            pack = form.save()
            messages.success(request, f'Pack "{pack.nombre}" creado exitosamente')
            return redirect('ventas:pack_list')
    else:
        form = PackDescuentoForm()

    # Agrupar servicios por tipo para mejor visualización
    servicios_por_tipo = {}
    for servicio in Servicio.objects.filter(activo=True, publicado=True).order_by('tipo_servicio', 'nombre'):
        tipo = servicio.get_tipo_servicio_display()
        if tipo not in servicios_por_tipo:
            servicios_por_tipo[tipo] = []
        servicios_por_tipo[tipo].append(servicio)

    context = {
        'form': form,
        'title': 'Crear Pack de Descuento',
        'servicios_por_tipo': servicios_por_tipo
    }
    return render(request, 'ventas/pack_descuento/form.html', context)


@login_required
def pack_edit_view(request, pk):
    """Editar pack de descuento existente"""
    pack = get_object_or_404(PackDescuento, pk=pk)

    if request.method == 'POST':
        form = PackDescuentoForm(request.POST, instance=pack)
        if form.is_valid():
            pack = form.save()
            messages.success(request, f'Pack "{pack.nombre}" actualizado exitosamente')
            return redirect('ventas:pack_list')
    else:
        form = PackDescuentoForm(instance=pack)

    # Agrupar servicios por tipo
    servicios_por_tipo = {}
    for servicio in Servicio.objects.filter(activo=True, publicado=True).order_by('tipo_servicio', 'nombre'):
        tipo = servicio.get_tipo_servicio_display()
        if tipo not in servicios_por_tipo:
            servicios_por_tipo[tipo] = []
        servicios_por_tipo[tipo].append(servicio)

    context = {
        'form': form,
        'pack': pack,
        'title': f'Editar Pack: {pack.nombre}',
        'servicios_por_tipo': servicios_por_tipo
    }
    return render(request, 'ventas/pack_descuento/form.html', context)


@login_required
def pack_toggle_active_view(request, pk):
    """Activar/desactivar pack rápidamente"""
    pack = get_object_or_404(PackDescuento, pk=pk)
    pack.activo = not pack.activo
    pack.save()

    estado = "activado" if pack.activo else "desactivado"
    messages.success(request, f'Pack "{pack.nombre}" {estado}')

    return redirect('ventas:pack_list')


@login_required
def pack_delete_view(request, pk):
    """Eliminar pack de descuento"""
    pack = get_object_or_404(PackDescuento, pk=pk)

    if request.method == 'POST':
        nombre = pack.nombre
        pack.delete()
        messages.success(request, f'Pack "{nombre}" eliminado exitosamente')
        return redirect('ventas:pack_list')

    context = {
        'pack': pack,
        'title': f'Eliminar Pack: {pack.nombre}'
    }
    return render(request, 'ventas/pack_descuento/confirm_delete.html', context)