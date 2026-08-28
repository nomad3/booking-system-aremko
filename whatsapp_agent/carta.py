# -*- coding: utf-8 -*-
"""Carta de precios para aperturas genéricas (P-34).

Tesis de Jorge (2026-08-20), respaldada por el estudio de primeras respuestas:
quien abre con «¿precios?» o «¿qué servicios tienen?» vino a mirar la vitrina —
si se le contesta con preguntas de calificación («¿para cuántas personas?»), se
apaga. La carta muestra la escalera completa de menor a mayor, desde el masaje
hasta el Refugio, y las preguntas llegan DESPUÉS, cuando el cliente elige.

Por qué el texto se arma EN CÓDIGO y no lo redacta el LLM:
1. Los precios de servicios salen del catálogo vivo (BD) — cambiar un precio en
   el admin cambia la carta sola, sin deploy y sin prompts con montos viejos.
2. «Tina para 2» exige multiplicar precio_base × 2, y la aritmética de precios
   está PROHIBIDA para Luna (regla dura del prompt): acá la hace Python.
3. El estudio mostró que el formato tarjeta (líneas con ✓) convirtió donde el
   párrafo murió — un texto fijo garantiza ese formato siempre.

Los «desde» de las experiencias vienen de las constantes canónicas de packs.py
cuando existen (Ritual/Refugio). Pausa y Noche de Aguas Calientes no tienen
constante propia — sus «desde» viven acá y DEBEN calzar con los montos vigentes
de las reglas del prompt (sección menú) y las ofertas dom-jue.
"""
from .grounding import formatear_precio

# «Desde» de las experiencias sin constante canónica en packs.py. Si cambian
# las ofertas, actualizar ACÁ y en las reglas del menú del prompt (grep por el
# monto). Pausa: tina simple + masaje para 2, dom-jue. Noche: cabaña + tina.
PAUSA_DESDE = 110000
NOCHE_AGUAS_DESDE = 160000


def construir_carta(masaje=None, tina_simple=None, tina_hidro=None, cabana=None):
    """Texto de la carta, ordenado de menor a mayor precio. Función pura.

    Recibe los «desde» de los servicios sueltos ya calculados (int o None si
    esa categoría no tiene servicios publicados hoy — la línea se omite).
    """
    from .packs import DIA_PRECIO_PLANO, REFUGIO_PRECIO_PLANO, RITUAL_PRECIO_DOMJUE

    # (etiqueta, precio, lleva_desde) — «desde» cuando hay variantes por tina/
    # cabaña o por día de semana; el Refugio es plano y el masaje es un precio único.
    items = []
    if masaje:
        items.append(('Masaje de relajación o descontracturante (por persona)',
                      masaje, False))
    if tina_simple:
        items.append(('Tina caliente junto al río (2 horas, para 2)',
                      tina_simple, True))
    if tina_hidro:
        items.append(('Tina con hidromasaje (2 horas, para 2)',
                      tina_hidro, True))
    if cabana:
        items.append(('Cabaña boutique (noche para 2, desayuno incluido)',
                      cabana, True))
    items.append(('Pausa junto al río: tina + masaje, para 2',
                  PAUSA_DESDE, True))
    items.append(('Noche de Aguas Calientes: cabaña + tina, para 2',
                  NOCHE_AGUAS_DESDE, True))
    # «por el día» va antes del Ritual por precio, y la etiqueta tiene que
    # decir las dos cosas: que la cabaña es suya durante el día (es lo que lo
    # diferencia de la Pausa, que también es sin dormir) y que no se pernocta.
    items.append(('Cabaña y spa por el día: cabaña, tina, masaje y desayuno, '
                  'para 2 (lun/mié/jue, sin pernoctar)',
                  DIA_PRECIO_PLANO, False))
    items.append(('Ritual del Río: cabaña + tina + masaje + desayuno, para 2',
                  RITUAL_PRECIO_DOMJUE, True))
    items.append(('Refugio Aremko: 2 noches en cabaña con tina y masaje, para 2',
                  REFUGIO_PRECIO_PLANO, False))
    items.sort(key=lambda it: it[1])

    lineas = ['Estos son nuestros servicios y experiencias 🌿']
    for etiqueta, precio, lleva_desde in items:
        prefijo = 'desde ' if lleva_desde else ''
        lineas.append(f'✓ {etiqueta} — {prefijo}{formatear_precio(precio)}')
    lineas.append('')
    lineas.append('¿Cuál te gustaría ver con fecha y hora?')
    return '\n'.join(lineas)


def carta_de_precios():
    """Lee el catálogo vivo y arma la carta. Mismos filtros que catalogo_vivo():
    publicados, activos, sin complementos. Nunca lanza: ante cualquier problema
    devuelve '' y el prompt simplemente no incluye la carta ese turno."""
    try:
        from django.db.models import Min

        from ventas.models import Servicio

        from .models import WhatsAppAgentConfig

        comp_ids = WhatsAppAgentConfig.get_solo().ids_complementarios()
        qs = (Servicio.objects
              .filter(publicado_web=True, activo=True)
              .exclude(id__in=comp_ids))

        masaje = qs.filter(tipo_servicio='masaje').aggregate(
            m=Min('precio_base'))['m']

        tinas = list(qs.filter(tipo_servicio='tina')
                     .values_list('nombre', 'precio_base'))
        simples = [int(p) for n, p in tinas
                   if p and 'hidromasaje' not in (n or '').lower()]
        hidros = [int(p) for n, p in tinas
                  if p and 'hidromasaje' in (n or '').lower()]

        # Cabañas: precio TOTAL por noche = precio_base × capacidad (mismo
        # criterio que el catálogo del prompt — mostrar por persona fue un bug real).
        cabanas = [int(p) * int(c or 2) for p, c in
                   qs.filter(tipo_servicio='cabana')
                   .values_list('precio_base', 'capacidad_maxima') if p]

        return construir_carta(
            masaje=int(masaje) if masaje else None,
            tina_simple=min(simples) * 2 if simples else None,
            tina_hidro=min(hidros) * 2 if hidros else None,
            cabana=min(cabanas) if cabanas else None,
        )
    except Exception:  # noqa: BLE001 — la carta nunca rompe el prompt
        import logging
        logging.getLogger(__name__).exception('Carta de precios: error armándola')
        return ''
