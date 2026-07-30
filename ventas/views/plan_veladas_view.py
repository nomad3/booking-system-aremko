"""Tablero OCULTO de estado del plan "Veladas & Celebraciones" (V-xx).

Página no listada en ningún menú, con slug no adivinable (ver la ruta en
aremko_project/urls.py) y sin login, para abrirla desde el celular. Muestra lo YA
construido + el backlog V-xx con su estado.

Cómo actualizar: cambiar el campo `estado` del ítem correspondiente (y opcional
`nota`/`commit`) acá y desplegar. Fuente narrativa: docs/PLAN_VELADAS.md.
"""
from django.shortcuts import render

# Bump manual cada vez que actualizamos el tablero.
ACTUALIZADO = '2026-07-30'

# estado ∈ {'hecho', 'progreso', 'pendiente'}
FUNDACION = [
    {'code': 'F1',   'titulo': 'Configurador + checkout', 'estado': 'hecho',
     'nota': '2 puertas, 1 motor: /experiencia-romantica/ (pareja) y /celebraciones/ (cumpleaños y despedidas)'},
    {'code': 'F1',   'titulo': 'Invitación sorpresa', 'estado': 'hecho',
     'nota': 'Link para la pareja, sin precios ni ambientación'},
    {'code': 'F1',   'titulo': 'Taxonomía románticas vs cumpleaños', 'estado': 'hecho',
     'nota': 'R1/R2 (flores) · color azul/rosado + con/sin torta · siempre para 2'},
    {'code': 'F2-B', 'titulo': 'Bebida incluida por defecto', 'estado': 'hecho',
     'nota': '$0, se descuenta del inventario el día de la visita'},
    {'code': 'Choc', 'titulo': 'Chocolates: inventario + precio + guard', 'estado': 'hecho',
     'nota': 'Producto real $16.000; se oculta solo si no hay stock'},
    {'code': 'F2-C', 'titulo': '"Personaliza tu velada"', 'estado': 'hecho',
     'nota': 'El cliente elige su bebida (jugos/vino/espumante/agua) desde la ficha'},
]

TRACKS = [
    {'titulo': 'A · Motor de venta (todo el año)', 'items': [
        {'code': 'V-01', 'titulo': 'Always-on: Meta frío + Mail tibio', 'estado': 'progreso',
         'nota': 'Contenido listo (campaña Meta Sabri + cuerpo de mail a la base); por lanzar'},
        {'code': 'V-02', 'titulo': 'Always-on Google (captura)', 'estado': 'pendiente',
         'nota': 'Keywords de intención + RSA'},
        {'code': 'V-03', 'titulo': 'Referido de la invitación', 'estado': 'pendiente',
         'nota': 'EN DEFINICIÓN — Jorge lo está pensando (código manual vs cupón real)'},
        {'code': 'V-04', 'titulo': 'GiftCard "Regala una velada"', 'estado': 'hecho',
         'nota': 'LIVE: card → elegidor (4 niveles × hidromasaje) → wizard con precio correcto. 8 niveles en prod'},
        {'code': 'V-05', 'titulo': 'Calendario de bengalas (12 meses)', 'estado': 'pendiente',
         'nota': 'San Valentín, Madre, Padre, Fiestas Patrias, fin de año'},
        {'code': 'V-06', 'titulo': 'Reels B-roll (montaje + reveal)', 'estado': 'pendiente',
         'nota': 'Orgánico que alimenta lo pagado'},
        {'code': 'V-07', 'titulo': 'Cadencia post-visita anclada a la fecha', 'estado': 'pendiente',
         'nota': 'Reseña + recordatorio del próximo aniversario'},
        {'code': 'V-08', 'titulo': 'Retargeting de abandonos', 'estado': 'pendiente',
         'nota': 'Re-impactar a quien no compra (Pixel ya instalado)'},
    ]},
    {'titulo': 'B · Nuevas ocasiones de pareja', 'items': [
        {'code': 'V-09', 'titulo': '"La Propuesta" (pedida de matrimonio)', 'estado': 'pendiente',
         'nota': 'La sorpresa máxima; ticket alto'},
        {'code': 'V-10', 'titulo': 'Babymoon', 'estado': 'pendiente',
         'nota': 'Última escapada antes del bebé'},
        {'code': 'V-11', 'titulo': '"Solo porque sí" / Autocuidado', 'estado': 'pendiente',
         'nota': 'Self-gift, evergreen, sin ocasión'},
        {'code': 'V-12', 'titulo': '"Volver a empezar" (reconciliación)', 'estado': 'pendiente',
         'nota': 'Ángulo de campaña sobre el mismo producto'},
    ]},
    {'titulo': 'C · Tinas grupales (celebraciones de grupo)', 'items': [
        {'code': 'V-13', 'titulo': 'Modo grupo en el configurador', 'estado': 'hecho',
         'nota': 'LIVE: 3ª ocasión Grupo (Calbuco 3-4, Osorno 3-5, $25.000/pers, cobra × N). Falta subir Osorno a capacidad 6 en admin'},
        {'code': 'V-14', 'titulo': 'Despedida de soltera / soltero', 'estado': 'hecho',
         'nota': 'LIVE: ocasión propia en el configurador (reusa modo grupo). Ambientación temática propia (B) = mejora futura'},
        {'code': 'V-15', 'titulo': 'Cumpleaños grupal (números redondos)', 'estado': 'pendiente',
         'nota': 'Foco 30/40/50'},
        {'code': 'V-16', 'titulo': 'Escapada de amigas / Reencuentro', 'estado': 'pendiente',
         'nota': "Girls' trip / galentine's (wellness grupal femenino)"},
        {'code': 'V-17', 'titulo': 'Revelación de sexo (gender reveal)', 'estado': 'pendiente',
         'nota': 'Quick win: reusa el color azul/rosado ya construido'},
        {'code': 'V-18', 'titulo': 'Celebración de logro', 'estado': 'pendiente',
         'nota': 'Jubilación, graduación, ascenso'},
    ]},
    {'titulo': 'D · Segmento empresas (B2B)', 'items': [
        {'code': 'V-19', 'titulo': 'GiftCards corporativas en volumen', 'estado': 'pendiente',
         'nota': 'Regalo de fin de año a clientes/empleados. Prioridad alta'},
        {'code': 'V-20', 'titulo': 'Incentivos y premios a empleados', 'estado': 'pendiente',
         'nota': 'Venta recurrente, ticket predecible'},
        {'code': 'V-21', 'titulo': 'Team building / cierre de proyecto', 'estado': 'pendiente',
         'nota': 'Usa el modo grupo (V-13)'},
        {'code': 'V-22', 'titulo': 'Convenio empresas', 'estado': 'pendiente',
         'nota': 'Tarifa preferente + acceso; ingreso recurrente'},
        {'code': 'V-23', 'titulo': 'Wellness corporativo', 'estado': 'pendiente',
         'nota': 'Paquetes trimestrales de bienestar'},
    ]},
]

_ORDEN = ['V-01', 'V-04', 'V-03', 'V-13', 'V-14', 'V-19']


def guia_equipo_veladas(request):
    """Guía interna para el equipo (Deborah + Angélica): qué es la Experiencia
    Romántica / Veladas, desde el cliente y desde la venta. Oculta, noindex."""
    return render(request, 'ventas/guia_equipo_veladas.html', {})


def _render_tablero(request, actualizado, fundacion, tracks, orden, titulo, h1, id_label, doc):
    """Renderiza el tablero genérico (mismo template) para cualquier plan."""
    total = sum(len(t['items']) for t in tracks)
    hechos = sum(1 for t in tracks for i in t['items'] if i['estado'] == 'hecho')
    progreso = sum(1 for t in tracks for i in t['items'] if i['estado'] == 'progreso')
    pct = round(100 * hechos / total) if total else 0
    return render(request, 'ventas/plan_veladas_estado.html', {
        'actualizado': actualizado, 'fundacion': fundacion, 'tracks': tracks,
        'total': total, 'hechos': hechos, 'progreso': progreso,
        'pendientes': total - hechos - progreso, 'pct': pct, 'orden': orden,
        'plan_titulo': titulo, 'plan_h1': h1, 'plan_id_label': id_label, 'plan_doc': doc,
    })


def plan_veladas_estado(request):
    return _render_tablero(request, ACTUALIZADO, FUNDACION, TRACKS, _ORDEN,
                           'Plan Veladas', '🥂 Plan Veladas & Celebraciones', 'V-xx', 'PLAN_VELADAS.md')


# =========================== Tablero Ficha (F-xx) ===========================
ACTUALIZADO_FICHA = '2026-07-24'

FUNDACION_FICHA = [
    {'code': '—', 'titulo': 'Ver la reserva + estado de pago', 'estado': 'hecho',
     'nota': 'Servicios contratados, total y saldo'},
    {'code': '—', 'titulo': 'Tips de la visita', 'estado': 'hecho', 'nota': 'Qué llevar, cómo llegar'},
    {'code': '—', 'titulo': 'Comanda digital', 'estado': 'hecho', 'nota': 'Pedir bebidas / comida'},
    {'code': '—', 'titulo': 'Pagar saldo online', 'estado': 'hecho', 'nota': 'Mercado Pago, hasta 12 cuotas'},
    {'code': 'F2-C', 'titulo': 'Personalizar la bebida', 'estado': 'hecho', 'nota': 'Elige jugos/vino/espumante/agua'},
    {'code': '—', 'titulo': 'Invitación sorpresa', 'estado': 'hecho', 'nota': 'Link para la pareja (si hay ambientación)'},
]

TRACKS_FICHA = [
    {'titulo': 'Fase 1 · ABRIR (que la abran y entiendan)', 'items': [
        {'code': 'F-01', 'titulo': 'Medir aperturas + "✓ abrió" en la bandeja', 'estado': 'progreso',
         'nota': 'Paso 0: saber si el cuello es abrir o activar'},
        {'code': 'F-02', 'titulo': 'Reencuadrar el mensaje → "Tu Aremko"', 'estado': 'pendiente',
         'nota': 'De comprobante a panel de la experiencia'},
        {'code': 'F-03', 'titulo': 'Onboarding al abrir', 'estado': 'pendiente',
         'nota': '"¿Qué puedes hacer acá?" de 3 íconos'},
    ]},
    {'titulo': 'Fase 2 · VENDER (upsell)', 'items': [
        {'code': 'F-04', 'titulo': 'Sección de upsell contextual', 'estado': 'pendiente',
         'nota': 'tina→masaje · masaje→noche · 1→2 noches'},
        {'code': 'F-05', 'titulo': 'Sumar a un toque', 'estado': 'pendiente',
         'nota': 'Paga la diferencia online (reusa checkout/MP)'},
        {'code': 'F-06', 'titulo': 'Medir conversión del upsell', 'estado': 'pendiente',
         'nota': 'El KPI que prueba que la ficha cobra'},
    ]},
    {'titulo': 'Fase 3 · VOLVER (razones para reabrir)', 'items': [
        {'code': 'F-07', 'titulo': 'Nudges por WhatsApp/Luna (3 momentos)', 'estado': 'pendiente',
         'nota': 'Reservar / días antes / el día'},
        {'code': 'F-08', 'titulo': 'Puente físico (QR)', 'estado': 'pendiente',
         'nota': 'QR en recepción/cabaña → abre la ficha'},
    ]},
    {'titulo': 'Fase 4 · APP (que se sienta app)', 'items': [
        {'code': 'F-09', 'titulo': 'Guardar en pantalla (PWA)', 'estado': 'pendiente',
         'nota': 'Ícono persistente, no un link perdido'},
        {'code': 'F-10', 'titulo': 'Recordatorios / avisos', 'estado': 'pendiente',
         'nota': 'Reseña post-visita, próximo aniversario'},
    ]},
]

_ORDEN_FICHA = ['F-01', 'F-02', 'F-04', 'F-05', 'F-07']


def plan_ficha_estado(request):
    return _render_tablero(request, ACTUALIZADO_FICHA, FUNDACION_FICHA, TRACKS_FICHA, _ORDEN_FICHA,
                           'Plan Ficha', '📱 La Ficha como app + upsell', 'F-xx', 'PLAN_FICHA.md')
