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

from django.utils import timezone

from . import escalation, grounding, prompt as prompt_mod
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
            'nombre': cliente.nombre if cliente.nombre else None,
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
            'fecha, sus HORARIOS libres. Úsala SIEMPRE para responder precio o disponibilidad — NO '
            'calcules precios tú. Para una pregunta de solo precio ("¿cuánto vale para 2?"), llama '
            'con `personas` y SIN `fecha`. Para disponibilidad ("¿hay el sábado?"), incluye `fecha` '
            '(ACEPTA "el sábado", "25 de junio" O formato YYYY-MM-DD; la herramienta resuelve '
            'internamente). Devuelve por servicio: `precio_total` (úsalo tal cual), `precio_por_persona`, '
            '`duracion_texto` (ej. "4 h" o "por noche"), `dia_semana` (devuelto por la herramienta) '
            'y `slots_libres`. USA SIEMPRE el `dia_semana` devuelto, NUNCA calcules tú.'
        ),
        'parameters': {
            'type': 'object',
            'properties': {
                'personas': {'type': 'integer', 'description': 'Cantidad de personas'},
                'fecha': {'type': 'string', 'description': 'Fecha YYYY-MM-DD (omitir si es solo precio)'},
                'tipo': {'type': 'string', 'enum': ['tina', 'masaje', 'cabana'],
                         'description': 'Tipo de servicio (opcional; omitir para todos)'},
            },
            'required': ['personas'],
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
            'fecha y personas.'
        ),
        'parameters': {
            'type': 'object',
            'properties': {
                'fecha': {'type': 'string', 'description': 'Fecha YYYY-MM-DD'},
                'personas': {'type': 'integer', 'description': 'Cantidad de personas'},
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
            'Cada opción trae `desayuno` ($20.000 para dos, día siguiente ~10:00): OFRÉCELO SOLO '
            'si el cliente pregunta por desayuno. Si `tina` es null, ofrece solo la cabaña. '
            'Requiere fecha (la noche de check-in).'
        ),
        'parameters': {
            'type': 'object',
            'properties': {
                'fecha': {'type': 'string', 'description': 'Fecha de la noche (check-in) YYYY-MM-DD'},
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
            'Ejemplo: cliente "2 noches desde el sábado 27" → fecha_llegada="2026-06-27", noches=2. '
            'Devuelve cabañas libres en TODAS las noches del rango, cada una con `total_por_noche` '
            '(tarifa plana) y `total_estadia`. Muestra solo los totales, NUNCA el precio unitario por persona.'
        ),
        'parameters': {
            'type': 'object',
            'properties': {
                'fecha_llegada': {'type': 'string', 'description': 'Fecha check-in YYYY-MM-DD (REQUERIDO)'},
                'noches': {'type': 'integer', 'description': 'Número de noches (entero ≥1). PREFERIDO sobre fecha_salida.'},
                'personas': {'type': 'integer', 'description': 'Cantidad de personas (1-2)'},
                'fecha_salida': {'type': 'string', 'description': 'Fecha check-out YYYY-MM-DD (alternativa si no tienes noches)'},
            },
            'required': ['fecha_llegada', 'personas'],
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
                'fecha': {'type': 'string', 'description': 'Fecha YYYY-MM-DD (REQUERIDO)'},
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
            'Devuelve: {success, carrito: {items_count, total, items}}'
        ),
        'parameters': {
            'type': 'object',
            'properties': {
                'servicio_id': {'type': 'integer', 'description': 'ID del servicio (tina/masaje/cabaña)'},
                'fecha': {'type': 'string', 'description': 'Fecha YYYY-MM-DD'},
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
            'Agrega un producto al carrito (tablas de queso, jugos, etc.). '
            'H-029 FASE 2. Mezcla servicios + productos en el mismo carrito.'
        ),
        'parameters': {
            'type': 'object',
            'properties': {
                'producto_id': {'type': 'integer', 'description': 'ID del producto'},
                'cantidad': {'type': 'integer', 'description': 'Cantidad a agregar'},
            },
            'required': ['producto_id', 'cantidad'],
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
            'DESPUÉS de esto: verificar_cliente → pedir datos que falten → confirmar → preparar_reserva.'
        ),
        'parameters': {
            'type': 'object',
            'properties': {},
            'required': [],
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


def _producir_borrador(config, mensaje, historial='', saludo_estado='', saludo_nombre='', datos_cliente=None, phone='', canal='whatsapp'):
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

    # 2) Catálogo vivo (grounding).
    try:
        catalogo = grounding.catalogo_vivo()
    except Exception as exc:  # noqa: BLE001 — nunca romper por el catálogo
        logger.exception('Agente WA: error armando catálogo: %s', exc)
        return _borrador_escala('no se pudo cargar el catálogo', error=str(exc)[:200])

    system_prompt = prompt_mod.build_system_prompt(
        config.persona_tono, catalogo, config.link_reserva, config.conocimiento,
        fecha_hoy=_fecha_hoy_texto(), saludo_estado=saludo_estado, saludo_nombre=saludo_nombre)
    user_prompt = prompt_mod.build_user_prompt(historial, mensaje, datos_cliente=datos_cliente)
    modelo = _modelo_efectivo(config)

    # 3) Llamada al LLM con tool-calling (disponibilidad). El provider nunca lanza;
    #    igual lo blindamos. Si el modelo no llama la tool, responde texto directo.

    # H-028 FIX: Crear closure de executor que capture el phone real para preparar_reserva
    def _tool_executor_con_contexto(name, args):
        """Ejecuta las tools del agente. Captura el phone del cliente para PropuestaReserva."""
        if name == 'consultar_disponibilidad':
            from .availability import disponibilidad
            try:
                return disponibilidad(
                    (args or {}).get('fecha'),
                    (args or {}).get('personas', 1),
                    (args or {}).get('tipo'),
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception('Agente WA: tool disponibilidad falló: %s', exc)
                return {'error': 'no se pudo consultar disponibilidad'}
        if name == 'consultar_disponibilidad_pack':
            from .packs import disponibilidad_pack_tina_masaje
            try:
                return disponibilidad_pack_tina_masaje(
                    (args or {}).get('fecha'),
                    (args or {}).get('personas', 2),
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
                    # Cliente existe: devolver datos + campos faltantes
                    faltan = []
                    if not cliente.nombre or len(cliente.nombre.strip()) < 3:
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
                        'nombre': cliente.nombre,
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
                    'documento_identidad': args.get('documento_identidad', '').strip(),
                    'region_id': region_id,
                    'comuna_id': None,  # Opcional por ahora
                }
                servicios = [{
                    'servicio_id': args.get('servicio_id'),
                    'fecha': args.get('fecha'),
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
        if name == 'agregar_servicio_carrito':
            # H-029 FASE 2: agregar servicio al carrito
            from carrito_reservas.services import CarritoService
            try:
                args = args or {}
                resultado = CarritoService.agregar_servicio(
                    canal=canal,
                    external_id=phone if phone else 'desconocido',
                    servicio_id=args.get('servicio_id'),
                    fecha=args.get('fecha'),
                    hora=args.get('hora'),
                    cantidad_personas=args.get('cantidad_personas', 1)
                )
                return resultado
            except Exception as exc:  # noqa: BLE001
                logger.exception('Agente WA: tool agregar_servicio_carrito falló: %s', exc)
                return {'error': f'no se pudo agregar servicio: {str(exc)[:100]}'}
        if name == 'agregar_producto_carrito':
            # H-029 FASE 2: agregar producto al carrito
            from carrito_reservas.services import CarritoService
            try:
                args = args or {}
                resultado = CarritoService.agregar_producto(
                    canal=canal,
                    external_id=phone if phone else 'desconocido',
                    producto_id=args.get('producto_id'),
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
        return _borrador_escala('respuesta vacía del modelo', error='empty_output',
                                modelo=modelo, tokens=tokens)

    return {
        'escalar': False, 'motivo': '', 'texto': texto, 'modelo': modelo, 'error': '',
        'input_tokens': tokens[0], 'output_tokens': tokens[1], 'latency_ms': tokens[2],
    }


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
