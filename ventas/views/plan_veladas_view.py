"""Tablero OCULTO de estado del plan "Veladas & Celebraciones" (V-xx).

Página no listada en ningún menú, con slug no adivinable (ver la ruta en
aremko_project/urls.py) y sin login, para abrirla desde el celular. Muestra lo YA
construido + el backlog V-xx con su estado.

Cómo actualizar: cambiar el campo `estado` del ítem correspondiente (y opcional
`nota`/`commit`) acá y desplegar. Fuente narrativa: docs/PLAN_VELADAS.md.
"""
from django.shortcuts import render

# Bump manual cada vez que actualizamos el tablero.
ACTUALIZADO = '2026-07-24'

# estado ∈ {'hecho', 'progreso', 'pendiente'}
FUNDACION = [
    {'code': 'F1',   'titulo': 'Configurador + checkout', 'estado': 'hecho',
     'nota': '/experiencia-romantica/ — la persona arma la velada de a dos'},
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
        {'code': 'V-01', 'titulo': 'Always-on Meta (evergreen)', 'estado': 'pendiente',
         'nota': 'Campaña permanente aniversario/sorpresa a la geo sur'},
        {'code': 'V-02', 'titulo': 'Always-on Google (captura)', 'estado': 'pendiente',
         'nota': 'Keywords de intención + RSA'},
        {'code': 'V-03', 'titulo': 'Referido de la invitación', 'estado': 'pendiente',
         'nota': 'Código para quien recibe la invitación → loop viral'},
        {'code': 'V-04', 'titulo': 'GiftCard "Regala una velada"', 'estado': 'pendiente',
         'nota': 'Voucher con validez larga; resuelve el "no sé la fecha". Prioridad alta'},
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
        {'code': 'V-13', 'titulo': 'Modo grupo en el configurador', 'estado': 'pendiente',
         'nota': 'Fundación del track. Resuelve la pregunta de Deborah'},
        {'code': 'V-14', 'titulo': 'Despedida de soltera / soltero', 'estado': 'pendiente',
         'nota': 'La apuesta más fuerte del track'},
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


def plan_veladas_estado(request):
    total = sum(len(t['items']) for t in TRACKS)
    hechos = sum(1 for t in TRACKS for i in t['items'] if i['estado'] == 'hecho')
    progreso = sum(1 for t in TRACKS for i in t['items'] if i['estado'] == 'progreso')
    pct = round(100 * hechos / total) if total else 0
    context = {
        'actualizado': ACTUALIZADO,
        'fundacion': FUNDACION,
        'tracks': TRACKS,
        'total': total, 'hechos': hechos, 'progreso': progreso,
        'pendientes': total - hechos - progreso,
        'pct': pct,
        'orden': _ORDEN,
    }
    return render(request, 'ventas/plan_veladas_estado.html', context)
