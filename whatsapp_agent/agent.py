"""Orquestador del agente IA de WhatsApp — Fase 1 (borrador asistido).

`generar_sugerencia(phone)` produce (o recupera de cache) el borrador para el
último entrante sin responder de una conversación. NO envía nada: solo deja la
sugerencia para que el humano (Deborah) la edite y mande desde aremko-cli.

Diseño F1:
- Generación LAZY (se llama al abrir la conversación), no en el webhook inbound:
  cero latencia en el hot-path de Meta y solo se gasta LLM en chats que se abren.
- Solo entrantes de texto sin atender. Reacciones/adjuntos no generan borrador.
- Pausa por conversación: si un humano respondió en las últimas N horas, el
  agente se calla (no sugiere) en ese chat.
- Sin escrituras al negocio: el agente solo lee catálogo y escribe su propia
  tabla de sugerencias.
"""

import logging
import re
import unicodedata

from django.utils import timezone

from . import escalation, grounding, prompt as prompt_mod, rollback
from .models import SugerenciaAgenteWhatsApp, WhatsAppAgentConfig

logger = logging.getLogger(__name__)


_DIAS_ES = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']


def _obtener_datos_cliente_por_phone(phone):
    """H-028 FIX: Obtiene datos del cliente existente por teléfono normalizado.

    Si el cliente existe, devuelve {nombre, email, documento_identidad, comuna_nombre}.
    Si faltan campos, devuelve None para esos campos (Luna los pide luego).
    Si el cliente NO existe, devuelve None.
    """
    try:
        from ventas.models import Cliente
        cliente = Cliente.objects.filter(telefono=phone).first()
        if not cliente:
            return None

        comuna_nombre = None
        if cliente.comuna:
            comuna_nombre = cliente.comuna.nombre
            logger.info(f'[Cliente {phone}] comuna_id={cliente.comuna_id}, nombre="{comuna_nombre}"')
        else:
            logger.warning(f'[Cliente {phone}] Sin comuna asignada (comuna_id={cliente.comuna_id})')

        return {
            'id': cliente.id,
            # Gate H-067: un nombre basura (pushname con emojis/símbolos) no se
            # expone al modelo — se trata como "sin nombre".
            'nombre': prompt_mod.nombre_presentable(cliente.nombre or '') or None,
            'email': cliente.email if cliente.email else None,
            'documento_identidad': cliente.documento_identidad if cliente.documento_identidad else None,
            'comuna_id': cliente.comuna_id if cliente.comuna_id else None,
            'comuna_nombre': comuna_nombre,
        }
    except Exception as e:
        logger.warning(f'Error obteniendo datos de cliente {phone}: {e}')
        return None

# Herramienta de disponibilidad para el agente (H-011 Fase A paso 2).
_TOOLS = [{
    'type': 'function',
    'function': {
        'name': 'consultar_disponibilidad',
        'description': (
            'Consulta servicios (tinas/masajes/cabañas) con su PRECIO TOTAL ya calculado y, si das '
            'fecha, sus HORARIOS libres. Úsala para responder PRECIO ("¿cuánto vale una tina?") y '
            'para disponibilidad de CABAÑAS — NO calcules precios tú. '
            '⚠️ EXCEPCIÓN (H-081/H-088): para ofrecer HORARIOS de una TINA o un MASAJE en una fecha '
            'concreta usa `alternativas_experiencia`, que devuelve UNA recomendación en vez de una '
            'lista. Si igual llamas aquí con `fecha` + `tipo` tina/masaje, esta herramienta te '
            'devolverá esa MISMA recomendación única (`recomendada` + `otras_alternativas`), no el '
            'listado: ofrece solo la recomendada, sin viñetas. '
            '⚠️ `personas` es OBLIGATORIO y debe ser la cantidad EXACTA que el '
            'cliente te dijo: si NO sabes cuántas personas son, NO llames esta herramienta — primero '
            'PREGÚNTALE al cliente cuántas personas. NUNCA asumas 1. La cantidad filtra los servicios '
            '(las cabañas y las tinas admiten máx 2 personas; con 3+ esos servicios NO aplican y la '
            'herramienta no los devuelve). Para una pregunta de solo precio ("¿cuánto vale para 2?"), '
            'llama con `personas` y SIN `fecha`. Para disponibilidad ("¿hay el sábado?"), incluye `fecha` '
            '(ACEPTA "el sábado", "25 de junio" O formato YYYY-MM-DD; la herramienta resuelve '
            'internamente). Devuelve por servicio: `precio_total` (úsalo tal cual), `precio_por_persona`, '
            '`duracion_texto` (ej. "4 h" o "por noche"), `dia_semana` (devuelto por la herramienta) '
            'y `slots_libres`. USA SIEMPRE el `dia_semana` devuelto, NUNCA calcules tú.'
        ),
        'parameters': {
            'type': 'object',
            'properties': {
                'personas': {'type': 'integer',
                             'description': 'Cantidad EXACTA de personas que dijo el cliente. NO la inventes '
                                            'ni asumas 1: si no la sabes, pregunta antes de llamar.'},
                'fecha': {'type': 'string', 'description': 'Pasá el TEXTO LITERAL del cliente tal cual ("próximo domingo", "el sábado", "25 de junio"). NO lo conviertas a YYYY-MM-DD ni calcules el día tú; la herramienta lo resuelve. Omitir si es solo precio.'},
                'tipo': {'type': 'string', 'enum': ['tina', 'masaje', 'cabana'],
                         'description': 'Tipo de servicio (opcional; omitir para todos)'},
            },
            'required': ['personas'],
        },
    },
}, {
    'type': 'function',
    'function': {
        'name': 'consultar_disponibilidad_combo',
        'description': (
            'ENRUTADOR — úsala SIEMPRE que el cliente quiera reservar o ver disponibilidad de '
            'UNO O VARIOS servicios. Junta en `servicios` TODO lo que mencionó (alojamiento/cabaña, '
            'tina, masaje) y el sistema elige solo el paquete correcto y arma el itinerario COMPLETO. '
            'Si pide alojamiento + tina + masaje = es el Ritual del Río (aunque no lo nombre): se '
            'devuelve como 1 unidad a $240.000. NUNCA ofrezcas servicio por servicio ni omitas uno '
            'que el cliente pidió; tú solo listas lo que pidió, el código arma la rama. El campo '
            '`rama` te dice qué se armó. Para el Ritual (rama="ritual") preséntalo como 1 paquete.'
        ),
        'parameters': {
            'type': 'object',
            'properties': {
                'servicios': {'type': 'array', 'items': {'type': 'string'},
                              'description': 'Lo que mencionó el cliente: "alojamiento"/"cabaña", "tina", "masaje" (en cualquier orden, los que dijo).'},
                'fecha': {'type': 'string', 'description': 'PASÁ EL TEXTO LITERAL del cliente ("este sabado", "próximo lunes", "25 de junio"); NO calcules el día ni lo conviertas a YYYY-MM-DD, la herramienta lo resuelve.'},
                'personas': {'type': 'integer', 'description': 'Cantidad EXACTA de personas que dijo el cliente. NO asumas 1; si no la sabes, pregunta antes.'},
            },
            'required': ['servicios', 'fecha', 'personas'],
        },
    },
}, {
    'type': 'function',
    'function': {
        'name': 'consultar_disponibilidad_pack',
        'description': (
            'Propone itinerarios de TINA + MASAJE el mismo día (pack). Úsala cuando el '
            'cliente quiere tina Y masaje juntos. Devuelve `opciones` (hasta 2: una "con '
            'hidromasaje" de mayor valor y otra "sin hidromasaje" más económica), cada una con '
            'la tina y el masaje YA compuestos (sin solaparse; el masaje queda cerca de los '
            'masajes ya reservados ese día) y con precio real y precio con descuento de pack '
            '(`hay_descuento`/`precio_con_descuento`). Ofrece las opciones tal cual. Requiere '
            'fecha y personas. '
            'Si el cliente YA recibió opciones para esa fecha y pregunta "¿más tarde?" / "¿algo '
            'después?" / "¿no hay otro horario?", vuelve a llamar esta misma tool con '
            'mas_tarde=true en vez de repetir la respuesta anterior o decir que no hay más — '
            'trae la alternativa MÁS TARDE siguiente si existe (nunca inventes ni asumas que no '
            'hay; deja que la tool te lo confirme).'
        ),
        'parameters': {
            'type': 'object',
            'properties': {
                'fecha': {'type': 'string', 'description': 'PASÁ EL TEXTO LITERAL del cliente ("próximo lunes", "el sábado", "25 de junio"); NO calcules el día ni lo conviertas a YYYY-MM-DD, la herramienta lo resuelve.'},
                'personas': {'type': 'integer', 'description': 'Cantidad de personas'},
                'mas_tarde': {'type': 'boolean', 'description': 'true SOLO si el cliente ya vio opciones para esta fecha y pidió algo más tarde. Trae la siguiente alternativa cronológica (no la primera). Default false.'},
            },
            'required': ['fecha', 'personas'],
        },
    },
}, {
    'type': 'function',
    'function': {
        'name': 'consultar_disponibilidad_pack_cabana',
        'description': (
            'Propone itinerarios de CABAÑA + TINA (1 noche, alojamiento). Úsala cuando el '
            'cliente quiere cabaña, o cabaña con tina. Las cabañas son SIEMPRE para 2 personas. '
            'Devuelve `opciones` = cabañas libres esa noche, cada una con check-in 16:00 / '
            'check-out 11:00 del día siguiente y una `tina` en el horario MÁS TARDE disponible '
            '(nunca antes de 16:00), con `precio_total` y `precio_con_descuento` (pack dom-jue). '
            'El `desayuno` ($20.000 para dos, día siguiente ~10:00) va INCLUIDO en el `precio_total`: '
            'menciónalo como parte del paquete ("incluye desayuno para dos"), NO como un extra opcional. '
            'Si `tina` es null, ofrece solo la cabaña (también con desayuno incluido). '
            'Requiere fecha (la noche de check-in).'
        ),
        'parameters': {
            'type': 'object',
            'properties': {
                'fecha': {'type': 'string', 'description': 'La noche (check-in). PASÁ EL TEXTO LITERAL del cliente ("próximo lunes", "el sábado", "25 de junio"); NO calcules el día ni lo conviertas a YYYY-MM-DD, la herramienta lo resuelve.'},
            },
            'required': ['fecha'],
        },
    },
}, {
    'type': 'function',
    'function': {
        'name': 'consultar_disponibilidad_alojamiento_multinoche',
        'description': (
            'Consulta cabañas libres para una estadía de VARIAS NOCHES (H-027). Máx 2 personas. '
            'DESAMBIGUA PRIMERO: si el cliente dice "cabaña para el 23 y 24", confirma cuántas '
            'noches son (ej. "¿1 noche [entrada 23, salida 24] o 2 noches [entrada 23, salida 25]?"). '
            'Una vez claro, pasa `fecha_llegada` (check-in) + `noches` (entero ≥1, PREFERIDO). '
            'Alternativa si solo tienes fechas: `fecha_salida` (check-out). '
            'Ejemplo: cliente "2 noches desde el sábado 27" → fecha_llegada="sábado 27" (TEXTO LITERAL, NO lo conviertas a fecha), noches=2. '
            'Devuelve cabañas libres en TODAS las noches del rango, cada una con `total_por_noche` '
            '(tarifa plana) y `total_estadia`. Muestra solo los totales, NUNCA el precio unitario por persona.'
        ),
        'parameters': {
            'type': 'object',
            'properties': {
                'fecha_llegada': {'type': 'string', 'description': 'Check-in (REQUERIDO). PASÁ EL TEXTO LITERAL del cliente ("próximo lunes", "el sábado 27"); NO calcules el día ni lo conviertas a YYYY-MM-DD, la herramienta lo resuelve.'},
                'noches': {'type': 'integer', 'description': 'Número de noches (entero ≥1). PREFERIDO sobre fecha_salida.'},
                'personas': {'type': 'integer', 'description': 'Cantidad de personas (1-2)'},
                'fecha_salida': {'type': 'string', 'description': 'Check-out (alternativa si no tienes noches). PASÁ EL TEXTO LITERAL del cliente; NO calcules el día.'},
            },
            'required': ['fecha_llegada', 'personas'],
        },
    },
}, {
    'type': 'function',
    'function': {
        'name': 'alternativas_experiencia',
        'description': (
            'COTIZADOR OFICIAL de experiencias (H-078/H-081): pausa (tina+masaje) | tina_sola | '
            'masaje_solo | noche_aguas_calientes (cabaña+tina) | ritual | refugio. Devuelve UNA '
            'opción `recomendada` (la más conveniente, armada por código con horarios válidos y '
            'precio con descuento) + `otras_alternativas` de respaldo. Ofrece SOLO la '
            'recomendada, redactada natural — NUNCA una lista de opciones. Si el cliente pide '
            'otro horario u otra tina, ofrece UNA de las otras (la que mejor calce). NUNCA '
            'armes tú una combinación tina+masaje ni inventes un horario: si una hora no vino '
            'de esta herramienta, NO existe. `fecha` acepta el texto literal del cliente ("el '
            'próximo miércoles"); usa SIEMPRE el `dia_semana` devuelto. ⚠️ `personas` es '
            'OBLIGATORIO: si no lo sabes, pregúntalo ANTES de llamar (NUNCA asumas 1). Ritual '
            'y Refugio son siempre para 2.'
        ),
        'parameters': {
            'type': 'object',
            'properties': {
                'tipo': {'type': 'string',
                         'enum': ['pausa', 'tina_sola', 'masaje_solo',
                                  'noche_aguas_calientes', 'ritual', 'refugio'],
                         'description': 'Tipo de experiencia a cotizar.'},
                'fecha': {'type': 'string',
                          'description': 'Fecha TAL CUAL la dijo el cliente ("el sábado", '
                                         '"5 de agosto" o YYYY-MM-DD); se resuelve internamente.'},
                'personas': {'type': 'integer',
                             'description': 'Cantidad EXACTA de personas que dijo el cliente. '
                                            'NO la inventes ni asumas 1.'},
            },
            'required': ['tipo', 'fecha', 'personas'],
        },
    },
}, {
    'type': 'function',
    'function': {
        'name': 'verificar_cliente',
        'description': (
            'Verifica si un cliente existe en la BD por teléfono y qué datos le faltan (H-028). '
            'ÚSALA PRIMERO antes de preparar_reserva para saber si pedir nombre/email/RUT. '
            'En WhatsApp: usa el teléfono de la conversación (NO pidas teléfono al cliente). '
            'En Instagram/Messenger: PIDE el teléfono al cliente PRIMERO, luego llama esta tool. '
            'Devuelve: {existe, cliente_id?, nombre?, email?, documento_identidad?, region?, faltan:[...]}. '
            'Si existe y tiene todo → directo a preparar_reserva sin pedir más datos. '
            'Si falta algo → pide SOLO lo que falta. '
            'Si no existe → pide nombre + email + RUT + región.'
        ),
        'parameters': {
            'type': 'object',
            'properties': {
                'telefono': {'type': 'string', 'description': 'Teléfono del cliente (ej. +56912345678 o 912345678)'},
            },
            'required': ['telefono'],
        },
    },
}, {
    'type': 'function',
    'function': {
        'name': 'preparar_reserva',
        'description': (
            'GATE DE DEBORAH (H-028): Prepara una propuesta de reserva pendiente de aprobación '
            'de Deborah. Úsala cuando el cliente CONFIRMA que quiere reservar (dice "sí, quiero", '
            '"confirmo", "adelante"). La propuesta guarda cliente (nombre, email, RUT, región) + '
            'servicios (tina/masaje/cabaña con fecha/hora/personas). Devuelve propuesta_id que '
            'aremko-cli manda a Deborah para aprobación. SOLO cuando cliente está 100% seguro. '
            'Requiere: nombre completo (≥3 caracteres), email válido, RUT válido (formato 12345678-9).'
        ),
        'parameters': {
            'type': 'object',
            'properties': {
                'nombre': {'type': 'string', 'description': 'Nombre del cliente (≥3 caracteres)'},
                'email': {'type': 'string', 'description': 'Email válido (ej. juan@example.com)'},
                'documento_identidad': {'type': 'string', 'description': 'RUT válido (formato: 12345678-9 o 12.345.678-9)'},
                'comuna': {'type': 'string', 'description': 'Nombre de comuna (ej. "Puerto Varas", "Osorno"; H-028 FIX: región se deduce de comuna)'},
                'servicio_id': {'type': 'integer', 'description': 'ID del servicio a reservar (REQUERIDO)'},
                'fecha': {'type': 'string', 'description': 'REQUERIDO. PASÁ EL TEXTO LITERAL del cliente ("próximo lunes", "el sábado", "25 de junio"); NO calcules el día ni lo conviertas a YYYY-MM-DD, la herramienta lo resuelve.'},
                'hora': {'type': 'string', 'description': 'Hora HH:MM (REQUERIDO)'},
                'cantidad_personas': {'type': 'integer', 'description': 'Cantidad de personas (1-2 para cabañas, 1-4 para tinas)'},
            },
            'required': ['nombre', 'email', 'documento_identidad', 'servicio_id', 'fecha', 'hora', 'cantidad_personas'],
        },
    },
}, {
    'type': 'function',
    'function': {
        'name': 'agregar_servicio_carrito',
        'description': (
            'Agrega un servicio al carrito (H-029 FASE 2). Luna va acumulando servicios '
            'hasta que el cliente dice "listo, voy a reservar/pagar". '
            'El carrito calcula descuentos dinámicamente (PackDescuento). '
            'Devuelve: {success, carrito: {items_count, total, items}}. '
            'IMPORTANTE: pasá SIEMPRE `nombre_servicio` con el nombre EXACTO que el cliente '
            'nombró (ej. "Llaima", "Puntiagudo") además del `servicio_id`; el sistema usa el '
            'nombre para confirmar el servicio correcto y evitar confundir servicios parecidos.'
        ),
        'parameters': {
            'type': 'object',
            'properties': {
                'servicio_id': {'type': 'integer', 'description': 'ID del servicio (tina/masaje/cabaña)'},
                'nombre_servicio': {'type': 'string', 'description': 'Nombre EXACTO del servicio que dijo el cliente, ej. "Llaima" (para confirmar el id correcto)'},
                'fecha': {'type': 'string', 'description': 'PASÁ EL TEXTO LITERAL del cliente ("próximo lunes", "el sábado", "25 de junio"); NO calcules el día ni lo conviertas a YYYY-MM-DD, la herramienta lo resuelve.'},
                'hora': {'type': 'string', 'description': 'Hora HH:MM'},
                'cantidad_personas': {'type': 'integer', 'description': 'Cantidad de personas'},
            },
            'required': ['servicio_id', 'fecha', 'hora', 'cantidad_personas'],
        },
    },
}, {
    'type': 'function',
    'function': {
        'name': 'agregar_producto_carrito',
        'description': (
            'Agrega un producto al carrito (tablas de quesos/jamones, jugos, etc.). '
            'H-029 FASE 2. Mezcla servicios + productos en el mismo carrito. '
            'IMPORTANTE: pasá SIEMPRE `nombre_producto` con el nombre EXACTO del producto del '
            'catálogo (ej. "Tabla Mixta de Quesos y Jamones"); el sistema resuelve el id por '
            'nombre (el catálogo no trae ids).'
        ),
        'parameters': {
            'type': 'object',
            'properties': {
                'nombre_producto': {'type': 'string', 'description': 'Nombre EXACTO del producto del catálogo (ej. "Tabla Mixta de Quesos y Jamones"). REQUERIDO.'},
                'producto_id': {'type': 'integer', 'description': 'ID del producto (opcional; normalmente no lo tenés, pasá nombre_producto)'},
                'cantidad': {'type': 'integer', 'description': 'Cantidad a agregar (default 1)'},
            },
            'required': ['nombre_producto', 'cantidad'],
        },
    },
}, {
    'type': 'function',
    'function': {
        'name': 'ver_carrito',
        'description': (
            'Obtiene el resumen del carrito actual. '
            'Devuelve: items, subtotales, descuentos aplicados, total. '
            'Usa esto para confirmar con el cliente antes de checkout.'
        ),
        'parameters': {
            'type': 'object',
            'properties': {},
            'required': [],
        },
    },
}, {
    'type': 'function',
    'function': {
        'name': 'quitar_item_carrito',
        'description': (
            'Quita un item del carrito por su índice. '
            'H-029 FASE 2. Recalcula totales automáticamente.'
        ),
        'parameters': {
            'type': 'object',
            'properties': {
                'indice': {'type': 'integer', 'description': 'Índice del item a quitar (0-based)'},
            },
            'required': ['indice'],
        },
    },
}, {
    'type': 'function',
    'function': {
        'name': 'checkout_carrito',
        'description': (
            'Inicia el CHECKOUT del carrito (H-029 FASE 2). '
            'Úsala cuando el cliente dice "listo", "quiero reservar", "voy a pagar". '
            'El carrito pasa a estado "checkout". Devuelve resumen final con descuentos. '
            'DESPUÉS de esto: recolectá los datos del cliente que falten y llamá confirmar_reserva_carrito.'
        ),
        'parameters': {
            'type': 'object',
            'properties': {},
            'required': [],
        },
    },
}, {
    'type': 'function',
    'function': {
        'name': 'confirmar_reserva_carrito',
        'description': (
            'CIERRA la reserva con TODOS los items del carrito (H-029 FASE 2). '
            'Llamá esto SOLO después de checkout_carrito y de tener los datos del cliente. '
            'Crea UNA propuesta de reserva con todos los servicios del carrito. '
            'Para cliente EXISTENTE no hace falta repetir datos que ya están en su ficha; '
            'pasá solo los que el cliente te dio en la conversación. '
            'Devuelve {success, propuesta_id, mensaje, total}. '
            'IMPORTANTE: cuando devuelva success=true, tu respuesta al cliente DEBE ser el campo '
            '`mensaje` TAL CUAL (verbatim). El `propuesta_id` es INTERNO (para el equipo): NUNCA lo '
            'menciones ni lo escribas al cliente. NO digas "tu reserva fue confirmada/registrada" — '
            'todavía es una propuesta; el `mensaje` ya dice lo correcto ("estamos preparando tu '
            'reserva, en un momento te enviamos los datos de pago").'
        ),
        'parameters': {
            'type': 'object',
            'properties': {
                'nombre': {'type': 'string', 'description': 'Nombre del cliente (omitir si ya está en su ficha)'},
                'email': {'type': 'string', 'description': 'Email del cliente (omitir si ya está en su ficha)'},
                'documento_identidad': {'type': 'string', 'description': 'RUT del cliente (omitir si ya está en su ficha)'},
                'comuna': {'type': 'string', 'description': 'Comuna del cliente, ej. "Puerto Varas" (omitir si ya está en su ficha)'},
                'telefono': {'type': 'string', 'description': 'Teléfono del cliente. En WhatsApp OMÍTELO (se usa el de la conversación). En Instagram/Messenger SÍ pásalo.'},
            },
            'required': [],
        },
    },
}, {
    'type': 'function',
    'function': {
        'name': 'confirmar_ritual',
        'description': (
            'CIERRA el Ritual del Río (H-031): cabaña + tina + masaje + desayuno como UNA '
            'unidad por $240.000. Llamá esto cuando el cliente CONFIRMA que quiere reservar el '
            'Ritual (después de haberle ofrecido el itinerario con consultar_disponibilidad_combo). '
            'NO uses el carrito ni confirmar_reserva_carrito para el Ritual: esta tool arma sola '
            'las 4 patas, el desayuno (incluido en la cabaña) y el descuento para clavar el total '
            'en $240.000, y crea UNA propuesta para Deborah. Devuelve {success, propuesta_id, total}. '
            'Para cliente EXISTENTE no repitas datos que ya están en su ficha; pasá solo los que '
            'el cliente te dio. NO digas que quedó reservado hasta recibir success=true.'
        ),
        'parameters': {
            'type': 'object',
            'properties': {
                'fecha': {'type': 'string', 'description': 'REQUERIDO. PASÁ EL TEXTO LITERAL del cliente ("este sábado", "el próximo miércoles", "1 de julio"); NO lo conviertas a YYYY-MM-DD, la herramienta lo resuelve.'},
                'nombre': {'type': 'string', 'description': 'Nombre del cliente (omitir si ya está en su ficha)'},
                'email': {'type': 'string', 'description': 'Email del cliente (omitir si ya está en su ficha)'},
                'documento_identidad': {'type': 'string', 'description': 'RUT del cliente (omitir si ya está en su ficha)'},
                'comuna': {'type': 'string', 'description': 'Comuna del cliente, ej. "Puerto Varas" (omitir si ya está en su ficha)'},
                'telefono': {'type': 'string', 'description': 'Teléfono del cliente. En WhatsApp OMÍTELO (se usa el de la conversación). En Instagram/Messenger SÍ pásalo.'},
            },
            'required': ['fecha'],
        },
    },
}, {
    'type': 'function',
    'function': {
        'name': 'consultar_disponibilidad_refugio',
        'description': (
            'Consulta disponibilidad del REFUGIO AREMKO: el Ritual del Río en estadía de 2 NOCHES '
            'en la MISMA cabaña (cabaña 2 noches + tina + masaje la primera noche + desayuno ambas '
            'mañanas), 2 personas, $290.000 plano todos los días. Usala cuando el cliente pida el '
            'Refugio o "2 noches" con el ritual. `fecha` = noche de LLEGADA (texto literal). '
            'Devuelve el itinerario (cabaña, tina, masaje, fechas de llegada/salida) o disponible=false.'
        ),
        'parameters': {
            'type': 'object',
            'properties': {
                'fecha': {'type': 'string', 'description': 'REQUERIDO. Noche de llegada en TEXTO LITERAL del cliente ("este viernes", "el 4 de julio"); NO la conviertas a YYYY-MM-DD.'},
            },
            'required': ['fecha'],
        },
    },
}, {
    'type': 'function',
    'function': {
        'name': 'confirmar_refugio',
        'description': (
            'CIERRA el Refugio Aremko (2 noches, misma cabaña, $290.000). Llamá esto cuando el '
            'cliente CONFIRMA que quiere reservar el Refugio (después de ofrecerle el itinerario con '
            'consultar_disponibilidad_refugio). NO uses el carrito: esta tool arma sola la cabaña por '
            'las 2 noches + tina + masaje + desayuno incluido y el descuento para clavar el total en '
            '$290.000, y crea UNA propuesta para Deborah. Devuelve {success, propuesta_id, total}. '
            'Para cliente EXISTENTE no repitas datos que ya están en su ficha. NO digas que quedó '
            'reservado hasta recibir success=true.'
        ),
        'parameters': {
            'type': 'object',
            'properties': {
                'fecha': {'type': 'string', 'description': 'REQUERIDO. Noche de LLEGADA en TEXTO LITERAL del cliente; NO la conviertas a YYYY-MM-DD, la herramienta la resuelve.'},
                'nombre': {'type': 'string', 'description': 'Nombre del cliente (omitir si ya está en su ficha)'},
                'email': {'type': 'string', 'description': 'Email del cliente (omitir si ya está en su ficha)'},
                'documento_identidad': {'type': 'string', 'description': 'RUT del cliente (omitir si ya está en su ficha)'},
                'comuna': {'type': 'string', 'description': 'Comuna del cliente (omitir si ya está en su ficha)'},
                'telefono': {'type': 'string', 'description': 'Teléfono del cliente. En WhatsApp OMÍTELO (se usa el de la conversación). En Instagram/Messenger SÍ pásalo.'},
            },
            'required': ['fecha'],
        },
    },
}, {
    'type': 'function',
    'function': {
        'name': 'enviar_ficha_experiencia',
        'description': (
            'Devuelve el link de la landing (ficha completa con fotos, video y reseñas) de UNO de '
            'los 4 programas boutique. Úsala cuando el cliente, tras ver el menú de programas o por '
            'iniciativa propia, pide MÁS DETALLE de un programa en particular (ej. "cuéntame más del '
            'Ritual", "mándame info de la Pausa", "quiero ver fotos del Refugio"). NO la uses para '
            'cotizar precio o disponibilidad de una fecha concreta — para eso usa '
            'consultar_disponibilidad_combo/pack/pack_cabana/refugio. Esta tool NO agenda ni cotiza, '
            'solo entrega el link informativo; el mensaje de WhatsApp mostrará automáticamente una '
            'vista previa con foto al pegar el link, así que no hace falta describir la experiencia '
            'en tu texto.'
        ),
        'parameters': {
            'type': 'object',
            'properties': {
                'programa': {
                    'type': 'string',
                    'enum': ['ritual', 'refugio', 'pausa', 'aguas_calientes'],
                    'description': (
                        'Cuál de los 4 programas: "ritual" (Ritual del Río, cabaña 1 noche + tina + '
                        'masaje + desayuno), "refugio" (Refugio Aremko, 2 noches), "pausa" (Pausa '
                        'junto al río, tina + masaje sin alojamiento), "aguas_calientes" (Noche de '
                        'Aguas Calientes, cabaña + tina sin masaje).'
                    ),
                },
            },
            'required': ['programa'],
        },
    },
}, {
    'type': 'function',
    'function': {
        'name': 'buscar_reservas_cliente',
        'description': (
            'Busca las reservas EXISTENTES de este cliente (H-060). Úsala cuando el cliente '
            'dice algo como "quiero agregar X a mi reserva", "ya reservé pero quiero sumar Y", '
            'o menciona una reserva que ya hizo. Devuelve una lista corta de sus reservas '
            'elegibles (no canceladas, con fecha vigente o reciente). Si hay UNA sola, seguí '
            'directo con esa (no hace falta preguntar cuál). Si hay VARIAS, preguntale al '
            'cliente cuál es mencionando fecha/resumen de cada una (ej. "¿es la del 4 de julio '
            'con la Tina Llaima, o la del 10 de julio?"), NUNCA el reserva_id interno. Si no '
            'tiene ninguna, avisale que no encontraste una reserva activa a su nombre.'
        ),
        'parameters': {
            'type': 'object',
            'properties': {
                'telefono': {'type': 'string', 'description': 'Teléfono del cliente (en WhatsApp se usa el de la conversación; omitir salvo en Instagram/Messenger)'},
            },
            'required': [],
        },
    },
}, {
    'type': 'function',
    'function': {
        'name': 'agregar_servicio_a_reserva_existente',
        'description': (
            'GATE DE DEBORAH (H-060): propone AGREGAR un servicio a una reserva YA CREADA '
            '(identificada antes con buscar_reservas_cliente) — la reserva puede ya estar '
            'pagada o parcial. NO modifica la reserva directamente: crea una propuesta que '
            'Deborah debe aprobar, igual que una reserva nueva. Llamala cuando el cliente '
            'confirma que quiere sumar un servicio a una reserva existente. Devuelve '
            'propuesta_id (interno, NUNCA lo menciones al cliente) + mensaje. Cuando '
            'success=true, respondé al cliente con el campo `mensaje` TAL CUAL (verbatim); '
            'NO digas que ya quedó agregado — todavía es una propuesta pendiente de revisión.'
        ),
        'parameters': {
            'type': 'object',
            'properties': {
                'reserva_id': {'type': 'integer', 'description': 'ID de la reserva existente (de buscar_reservas_cliente). REQUERIDO.'},
                'servicio_id': {'type': 'integer', 'description': 'ID del servicio a agregar'},
                'nombre_servicio': {'type': 'string', 'description': 'Nombre EXACTO del servicio que dijo el cliente (ej. "Llaima"), para confirmar el id correcto'},
                'fecha': {'type': 'string', 'description': 'PASÁ EL TEXTO LITERAL del cliente ("mañana", "el sábado"); NO calcules el día, la herramienta lo resuelve. REQUERIDO.'},
                'hora': {'type': 'string', 'description': 'Hora HH:MM. REQUERIDO.'},
                'cantidad_personas': {'type': 'integer', 'description': 'Cantidad de personas. REQUERIDO (no asumas 1).'},
            },
            'required': ['reserva_id', 'fecha', 'hora', 'cantidad_personas'],
        },
    },
}, {
    'type': 'function',
    'function': {
        'name': 'agregar_producto_a_reserva_existente',
        'description': (
            'GATE DE DEBORAH (H-060): propone AGREGAR un producto (tabla de quesos, jugo, '
            'etc.) a una reserva YA CREADA (identificada antes con buscar_reservas_cliente). '
            'NO modifica la reserva directamente: crea una propuesta que Deborah debe aprobar. '
            'Llamala cuando el cliente confirma que quiere sumar un producto a una reserva '
            'existente. Devuelve propuesta_id (interno, NUNCA lo menciones al cliente) + '
            'mensaje. Cuando success=true, respondé al cliente con el campo `mensaje` TAL '
            'CUAL; NO digas que ya quedó agregado — todavía es una propuesta pendiente.'
        ),
        'parameters': {
            'type': 'object',
            'properties': {
                'reserva_id': {'type': 'integer', 'description': 'ID de la reserva existente (de buscar_reservas_cliente). REQUERIDO.'},
                'nombre_producto': {'type': 'string', 'description': 'Nombre EXACTO del producto del catálogo (ej. "Tabla Mixta de Quesos y Jamones"). REQUERIDO.'},
                'producto_id': {'type': 'integer', 'description': 'ID del producto (opcional; normalmente no lo tenés, pasá nombre_producto)'},
                'cantidad': {'type': 'integer', 'description': 'Cantidad a agregar (default 1)'},
            },
            'required': ['reserva_id', 'nombre_producto'],
        },
    },
}]


def _fecha_hoy_texto():
    """'2026-06-14 (domingo)' en hora de Chile, para que el LLM resuelva 'el sábado'."""
    from django.utils import timezone
    hoy = timezone.localtime(timezone.now())
    return f'{hoy.strftime("%Y-%m-%d")} ({_DIAS_ES[hoy.weekday()]})'


def get_config():
    return WhatsAppAgentConfig.get_solo()


def _modelo_efectivo(config):
    if config.model_name.strip():
        return config.model_name.strip()
    from django.conf import settings
    return getattr(settings, 'DPV_LLM_MODEL', 'anthropic/claude-haiku-4.5')


def config_to_dict(config):
    """Para GET /api/whatsapp/agente/config."""
    return {
        'activo': config.activo,
        'modo': config.modo,
        'persona_tono': config.persona_tono,
        'conocimiento': config.conocimiento,
        'link_reserva': config.link_reserva,
        'model_name': config.model_name,
        'modelo_efectivo': _modelo_efectivo(config),
        'temperature': float(config.temperature),
        'max_tokens': config.max_tokens,
        'history_window': config.history_window,
        'pausa_horas_tras_humano': config.pausa_horas_tras_humano,
        'ausencia_activa': config.ausencia_activa,
        'ausencia_mensaje': config.ausencia_mensaje,
        'ausencia_anti_spam_horas': config.ausencia_anti_spam_horas,
        'prompt_version': prompt_mod.PROMPT_VERSION,
    }


def _fecha_iso(valor):
    """Resuelve la fecha (texto del cliente o ISO) a 'YYYY-MM-DD' de forma determinística.
    Si no se puede resolver, devuelve el valor tal cual (no empeora el comportamiento).
    Evita que el carrito/reserva guarde texto como "próximo lunes" sin resolver."""
    try:
        from .availability import _parse_fecha
        d = _parse_fecha(valor)
        return d.isoformat() if d else valor
    except Exception:  # noqa: BLE001
        return valor


def sugerencia_to_dict(sug):
    """Para el campo `sugerencia_agente` del detalle de conversación."""
    if sug is None:
        return None
    return {
        'texto': sug.texto,
        'escalar': sug.escalar,
        'motivo': sug.motivo_escalar,
        'modo': sug.modo,
        'modelo': sug.modelo,
        'error': sug.error,
        'generada_at': sug.created_at.isoformat(),
        'responde_a': sug.wa_message_id,
    }


def _entrante_a_responder(phone):
    """El último entrante de texto sin atender de esta conversación, o None."""
    from ventas.models import WhatsAppMessage
    return (
        WhatsAppMessage.objects
        .filter(phone=phone, direction='in', requiere_atencion=True)
        .exclude(msg_type='reaction')
        .order_by('-timestamp')
        .first()
    )


def _conversacion_pausada(phone, horas):
    """True si un humano respondió en este chat dentro de la ventana de pausa.

    "Humano" = saliente que NO marcamos como del agente. En F1 ningún saliente
    es del agente, así que cualquier saliente reciente pausa la sugerencia.
    """
    if not horas:
        return False
    from ventas.models import WhatsAppMessage
    limite = timezone.now() - timezone.timedelta(hours=horas)
    return (
        WhatsAppMessage.objects
        .filter(phone=phone, direction='out', timestamp__gte=limite)
        .exists()
    )


def _historial_texto(phone, antes_de_ts, window):
    """Últimos `window` mensajes previos al entrante a responder, como texto."""
    from ventas.models import WhatsAppMessage
    msgs = list(
        WhatsAppMessage.objects
        .filter(phone=phone, timestamp__lt=antes_de_ts)
        .exclude(msg_type='reaction')
        # H-045: si el número es TAMBIÉN staff, recibe avisos operativos (H-038 "🔔 Nueva tarea ·")
        # en el mismo hilo. Esos avisos NO son parte de la conversación con el cliente y descarrilan
        # al agente (modelo liviano) → se excluyen del contexto que lee Luna (siguen en la bandeja).
        .exclude(direction='out', body__contains='Nueva tarea ·')
        .order_by('-timestamp')[:window]
    )
    msgs.reverse()
    lineas = []
    for m in msgs:
        cuerpo = (m.body or '').strip()
        if not cuerpo:
            cuerpo = f'({m.msg_type})'
        quien = 'Cliente' if m.direction == 'in' else 'Aremko'
        lineas.append(f'[{quien}]: {cuerpo}')
    return '\n'.join(lineas)


def _estado_estructurado(canal, external_id):
    """Estado EN CURSO de este cliente (carrito + cotización vigente) como texto compacto.

    Se inyecta SIEMPRE en el prompt para que Luna no dependa de la ventana de mensajes ni de
    "recordar": el carrito y la propuesta viven en la BD (fuente de verdad). Determinístico y
    READ-ONLY (no crea carrito vacío). Devuelve '' si no hay nada en curso.

    - Carrito: solo si tiene ítems y fue tocado hace < 24h (evita resucitar uno abandonado).
    - Cotización: solo la pendiente vigente (TTL 24h en esta_vigente()).
    """
    if not external_id:
        return ''
    from django.utils import timezone
    bloques = []
    try:
        from carrito_reservas.models import CarritoReserva
        carrito = CarritoReserva.objects.filter(canal=canal, external_id=external_id).first()
        reciente = (carrito is not None and carrito.updated_at is not None
                    and carrito.updated_at >= timezone.now() - timezone.timedelta(hours=24))
        if carrito and carrito.items and reciente:
            lineas = []
            for it in carrito.items:
                if it.get('tipo') == 'producto':
                    lineas.append(f"  - [producto] {it.get('nombre')} x{it.get('cantidad', 1)} "
                                  f"= ${int(it.get('subtotal') or 0):,}")
                else:
                    lineas.append(f"  - [servicio_id {it.get('servicio_id')}] {it.get('nombre')} · "
                                  f"{it.get('fecha')} {it.get('hora')} · "
                                  f"{it.get('cantidad_personas')} pers = ${int(it.get('subtotal') or 0):,}")
            if carrito.descuento_combo:
                lineas.append(f"  - Descuento pack = -${int(carrito.descuento_combo):,}")
            lineas.append(f"  TOTAL carrito: ${int(carrito.total or 0):,}")
            bloques.append(
                'CARRITO EN CURSO (ya agregado — NO lo vuelvas a preguntar ni a agregar; usá estos '
                'servicio_id y horas TAL CUAL si necesitás referirte a ellos):\n' + '\n'.join(lineas))
    except Exception:  # noqa: BLE001 — el estado es contexto, nunca debe tumbar el borrador
        logger.exception('[estado] no se pudo leer el carrito de %s/%s', canal, external_id)
    try:
        from .models import PropuestaReserva
        prop = (PropuestaReserva.objects
                .filter(canal=canal, external_id=external_id, estado='pendiente')
                .order_by('-created_at').first())
        if prop is not None and prop.esta_vigente():
            bloques.append(
                f'COTIZACIÓN YA ENVIADA Y VIGENTE (total ${int(prop.total or 0):,}): el cliente ya la '
                'tiene para aprobar. Si pide un cambio, ajustá sobre ESA; NO armes otra cotización '
                'desde cero. NO digas que está "confirmada"/"reservada" hasta que la apruebe.')
    except Exception:  # noqa: BLE001
        logger.exception('[estado] no se pudo leer la propuesta de %s/%s', canal, external_id)
    if not bloques:
        return ''
    return ('# ESTADO ACTUAL DE ESTE CLIENTE (fuente de verdad de la BD — úsalo SIEMPRE; '
            'prima sobre lo que recuerdes del chat)\n' + '\n\n'.join(bloques))


def _guardar(entrante, *, texto='', escalar=False, motivo='', modo='', modelo='',
             error='', input_tokens=0, output_tokens=0, latency_ms=0):
    """Crea/actualiza la sugerencia (cache por wa_message_id)."""
    sug, _ = SugerenciaAgenteWhatsApp.objects.update_or_create(
        wa_message_id=entrante.wa_message_id,
        defaults=dict(
            phone=entrante.phone, texto=texto, escalar=escalar, motivo_escalar=motivo[:200],
            modo=modo, modelo=modelo[:120], error=error[:200],
            input_tokens=input_tokens, output_tokens=output_tokens, latency_ms=latency_ms,
        ),
    )
    return sug


def _borrador_escala(motivo, *, error='', modelo='', tokens=(0, 0, 0)):
    return {
        'escalar': True, 'motivo': motivo, 'texto': '', 'modelo': modelo, 'error': error,
        'input_tokens': tokens[0], 'output_tokens': tokens[1], 'latency_ms': tokens[2],
    }


def _contexto_saludo(entrante):
    """(estado_saludo, nombre) determinístico para un entrante. Tolerante a fallos.

    estado: 'primer_contacto' / 'regreso' / 'en_conversacion' (ver prompt.clasificar_saludo).
    nombre: nombre de pila usable (cliente conocido o perfil de WhatsApp), o '' si no hay.
    """
    try:
        from ventas.models import WhatsAppMessage
        previo = (
            WhatsAppMessage.objects
            .filter(phone=entrante.phone, timestamp__lt=entrante.timestamp)
            .exclude(msg_type='reaction')
            .order_by('-timestamp')
            .values_list('timestamp', flat=True)
            .first()
        )
        hay_previos = previo is not None
        dias = (entrante.timestamp - previo).days if hay_previos else None
        estado = prompt_mod.clasificar_saludo(hay_previos, dias)

        nombre = ''
        if getattr(entrante, 'cliente_id', None):
            nombre = prompt_mod.saneo_nombre(getattr(entrante.cliente, 'nombre', ''))
        if not nombre:
            nombre = prompt_mod.saneo_nombre(getattr(entrante, 'contact_name', ''))
        return estado, nombre
    except Exception:  # noqa: BLE001 — el saludo nunca debe tumbar el borrador
        logger.exception('Agente WA: no se pudo calcular el contexto de saludo')
        return '', ''


def _cierre_fallback_tras_tools(tool_calls_executed):
    """Cierre determinístico para cuando el modelo devuelve VACÍO pero YA ejecutó tools que
    cambiaron el carrito/propuesta (quirk gemini-flash: ejecuta las tools y no redacta el cierre).
    La acción NO se pierde (el carrito ya quedó armado); solo faltó el texto → damos uno para que la
    conversación no se trabe. Devuelve '' si no hubo ninguna tool de carrito/propuesta exitosa
    (en ese caso sí corresponde escalar a humano)."""
    confirmo = agrego = False
    for tc in (tool_calls_executed or []):
        name, res = tc.get('name'), tc.get('result')
        if not escalation.tool_result_ok(res):
            continue
        if name in ('confirmar_reserva_carrito', 'confirmar_ritual', 'confirmar_refugio'):
            confirmo = True
        elif name in ('agregar_servicio_carrito', 'agregar_producto_carrito', 'quitar_item_carrito'):
            agrego = True
    if confirmo:
        return '¡Listo! Te preparé la cotización para que la revises. 🌿'
    if agrego:
        return ('¡Listo! Ya lo tengo en tu carrito. ¿Querés sumar algo más o te envío la '
                'cotización para que la revises? 🌿')
    return ''


# Tope de alternativas de RESPALDO devueltas al modelo además de la recomendada
# (contexto acotado; el total real viaja en `total_alternativas`).
_MAX_ALTERNATIVAS_TOOL = 8


def _hora_itinerario_min(alt):
    """Minutos desde medianoche de la primera hora del itinerario (0 si no parsea).
    Para el desempate de orden H-081: a igual precio, el horario MÁS TARDE primero."""
    try:
        itin = alt.get('itinerario') or []
        h = (itin[0].get('hora') or '') if itin else ''
        hh, mm = h.split(':')
        return int(hh) * 60 + int(mm)
    except Exception:  # noqa: BLE001 — orden best-effort, nunca romper la tool
        return 0


def _resolver_ambientacion(nombre_servicio):
    """H-080: resuelve el ID de una ambientación por nombre (determinista).

    El override por nombre de agregar_servicio_carrito solo mira TIPOS_PRINCIPALES,
    así que "Ambientación romántica R1" no resolvía a nada: el modelo conocía la
    lista (catálogo H-079) pero no tenía CÓMO agregarla y se auto-escalaba con
    "producto no encontrado en el catálogo" (caso real 2026-07-29, "reservame la
    R1 de 32.000"). Mismo filtro que el catálogo/picker: activa + precio real.

    Devuelve el id si el nombre matchea UNA sola ambientación; None si 0 o 2+.
    """
    nombre = (nombre_servicio or '').strip()
    if not nombre:
        return None
    from ventas.models import Servicio
    matches = list(Servicio.objects.filter(
        activo=True,
        categoria__nombre__iexact='Ambientaciones',
        precio_base__gt=1,
        nombre__icontains=nombre,
    ).values_list('id', flat=True)[:2])
    return matches[0] if len(matches) == 1 else None


def _es_ambientacion(servicio_id):
    """True si el servicio pertenece a la categoría Ambientaciones."""
    from ventas.models import Servicio
    return Servicio.objects.filter(
        id=servicio_id, categoria__nombre__iexact='Ambientaciones').exists()


# H-083: palabras de un nombre de ambientación que NO cuentan como "el cliente la
# nombró" (genéricas — con solo esto no hay confirmación de UNA en particular).
_PALABRAS_GENERICAS_AMB = {
    'ambientacion', 'ambientación', 'ambientaciones', 'decoracion', 'decoración',
    'decoraciones', 'servicio', 'de', 'con', 'la', 'el', 'los', 'las', 'para', 'y', 'o',
}
_RE_ASENTIMIENTO_AMB = re.compile(
    r'\b(s[ií]|ya|dale|ok(ey)?|bueno|claro|obvio|perfect[oa]|genial|'
    r'me (gusta|encanta|sirve)|(la|lo|esa|ese) quiero|quiero (esa|ese|una|uno|la|el)|'
    r'esa( misma)?|ese( mismo)?|agr[eé]g\w*|s[uú]m[ae]\w*|an[oó]t\w*|reserv\w*|'
    r'pon(me|le|la|lo)?|porfa\w*|por favor)\b'
)


def _cliente_confirmo_ambientacion(mensaje, nombre_ambientacion):
    """H-083: gate determinista anti agregado prematuro de ambientaciones.

    True SOLO si el mensaje del cliente (el que este turno responde) NOMBRA la
    ambientación (alguna palabra significativa de su nombre) o trae un ASENTIMIENTO
    explícito sin negación ("sí", "esa", "agrégala", "resérvame la R1"...).

    Una pregunta informativa ("¿tienes ambientaciones?") devuelve False — caso real
    2026-07-30: ante esa pregunta el modelo agregó la R1 al carrito de inmediato,
    saltándose la instrucción de confirmar (las instrucciones no bastan; esto lo
    fuerza el código). Función PURA: testeable sin DB.
    """
    m = (mensaje or '').lower()
    if not m.strip():
        return False
    # (a) La nombra: alguna palabra significativa del nombre aparece en el mensaje.
    for palabra in re.split(r'[^0-9a-záéíóúñü]+', (nombre_ambientacion or '').lower()):
        if len(palabra) >= 2 and palabra not in _PALABRAS_GENERICAS_AMB:
            if re.search(r'\b' + re.escape(palabra) + r'\b', m):
                return True
    # (b) Negación explícita → jamás es confirmación ("no, esa no", "todavía no").
    if re.search(r'\bno\b', m):
        return False
    # (c) Asentimiento corto ("sí", "dale", "esa", "agrégala"...).
    return _RE_ASENTIMIENTO_AMB.search(m) is not None


# ============================================================================
# H-084 — gate anti "variante elegida por el modelo" (productos)
# ----------------------------------------------------------------------------
# Caso real 2026-07-30: cliente "Si un jugo" → el modelo agregó "Jugo Natural de
# Frambuesa" al carrito Y ADEMÁS redactó "¿de qué sabor te gustaría?" (H-082):
# texto y acción contradictorios. El texto lo arregló la instrucción; la acción
# solo se arregla en código: un producto entra al carrito únicamente si el
# CONTEXTO del cliente lo desambigua (su mensaje o, si solo asintió, la última
# oferta de Aremko en el historial). Empate entre variantes → se bloquea y se le
# ordena al modelo preguntar cuál.
# ============================================================================

_STOP_PROD = {
    'de', 'del', 'la', 'el', 'los', 'las', 'un', 'una', 'unos', 'unas',
    'y', 'o', 'u', 'con', 'sin', 'para', 'por', 'en', 'al', 'a',
}

# H-085: número de personas en palabras (respuestas típicas del cliente).
_PERSONAS_PALABRA = {'una': 1, 'dos': 2, 'tres': 3, 'cuatro': 4, 'cinco': 5, 'seis': 6}


def _es_asentimiento_puro(mensaje):
    """True si el mensaje es SOLO un asentimiento corto ("sí", "dale", "ok") sin
    datos nuevos (sin números, sin negación, corto). En un turno así, el cliente
    acepta lo YA ofrecido — no pudo haber cambiado personas/fecha/servicio."""
    m = _normalizar_txt(mensaje).strip()
    if not m or len(m) > 25 or re.search(r'\d', m) or re.search(r'\bno\b', m):
        return False
    return _RE_ASENTIMIENTO_AMB.search(m) is not None


def _personas_declaradas_por_cliente(historial):
    """Última cantidad de personas que DECLARÓ el cliente en el historial (líneas
    `[Cliente]:`): respuesta suelta ("2"), "2 personas", "para dos", "somos 4".
    None si nunca la declaró. Rango sano 1..10."""
    for linea in reversed((historial or '').splitlines()):
        if not linea.startswith('[Cliente]:'):
            continue
        cuerpo = _normalizar_txt(linea[len('[Cliente]:'):]).strip()
        n = None
        m = re.fullmatch(r'(\d{1,2})', cuerpo)
        if m:
            n = int(m.group(1))
        if n is None:
            m = re.search(r'\b(\d{1,2})\s*personas?\b', cuerpo)
            if m:
                n = int(m.group(1))
        if n is None:
            m = re.search(r'\b(?:para|somos)\s+(\d{1,2})\b', cuerpo)
            if m:
                n = int(m.group(1))
        if n is None:
            m = (re.fullmatch(r'(una|dos|tres|cuatro|cinco|seis)', cuerpo)
                 or re.search(r'\b(?:para|somos)\s+(una|dos|tres|cuatro|cinco|seis)\b', cuerpo))
            if m:
                n = _PERSONAS_PALABRA.get(m.group(1))
        if n is not None and 1 <= n <= 10:
            return n
    return None


def _normalizar_txt(s):
    """minúsculas + sin tildes (para comparar 'melón' con 'melon')."""
    s = unicodedata.normalize('NFD', (s or '').lower())
    return ''.join(c for c in s if unicodedata.category(c) != 'Mn')


def _palabras_significativas_producto(nombre):
    return [w for w in re.split(r'[^0-9a-zñ]+', _normalizar_txt(nombre))
            if len(w) >= 2 and w not in _STOP_PROD]


def _token_en_texto(palabra, texto_norm):
    """Match por palabra completa, tolerando singular/plural del español:
    jugo↔jugos, natural↔naturales, jamón↔jamones."""
    variantes = {palabra, palabra + 's', palabra + 'es'}
    if len(palabra) >= 4 and palabra.endswith('es'):
        variantes.add(palabra[:-2])
    if len(palabra) >= 3 and palabra.endswith('s'):
        variantes.add(palabra[:-1])
    return any(re.search(r'\b' + re.escape(v) + r'\b', texto_norm) for v in variantes)


def _elegir_producto_por_contexto(contexto_norm, candidatos):
    """PURA. candidatos: [(id, nombre)]. Puntúa cada producto por cuántas palabras
    significativas de su nombre aparecen en el contexto (y qué fracción de su nombre
    queda cubierta — así "tabla de quesos" le gana a "Tabla Mixta de Quesos y
    Jamones"). Devuelve (id_único_mejor | None, [nombres_empatados])."""
    puntajes = []
    for pid, nombre in candidatos:
        palabras = _palabras_significativas_producto(nombre)
        if not palabras:
            continue
        hits = sum(1 for w in palabras if _token_en_texto(w, contexto_norm))
        if hits:
            puntajes.append((hits, hits / len(palabras), pid, nombre))
    if not puntajes:
        return None, []
    puntajes.sort(key=lambda t: (-t[0], -t[1]))
    tope = (puntajes[0][0], puntajes[0][1])
    top = [t for t in puntajes if (t[0], t[1]) == tope]
    if len(top) == 1:
        return top[0][2], []
    return None, [t[3] for t in top[:4]]


def _cliente_eligio_producto(mensaje, historial, producto_id, candidatos=None):
    """H-084: True si el contexto del cliente desambigua EXACTAMENTE producto_id.

    Contexto = su último mensaje; si ahí no menciona ningún producto (asentimiento
    puro tipo "sí"), se usa la última línea de Aremko del historial (la oferta a la
    que asintió). `candidatos` inyectable para tests; en producción se leen de la BD
    (mismo filtro que la resolución por nombre del handler).

    Devuelve (ok, texto_opciones_para_preguntar)."""
    if candidatos is None:
        from ventas.models import Producto
        candidatos = list(
            Producto.objects.filter(publicado_web=True, cantidad_disponible__gt=0)
            .values_list('id', 'nombre'))

    elegido, empatados = _elegir_producto_por_contexto(_normalizar_txt(mensaje or ''), candidatos)
    if elegido is None and not empatados:
        ultima = ''
        for linea in reversed((historial or '').splitlines()):
            if linea.startswith('[Aremko]:'):
                ultima = linea
                break
        if ultima:
            elegido, empatados = _elegir_producto_por_contexto(_normalizar_txt(ultima), candidatos)
    if elegido == producto_id:
        return True, ''
    return False, ', '.join(empatados) if empatados else 'varias opciones similares'


def _agregar_ambientacion_al_carrito(canal, external_id, servicio_id):
    """H-080: agrega una ambientación (servicio) con las guardias deterministas:
    cantidad SIEMPRE 1 (su precio es por unidad; el motor multiplica base × cantidad)
    y fecha/hora HEREDADAS de la primera línea de servicio con fecha (la tina) — de la
    propuesta vigente si existe (H-043), si no del carrito. Sin tina aún → sin fecha
    (Deborah la ajusta con el lápiz del cajón).

    La usa el cross-fix del handler de agregar_producto_carrito: el modelo tiende a
    tratar la ambientación como "producto" (es un add-on, igual que tablas/jugos)."""
    from .models import PropuestaReserva
    from .reserva_service import agregar_servicio_a_propuesta

    fecha = hora = None
    prop = (PropuestaReserva.objects
            .filter(canal=canal, external_id=external_id, estado='pendiente')
            .order_by('-created_at').first())
    if prop is not None and prop.esta_vigente():
        candidatos = (prop.payload or {}).get('servicios') or []
        for s in candidatos:
            if s.get('fecha'):
                fecha, hora = s.get('fecha'), s.get('hora')
                break
    else:
        from carrito_reservas.models import CarritoReserva
        carrito = CarritoReserva.objects.filter(canal=canal, external_id=external_id).first()
        for it in (carrito.items if carrito else None) or []:
            if it.get('tipo') != 'producto' and it.get('fecha'):
                fecha, hora = it.get('fecha'), it.get('hora')
                break

    actualizado = agregar_servicio_a_propuesta(
        canal=canal, external_id=external_id, servicio_id=servicio_id,
        fecha=fecha, hora=hora, cantidad_personas=1)
    if actualizado is not None:
        return actualizado
    from carrito_reservas.services import CarritoService
    return CarritoService.agregar_servicio(
        canal=canal, external_id=external_id, servicio_id=servicio_id,
        fecha=fecha, hora=hora, cantidad_personas=1)


# H-088: "tina/masaje + fecha" es una pregunta de HORARIOS, y esas se responden con
# UNA recomendación (H-081), no con la lista completa. Mapea el `tipo` de
# `consultar_disponibilidad` al tipo de experiencia equivalente.
_TIPO_A_EXPERIENCIA = {'tina': 'tina_sola', 'masaje': 'masaje_solo'}

# H-089: qué agrega cada ambientación superior sobre su base. Mapeo por ID, igual
# que el resto de la taxonomía: los NOMBRES no dicen "ramo", así que un match por
# texto sobre el nombre no encontraría nada.
#   R1 (id 22, $32.000) + ramo de flores = R2 (id 23, $68.000).
# Sin esto, pedir "un ramo" sobre una R1 terminaba vendiendo el Producto suelto
# ($38.000) → $70.000, MÁS caro que la R2 que ya incluye exactamente eso.
_UPGRADE_AMBIENTACION = {
    22: {'destino_id': 23, 'extra': ('ramo', 'ramos', 'flor', 'flores')},
}


def upgrade_por_extra(mensaje, items_carrito):
    """Detecta que el cliente pide un extra ya incluido en una versión superior.

    Devuelve {'indice', 'base_id', 'destino_id'} del ítem del carrito que conviene
    cambiar, o None si no aplica. Función PURA: no toca el carrito ni decide
    precios — solo detecta la oportunidad. Ofrecer y confirmar sigue el flujo
    normal (H-083: nada entra al carrito sin que el cliente lo acepte).
    """
    txt = _normalizar_txt(mensaje or '')
    if not txt:
        return None
    for indice, item in enumerate(items_carrito or []):
        if (item or {}).get('tipo') != 'servicio':
            continue
        try:
            sid = int(item.get('servicio_id'))
        except (TypeError, ValueError):
            continue
        regla = _UPGRADE_AMBIENTACION.get(sid)
        if regla and any(palabra in txt for palabra in regla['extra']):
            return {'indice': indice, 'base_id': sid, 'destino_id': regla['destino_id']}
    return None


def acepto_el_cambio(mensaje, historial, nombre_destino):
    """True si el cliente asiente Y el último mensaje de Luna ofreció ESE cambio.

    Función PURA. Pide las dos señales juntas a propósito: un "claro" suelto no
    alcanza (podría estar aceptando otra cosa), y que Luna haya ofrecido el cambio
    tampoco (el cliente pudo no contestar). Solo las dos juntas autorizan a mover
    el carrito sin preguntar de nuevo.
    """
    if not nombre_destino or not _es_asentimiento_puro(mensaje):
        return False
    ultima = ''
    for linea in reversed((historial or '').splitlines()):
        if linea.startswith('[Aremko]:'):
            ultima = _normalizar_txt(linea)
            break
    if not ultima:
        return False
    return _normalizar_txt(nombre_destino) in ultima and 'cambi' in ultima


def aplicar_upgrade_si_acepto(canal, phone, mensaje, historial):
    """Ejecuta el cambio de ambientación EN CÓDIGO cuando el cliente lo acepta.

    Nace del caso real del 2026-08-01: Luna ofreció cambiar la R1 por la R2, Jorge
    dijo "claro", y ella respondió "ha sido agregada" SIN llamar una sola
    herramienta — el carrito quedó con la R1. El motivo de fondo: la instrucción
    con el índice y las tools viajaba en el RESULTADO de la tool del turno
    anterior, y en el turno del "claro" el modelo ya no la tiene: solo ve el
    historial de texto. Pedirle que recuerde y encadene dos llamadas era pedirle
    justo lo que este agente hace mal.

    Devuelve el texto de confirmación (hecho consumado) o '' si no aplica.
    """
    try:
        from carrito_reservas.services import CarritoService
        externo = phone or 'desconocido'
        items = (CarritoService.ver_carrito(canal=canal, external_id=externo)
                 or {}).get('items') or []
    except Exception:  # noqa: BLE001
        return ''

    from ventas.models import Servicio
    for indice, item in enumerate(items):
        if (item or {}).get('tipo') != 'servicio':
            continue
        try:
            sid = int(item.get('servicio_id'))
        except (TypeError, ValueError):
            continue
        regla = _UPGRADE_AMBIENTACION.get(sid)
        if not regla:
            continue
        destino = Servicio.objects.filter(id=regla['destino_id'], activo=True).first()
        if destino is None or not acepto_el_cambio(mensaje, historial, destino.nombre):
            continue

        # Orden: quitar primero. Si el agregado fallara, el carrito queda SIN la
        # ambientación (visible en el panel) en vez de con las dos cobradas.
        try:
            CarritoService.quitar_item(canal=canal, external_id=externo, indice=indice)
            res = _agregar_ambientacion_al_carrito(canal, externo, destino.id)
        except Exception as exc:  # noqa: BLE001
            logger.exception('[H-090] falló el cambio de ambientación: %s', exc)
            return ''
        if not escalation.tool_result_ok(res):
            logger.error('[H-090] el agregado de la ambientación superior no fue ok: %s', res)
            return ''

        precio = f'{int(destino.precio_base):,}'.replace(',', '.')
        logger.info('[H-090] cambio de ambientación aplicado en código: %s → %s',
                    sid, destino.id)
        return (f'¡Listo! Cambié tu ambientación por la {destino.nombre}, que ya incluye '
                f'todo eso, por ${precio}. ¿Te envío la cotización para que la revises?')
    return ''


def instruccion_sin_reservas(hay_cotizacion, hay_carrito):
    """Qué decirle al modelo cuando el cliente NO tiene reservas ya creadas.

    Caso real (Jorge 2026-08-01): con una COTIZACIÓN en curso aceptó una
    ambientación y Luna escaló *"no se encontró la reserva para agregar la
    ambientación"*. `buscar_reservas_cliente` devolvía `reservas: []` sin decir
    nada más, y el modelo leyó ese vacío como un callejón sin salida.

    Pero una cotización vigente NO es un callejón: se le suma con las tools del
    carrito. Devolver el vacío a secas era esconderle la salida.
    """
    if hay_cotizacion or hay_carrito:
        donde = 'una cotización en curso' if hay_cotizacion else 'un carrito armándose'
        return (
            f'El cliente NO tiene reservas ya creadas, pero SÍ tiene {donde}. '
            f'Para sumarle algo usa `agregar_servicio_carrito` o '
            f'`agregar_producto_carrito` (esas suman a lo que ya está armado). '
            f'NO escales ni le digas que no encontraste su reserva.')
    return ('El cliente no tiene reservas creadas ni nada armado. Si quiere algo, '
            'empieza una reserva nueva con las tools del carrito.')


def _estado_cotizacion_carrito(canal, external_id):
    """(hay_cotizacion_vigente, hay_carrito_con_items). Best-effort."""
    hay_cot = hay_carrito = False
    try:
        from .models import PropuestaReserva
        prop = (PropuestaReserva.objects
                .filter(canal=canal, external_id=external_id, estado='pendiente')
                .order_by('-created_at').first())
        hay_cot = bool(prop is not None and prop.esta_vigente())
    except Exception:  # noqa: BLE001
        pass
    try:
        from carrito_reservas.models import CarritoReserva
        carrito = CarritoReserva.objects.filter(
            canal=canal, external_id=external_id).first()
        hay_carrito = bool(carrito and (carrito.items or []))
    except Exception:  # noqa: BLE001
        pass
    return hay_cot, hay_carrito


def oferta_upgrade_ambientacion(canal, phone, texto):
    """Respuesta lista para ofrecer el cambio, o None si no aplica.

    Se evalúa ANTES de resolver el producto a propósito: si el extra suelto está
    publicado (como quedó el "Ramo de flores" el 2026-08-01), el producto resuelve
    y —de chequear después— nunca se llegaría a ofrecer el upgrade. El cliente
    terminaría pagando R1 + ramo ($70.000) en vez de la R2 ($68.000), que incluye
    exactamente eso.
    """
    try:
        from carrito_reservas.services import CarritoService
        items = (CarritoService.ver_carrito(
            canal=canal, external_id=phone or 'desconocido') or {}).get('items') or []
    except Exception:  # noqa: BLE001 — sin carrito legible, se sigue de largo
        return None

    up = upgrade_por_extra(texto, items)
    if not up:
        return None

    from ventas.models import Servicio
    servs = {s.id: s for s in Servicio.objects.filter(
        id__in=[up['base_id'], up['destino_id']])}
    base, dest = servs.get(up['base_id']), servs.get(up['destino_id'])
    if dest is None:
        return None  # la superior no existe/está inactiva: nada que ofrecer

    logger.info(
        '[H-089] extra ya incluido en la ambientación superior (%s → %s) → se ofrece '
        'el cambio en vez de vender el extra suelto', up['base_id'], up['destino_id'])
    return {
        'success': False,
        'error': 'conviene_upgrade_ambientacion',
        'upgrade': {
            'indice_a_quitar': up['indice'],
            'ambientacion_actual': getattr(base, 'nombre', ''),
            'ambientacion_sugerida': dest.nombre,
            'precio_sugerida': int(dest.precio_base),
        },
        'mensaje': (
            f'Eso ya viene incluido en "{dest.nombre}" (${int(dest.precio_base):,}'.replace(',', '.')
            + f'). NO lo agregues como producto aparte: sale más caro y queda duplicado. '
              f'Ofrécele en UNA frase cambiar su "{getattr(base, "nombre", "")}" por esa, '
              f'diciendo el precio. Si acepta, llama `quitar_item_carrito` con '
              f'indice={up["indice"]} y después agrega la sugerida.'),
    }


def ruta_una_recomendacion(tipo, fecha):
    """Tipo de experiencia si esta consulta debe salir como UNA recomendación, o None.

    SÍ (una sola opción): tina o masaje CON fecha → el cliente pregunta horarios.
    NO (listado normal): sin fecha (es pregunta de precio), cabañas, o sin tipo
    (es el menú, que legítimamente enumera).
    """
    if not fecha:
        return None
    return _TIPO_A_EXPERIENCIA.get((str(tipo or '')).strip().lower())


def _tool_alternativas_experiencia(args):
    """Handler de la tool `alternativas_experiencia` (H-078).

    Cotiza una experiencia con el MISMO motor H-061 de las "olitas" de la bandeja
    (whatsapp_agent/alternativas.py). Las horas salen de la misma grilla que valida
    `agregar_servicio_carrito` (`extraer_slots_para_fecha`) → todo lo que se ofrece
    acá es agregable al carrito después. Caso real que motiva esto (2026-07-29): el
    modelo redactó "masaje a las 16:45" en el texto de opciones — hora inventada que
    el validador del carrito rechazó recién al intentar agregarla.
    """
    from . import alternativas as alternativas_mod
    from .availability import resolver_fecha

    args = args or {}
    tipo = (str(args.get('tipo') or '')).strip().lower()

    try:
        personas = int(args.get('personas'))
    except (TypeError, ValueError):
        personas = 0
    if personas < 1:
        return {'success': False, 'error': 'falta_personas',
                'mensaje': 'Necesito saber para cuántas personas es. Pregúntale al cliente '
                           'antes de cotizar. NO asumas 1.'}

    r = resolver_fecha((str(args.get('fecha') or '')).strip())
    if not r or r.get('error') or not r.get('fecha_iso'):
        return {'success': False, 'error': 'fecha_invalida',
                'mensaje': (r or {}).get('error')
                or 'No pude resolver la fecha. Pídele al cliente la fecha exacta.'}
    if r.get('ambiguo'):
        return {'success': False, 'error': 'fecha_ambigua',
                'mensaje': 'La fecha es ambigua (el día de la semana no calza con el número). '
                           'Confírmala con el cliente antes de cotizar.'}

    res = alternativas_mod.construir_alternativas(tipo, r['fecha_iso'], personas)
    if res.get('error'):
        return {'success': False, 'error': 'alternativas_invalidas', 'mensaje': res['error']}

    # H-081 (decisión de Jorge 2026-07-30): Luna ofrece UNA sola opción a la vez — las
    # listas de 3-4 combos con asteriscos se ven "de robot". Orden determinista: la MÁS
    # BARATA primero (precio final, luego precio normal) y, a igual precio, el horario
    # MÁS TARDE (regla de la casa: deja el día libre). Las demás viajan como respaldo
    # para cuando el cliente pida "otro horario" / "otra tina".
    alts = sorted(
        list(res.get('alternativas') or []),
        key=lambda a: (
            a.get('precio_con_descuento') or 0,
            a.get('precio_total') or 0,
            -_hora_itinerario_min(a),
        ),
    )
    if not alts:
        return {
            'success': True,
            'tipo': res.get('tipo'),
            'nombre_experiencia': res.get('nombre_experiencia'),
            'fecha': r['fecha_iso'],
            'dia_semana': r.get('dia_semana'),
            'personas': personas,
            'total_alternativas': 0,
            'recomendada': None,
            'otras_alternativas': [],
            'instruccion': ('No hay disponibilidad ese día para esta experiencia: dilo con '
                            'calidez y ofrece consultar otra fecha. NUNCA inventes horarios.'),
        }
    return {
        'success': True,
        'tipo': res.get('tipo'),
        'nombre_experiencia': res.get('nombre_experiencia'),
        'fecha': r['fecha_iso'],
        'dia_semana': r.get('dia_semana'),
        'personas': personas,
        'total_alternativas': len(alts),
        'recomendada': alts[0],
        'otras_alternativas': alts[1:1 + _MAX_ALTERNATIVAS_TOOL],
        'instruccion': ('Ofrece SOLO la `recomendada`, redactada NATURAL en 1-2 frases (usa su '
                        '`texto_sugerido` como base, con sus horas y precios EXACTOS, '
                        'mencionando para cuántas personas es, y el '
                        '`dia_semana` devuelto). PROHIBIDO listar varias opciones o usar '
                        'asteriscos/viñetas. Cierra preguntando si le acomoda o si prefiere '
                        'otro horario u otra tina. Si el cliente pide algo distinto (más '
                        'tarde, más temprano, con/sin hidromasaje), ofrece UNA sola de '
                        '`otras_alternativas` — la que mejor calce con lo pedido — nunca la '
                        'lista completa. Si ninguna calza, dilo y ofrece otra fecha.'),
    }


def _producir_borrador(config, mensaje, historial='', saludo_estado='', saludo_nombre='',
                       datos_cliente=None, phone='', canal='whatsapp'):
    """Wrapper H-078 sobre `_producir_borrador_inner`: si el turno ESCALA (el texto se
    frena y no llega al cliente), revierte las mutaciones de carrito/propuesta que las
    tools de ese mismo turno alcanzaron a hacer — un turno sin mensaje no deja residuo
    (caso real 2026-07-29: tina fantasma en el carrito tras un turno frenado por H-045).
    """
    ident = (phone or '').strip()
    snap = None
    if ident:
        try:
            snap = rollback.snapshot_estado_venta(canal, ident)
        except Exception:  # noqa: BLE001 — sin snapshot igual se produce el borrador
            logger.exception('[Agente WA] H-078: no se pudo capturar el snapshot pre-turno')
    try:
        d = _producir_borrador_inner(
            config, mensaje, historial=historial, saludo_estado=saludo_estado,
            saludo_nombre=saludo_nombre, datos_cliente=datos_cliente, phone=phone, canal=canal)
    except Exception:
        # Turno reventado = tampoco salió mensaje → mismo invariante que escalar.
        if snap is not None and rollback.restaurar_estado_venta(canal, ident, snap):
            logger.warning('[Agente WA] H-078: excepción en el turno → estado de venta restaurado')
        raise
    if d.get('escalar') and snap is not None:
        if rollback.restaurar_estado_venta(canal, ident, snap):
            logger.warning('[Agente WA] H-078: turno escalado → carrito/propuesta restaurados '
                           'al estado pre-turno')
    return d


def _producir_borrador_inner(config, mensaje, historial='', saludo_estado='', saludo_nombre='', datos_cliente=None, phone='', canal='whatsapp'):
    """Genera el borrador para un texto de cliente. SIN DB y SIN gate de `activo`.

    Devuelve un dict {escalar, motivo, texto, modelo, error, *tokens}. Lo usan
    tanto el flujo en vivo (`generar_sugerencia`) como el comando de prueba.

    datos_cliente: dict {nombre, email, documento_identidad, region_nombre} si el cliente
                   existe en BD. Luna evita pedir lo que ya tiene.
    phone: E.164 teléfono del cliente (ej. +56958655810) para usar como external_id en PropuestaReserva
    canal: 'whatsapp' o similar (para validación de propuestas)
    """
    # 1) Heurística de escalamiento antes de gastar tokens.
    motivo_pre = escalation.pre_escalar(mensaje)
    if motivo_pre:
        return _borrador_escala(motivo_pre)

    # 1b) H-090: si el cliente acaba de aceptar un cambio de ambientación, lo hace
    # el CÓDIGO y el CÓDIGO redacta la confirmación. No se le pide al modelo que
    # encadene quitar+agregar: ya se comprobó que en ese turno narra en vez de
    # ejecutar. Corta el turno acá — la acción ya pasó y el texto la refleja.
    try:
        confirmacion = aplicar_upgrade_si_acepto(canal, phone, mensaje, historial)
    except Exception as exc:  # noqa: BLE001 — nunca romper el turno por esto
        logger.exception('[H-090] error evaluando el cambio de ambientación: %s', exc)
        confirmacion = ''
    if confirmacion:
        return {'escalar': False, 'motivo': '', 'texto': confirmacion, 'modelo': 'codigo',
                'error': '', 'input_tokens': 0, 'output_tokens': 0, 'latency_ms': 0}

    # 2) Catálogo vivo (grounding).
    try:
        catalogo = grounding.catalogo_vivo()
    except Exception as exc:  # noqa: BLE001 — nunca romper por el catálogo
        logger.exception('Agente WA: error armando catálogo: %s', exc)
        return _borrador_escala('no se pudo cargar el catálogo', error=str(exc)[:200])

    # Armado de prompts. Un error aquí (ej. llave sin escapar en un f-string del
    # prompt → NameError) NUNCA debe tragarse en null global: deriva a humano.
    try:
        system_prompt = prompt_mod.build_system_prompt(
            config.persona_tono, catalogo, config.link_reserva, config.conocimiento,
            fecha_hoy=_fecha_hoy_texto(), saludo_estado=saludo_estado, saludo_nombre=saludo_nombre)
        # Estado en curso (carrito + cotización vigente) leído de la BD, para que Luna no
        # dependa de la ventana de mensajes ni de "recordar" lo ya armado.
        estado_actual = _estado_estructurado(canal, phone)
        user_prompt = prompt_mod.build_user_prompt(
            historial, mensaje, datos_cliente=datos_cliente, estado_actual=estado_actual)
    except Exception as exc:  # noqa: BLE001 — nunca romper por el armado del prompt
        logger.exception('Agente WA: error armando el prompt: %s', exc)
        return _borrador_escala('no se pudo armar el prompt', error=str(exc)[:200])

    modelo = _modelo_efectivo(config)

    # 3) Llamada al LLM con tool-calling (disponibilidad). El provider nunca lanza;
    #    igual lo blindamos. Si el modelo no llama la tool, responde texto directo.

    # H-028 FIX: Crear closure de executor que capture el phone real para preparar_reserva
    def _tool_executor_con_contexto(name, args):
        """Ejecuta las tools del agente. Captura el phone del cliente para PropuestaReserva."""
        if name == 'consultar_disponibilidad':
            from .availability import disponibilidad
            try:
                args = args or {}
                # NO defaultear a 1 persona: el precio es POR PERSONA, así que asumir 1
                # daría total y disponibilidad mal. Si el cliente no dijo la cantidad,
                # forzamos a Luna a preguntarla en vez de inventarla.
                personas_raw = args.get('personas')
                try:
                    personas = int(personas_raw)
                except (TypeError, ValueError):
                    personas = 0
                if personas < 1:
                    return {'error': 'falta_personas',
                            'mensaje': 'Antes de consultar disponibilidad, pregúntale al cliente para cuántas personas será. NO asumas 1.'}
                # H-088 (Jorge 2026-08-01: "ofrece 2 alternativas cuando dijimos que
                # ofreciera solo una"). La REGLA DURA H-081 mandaba usar
                # `alternativas_experiencia` para horarios de tina/masaje, pero la
                # DESCRIPCIÓN de esta herramienta decía "úsala SIEMPRE para precio o
                # disponibilidad": dos "siempre" contradictorios, y ganó el que está
                # pegado a la decisión de llamar la función. Además esta devolvía
                # TODAS las tinas con TODOS sus slots — la forma del dato ERA una
                # lista, así que el modelo la listó. Se fuerza en CÓDIGO: horarios de
                # tina/masaje en una fecha salen con la misma forma de UNA
                # recomendación. Si el dato no viene como lista, no se puede listar.
                fecha = args.get('fecha')
                tipo_exp = ruta_una_recomendacion(args.get('tipo'), fecha)
                if tipo_exp:
                    return _tool_alternativas_experiencia(
                        {'tipo': tipo_exp, 'fecha': fecha, 'personas': personas})
                return disponibilidad(fecha, personas, args.get('tipo'))
            except Exception as exc:  # noqa: BLE001
                logger.exception('Agente WA: tool disponibilidad falló: %s', exc)
                return {'error': 'no se pudo consultar disponibilidad'}
        if name == 'consultar_disponibilidad_combo':
            # H-031: enrutador determinístico — Luna lista los servicios, el código elige la rama.
            from .packs import router_disponibilidad
            try:
                args = args or {}
                try:
                    personas = int(args.get('personas'))
                except (TypeError, ValueError):
                    personas = 0
                if personas < 1:
                    return {'error': 'falta_personas',
                            'mensaje': 'Antes de consultar, pregúntale al cliente para cuántas personas será. NO asumas 1.'}
                return router_disponibilidad(args.get('servicios'), args.get('fecha'), personas)
            except Exception as exc:  # noqa: BLE001
                logger.exception('Agente WA: tool combo falló: %s', exc)
                return {'error': 'no se pudo consultar disponibilidad'}
        if name == 'consultar_disponibilidad_pack':
            from .packs import disponibilidad_pack_tina_masaje
            try:
                return disponibilidad_pack_tina_masaje(
                    (args or {}).get('fecha'),
                    (args or {}).get('personas', 2),
                    mas_tarde=bool((args or {}).get('mas_tarde', False)),
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception('Agente WA: tool pack falló: %s', exc)
                return {'error': 'no se pudo componer el pack'}
        if name == 'consultar_disponibilidad_pack_cabana':
            from .packs import disponibilidad_pack_cabana_tina
            try:
                return disponibilidad_pack_cabana_tina((args or {}).get('fecha'))
            except Exception as exc:  # noqa: BLE001
                logger.exception('Agente WA: tool pack cabaña falló: %s', exc)
                return {'error': 'no se pudo componer el pack de cabaña'}
        if name == 'consultar_disponibilidad_alojamiento_multinoche':
            from .availability import disponibilidad_alojamiento_multinoche
            try:
                return disponibilidad_alojamiento_multinoche(
                    (args or {}).get('fecha_llegada'),
                    (args or {}).get('personas', 1),
                    noches=(args or {}).get('noches'),
                    fecha_salida=(args or {}).get('fecha_salida'),
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception('Agente WA: tool alojamiento multinoche falló: %s', exc)
                return {'error': 'no se pudo consultar disponibilidad de alojamiento'}
        if name == 'verificar_cliente':
            # H-028: verificar si cliente existe y qué datos le faltan
            from django.conf import settings
            try:
                args = args or {}
                telefono = (args.get('telefono') or '').strip()
                # En WhatsApp el teléfono es el external_id de la conversación: Luna NO
                # lo ve en el chat, así que lo usamos directo para no pedírselo al cliente.
                if not telefono and canal == 'whatsapp':
                    telefono = external_id
                if not telefono:
                    return {
                        'success': False,
                        'error': 'telefono_requerido',
                        'mensaje': 'Teléfono es requerido'
                    }

                # Llamar al endpoint lookup_cliente vía ClienteService
                from ventas.services.cliente_service import ClienteService
                try:
                    cliente, telefono_normalizado = ClienteService.buscar_cliente_por_telefono(telefono)
                except Exception:
                    cliente = None
                    telefono_normalizado = None

                if cliente:
                    # Cliente existe: devolver datos + campos faltantes. El nombre
                    # pasa por el gate H-067: un nombre basura (pushname con
                    # emojis/símbolos) se trata como "sin nombre" → Luna lo pide.
                    nombre_ok = prompt_mod.nombre_presentable(cliente.nombre or '')
                    faltan = []
                    if not nombre_ok:
                        faltan.append('nombre')
                    if not cliente.email:
                        faltan.append('email')
                    if not cliente.documento_identidad:
                        faltan.append('documento_identidad')
                    if not cliente.region_id:
                        faltan.append('region')

                    return {
                        'existe': True,
                        'cliente_id': cliente.id,
                        'nombre': nombre_ok or None,
                        'email': cliente.email,
                        'documento_identidad': cliente.documento_identidad,
                        'region': cliente.region.nombre if cliente.region else None,
                        'faltan': faltan
                    }
                else:
                    # Cliente no existe: pedir todos los datos
                    return {
                        'existe': False,
                        'faltan': ['nombre', 'email', 'documento_identidad', 'region']
                    }
            except Exception as exc:  # noqa: BLE001
                logger.exception('Agente WA: tool verificar_cliente falló: %s', exc)
                return {
                    'success': False,
                    'error': 'internal_error',
                    'mensaje': f'Error verificando cliente: {str(exc)[:100]}'
                }
        if name == 'preparar_reserva':
            from .reserva_service import preparar_reserva as servicio_preparar_reserva
            from ventas.services.cliente_service import ClienteService
            try:
                args = args or {}

                # H-028 FIX: Usar el phone REAL del cliente (capturado en la closure)
                external_id = phone if phone else '+56912345678'
                logger.info(f'[preparar_reserva] Usando external_id={external_id} para PropuestaReserva')

                # H-028 FIX: Luna pasa comuna (string), deducir region_id de la comuna
                region_id = None
                comuna_nombre = args.get('comuna', '').strip()
                if comuna_nombre:
                    from ventas.models import Comuna
                    try:
                        # Buscar comuna por nombre y deducir región
                        logger.info(f'[preparar_reserva] Buscando comuna: "{comuna_nombre}"')
                        comuna = Comuna.objects.filter(nombre__icontains=comuna_nombre).first()
                        if not comuna:
                            # Debug: listar todas las comunas para verificar
                            todas = list(Comuna.objects.values_list('nombre', flat=True)[:10])
                            logger.warning(f'Comuna "{comuna_nombre}" no encontrada. Ejemplos en BD: {todas}')
                            return {
                                'success': False,
                                'error': 'comuna_not_found',
                                'mensaje': f'Comuna "{comuna_nombre}" no encontrada'
                            }
                        region_id = comuna.region_id
                    except Exception as e:
                        logger.warning(f'Error buscando comuna "{comuna_nombre}": {e}')
                        return {
                            'success': False,
                            'error': 'internal_error',
                            'mensaje': f'Error al buscar comuna: {str(e)[:100]}'
                        }

                # Construir payload compatible con preparar_reserva()
                cliente_data = {
                    'nombre': args.get('nombre', '').strip(),
                    'email': args.get('email', '').strip(),
                    # En WhatsApp el teléfono es el external_id; crear_reserva lo exige.
                    'telefono': (args.get('telefono') or (external_id if canal == 'whatsapp' else '')).strip(),
                    'documento_identidad': args.get('documento_identidad', '').strip(),
                    'region_id': region_id,
                    'comuna_id': None,  # Opcional por ahora
                }
                # Defensa en código: no crear reserva con una hora alucinada que no
                # corresponde a un slot real (ej. 16:30).
                from .availability import validar_hora_es_slot
                err_hora = validar_hora_es_slot(args.get('servicio_id'), args.get('fecha'), args.get('hora'))
                if err_hora:
                    return {'success': False, **err_hora}
                servicios = [{
                    'servicio_id': args.get('servicio_id'),
                    'fecha': _fecha_iso(args.get('fecha')),
                    'hora': args.get('hora'),
                    'cantidad_personas': args.get('cantidad_personas', 1),
                }]
                payload = {
                    'cliente': cliente_data,
                    'servicios': servicios,
                    'metodo_pago': 'pendiente',
                }
                resultado = servicio_preparar_reserva(
                    canal=canal,
                    external_id=external_id,
                    payload=payload,
                    idempotency_key=None
                )
                if not resultado.get('success'):
                    logger.error(f'[preparar_reserva FAILED] Error: {resultado.get("error")}, Mensaje: {resultado.get("mensaje")}')
                return resultado
            except Exception as exc:  # noqa: BLE001
                logger.exception('Agente WA: tool preparar_reserva EXCEPCIÓN: %s', exc)
                return {'error': f'no se pudo preparar reserva: {str(exc)[:100]}'}
        if name == 'alternativas_experiencia':
            # H-078: cotizador oficial — el motor arma las opciones, el modelo solo las presenta.
            try:
                return _tool_alternativas_experiencia(args)
            except Exception as exc:  # noqa: BLE001
                logger.exception('Agente WA: tool alternativas_experiencia falló: %s', exc)
                return {'error': f'no se pudo cotizar la experiencia: {str(exc)[:100]}'}
        if name == 'agregar_servicio_carrito':
            # H-029 FASE 2: agregar servicio al carrito
            from carrito_reservas.services import CarritoService
            try:
                args = args or {}
                # H-045 seguimiento: loguear lo que Luna realmente pidió — sin esto, cuando el
                # add "falla" no hay forma de saber si el servicio_id que mandó era el correcto
                # (caso real 2026-07-22: no se pudo confirmar si tomó el id equivocado o no).
                logger.info(
                    '[agregar_servicio_carrito] args recibidos: servicio_id=%s nombre_servicio=%s '
                    'fecha=%s hora=%s cantidad_personas=%s',
                    args.get('servicio_id'), args.get('nombre_servicio'), args.get('fecha'),
                    args.get('hora'), args.get('cantidad_personas'))
                servicio_id = args.get('servicio_id')
                # Override determinístico: si el LLM pasó el nombre que dijo el cliente y
                # resuelve a UN único servicio principal, usar ESE id (evita que el modelo
                # tome el id equivocado entre servicios parecidos, ej. "Llaima" vs "Puntiagudo").
                nombre_servicio = (args.get('nombre_servicio') or '').strip()
                if nombre_servicio:
                    from ventas.models import Servicio
                    from .availability import TIPOS_PRINCIPALES
                    matches = list(Servicio.objects.filter(
                        publicado_web=True, activo=True,
                        tipo_servicio__in=TIPOS_PRINCIPALES,
                        nombre__icontains=nombre_servicio,
                    ).values_list('id', flat=True)[:2])
                    if len(matches) == 1 and matches[0] != servicio_id:
                        logger.info('[agregar_servicio_carrito] override por nombre "%s": id %s → %s',
                                    nombre_servicio, servicio_id, matches[0])
                        servicio_id = matches[0]
                    elif len(matches) != 1:
                        # H-080: el nombre no resolvió a un principal → probar ambientaciones
                        # (categoría propia, tipo 'otro'; el catálogo H-079 las lista por nombre).
                        amb_id = _resolver_ambientacion(nombre_servicio)
                        if amb_id is not None and amb_id != servicio_id:
                            logger.info('[agregar_servicio_carrito] override ambientación "%s": id %s → %s',
                                        nombre_servicio, servicio_id, amb_id)
                            servicio_id = amb_id
                # H-080: una ambientación es UNA decoración por tina — su precio es por
                # unidad, no por persona (precio = base × cantidad_personas: con 2 se
                # duplicaría). Se fuerza 1 en código, pase lo que pase el modelo.
                es_ambientacion = servicio_id is not None and _es_ambientacion(servicio_id)
                if es_ambientacion:
                    # H-083: gate anti agregado prematuro — solo entra si el cliente la
                    # nombró o la aceptó en SU último mensaje (no basta la instrucción).
                    from ventas.models import Servicio as _ServH083
                    nombre_amb = (_ServH083.objects.filter(id=servicio_id)
                                  .values_list('nombre', flat=True).first()) or ''
                    if not _cliente_confirmo_ambientacion(mensaje, nombre_amb):
                        logger.info(
                            '[agregar_servicio_carrito] H-083: ambientación "%s" SIN confirmación '
                            'del cliente (mensaje: %r) → bloqueada', nombre_amb, (mensaje or '')[:80])
                        return {'success': False, 'error': 'requiere_confirmacion',
                                'mensaje': (f'El cliente aún NO ha confirmado la ambientación '
                                            f'"{nombre_amb}". NO la agregues todavía: responde su '
                                            f'pregunta u ofrécesela, y agrégala SOLO cuando él la '
                                            f'nombre o la acepte explícitamente.')}
                    cantidad = 1
                else:
                    # NO defaultear a 1 persona (el precio es POR PERSONA): exigir la cantidad
                    # real del cliente. Si falta, Luna debe preguntarla antes de agregar.
                    try:
                        cantidad = int(args.get('cantidad_personas'))
                    except (TypeError, ValueError):
                        cantidad = 0
                    if cantidad < 1:
                        return {'success': False, 'error': 'falta_personas',
                                'mensaje': 'Necesito saber para cuántas personas es. Pregúntale al cliente antes de agregar al carrito. NO asumas 1.'}
                    # H-085: en un turno de ASENTIMIENTO PURO ("sí") el cliente acepta lo
                    # YA ofrecido — no pudo haber cambiado las personas. Si declaró N en
                    # la conversación y el modelo pasa otra cosa, gana el cliente (caso
                    # real 2026-07-30: "Si" a la Pausa para 2 → el modelo agregó tina y
                    # masaje para 1 → $65.000 sin descuento de pack).
                    if _es_asentimiento_puro(mensaje):
                        declaradas = _personas_declaradas_por_cliente(historial)
                        if declaradas is not None and declaradas != cantidad:
                            logger.info(
                                '[agregar_servicio_carrito] H-085: personas %s → %s '
                                '(asentimiento puro; el cliente declaró %s)',
                                cantidad, declaradas, declaradas)
                            cantidad = declaradas
                # Defensa en código: el modelo liviano a veces inventa una hora que no
                # es un slot real (ej. 16:30). No agregar al carrito si la hora no existe.
                from .availability import validar_hora_es_slot
                err_hora = validar_hora_es_slot(servicio_id, args.get('fecha'), args.get('hora'))
                if err_hora:
                    logger.info(
                        '[agregar_servicio_carrito] hora inválida: servicio_id=%s fecha=%s hora=%s → %s',
                        servicio_id, args.get('fecha'), args.get('hora'), err_hora.get('mensaje'))
                    return {'success': False, **err_hora}
                external_id = phone if phone else 'desconocido'
                # H-043: si ya hay una propuesta vigente (cotización ya armada), sumar el SERVICIO
                # a ESA propuesta (recalcula total + descuento de pack) en vez de abrir un carrito
                # separado que la dejaría desincronizada (el masaje agregado tras cotizar no llegaba
                # al cajón). Espejo del camino de productos (H-040).
                from .reserva_service import agregar_servicio_a_propuesta
                actualizado = agregar_servicio_a_propuesta(
                    canal=canal, external_id=external_id, servicio_id=servicio_id,
                    fecha=_fecha_iso(args.get('fecha')), hora=args.get('hora'),
                    cantidad_personas=cantidad)
                if actualizado is not None:
                    logger.info(
                        '[agregar_servicio_carrito] fusionado a propuesta vigente: servicio_id=%s → '
                        'success=%s mensaje=%s',
                        servicio_id, actualizado.get('success'), actualizado.get('mensaje'))
                    return actualizado
                resultado = CarritoService.agregar_servicio(
                    canal=canal,
                    external_id=external_id,
                    servicio_id=servicio_id,
                    fecha=_fecha_iso(args.get('fecha')),
                    hora=args.get('hora'),
                    cantidad_personas=cantidad
                )
                logger.info(
                    '[agregar_servicio_carrito] servicio_id final=%s → success=%s error=%s mensaje=%s',
                    servicio_id, resultado.get('success'), resultado.get('error'), resultado.get('mensaje'))
                return resultado
            except Exception as exc:  # noqa: BLE001
                logger.exception('Agente WA: tool agregar_servicio_carrito falló: %s', exc)
                return {'error': f'no se pudo agregar servicio: {str(exc)[:100]}'}
        if name == 'agregar_producto_carrito':
            # H-029 FASE 2: agregar producto al carrito
            from carrito_reservas.services import CarritoService
            try:
                args = args or {}
                producto_id = args.get('producto_id')
                # El catálogo que ve Luna NO trae ids de producto (solo nombre/precio), así que
                # casi siempre llega solo el nombre. Resolver el id por nombre (match único
                # publicado y activo). Igual que el override por nombre de los servicios.
                nombre_producto = (args.get('nombre_producto') or '').strip()
                # H-089: el upgrade se evalúa ANTES de resolver el producto. Si se
                # chequeara después, publicar el extra suelto lo desactivaría en
                # silencio (pasó con el "Ramo de flores" el 2026-08-01): el producto
                # resolvería y jamás se ofrecería el cambio, más barato y sin duplicar.
                _oferta = oferta_upgrade_ambientacion(
                    canal, phone, f'{nombre_producto} {mensaje}')
                if _oferta:
                    return _oferta
                if nombre_producto:
                    from ventas.models import Producto
                    matches = list(Producto.objects.filter(
                        publicado_web=True, cantidad_disponible__gt=0,
                        nombre__icontains=nombre_producto,
                    ).values_list('id', flat=True)[:2])
                    if len(matches) == 1:
                        producto_id = matches[0]
                    elif len(matches) > 1:
                        return {'success': False, 'error': 'producto_ambiguo',
                                'mensaje': f'Hay varios productos que coinciden con "{nombre_producto}"; pedí al cliente que precise cuál.'}
                if not producto_id:
                    # H-080: el modelo suele tratar una AMBIENTACIÓN como "producto" (es un
                    # add-on, igual que tablas/jugos — caso real: "reservame la R1" llegó por
                    # esta tool). Si el nombre resuelve a UNA ambientación, se agrega como
                    # SERVICIO (cantidad 1, fecha/hora heredadas de la tina) en vez de fallar.
                    amb_id = _resolver_ambientacion(nombre_producto)
                    if amb_id is not None:
                        # H-083: mismo gate anti agregado prematuro que en el camino de servicio.
                        from ventas.models import Servicio as _ServH083b
                        nombre_amb = (_ServH083b.objects.filter(id=amb_id)
                                      .values_list('nombre', flat=True).first()) or nombre_producto
                        if not _cliente_confirmo_ambientacion(mensaje, nombre_amb):
                            logger.info(
                                '[agregar_producto_carrito] H-083: ambientación "%s" SIN confirmación '
                                'del cliente (mensaje: %r) → bloqueada', nombre_amb, (mensaje or '')[:80])
                            return {'success': False, 'error': 'requiere_confirmacion',
                                    'mensaje': (f'El cliente aún NO ha confirmado la ambientación '
                                                f'"{nombre_amb}". NO la agregues todavía: responde su '
                                                f'pregunta u ofrécesela, y agrégala SOLO cuando él la '
                                                f'nombre o la acepte explícitamente.')}
                        logger.info(
                            '[agregar_producto_carrito] "%s" resuelto como AMBIENTACIÓN (servicio %s) → cross-add',
                            nombre_producto, amb_id)
                        return _agregar_ambientacion_al_carrito(
                            canal, phone if phone else 'desconocido', amb_id)
                    return {'success': False, 'error': 'producto_no_resuelto',
                            'mensaje': f'No encontré el producto "{nombre_producto}" en el catálogo disponible.'}
                # H-084: gate anti variante-elegida-por-el-modelo (espejo del H-083 de
                # ambientaciones). "Si un jugo" NO autoriza a elegir el sabor: el producto
                # entra solo si el contexto del cliente lo desambigua.
                ok_variante, opciones_txt = _cliente_eligio_producto(mensaje, historial, producto_id)
                if not ok_variante:
                    logger.info(
                        '[agregar_producto_carrito] H-084: producto %s sin desambiguar por el '
                        'cliente (mensaje %r) → bloqueado; opciones: %s',
                        producto_id, (mensaje or '')[:80], opciones_txt)
                    return {'success': False, 'error': 'variante_no_confirmada',
                            'mensaje': (f'El cliente aún no especificó cuál quiere: hay varias '
                                        f'opciones parecidas ({opciones_txt}). Pregúntale cuál '
                                        f'prefiere en UNA frase (variantes inline, sin viñetas). '
                                        f'NO elijas tú por él.')}
                external_id = phone if phone else 'desconocido'
                # H-040 #1: si ya hay una propuesta vigente (Ritual/Refugio/pack ya cotizado),
                # sumar el producto a ESA propuesta (no abrir un carrito separado que la pisaría).
                from .reserva_service import agregar_producto_a_propuesta
                actualizado = agregar_producto_a_propuesta(
                    canal=canal, external_id=external_id,
                    producto_id=producto_id, cantidad=args.get('cantidad', 1))
                if actualizado is not None:
                    return actualizado
                resultado = CarritoService.agregar_producto(
                    canal=canal,
                    external_id=external_id,
                    producto_id=producto_id,
                    cantidad=args.get('cantidad', 1)
                )
                return resultado
            except Exception as exc:  # noqa: BLE001
                logger.exception('Agente WA: tool agregar_producto_carrito falló: %s', exc)
                return {'error': f'no se pudo agregar producto: {str(exc)[:100]}'}
        if name == 'ver_carrito':
            # H-029 FASE 2: ver carrito
            from carrito_reservas.services import CarritoService
            try:
                return CarritoService.ver_carrito(
                    canal=canal,
                    external_id=phone if phone else 'desconocido'
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception('Agente WA: tool ver_carrito falló: %s', exc)
                return {'error': f'no se pudo obtener carrito: {str(exc)[:100]}'}
        if name == 'quitar_item_carrito':
            # H-029 FASE 2: quitar item del carrito
            from carrito_reservas.services import CarritoService
            try:
                args = args or {}
                resultado = CarritoService.quitar_item(
                    canal=canal,
                    external_id=phone if phone else 'desconocido',
                    indice=args.get('indice', 0)
                )
                return resultado
            except Exception as exc:  # noqa: BLE001
                logger.exception('Agente WA: tool quitar_item_carrito falló: %s', exc)
                return {'error': f'no se pudo quitar item: {str(exc)[:100]}'}
        if name == 'checkout_carrito':
            # H-029 FASE 2: iniciar checkout
            from carrito_reservas.services import CarritoService
            try:
                resultado = CarritoService.checkout_carrito(
                    canal=canal,
                    external_id=phone if phone else 'desconocido'
                )
                return resultado
            except Exception as exc:  # noqa: BLE001
                logger.exception('Agente WA: tool checkout_carrito falló: %s', exc)
                return {'error': f'no se pudo hacer checkout: {str(exc)[:100]}'}
        if name == 'confirmar_reserva_carrito':
            # H-029 FASE 2: colapsa checkout→verificar→preparar en UN paso determinístico.
            # Crea UNA PropuestaReserva con TODOS los items del carrito, keyeada por el
            # phone REAL del cliente (capturado en la closure, igual que preparar_reserva).
            from carrito_reservas.models import CarritoReserva
            from carrito_reservas.services import CarritoService
            from .reserva_service import preparar_reserva as servicio_preparar_reserva
            try:
                args = args or {}
                external_id = phone if phone else '+56912345678'

                carrito = CarritoReserva.objects.filter(canal=canal, external_id=external_id).first()
                if carrito is None or not carrito.items:
                    return {
                        'success': False,
                        'error': 'carrito_vacio',
                        'mensaje': 'No hay carrito con items para confirmar. Agregá servicios primero.'
                    }

                # Datos del cliente: lo que dio en la conversación (args) PRIORIZA, y se
                # completa con la ficha del cliente existente (datos_cliente del scope).
                ficha = datos_cliente or {}
                nombre = (args.get('nombre') or ficha.get('nombre') or '').strip()
                email = (args.get('email') or ficha.get('email') or '').strip()
                documento = (args.get('documento_identidad') or ficha.get('documento_identidad') or '').strip()
                comuna_nombre = (args.get('comuna') or ficha.get('comuna_nombre') or '').strip()
                # Teléfono: en WhatsApp es el external_id de la conversación; en IG/Messenger
                # el cliente lo da explícito (external_id ahí es un PSID/IGSID, no un teléfono).
                telefono = (args.get('telefono') or '').strip()
                if not telefono and canal == 'whatsapp':
                    telefono = external_id

                # Deducir region_id de la comuna (igual que preparar_reserva).
                region_id = None
                comuna_id = ficha.get('comuna_id')
                if comuna_nombre:
                    from ventas.models import Comuna
                    comuna = Comuna.objects.filter(nombre__icontains=comuna_nombre).first()
                    if not comuna:
                        return {
                            'success': False,
                            'error': 'comuna_not_found',
                            'mensaje': f'Comuna "{comuna_nombre}" no encontrada'
                        }
                    region_id = comuna.region_id
                    comuna_id = comuna.id

                # Validar que tengamos los datos mínimos antes de crear la propuesta.
                faltan = [k for k, v in (('nombre', nombre), ('email', email),
                                         ('documento_identidad', documento), ('comuna', comuna_nombre),
                                         ('telefono', telefono)) if not v]
                if faltan:
                    return {
                        'success': False,
                        'error': 'faltan_datos',
                        'faltan': faltan,
                        'mensaje': f'Faltan datos del cliente: {", ".join(faltan)}'
                    }

                cliente_data = {
                    'nombre': nombre,
                    'email': email,
                    'telefono': telefono,
                    'documento_identidad': documento,
                    'region_id': region_id,
                    'comuna_id': comuna_id,
                }
                payload = CarritoService.construir_payload_reserva_desde_carrito(carrito, cliente_data)

                # Idempotencia: si Luna reintenta, no se duplica la propuesta del mismo carrito.
                resultado = servicio_preparar_reserva(
                    canal=canal,
                    external_id=external_id,
                    payload=payload,
                    idempotency_key=f'carrito-{carrito.id}',
                )
                if not resultado.get('success'):
                    logger.error('[confirmar_reserva_carrito] preparar_reserva falló: %s', resultado)
                    return resultado

                logger.info('[confirmar_reserva_carrito] propuesta %s creada para %s ($%s)',
                            resultado.get('propuesta_id', '')[:8], external_id, resultado.get('total'))
                total = resultado.get('total', 0)
                return {
                    'success': True,
                    'propuesta_id': resultado.get('propuesta_id'),
                    'total': total,
                    'mensaje': (
                        f'¡Perfecto! Te preparo la cotización (total ${total:,}) y te la '
                        f'enviamos en un momento para que la revises. 🌿'
                    ),
                }
            except Exception as exc:  # noqa: BLE001
                logger.exception('Agente WA: tool confirmar_reserva_carrito falló: %s', exc)
                return {'success': False, 'error': 'internal_error',
                        'mensaje': f'no se pudo confirmar la reserva: {str(exc)[:100]}'}
        if name == 'confirmar_ritual':
            # H-031 pieza 3: crea UNA propuesta del Ritual del Río (cabaña+tina+masaje+desayuno)
            # clavada en $240.000, sin pasar por el carrito. Mismo camino de cliente/propuesta
            # que confirmar_reserva_carrito, pero los servicios los arma construir_servicios_ritual.
            from .reserva_service import preparar_reserva as servicio_preparar_reserva
            from .packs import construir_servicios_ritual
            from carrito_reservas.services import CarritoService
            try:
                args = args or {}
                external_id = phone if phone else '+56912345678'

                fecha = (args.get('fecha') or '').strip()
                if not fecha:
                    return {'success': False, 'error': 'falta_fecha',
                            'mensaje': 'Indicá la fecha del Ritual.'}

                # H-044: si el cliente ya había agregado un producto (ej. una tabla) al
                # carrito ANTES de que existiera esta propuesta, se fusiona acá — si no,
                # quedaba huérfano en el carrito y nunca llegaba a la cotización final.
                productos_carrito = CarritoService.obtener_productos_pendientes(canal, external_id)

                armado = construir_servicios_ritual(fecha)
                if armado.get('error'):
                    return {'success': False, 'error': 'ritual_error', 'mensaje': armado['error']}
                if not armado.get('disponible'):
                    return {'success': False, 'error': 'ritual_no_disponible',
                            'mensaje': (armado.get('nota')
                                        or 'No hay disponibilidad para el Ritual esa fecha; ofrecé otra.')}

                # Datos del cliente: lo de la conversación (args) prioriza, completa con la ficha.
                ficha = datos_cliente or {}
                nombre = (args.get('nombre') or ficha.get('nombre') or '').strip()
                email = (args.get('email') or ficha.get('email') or '').strip()
                documento = (args.get('documento_identidad') or ficha.get('documento_identidad') or '').strip()
                comuna_nombre = (args.get('comuna') or ficha.get('comuna_nombre') or '').strip()
                telefono = (args.get('telefono') or '').strip()
                if not telefono and canal == 'whatsapp':
                    telefono = external_id

                region_id = None
                comuna_id = ficha.get('comuna_id')
                if comuna_nombre:
                    from ventas.models import Comuna
                    comuna = Comuna.objects.filter(nombre__icontains=comuna_nombre).first()
                    if not comuna:
                        return {'success': False, 'error': 'comuna_not_found',
                                'mensaje': f'Comuna "{comuna_nombre}" no encontrada'}
                    region_id = comuna.region_id
                    comuna_id = comuna.id

                faltan = [k for k, v in (('nombre', nombre), ('email', email),
                                         ('documento_identidad', documento), ('comuna', comuna_nombre),
                                         ('telefono', telefono)) if not v]
                if faltan:
                    return {'success': False, 'error': 'faltan_datos', 'faltan': faltan,
                            'mensaje': f'Faltan datos del cliente: {", ".join(faltan)}'}

                cliente_data = {
                    'nombre': nombre, 'email': email, 'telefono': telefono,
                    'documento_identidad': documento, 'region_id': region_id, 'comuna_id': comuna_id,
                }
                payload = {'cliente': cliente_data, 'servicios': armado['servicios'],
                           'productos': productos_carrito,
                           'metodo_pago': 'pendiente', 'es_ritual': True}

                resultado = servicio_preparar_reserva(
                    canal=canal,
                    external_id=external_id,
                    payload=payload,
                    idempotency_key=f'ritual-{external_id}-{armado["fecha"]}',
                )
                if not resultado.get('success'):
                    logger.error('[confirmar_ritual] preparar_reserva falló: %s', resultado)
                    return resultado

                # Ya quedaron dentro de la propuesta recién creada — limpiar del carrito
                # para no duplicarlos si el cliente agrega algo más después.
                if productos_carrito:
                    CarritoService.limpiar_productos(canal, external_id)

                total = resultado.get('total', 0)
                logger.info('[confirmar_ritual] propuesta %s creada para %s ($%s, descuento $%s)',
                            resultado.get('propuesta_id', '')[:8], external_id, total,
                            armado.get('descuento'))
                return {
                    'success': True,
                    'propuesta_id': resultado.get('propuesta_id'),
                    'total': total,
                    'mensaje': (
                        f'¡Perfecto! Te preparo la cotización de tu Ritual del Río (total ${total:,}) '
                        'y te la enviamos en un momento para que la revises. 🌿🌙'
                    ),
                }
            except Exception as exc:  # noqa: BLE001
                logger.exception('Agente WA: tool confirmar_ritual falló: %s', exc)
                return {'success': False, 'error': 'internal_error',
                        'mensaje': f'no se pudo confirmar el Ritual: {str(exc)[:100]}'}
        if name == 'consultar_disponibilidad_refugio':
            from .packs import disponibilidad_refugio
            try:
                args = args or {}
                return dict(disponibilidad_refugio(args.get('fecha')), rama='refugio')
            except Exception as exc:  # noqa: BLE001
                logger.exception('Agente WA: tool consultar_disponibilidad_refugio falló: %s', exc)
                return {'error': f'no se pudo consultar el Refugio: {str(exc)[:100]}'}
        if name == 'confirmar_refugio':
            # Refugio Aremko: crea UNA propuesta de 2 noches (misma cabaña) + tina + masaje +
            # desayuno, clavada en $290.000. Mismo camino de cliente/propuesta que confirmar_ritual.
            from .reserva_service import preparar_reserva as servicio_preparar_reserva
            from .packs import construir_servicios_refugio
            from carrito_reservas.services import CarritoService
            try:
                args = args or {}
                external_id = phone if phone else '+56912345678'

                fecha = (args.get('fecha') or '').strip()
                if not fecha:
                    return {'success': False, 'error': 'falta_fecha',
                            'mensaje': 'Indicá la fecha de llegada del Refugio.'}

                # H-044: mismo fix que confirmar_ritual — fusionar productos que ya
                # estaban sueltos en el carrito antes de que existiera esta propuesta.
                productos_carrito = CarritoService.obtener_productos_pendientes(canal, external_id)

                armado = construir_servicios_refugio(fecha)
                if armado.get('error'):
                    return {'success': False, 'error': 'refugio_error', 'mensaje': armado['error']}
                if not armado.get('disponible'):
                    return {'success': False, 'error': 'refugio_no_disponible',
                            'mensaje': (armado.get('nota')
                                        or 'No hay disponibilidad para el Refugio esa fecha; ofrecé otra.')}

                ficha = datos_cliente or {}
                nombre = (args.get('nombre') or ficha.get('nombre') or '').strip()
                email = (args.get('email') or ficha.get('email') or '').strip()
                documento = (args.get('documento_identidad') or ficha.get('documento_identidad') or '').strip()
                comuna_nombre = (args.get('comuna') or ficha.get('comuna_nombre') or '').strip()
                telefono = (args.get('telefono') or '').strip()
                if not telefono and canal == 'whatsapp':
                    telefono = external_id

                region_id = None
                comuna_id = ficha.get('comuna_id')
                if comuna_nombre:
                    from ventas.models import Comuna
                    comuna = Comuna.objects.filter(nombre__icontains=comuna_nombre).first()
                    if not comuna:
                        return {'success': False, 'error': 'comuna_not_found',
                                'mensaje': f'Comuna "{comuna_nombre}" no encontrada'}
                    region_id = comuna.region_id
                    comuna_id = comuna.id

                faltan = [k for k, v in (('nombre', nombre), ('email', email),
                                         ('documento_identidad', documento), ('comuna', comuna_nombre),
                                         ('telefono', telefono)) if not v]
                if faltan:
                    return {'success': False, 'error': 'faltan_datos', 'faltan': faltan,
                            'mensaje': f'Faltan datos del cliente: {", ".join(faltan)}'}

                cliente_data = {
                    'nombre': nombre, 'email': email, 'telefono': telefono,
                    'documento_identidad': documento, 'region_id': region_id, 'comuna_id': comuna_id,
                }
                payload = {'cliente': cliente_data, 'servicios': armado['servicios'],
                           'productos': productos_carrito,
                           'metodo_pago': 'pendiente', 'es_refugio': True}

                resultado = servicio_preparar_reserva(
                    canal=canal,
                    external_id=external_id,
                    payload=payload,
                    idempotency_key=f'refugio-{external_id}-{armado["fecha"]}',
                )
                if not resultado.get('success'):
                    logger.error('[confirmar_refugio] preparar_reserva falló: %s', resultado)
                    return resultado

                if productos_carrito:
                    CarritoService.limpiar_productos(canal, external_id)

                total = resultado.get('total', 0)
                logger.info('[confirmar_refugio] propuesta %s creada para %s ($%s, descuento $%s)',
                            resultado.get('propuesta_id', '')[:8], external_id, total,
                            armado.get('descuento'))
                return {
                    'success': True,
                    'propuesta_id': resultado.get('propuesta_id'),
                    'total': total,
                    'mensaje': (
                        f'¡Perfecto! Te preparo la cotización de tu Refugio Aremko (2 noches, total '
                        f'${total:,}) y te la enviamos en un momento para que la revises. 🌿🌙'
                    ),
                }
            except Exception as exc:  # noqa: BLE001
                logger.exception('Agente WA: tool confirmar_refugio falló: %s', exc)
                return {'success': False, 'error': 'internal_error',
                        'mensaje': f'no se pudo confirmar el Refugio: {str(exc)[:100]}'}
        if name == 'enviar_ficha_experiencia':
            try:
                from .packs import ficha_experiencia
                args = args or {}
                clave = (args.get('programa') or '').strip().lower()
                ficha = ficha_experiencia(clave)
                if not ficha:
                    return {'error': 'programa_invalido',
                            'mensaje': f'Programa "{clave}" no reconocido; usa ritual/refugio/pausa/aguas_calientes.'}
                return {
                    'success': True,
                    'nombre_experiencia': ficha['nombre'],
                    'url': ficha['url'],
                    'resumen': ficha['resumen'],
                    'mensaje_sugerido': (
                        f"Te dejo la ficha completa del {ficha['nombre']}: {ficha['url']} — ahí ves "
                        'fotos, el detalle y el precio 🌿'
                    ),
                }
            except Exception as exc:  # noqa: BLE001
                logger.exception('Agente WA: tool enviar_ficha_experiencia falló: %s', exc)
                return {'error': f'no se pudo obtener la ficha: {str(exc)[:100]}'}
        if name == 'buscar_reservas_cliente':
            # H-060: descubrimiento de reservas existentes (solo lectura)
            from .reserva_service import buscar_reservas_elegibles
            try:
                args = args or {}
                telefono = (args.get('telefono') or '').strip()
                if not telefono and canal == 'whatsapp':
                    telefono = external_id
                if not telefono:
                    return {'success': False, 'error': 'telefono_requerido',
                            'mensaje': 'Teléfono es requerido'}
                elegibles = buscar_reservas_elegibles(telefono)
                reservas = [{
                    'reserva_id': r['reserva_id'],
                    'numero': r['numero'],
                    'fecha_principal': r['fecha_principal'].isoformat() if r['fecha_principal'] else None,
                    'resumen_corto': r['resumen_corto'],
                    'estado_pago': r['estado_pago'],
                    'total': r['total'],
                } for r in elegibles]
                # H-091: sin reservas NO es callejón sin salida si hay una cotización
                # o un carrito en curso — hay que decírselo, o escala.
                if not reservas:
                    hay_cot, hay_carrito = _estado_cotizacion_carrito(canal, external_id)
                    logger.info(
                        '[buscar_reservas_cliente] 0 reservas para %s · cotización=%s carrito=%s',
                        telefono, hay_cot, hay_carrito)
                    return {'success': True, 'reservas': [],
                            'instruccion': instruccion_sin_reservas(hay_cot, hay_carrito)}
                logger.info('[buscar_reservas_cliente] %s reserva(s) elegibles para %s',
                            len(reservas), telefono)
                return {'success': True, 'reservas': reservas}
            except Exception as exc:  # noqa: BLE001
                logger.exception('Agente WA: tool buscar_reservas_cliente falló: %s', exc)
                return {'success': False, 'error': 'internal_error',
                        'mensaje': f'Error buscando reservas: {str(exc)[:100]}'}
        if name == 'agregar_servicio_a_reserva_existente':
            # H-060: GATE DE DEBORAH — propone (no aplica) agregar un servicio a una
            # reserva ya creada. Mismo patrón de resolución por nombre/validación de
            # hora que agregar_servicio_carrito.
            from .reserva_service import preparar_adicion_a_reserva
            from .availability import validar_hora_es_slot
            try:
                args = args or {}
                reserva_id = args.get('reserva_id')
                # H-091: este camino no dejaba NINGÚN rastro en los logs. Al
                # diagnosticar el caso del 2026-08-01 no se pudo distinguir "no lo
                # llamó" de "lo llamó y falló" — un agujero de observabilidad que
                # costó una ronda entera de ida y vuelta.
                logger.info(
                    '[agregar_servicio_a_reserva_existente] reserva_id=%s servicio_id=%s '
                    'nombre=%r fecha=%s hora=%s',
                    reserva_id, args.get('servicio_id'), args.get('nombre_servicio'),
                    args.get('fecha'), args.get('hora'))
                if not reserva_id:
                    return {'success': False, 'error': 'falta_reserva_id',
                            'mensaje': 'Falta el ID de la reserva; llamá primero buscar_reservas_cliente.'}
                servicio_id = args.get('servicio_id')
                nombre_servicio = (args.get('nombre_servicio') or '').strip()
                if nombre_servicio:
                    from ventas.models import Servicio
                    from .availability import TIPOS_PRINCIPALES
                    matches = list(Servicio.objects.filter(
                        publicado_web=True, activo=True,
                        tipo_servicio__in=TIPOS_PRINCIPALES,
                        nombre__icontains=nombre_servicio,
                    ).values_list('id', flat=True)[:2])
                    if len(matches) == 1 and matches[0] != servicio_id:
                        servicio_id = matches[0]
                if not servicio_id:
                    return {'success': False, 'error': 'servicio_no_resuelto',
                            'mensaje': f'No encontré el servicio "{nombre_servicio}" en el catálogo.'}
                try:
                    cantidad = int(args.get('cantidad_personas'))
                except (TypeError, ValueError):
                    cantidad = 0
                if cantidad < 1:
                    return {'success': False, 'error': 'falta_personas',
                            'mensaje': 'Necesito saber para cuántas personas es. Pregúntale al cliente antes. NO asumas 1.'}
                fecha_iso = _fecha_iso(args.get('fecha'))
                err_hora = validar_hora_es_slot(servicio_id, fecha_iso, args.get('hora'))
                if err_hora:
                    return {'success': False, **err_hora}

                external_id = phone if phone else 'desconocido'
                servicios_data = [{
                    'servicio_id': servicio_id, 'fecha': fecha_iso,
                    'hora': args.get('hora'), 'cantidad_personas': cantidad,
                }]
                resultado = preparar_adicion_a_reserva(
                    canal=canal, external_id=external_id, reserva_id=reserva_id,
                    servicios_data=servicios_data)
                if not resultado.get('success'):
                    return resultado
                return {
                    'success': True,
                    'propuesta_id': resultado['propuesta_id'],
                    'mensaje': (
                        f"¡Listo! Propuse agregar esto a tu Reserva RES-{reserva_id} "
                        f"(total adicional ${resultado['total']:,}). Te confirmamos en breve. 🌿"
                    ),
                }
            except Exception as exc:  # noqa: BLE001
                logger.exception('Agente WA: tool agregar_servicio_a_reserva_existente falló: %s', exc)
                return {'success': False, 'error': 'internal_error',
                        'mensaje': f'No se pudo preparar la adición: {str(exc)[:100]}'}
        if name == 'agregar_producto_a_reserva_existente':
            # H-060: GATE DE DEBORAH — propone (no aplica) agregar un producto a una
            # reserva ya creada. Mismo patrón de resolución por nombre que
            # agregar_producto_carrito.
            from .reserva_service import preparar_adicion_a_reserva
            try:
                args = args or {}
                reserva_id = args.get('reserva_id')
                if not reserva_id:
                    return {'success': False, 'error': 'falta_reserva_id',
                            'mensaje': 'Falta el ID de la reserva; llamá primero buscar_reservas_cliente.'}
                producto_id = args.get('producto_id')
                nombre_producto = (args.get('nombre_producto') or '').strip()
                if nombre_producto:
                    from ventas.models import Producto
                    matches = list(Producto.objects.filter(
                        publicado_web=True, cantidad_disponible__gt=0,
                        nombre__icontains=nombre_producto,
                    ).values_list('id', flat=True)[:2])
                    if len(matches) == 1:
                        producto_id = matches[0]
                    elif len(matches) > 1:
                        return {'success': False, 'error': 'producto_ambiguo',
                                'mensaje': f'Hay varios productos que coinciden con "{nombre_producto}"; pedí al cliente que precise cuál.'}
                if not producto_id:
                    return {'success': False, 'error': 'producto_no_resuelto',
                            'mensaje': f'No encontré el producto "{nombre_producto}" en el catálogo disponible.'}

                external_id = phone if phone else 'desconocido'
                productos_data = [{'producto_id': producto_id, 'cantidad': args.get('cantidad', 1)}]
                resultado = preparar_adicion_a_reserva(
                    canal=canal, external_id=external_id, reserva_id=reserva_id,
                    productos_data=productos_data)
                if not resultado.get('success'):
                    return resultado
                return {
                    'success': True,
                    'propuesta_id': resultado['propuesta_id'],
                    'mensaje': (
                        f"¡Listo! Propuse agregar esto a tu Reserva RES-{reserva_id} "
                        f"(total adicional ${resultado['total']:,}). Te confirmamos en breve. 🌿"
                    ),
                }
            except Exception as exc:  # noqa: BLE001
                logger.exception('Agente WA: tool agregar_producto_a_reserva_existente falló: %s', exc)
                return {'success': False, 'error': 'internal_error',
                        'mensaje': f'No se pudo preparar la adición: {str(exc)[:100]}'}
        return {'error': f'herramienta desconocida: {name}'}

    try:
        from destino_puerto_varas.services.llm.openrouter_provider import OpenRouterProvider
        provider = OpenRouterProvider()
        resultado = provider.generate_with_tools(
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt},
            ],
            tools=_TOOLS,
            tool_executor=_tool_executor_con_contexto,
            model=modelo,
            max_tokens=config.max_tokens,
            temperature=float(config.temperature),
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception('Agente WA: provider lanzó excepción: %s', exc)
        return _borrador_escala('modelo no disponible', error=str(exc)[:200], modelo=modelo)

    tokens = (resultado.input_tokens, resultado.output_tokens, resultado.latency_ms)

    # 4) Fallback seguro: si el LLM falló, deriva a humano (no inventamos).
    if not resultado.ok:
        return _borrador_escala('modelo no disponible', error=resultado.error[:200],
                                modelo=modelo, tokens=tokens)

    # 5) ¿El LLM decidió escalar?
    escalar, motivo_llm, texto_limpio = escalation.parse_escalada(resultado.text)
    if escalar:
        return _borrador_escala(motivo_llm, modelo=modelo, tokens=tokens)

    texto = escalation.sanear_salida(texto_limpio)
    if not texto:
        # Quirk (gemini-flash): a veces devuelve VACÍO tras ejecutar tools (el force-text del
        # provider intenta primero un cierre natural; si tampoco, caemos acá). Si esas tools
        # cambiaron el carrito/propuesta con éxito, NO escalamos —la acción YA pasó— y damos un
        # cierre determinístico para que la conversación no se trabe (H-047).
        cierre = _cierre_fallback_tras_tools(resultado.tool_calls_executed)
        if cierre:
            logger.info('[Agente WA] modelo vacío tras tools → cierre determinístico')
            return {'escalar': False, 'motivo': '', 'texto': cierre, 'modelo': modelo, 'error': '',
                    'input_tokens': tokens[0], 'output_tokens': tokens[1], 'latency_ms': tokens[2]}
        return _borrador_escala('respuesta vacía del modelo', error='empty_output',
                                modelo=modelo, tokens=tokens)

    # H-045: el texto no está vacío, pero puede contradecir una tool que sí tuvo éxito en este
    # mismo turno (ver comentario junto a escalation.hay_contradiccion_exito_vs_texto). No se
    # manda así.
    if escalation.hay_contradiccion_exito_vs_texto(texto, resultado.tool_calls_executed):
        logger.warning(
            '[Agente WA] posible contradicción texto vs tool exitosa → escalar. Texto: %s',
            texto[:200])
        return _borrador_escala(
            'posible contradicción: el texto niega algo que una tool ya confirmó exitoso',
            modelo=modelo, tokens=tokens)

    # H-090: el espejo del anterior — el texto AFIRMA una mutación que ninguna tool
    # hizo. Sin esto, el cliente cree que su carrito cambió y no cambió.
    if escalation.afirma_mutacion_sin_tool(texto, resultado.tool_calls_executed):
        logger.warning(
            '[Agente WA] H-090: el texto afirma un cambio de carrito que NINGUNA tool hizo '
            '→ escalar. Texto: %s', texto[:200])
        return _borrador_escala(
            'el texto dice que se agregó/cambió algo, pero ninguna herramienta tocó el carrito',
            modelo=modelo, tokens=tokens)

    # H-096: si preguntó algo que El Pase ya responde, se le suma el link.
    texto = sumar_pase_si_pregunta(texto, mensaje, phone)

    return {
        'escalar': False, 'motivo': '', 'texto': texto, 'modelo': modelo, 'error': '',
        'input_tokens': tokens[0], 'output_tokens': tokens[1], 'latency_ms': tokens[2],
    }


def sumar_pase_si_pregunta(texto, mensaje_cliente, phone):
    """Agrega el link de El Pase cuando el cliente pregunta algo que vive ahí.

    Es la parte del guion de Deborah que Luna SÍ puede sostener. Ella no aguanta
    cinco turnos de "ábrelo… ¿lo ves?" (H-085, H-090), pero cuando el cliente
    pregunta por su cuenta, responder con El Pase logra lo mismo: abre la
    pantalla. Y de a una cosa, que es la regla de la casa (H-088).

    Va en CÓDIGO y no en el prompt por lo de siempre: una regla más entre veinte
    se cumple a veces. Además tapa un hueco real — Luna **no tiene** los datos de
    wifi, así que hoy no puede responder esa pregunta de ninguna forma.

    Es aditivo y no reescribe nada del modelo: en el peor caso sobra un link.
    """
    from . import pase as pase_mod

    try:
        tema = pase_mod.tema_del_pase(mensaje_cliente)
        if not tema:
            return texto

        venta = _reserva_vigente_del_cliente(phone)
        if venta is None:
            return texto   # sin reserva no hay Pase que mandar

        from ventas.views.ficha_reserva_view import url_ficha_reserva
        agregado = pase_mod.respuesta_del_pase(tema, url_ficha_reserva(venta.id))
        if not agregado or agregado in texto:
            return texto

        logger.info('[Agente WA] H-096: pregunta de %s → se suma El Pase (reserva %s)',
                    tema, venta.id)
        return f'{texto}\n\n{agregado}'
    except Exception:  # noqa: BLE001 — sumar un link jamás puede tumbar la respuesta
        logger.exception('[Agente WA] H-096: no se pudo sumar El Pase')
        return texto


def _reserva_vigente_del_cliente(phone):
    """La reserva vigente del cliente, o None.

    Solo reservas de hoy en adelante: el Pase de una visita del mes pasado no le
    sirve a nadie y confundiría más de lo que ayuda. Reusa el mismo buscador de
    cliente que el resto del agente — el teléfono de WhatsApp llega en formatos
    distintos y esa normalización ya está resuelta (ver H-067 / PhoneService).
    """
    from django.utils import timezone

    from ventas.models import VentaReserva
    from ventas.services.cliente_service import ClienteService

    if not (phone or '').strip():
        return None
    cliente, _ = ClienteService.buscar_cliente_por_telefono(phone)
    if not cliente:
        return None
    return (VentaReserva.objects
            .filter(cliente=cliente,
                    reservaservicios__fecha_agendamiento__gte=timezone.localdate())
            .exclude(estado_reserva='cancelado')
            .order_by('id')
            .last())


def generar_sugerencia(phone, *, forzar=False):
    """Devuelve la SugerenciaAgenteWhatsApp para el último entrante sin responder.

    None si el agente está apagado, no hay entrante pendiente, o el chat está
    pausado. Usa cache por wa_message_id salvo `forzar=True`.
    """
    config = get_config()
    if not config.activo:
        return None
    # Precedencia del mensaje de ausencia (H-008): si está activo, no se sugiere
    # borrador (la ausencia auto-responde por su cuenta en el inbound).
    if config.ausencia_activa:
        return None

    entrante = _entrante_a_responder(phone)
    if entrante is None:
        return None

    # Cache: ya generamos para este entrante.
    if not forzar:
        existente = SugerenciaAgenteWhatsApp.objects.filter(
            wa_message_id=entrante.wa_message_id
        ).first()
        if existente is not None:
            return existente

    # Pausa por conversación: SOLO en modos auto (para no pisar a un humano que
    # está atendiendo, ya que ahí el agente SÍ enviaría). En modo borrador no
    # aplica: sugerir es inofensivo y útil aunque haya un saliente reciente (el
    # agente no manda nada; aremko-cli solo precarga el cajón si está vacío).
    if config.modo != 'borrador' and _conversacion_pausada(phone, config.pausa_horas_tras_humano):
        return None

    historial = _historial_texto(phone, entrante.timestamp, config.history_window)
    saludo_estado, saludo_nombre = _contexto_saludo(entrante)
    # H-028 FIX: Obtener datos del cliente existente (si los hay)
    datos_cliente = _obtener_datos_cliente_por_phone(phone)
    d = _producir_borrador(config, entrante.body, historial,
                           saludo_estado=saludo_estado, saludo_nombre=saludo_nombre,
                           datos_cliente=datos_cliente, phone=phone, canal='whatsapp')
    return _guardar(
        entrante, texto=d['texto'], escalar=d['escalar'], motivo=d['motivo'],
        modo=config.modo, modelo=d['modelo'], error=d['error'],
        input_tokens=d['input_tokens'], output_tokens=d['output_tokens'],
        latency_ms=d['latency_ms'],
    )
