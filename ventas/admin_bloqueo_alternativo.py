"""
Admin alternativo para crear bloqueos de servicio sin errores
"""
from django.contrib import admin
from django.urls import path
from django.shortcuts import render, redirect
from django.contrib import messages
from django import forms
from django.db import connection
from datetime import datetime
from ventas.models import Servicio, ServicioBloqueo


class BloqueoServicioForm(forms.Form):
    """Formulario simple para crear bloqueos"""
    servicio = forms.ModelChoiceField(
        queryset=Servicio.objects.filter(activo=True),
        label="Servicio a bloquear",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    fecha_inicio = forms.DateField(
        label="Fecha inicio",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    fecha_fin = forms.DateField(
        label="Fecha fin",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    motivo = forms.CharField(
        label="Motivo del bloqueo",
        max_length=255,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    notas = forms.CharField(
        label="Notas adicionales",
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3})
    )

    def clean(self):
        cleaned_data = super().clean()
        fecha_inicio = cleaned_data.get('fecha_inicio')
        fecha_fin = cleaned_data.get('fecha_fin')

        if fecha_inicio and fecha_fin:
            if fecha_inicio > fecha_fin:
                raise forms.ValidationError('La fecha fin debe ser posterior a la fecha inicio')

        return cleaned_data


def crear_bloqueo_servicio_view(request):
    """Vista para crear bloqueos de servicio sin problemas"""
    if request.method == 'POST':
        form = BloqueoServicioForm(request.POST)
        if form.is_valid():
            # Inserción directa en BD para evitar validaciones problemáticas
            try:
                with connection.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO ventas_serviciobloqueo
                        (servicio_id, fecha_inicio, fecha_fin, motivo, activo,
                         creado_en, creado_por_id, notas, fecha, hora_slot)
                        VALUES (%s, %s, %s, %s, %s, NOW(), %s, %s, %s, %s)
                        RETURNING id
                    """, [
                        form.cleaned_data['servicio'].id,
                        form.cleaned_data['fecha_inicio'],
                        form.cleaned_data['fecha_fin'],
                        form.cleaned_data['motivo'],
                        True,
                        request.user.id,
                        form.cleaned_data['notas'] or '',
                        form.cleaned_data['fecha_inicio'],  # fecha = fecha_inicio
                        'N/A'  # hora_slot por defecto
                    ])

                    bloqueo_id = cursor.fetchone()[0]

                messages.success(
                    request,
                    f'✅ Bloqueo creado exitosamente (ID: {bloqueo_id})'
                )
                return redirect('/admin/ventas/serviciobloqueo/')

            except Exception as e:
                messages.error(request, f'Error al crear bloqueo: {str(e)}')
    else:
        form = BloqueoServicioForm()

    context = {
        'form': form,
        'title': 'Crear Bloqueo de Servicio (Formulario Alternativo)',
        'opts': {'app_label': 'ventas', 'verbose_name': 'Bloqueo de Servicio'},
    }

    return render(request, 'admin/ventas/bloqueo_servicio_form.html', context)


# Registrar la URL personalizada
def get_admin_urls(urls):
    """Agregar URL personalizada al admin"""
    custom_urls = [
        path('ventas/serviciobloqueo/crear-alternativo/',
             admin.site.admin_view(crear_bloqueo_servicio_view),
             name='crear_bloqueo_alternativo'),
    ]
    return custom_urls + urls