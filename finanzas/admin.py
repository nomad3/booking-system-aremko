# -*- coding: utf-8 -*-
"""Admin de finanzas — SOLO superusuario, igual que costos_web.

Es el instrumento del dueño: ni staff ni operación lo ven. El botón
"Registrar traspaso" crea las DOS piernas de una vez, porque un traspaso
digitado a mano por un solo lado es la fuente clásica de descuadres.
"""
from django import forms
from django.contrib import admin, messages
from django.shortcuts import redirect, render
from django.urls import path

from .models import (CategoriaFinanciera, CuentaFinanciera,
                     MovimientoFinanciero, SaldoMensual)


class SoloSuperusuario:
    def has_module_permission(self, request):
        return bool(request.user and request.user.is_superuser)

    def has_view_permission(self, request, obj=None):
        return bool(request.user and request.user.is_superuser)

    def has_add_permission(self, request):
        return bool(request.user and request.user.is_superuser)

    def has_change_permission(self, request, obj=None):
        return bool(request.user and request.user.is_superuser)

    def has_delete_permission(self, request, obj=None):
        return bool(request.user and request.user.is_superuser)


@admin.register(CuentaFinanciera)
class CuentaFinancieraAdmin(SoloSuperusuario, admin.ModelAdmin):
    list_display = ('nombre', 'clave', 'tipo', 'activa')
    list_filter = ('tipo', 'activa')
    search_fields = ('nombre', 'clave')


@admin.register(CategoriaFinanciera)
class CategoriaFinancieraAdmin(SoloSuperusuario, admin.ModelAdmin):
    list_display = ('nombre', 'clave', 'clase', 'orden')
    list_filter = ('clase',)
    list_editable = ('orden',)
    # Requerido por el autocomplete de categoría en MovimientoFinanciero.
    search_fields = ('nombre', 'clave')


class TraspasoForm(forms.Form):
    fecha = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    desde = forms.ModelChoiceField(queryset=CuentaFinanciera.objects.filter(activa=True),
                                   label='Sale de')
    hacia = forms.ModelChoiceField(queryset=CuentaFinanciera.objects.filter(activa=True),
                                   label='Entra a')
    monto = forms.DecimalField(min_value=1, decimal_places=0, max_digits=12)
    descripcion = forms.CharField(max_length=255, required=False)

    def clean(self):
        datos = super().clean()
        if datos.get('desde') and datos.get('desde') == datos.get('hacia'):
            raise forms.ValidationError('Origen y destino no pueden ser la misma cuenta.')
        return datos


@admin.register(MovimientoFinanciero)
class MovimientoFinancieroAdmin(SoloSuperusuario, admin.ModelAdmin):
    change_list_template = 'finanzas/movimiento_changelist.html'
    list_display = ('fecha', 'cuenta', 'clase', 'sentido', 'monto_fmt',
                    'categoria', 'descripcion_corta', 'fuente', 'fecha_estimada')
    list_filter = ('clase', 'categoria__grupo', 'cuenta', 'categoria', 'fuente',
                   'fecha_estimada')
    search_fields = ('descripcion', 'referencia')
    date_hierarchy = 'fecha'
    list_select_related = ('cuenta', 'categoria')
    # La reclasificación es el trabajo fino de la jornada P-22: la categoría se
    # edita EN LA LISTA (dropdown por fila + botón Guardar al pie). Flujo de
    # Jorge: filtrar por «Por clasificar», asignar en lote, guardar.
    list_editable = ('categoria',)
    autocomplete_fields = ('categoria',)
    readonly_fields = ('traspaso_par', 'creado_en', 'actualizado_en')

    @admin.display(description='Monto', ordering='monto')
    def monto_fmt(self, obj):
        signo = '+' if obj.sentido == 'entra' else '−'
        return f'{signo}${obj.monto:,.0f}'.replace(',', '.')

    @admin.display(description='Descripción')
    def descripcion_corta(self, obj):
        return (obj.descripcion or '')[:60]

    def get_urls(self):
        urls = super().get_urls()
        extra = [path('traspaso/', self.admin_site.admin_view(self.vista_traspaso),
                      name='finanzas_registrar_traspaso')]
        return extra + urls

    def vista_traspaso(self, request):
        if not request.user.is_superuser:
            return redirect('admin:index')
        form = TraspasoForm(request.POST or None)
        if request.method == 'POST' and form.is_valid():
            d = form.cleaned_data
            salida = MovimientoFinanciero.objects.create(
                fecha=d['fecha'], cuenta=d['desde'], clase='traspaso', sentido='sale',
                monto=d['monto'], descripcion=d['descripcion'] or f"Traspaso a {d['hacia'].nombre}",
                fuente='manual')
            entrada = MovimientoFinanciero.objects.create(
                fecha=d['fecha'], cuenta=d['hacia'], clase='traspaso', sentido='entra',
                monto=d['monto'], descripcion=d['descripcion'] or f"Traspaso desde {d['desde'].nombre}",
                fuente='manual', traspaso_par=salida)
            salida.traspaso_par = entrada
            salida.save(update_fields=['traspaso_par'])
            messages.success(request, 'Traspaso registrado: dos líneas creadas y enlazadas.')
            return redirect('admin:finanzas_movimientofinanciero_changelist')
        contexto = dict(self.admin_site.each_context(request), form=form,
                        title='Registrar traspaso entre cuentas')
        return render(request, 'finanzas/traspaso_form.html', contexto)


@admin.register(SaldoMensual)
class SaldoMensualAdmin(SoloSuperusuario, admin.ModelAdmin):
    list_display = ('periodo', 'cuenta', 'saldo_fmt', 'fuente', 'notas')
    list_filter = ('cuenta', 'fuente')
    date_hierarchy = 'periodo'

    @admin.display(description='Saldo de cierre', ordering='saldo_cierre')
    def saldo_fmt(self, obj):
        return f'${obj.saldo_cierre:,.0f}'.replace(',', '.')
