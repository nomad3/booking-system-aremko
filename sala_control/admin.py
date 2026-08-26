# -*- coding: utf-8 -*-
"""Admin de la sala de control: pensado para editarse desde el celular."""
from django.contrib import admin

from .models import (CorteAds, MarcaPublicacion, NotaDelDia, NotaNegocio,
                     PrioridadSemana)


@admin.register(PrioridadSemana)
class PrioridadSemanaAdmin(admin.ModelAdmin):
    list_display = ('semana_inicio', 'negocio', 'orden', 'texto', 'hecha')
    list_filter = ('negocio', 'hecha', 'semana_inicio')
    list_editable = ('hecha',)   # marcar una como lista, desde el teléfono
    search_fields = ('texto',)
    ordering = ('-semana_inicio', 'negocio', 'orden')


@admin.register(NotaNegocio)
class NotaNegocioAdmin(admin.ModelAdmin):
    list_display = ('negocio', 'texto', 'actualizada')
    list_filter = ('negocio',)


@admin.register(NotaDelDia)
class NotaDelDiaAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'negocio', 'texto', 'hecha')
    list_filter = ('fecha', 'negocio', 'hecha')
    search_fields = ('texto',)


@admin.register(MarcaPublicacion)
class MarcaPublicacionAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'publicacion_id', 'titulo', 'marcada_en')
    list_filter = ('fecha',)


@admin.register(CorteAds)
class CorteAdsAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'meta', 'google', 'dias_ventana', 'calculado_en')
    readonly_fields = ('calculado_en',)
