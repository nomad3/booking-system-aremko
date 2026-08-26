# -*- coding: utf-8 -*-
"""El panel del día: lo que el correo de las 8:00 no puede ser.

El correo es una foto del amanecer. El día se vive entre las 8 y las 20, y en
ese rato entran reservas, alguien escribe, aparece un pendiente que nadie
previó. Esto es la mesa de trabajo: se mira, se marca y se agrega.

Separación de velocidades: lo que sale de la base (ventas, conversaciones,
pendientes, caja) es instantáneo y se refresca solo. Lo que sale de Meta y
Google demora segundos, así que viaja congelado desde el corte de la mañana y
SIEMPRE se muestra con su hora — un número de publicidad sin hora se lee como
si fuera de este minuto.
"""
from datetime import date

from django.contrib.auth.decorators import user_passes_test
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_POST

from . import fuentes, resumen
from .models import CorteAds, MarcaPublicacion, NotaDelDia, PrioridadSemana

GRUPO_COLABORADOR = 'Finanzas colaborador'


def puede_ver_sala(u):
    """Mismo criterio que finanzas: el panel muestra caja y ventas."""
    return u.is_superuser or u.groups.filter(name=GRUPO_COLABORADOR).exists()


def guardar_corte_ads(ads, hoy=None):
    """Congela el gasto de publicidad del día. Lo llama el comando de la
    mañana; el panel solo lee.

    Un fallo de red deja `None`, que NO es cero: el panel dirá «no se pudo
    leer» en vez de mostrar un cero que se leería como «no gastamos nada».
    """
    hoy = hoy or date.today()
    corte, _ = CorteAds.objects.update_or_create(
        fecha=hoy,
        defaults={'meta': ads.get('meta'), 'google': ads.get('google'),
                  'dias_ventana': ads.get('dias') or 0},
    )
    return corte


def _pendientes_del_dia(hoy):
    """Las publicaciones de hoy con su estado combinado.

    Resuelta = el Telar dice «publicada» O el dueño la marcó acá. Son dos
    preguntas distintas («¿se publicó?» / «¿ya me hice cargo?») y por eso no
    compiten: cualquiera de las dos despeja la fila.
    """
    telar = fuentes.plan_del_dia(fecha=hoy)
    if telar is None:
        return None, None
    marcadas = set(MarcaPublicacion.objects
                   .filter(fecha=hoy).values_list('publicacion_id', flat=True))
    filas = []
    for p in telar.get('publicaciones') or []:
        por_telar = p.get('estado') == 'publicada'
        marcada = p.get('id') in marcadas
        filas.append({**p,
                      'resuelta': por_telar or marcada,
                      'por_telar': por_telar,
                      'marcada_por_mi': marcada})
    return filas, telar.get('semana')


@user_passes_test(puede_ver_sala)
def sala(request):
    hoy = date.today()
    lunes = fuentes.lunes_de(hoy)

    publicaciones, semana = _pendientes_del_dia(hoy)
    caja = fuentes.caja(hoy)
    gasto = fuentes.gasto_diario(hasta=hoy)

    caja_total = caja['total'] if caja else None
    colchon = None
    if caja_total is not None and gasto and gasto['promedio_diario']:
        from finanzas.services import colchon_dias
        colchon = colchon_dias(caja_total, gasto['promedio_diario'])

    return render(request, 'sala_control/sala.html', {
        'hoy': hoy,
        'ventas': fuentes.ventas_del_dia(hoy),
        'cotizaciones': fuentes.cotizaciones_del_dia(hoy),
        'conversaciones': fuentes.conversaciones_esperando(hoy=hoy),
        'publicaciones': publicaciones,
        'semana_telar': semana,
        'prioridades': PrioridadSemana.objects.filter(semana_inicio=lunes),
        'notas': NotaDelDia.objects.filter(fecha=hoy),
        'caja': caja,
        'caja_total': caja_total,
        'colchon': colchon,
        'umbral_caja': resumen._umbral_caja(),
        'corte_ads': CorteAds.objects.filter(fecha__lte=hoy).first(),
    })


def _volver():
    return HttpResponseRedirect(reverse('sala_control:sala'))


@require_POST
@user_passes_test(puede_ver_sala)
def marcar_publicacion(request):
    """Marcar o desmarcar una pieza. Desmarcar importa: equivocarse y no poder
    deshacer es lo que hace que la gente deje de marcar."""
    try:
        pid = int(request.POST.get('publicacion_id') or 0)
    except (TypeError, ValueError):
        return _volver()
    if not pid:
        return _volver()

    hoy = date.today()
    existente = MarcaPublicacion.objects.filter(fecha=hoy, publicacion_id=pid)
    if existente.exists():
        existente.delete()
    else:
        MarcaPublicacion.objects.create(
            fecha=hoy, publicacion_id=pid,
            titulo=(request.POST.get('titulo') or '')[:200])
    return _volver()


@require_POST
@user_passes_test(puede_ver_sala)
def agregar_nota(request):
    texto = (request.POST.get('texto') or '').strip()
    if texto:
        NotaDelDia.objects.create(
            fecha=date.today(), texto=texto[:300],
            link=(request.POST.get('link') or '').strip()[:200],
            negocio=request.POST.get('negocio') or 'aremko')
    return _volver()


@require_POST
@user_passes_test(puede_ver_sala)
def alternar_nota(request):
    nota = NotaDelDia.objects.filter(id=request.POST.get('nota_id')).first()
    if nota:
        nota.hecha = not nota.hecha
        nota.save(update_fields=['hecha'])
    return _volver()


@require_POST
@user_passes_test(puede_ver_sala)
def alternar_prioridad(request):
    p = PrioridadSemana.objects.filter(id=request.POST.get('prioridad_id')).first()
    if p:
        p.hecha = not p.hecha
        p.save(update_fields=['hecha'])
    return _volver()


@require_POST
@user_passes_test(puede_ver_sala)
def refrescar_ads(request):
    """Ir a buscar el gasto de publicidad ahora, a pedido.

    A mano y no automático: son varias llamadas de red que demoran segundos, y
    un panel que se refresca solo las pediría decenas de veces al día.
    """
    guardar_corte_ads(fuentes.publicidad(fuentes.dias_transcurridos_del_mes()))
    return _volver()
