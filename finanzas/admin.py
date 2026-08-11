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
                     MovimientoFinanciero, ReglaGlosa, SaldoMensual)
from .reglas_glosa import patron_sugerido


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
    # El presupuesto se escribe ACÁ, en la lista: filtrar por gasto y llenar
    # la columna de arriba a abajo en una sola pantalla (Jorge 2026-08-10).
    list_display = ('nombre', 'clave', 'clase', 'grupo', 'presupuesto_fmt',
                    'presupuesto_mensual', 'presupuesto_pct_ventas', 'orden')
    list_filter = ('clase', 'grupo')
    list_editable = ('presupuesto_mensual', 'presupuesto_pct_ventas', 'orden')
    # Requerido por el autocomplete de categoría en MovimientoFinanciero.
    search_fields = ('nombre', 'clave')

    @admin.display(description='Presupuesto', ordering='presupuesto_mensual')
    def presupuesto_fmt(self, obj):
        # El % manda: si está puesto, el monto fijo de al lado no se usa, y
        # mostrarlo como si rigiera sería mentir en la propia pantalla donde
        # se edita.
        if obj.presupuesto_pct_ventas:
            return f'{obj.presupuesto_pct_ventas:.10g}% de las ventas'
        if not obj.presupuesto_mensual:
            return '— sin definir'
        return f'${obj.presupuesto_mensual:,.0f}/mes'.replace(',', '.')


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


def _es_colaborador(user):
    return user.groups.filter(name='Finanzas colaborador').exists()


class SuperusuarioOColaborador:
    """Movimientos: el colaborador (Alda) VE y solo cambia la categoría.
    Crear/borrar y el resto de los modelos siguen siendo del superusuario."""

    def has_module_permission(self, request):
        return request.user.is_superuser or _es_colaborador(request.user)

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_change_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def get_readonly_fields(self, request, obj=None):
        base = super().get_readonly_fields(request, obj)
        if request.user.is_superuser:
            return base
        # Colaborador: TODO readonly salvo la categoría (el triaje).
        campos = [f.name for f in self.model._meta.fields if f.name != 'categoria']
        return tuple(set(base) | set(campos))


@admin.register(MovimientoFinanciero)
class MovimientoFinancieroAdmin(SuperusuarioOColaborador, admin.ModelAdmin):
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
    actions = ['siempre_esta_categoria']

    @admin.action(description='Siempre esta categoría para esta glosa')
    def siempre_esta_categoria(self, request, queryset):
        """Enseña una regla a partir de un movimiento ya clasificado.

        No escribe de inmediato: manda a una pantalla que muestra el patrón
        propuesto (editable) y cuántos movimientos ya cargados se
        reclasificarían. Las glosas traen números que cambian mes a mes, así
        que fijar el patrón a ciegas haría una regla que no calza nunca más.
        """
        if not request.user.is_superuser:
            self.message_user(request, 'La lista «siempre Aremko» la administra '
                                       'solo el dueño.', level=messages.ERROR)
            return None
        sin_categoria = [m for m in queryset if m.categoria_id is None]
        if sin_categoria:
            self.message_user(
                request, 'Primero asigná la categoría en la lista y guardá: la '
                         'regla se aprende del movimiento ya clasificado.',
                level=messages.ERROR)
            return None
        ids = ','.join(str(m.pk) for m in queryset)
        return redirect(f'aprender-regla/?ids={ids}')

    @admin.display(description='Monto', ordering='monto')
    def monto_fmt(self, obj):
        signo = '+' if obj.sentido == 'entra' else '−'
        return f'{signo}${obj.monto:,.0f}'.replace(',', '.')

    @admin.display(description='Descripción')
    def descripcion_corta(self, obj):
        return (obj.descripcion or '')[:60]

    def get_urls(self):
        urls = super().get_urls()
        extra = [
            path('traspaso/', self.admin_site.admin_view(self.vista_traspaso),
                 name='finanzas_registrar_traspaso'),
            path('aprender-regla/',
                 self.admin_site.admin_view(self.vista_aprender_regla),
                 name='finanzas_aprender_regla'),
        ]
        return extra + urls

    def vista_aprender_regla(self, request):
        """Confirmar el patrón antes de fijarlo, y ver qué reclasifica."""
        if not request.user.is_superuser:
            return redirect('admin:finanzas_movimientofinanciero_changelist')

        crudos = (request.POST.get('ids') or request.GET.get('ids') or '')
        ids = [int(x) for x in crudos.split(',') if x.strip().isdigit()]
        movs = list(MovimientoFinanciero.objects
                    .filter(pk__in=ids).select_related('categoria', 'cuenta'))
        if not movs:
            return redirect('admin:finanzas_movimientofinanciero_changelist')

        propuestas = []
        for i, m in enumerate(movs):
            patron = (request.POST.get(f'patron_{i}')
                      or patron_sugerido(m.descripcion))
            alcance = MovimientoFinanciero.objects.filter(
                clase='gasto', categoria__clave='por_clasificar',
                descripcion__icontains=patron).exclude(pk=m.pk)
            propuestas.append({
                'indice': i, 'movimiento': m, 'patron': patron,
                'ya_existe': ReglaGlosa.objects.filter(patron=patron.upper()
                                                       ).first(),
                # Sin esto, «cuántos toca» sería una sorpresa después de
                # apretar el botón. Es la lección de revisar_duplicados.
                'reclasifica': alcance.count(),
            })

        if request.method == 'POST' and request.POST.get('confirmar'):
            creadas = tocados = 0
            for p in propuestas:
                patron = (p['patron'] or '').strip().upper()
                if not patron:
                    continue
                regla, nueva = ReglaGlosa.objects.get_or_create(
                    patron=patron,
                    defaults={'categoria': p['movimiento'].categoria,
                              'creada_por': request.user,
                              'nota': f'Aprendida de: {p["movimiento"].descripcion[:120]}'})
                creadas += 1 if nueva else 0
                tocados += (MovimientoFinanciero.objects
                            .filter(clase='gasto',
                                    categoria__clave='por_clasificar',
                                    descripcion__icontains=patron)
                            .update(categoria=regla.categoria))
            self.message_user(
                request,
                f'{creadas} regla(s) nueva(s) · {tocados} movimiento(s) que '
                f'estaban por clasificar quedaron asignados.',
                level=messages.SUCCESS)
            return redirect('admin:finanzas_movimientofinanciero_changelist')

        contexto = dict(self.admin_site.each_context(request),
                        propuestas=propuestas, ids=crudos,
                        title='Enseñar una regla: siempre esta categoría')
        return render(request, 'finanzas/aprender_regla.html', contexto)

    def vista_traspaso(self, request):
        # El traspaso crea movimientos: solo el dueño. El colaborador que
        # llegue por URL vuelve al listado sin drama.
        if not request.user.is_superuser:
            return redirect('admin:finanzas_movimientofinanciero_changelist')
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


@admin.register(ReglaGlosa)
class ReglaGlosaAdmin(SoloSuperusuario, admin.ModelAdmin):
    """La lista finita de Jorge. SoloSuperusuario a propósito: Alda clasifica
    movimientos uno a uno, pero la regla que decide para siempre es de él."""
    list_display = ('patron', 'categoria', 'activa', 'nota', 'creada_por',
                    'creado_en')
    list_filter = ('activa', 'categoria__grupo', 'categoria')
    search_fields = ('patron', 'nota')
    list_editable = ('activa',)
    autocomplete_fields = ('categoria',)
    readonly_fields = ('creada_por', 'creado_en')

    def save_model(self, request, obj, form, change):
        if not change and obj.creada_por_id is None:
            obj.creada_por = request.user
        super().save_model(request, obj, form, change)
