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

    # Agrupar servicios publicados en web por categoría basada en nombre
    servicios_por_tipo = {}

    # Obtener SOLO servicios publicados en web
    servicios_query = Servicio.objects.filter(
        publicado_web=True
    ).order_by('nombre')

    # Agrupar por categoría inferida del nombre
    for servicio in servicios_query:
        nombre_lower = servicio.nombre.lower()

        # Determinar categoría basada en el nombre
        if any(word in nombre_lower for word in ['tina', 'tinaja', 'termas']):
            categoria = 'TINAS'
        elif any(word in nombre_lower for word in ['cabaña', 'cabana', 'torre', 'refugio', 'lodge']):
            categoria = 'CABAÑAS'
        elif any(word in nombre_lower for word in ['masaje', 'spa', 'relajación', 'descontracturante']):
            categoria = 'MASAJES'
        else:
            categoria = 'OTROS'

        if categoria not in servicios_por_tipo:
            servicios_por_tipo[categoria] = []
        servicios_por_tipo[categoria].append(servicio)

    # Debug: imprimir qué encontramos
    print(f"DEBUG: Categorías encontradas: {list(servicios_por_tipo.keys())}")
    for categoria, servicios in servicios_por_tipo.items():
        print(f"  {categoria}: {len(servicios)} servicios")
        for s in servicios[:3]:  # Mostrar primeros 3 de cada categoría
            print(f"    - {s.nombre}")

    context = {
        'form': form,
        'title': 'Crear Pack de Descuento',
        'servicios_por_tipo': servicios_por_tipo,
        'tipo_servicio_choices': PackDescuento.TIPO_SERVICIO_CHOICES
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

    # Agrupar servicios publicados en web por categoría basada en nombre
    servicios_por_tipo = {}

    # Obtener SOLO servicios publicados en web
    servicios_query = Servicio.objects.filter(
        publicado_web=True
    ).order_by('nombre')

    # Agrupar por categoría inferida del nombre
    for servicio in servicios_query:
        nombre_lower = servicio.nombre.lower()

        # Determinar categoría basada en el nombre
        if any(word in nombre_lower for word in ['tina', 'tinaja', 'termas']):
            categoria = 'TINAS'
        elif any(word in nombre_lower for word in ['cabaña', 'cabana', 'torre', 'refugio', 'lodge']):
            categoria = 'CABAÑAS'
        elif any(word in nombre_lower for word in ['masaje', 'spa', 'relajación', 'descontracturante']):
            categoria = 'MASAJES'
        else:
            categoria = 'OTROS'

        if categoria not in servicios_por_tipo:
            servicios_por_tipo[categoria] = []
        servicios_por_tipo[categoria].append(servicio)

    # Debug: imprimir qué encontramos
    print(f"DEBUG Edit: Categorías encontradas: {list(servicios_por_tipo.keys())}")
    for categoria, servicios in servicios_por_tipo.items():
        print(f"  {categoria}: {len(servicios)} servicios")
        for s in servicios[:3]:  # Mostrar primeros 3 de cada categoría
            print(f"    - {s.nombre}")

    context = {
        'form': form,
        'pack': pack,
        'title': f'Editar Pack: {pack.nombre}',
        'servicios_por_tipo': servicios_por_tipo,
        'tipo_servicio_choices': PackDescuento.TIPO_SERVICIO_CHOICES
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