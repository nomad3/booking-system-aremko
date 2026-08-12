# -*- coding: utf-8 -*-
"""Venta de gift cards por Luna (pedido de Jorge 2026-08-12).

El caso que se caía: «quiero regalar dos masajes para mis papás» — Luna no
tenía camino y la venta moría ahí. Este módulo le da los dos pasos:

1. catalogo_giftcards(): las experiencias regalables, LEÍDAS DE LA BD en cada
   conversación. Jorge agrega «Masaje para dos» en el admin y Luna la ofrece
   en el mensaje siguiente, sin deploy.
2. preparar_giftcard(): arma la PropuestaReserva con payload['giftcards'] —
   el MISMO cajón que las reservas: Deborah aprueba, se crea la venta con sus
   GiftCards y sale el Pase con los datos de transferencia. Al registrarse el
   pago, la señal existente envía las cartas por email sola.

Lo que a propósito NO hay acá: disponibilidad. Una gift card no ocupa slot ni
tiene fecha — vale 365 días y el destinatario agenda después. Ese es además el
argumento de venta que Luna debe decir.
"""
import logging
import uuid
from datetime import timedelta

from django.utils import timezone

from whatsapp_agent.models import PropuestaReserva

logger = logging.getLogger(__name__)

# Tope defensivo por venta: Luna es un LLM y un «regalo para los 40 invitados»
# merece pasar por un humano, no crearse solo.
MAX_GIFTCARDS_POR_VENTA = 10
MONTO_MINIMO_VALOR = 20000       # tarjeta de valor libre: piso razonable
MONTO_MAXIMO_VALOR = 1000000


def cartas_en_payload(payload):
    """Cuántas CARTAS (unidades, no líneas) hay en una propuesta de gift cards."""
    return sum(max(1, int(item.get('cantidad') or 1))
               for item in (payload or {}).get('giftcards') or [])


def texto_incluye(productos_data):
    """«Incluye: 2 Jugo Natural de Frambuesa · 1 Tabla de Quesos», o '' si no hay.

    Jorge (2026-08-12): cuando alguien regala una experiencia y suma jugos o una
    tabla, eso es parte del REGALO — tiene que decirlo la carta que recibe la
    persona, no quedar como un producto suelto de la venta que nadie entrega.
    """
    from ventas.models import Producto

    if not productos_data:
        return ''
    partes = []
    for item in productos_data:
        try:
            producto = Producto.objects.get(id=item.get('producto_id'))
        except (Producto.DoesNotExist, ValueError, TypeError):
            continue  # un producto borrado no puede tumbar la venta
        partes.append(f"{max(1, int(item.get('cantidad') or 1))} {producto.nombre}")
    return 'Incluye: ' + ' · '.join(partes) if partes else ''


def _lineas_del_cliente(historial):
    """Solo lo que escribió el CLIENTE, normalizado."""
    import unicodedata
    salida = []
    for linea in (historial or '').splitlines():
        if not linea.startswith('[Cliente]:'):
            continue
        crudo = linea[len('[Cliente]:'):]
        plano = unicodedata.normalize('NFKD', crudo).encode('ascii', 'ignore').decode()
        salida.append(plano.lower())
    return salida


def _lo_dijo_el_cliente(texto, historial, minimo=0.6):
    """¿Ese texto salió del cliente, o lo inventó Luna?

    H-094 (2026-08-12): el gate anterior solo se cerraba si venían VACÍOS el
    destinatario y la dedicatoria. Luna lo esquivó en el mismo segundo —
    reintentó con un nombre inventado y la cotización salió igual (log de las
    18:20:17). Un dato que el modelo puede fabricar no es un dato del cliente.

    Se pide que al menos `minimo` de las palabras significativas aparezcan en
    lo que el cliente escribió: tolera que Luna corrija una tilde o el orden,
    pero no que invente «Para mi mamá con cariño» de la nada.
    """
    import unicodedata

    dicho = ' '.join(_lineas_del_cliente(historial))
    if not dicho:
        return False
    palabras = _palabras_clave(texto)
    if not palabras:
        # Nombre demasiado corto para el filtro de palabras («Ana», «Jo»):
        # se busca tal cual, sin tildes.
        plano = unicodedata.normalize('NFKD', texto or '')
        plano = plano.encode('ascii', 'ignore').decode().lower().strip()
        return bool(plano) and plano in dicho
    encontradas = sum(1 for p in palabras if p in dicho)
    return encontradas / len(palabras) >= minimo


# El orden de las preguntas lo fijó Jorge (2026-08-12): «Nombre del
# destinatario, después si quiere incluir una frase, correo suyo donde llegará
# la giftcard, nombre suyo. Así pregunta por pregunta se completan estos datos
# y luego se prepara la cotización».
#
# Vive acá y no en el prompt porque el prompt ya lo pedía y no alcanzó: Luna no
# sostiene guiones. La herramienta devuelve UNA pregunta por vez y se niega a
# cotizar hasta tenerlas todas.
def _falta(error, pregunta, detalle=''):
    """Falta un dato: se devuelve LA PREGUNTA, no un reto.

    `mensaje` es el campo que Luna copia al cliente (así se lo pide el prompt
    para el caso exitoso, y lo generaliza). El 2026-08-12 a las 14:45 esto se
    vio en vivo: el campo traía la instrucción interna y al cliente le llegó
    «ALTO. Todavía no se puede cotizar. Mandá al cliente EXACTAMENTE...».
    Vergonzoso y culpa del diseño, no del modelo.

    Ahora `mensaje` ES la pregunta: si Luna lo copia tal cual, el cliente lee
    justo lo que corresponde. Lo interno vive en `instruccion`, aparte.
    """
    return {
        'success': False,
        'error': error,
        'mensaje': pregunta,
        'siguiente_pregunta': pregunta,
        'instruccion': (f'{detalle}Falta un dato para cotizar. Mandá el campo '
                        f'`mensaje` tal cual, una sola pregunta, y esperá la '
                        f'respuesta del cliente antes de volver a llamar esta '
                        f'herramienta. No completes el dato vos.'),
    }


def catalogo_giftcards():
    """Experiencias regalables activas, compacto para el LLM.

    Devuelve {'success': True, 'experiencias': [...], 'nota': str}.
    """
    from ventas.models import GiftCardExperiencia

    experiencias = []
    for e in (GiftCardExperiencia.objects.filter(activo=True)
              .order_by('categoria', 'orden', 'nombre')):
        experiencias.append({
            'id': e.id_experiencia,
            'nombre': e.nombre,
            'categoria': e.get_categoria_display(),
            'precio': int(e.monto_fijo) if e.monto_fijo else None,
            'montos_sugeridos': [int(m) for m in (e.montos_sugeridos or [])],
            'descripcion': (e.descripcion or '')[:120],
        })
    return {
        'success': True,
        'experiencias': experiencias,
        'nota': ('Una gift card no lleva fecha: vale 1 año y quien la recibe '
                 'agenda cuando quiera. Ofrecé UNA opción a la vez.'),
    }


# Palabras que no distinguen una experiencia de otra. «para/dos/junto/río» NO
# están: «Masaje para dos» y «Tina para dos junto al río» se separan por ellas.
_PALABRAS_VACIAS = {'de', 'la', 'el', 'los', 'las', 'un', 'una', 'o', 'y',
                    'a', 'en', 'con', 'del', 'min', 'mins', 'minutos', 'hrs',
                    'giftcard', 'gift', 'card'}


def _palabras_clave(texto):
    """Palabras significativas, sin tildes, puntuación, números ni plurales.

    «Masaje Relajación o Descontracturante (50 min)» →
    {'masaje', 'relajacion', 'descontracturante'} — lo mismo dé cómo venga
    escrito: mayúsculas, tildes, paréntesis, puntos medios u orden.

    El plural se recorta a los DOS lados por igual, así que da lo mismo si
    coinciden en singular o no: «dos masajes» (la frase real de Jorge) tiene
    que calzar con «Masaje para Dos». «dos» queda intacto — solo se recorta
    con más de 3 letras.
    """
    import re
    import unicodedata

    plano = unicodedata.normalize('NFKD', texto or '')
    plano = plano.encode('ascii', 'ignore').decode().lower()
    palabras = set()
    for p in re.findall(r'[a-z]+', plano):
        if len(p) < 3 or p in _PALABRAS_VACIAS:
            continue
        palabras.add(p[:-1] if len(p) > 3 and p.endswith('s') else p)
    return palabras


def _resolver_experiencia(texto):
    """(experiencia, None) o (None, error_dict) a partir de id O nombre.

    Dos intentos reales de Jorge (2026-08-12) enseñaron esto:
    1. El resultado del catálogo no sobrevive entre turnos: al confirmar, el
       modelo reconstruye el nombre de memoria.
    2. Ese nombre reconstruido difiere del catálogo en puntuación, tildes o
       cola («(50 min)» vs «· 50 min»), así que un icontains literal tampoco
       alcanza.

    El calce va por PALABRAS normalizadas: si todas las palabras clave del
    texto están en el nombre de UNA sola experiencia activa, es esa. Si
    ninguna o varias, NO se adivina: el error devuelve el catálogo con ids
    para que el modelo se corrija en el mismo turno.
    """
    from ventas.models import GiftCardExperiencia

    activas = list(GiftCardExperiencia.objects.filter(activo=True))
    texto = (texto or '').strip()
    if texto:
        for e in activas:
            if e.id_experiencia == texto:
                return e, None
        claves = _palabras_clave(texto)
        if claves:
            candidatos = [e for e in activas
                          if claves <= _palabras_clave(e.nombre)
                          or claves == _palabras_clave(e.id_experiencia)]
            # Calce EXACTO primero: «Velada Sorpresa · Dulce» es subconjunto
            # de «… Dulce + hidromasaje», así que pedir la base siempre daba
            # ambigüedad y las 4 veladas simples eran irresolubles por nombre.
            # Si una candidata usa exactamente las mismas palabras, es esa.
            exactas = [e for e in candidatos
                       if _palabras_clave(e.nombre) == claves]
            if len(exactas) == 1:
                return exactas[0], None
            if len(candidatos) == 1:
                return candidatos[0], None

    disponibles = [{'id': e.id_experiencia, 'nombre': e.nombre,
                    'precio': int(e.monto_fijo) if e.monto_fijo else None}
                   for e in sorted(activas, key=lambda e: (e.categoria, e.orden))]
    return None, {
        'success': False, 'error': 'experiencia_no_existe',
        'mensaje': (f'No pude identificar la gift card «{texto}». Elegí el id '
                    'correcto de experiencias_disponibles y volvé a llamar '
                    'esta MISMA herramienta ahora — NO le muestres esta lista '
                    'al cliente ni le pidas que elija de nuevo.'),
        'experiencias_disponibles': disponibles,
    }


def preparar_giftcard(canal, external_id, cliente_data, giftcards_data,
                      idempotency_key=None, sin_datos_regalo=False,
                      historial=''):
    """Crea la propuesta de venta de gift cards (mismo cajón que las reservas).

    giftcards_data: [{experiencia_id, monto (solo si la experiencia es de
    valor libre), cantidad, destinatario_nombre, mensaje}]

    LA SECUENCIA DE PREGUNTAS LA MANDA ESTA HERRAMIENTA, no el prompt (Jorge,
    2026-08-12): destinatario → dedicatoria → email del comprador → nombre del
    comprador, UNA por mensaje. Mientras falte alguna, devuelve
    `siguiente_pregunta` y se niega a cotizar.

    Historia de por qué está acá y no en palabras:
      · 01:46 — Luna saltó al cierre y la carta salió «para su hijo».
        Se agregó el bloqueo por campos vacíos + el flag `sin_datos_regalo`.
      · 18:20 — el flag se verificó contra el historial (H-093)... y Luna
        reintentó EN EL MISMO SEGUNDO con un nombre inventado. Como los campos
        ya no venían vacíos, la puerta no se cerró y la cotización salió.
      · Ahora los datos además tienen que haber salido de la boca del cliente.

    Cada UNIDAD es una GiftCard propia. El precio SIEMPRE se lee del catálogo —
    el LLM no fija precios (defense in depth: igual que recalcular_propuesta).
    """
    from ventas.models import GiftCardExperiencia

    try:
        if not giftcards_data:
            return {'success': False, 'error': 'validation_error',
                    'mensaje': 'Debe incluir al menos una gift card'}

        # Primero: ¿qué se está regalando? Si el id no resuelve, el error trae el
        # catálogo y el modelo se corrige solo — enterarse de eso DESPUÉS de
        # cuatro preguntas al cliente sería absurdo.
        for gc in giftcards_data:
            _exp, error = _resolver_experiencia((gc.get('experiencia_id') or '').strip())
            if _exp is None:
                return error

        primera = giftcards_data[0] or {}
        destinatario = (primera.get('destinatario_nombre') or '').strip()
        dedicatoria = (primera.get('mensaje') or '').strip()
        nombre = (cliente_data.get('nombre') or '').strip()
        email = (cliente_data.get('email') or '').strip()

        # 1. ¿A nombre de quién va?
        if not destinatario:
            return _falta('falta_destinatario',
                          '¿A nombre de quién va la gift card? Contame su nombre 🌿')
        if not _lo_dijo_el_cliente(destinatario, historial):
            logger.info('[preparar_giftcard] H-094: destinatario %r no aparece en lo '
                        'que escribió el cliente → se pide de nuevo', destinatario[:40])
            return _falta('destinatario_no_lo_dijo_el_cliente',
                          '¿A nombre de quién va la gift card? Contame su nombre 🌿',
                          detalle='Ese nombre no lo dijo el cliente. ')

        # 2. ¿Quiere dejarle una frase escrita?
        if not dedicatoria and not sin_datos_regalo:
            return _falta('falta_dedicatoria',
                          '¿Querés incluirle una frase? Escribila como quieras '
                          'que aparezca en la carta ✨')
        if dedicatoria and not _lo_dijo_el_cliente(dedicatoria, historial):
            logger.info('[preparar_giftcard] H-094: dedicatoria inventada por el '
                        'modelo → se pide de nuevo')
            return _falta('dedicatoria_no_la_dijo_el_cliente',
                          '¿Querés incluirle una frase? Escribila como quieras '
                          'que aparezca en la carta ✨',
                          detalle='Esa frase no la escribió el cliente. ')

        # 3. ¿A qué correo se la mandamos? (la carta viaja por email)
        if not email or '@' not in email:
            return _falta('falta_email',
                          '¿A qué correo te enviamos la gift card? 📩')

        # 4. ¿A nombre de quién va la compra?
        if not nombre or len(nombre) < 3:
            return _falta('falta_nombre_comprador',
                          '¿Y cuál es tu nombre, para dejar la compra a tu nombre?')


        if idempotency_key:
            previa = PropuestaReserva.objects.filter(
                idempotency_key=idempotency_key).first()
            if previa and previa.esta_vigente():
                logger.info('[Luna] Propuesta giftcard duplicada (idempotente): %s',
                            idempotency_key[:24])
                return {'success': True, 'propuesta_id': previa.propuesta_id,
                        'resumen_texto': previa.resumen_texto,
                        'total': int(previa.total), 'duplicada': True}

        lineas, items, total, n_cartas = [], [], 0, 0
        for gc in giftcards_data:
            exp_id = (gc.get('experiencia_id') or '').strip()
            exp, error = _resolver_experiencia(exp_id)
            if exp is None:
                return error
            cantidad = max(1, int(gc.get('cantidad') or 1))

            if exp.tiene_monto_fijo():
                monto = int(exp.monto_fijo)
            else:
                # Tarjeta de valor: el monto lo elige el cliente, con pisos y
                # techos para que un typo del LLM no venda una carta de $2.
                try:
                    monto = int(gc.get('monto') or 0)
                except (TypeError, ValueError):
                    monto = 0
                if not (MONTO_MINIMO_VALOR <= monto <= MONTO_MAXIMO_VALOR):
                    return {'success': False, 'error': 'monto_invalido',
                            'mensaje': (f'Para «{exp.nombre}» falta el monto: entre '
                                        f'${MONTO_MINIMO_VALOR:,} y ${MONTO_MAXIMO_VALOR:,}')}

            n_cartas += cantidad
            total += monto * cantidad
            destinatario = (gc.get('destinatario_nombre') or '').strip()
            items.append({
                'experiencia_id': exp.id_experiencia,
                'experiencia_nombre': exp.nombre,
                'precio': monto,
                'cantidad': cantidad,
                'destinatario_nombre': destinatario,
                'mensaje': (gc.get('mensaje') or '').strip()[:500],
            })
            para = f' para {destinatario}' if destinatario else ''
            lineas.append(f'{cantidad}x Gift Card {exp.nombre}{para} = ${monto * cantidad:,}')

        if n_cartas > MAX_GIFTCARDS_POR_VENTA:
            return {'success': False, 'error': 'demasiadas_giftcards',
                    'mensaje': (f'Son {n_cartas} gift cards: para pedidos así de '
                                'grandes lo ve el equipo directamente.')}

        resumen = '🎁 ' + '\n🎁 '.join(lineas)
        propuesta = PropuestaReserva.objects.create(
            propuesta_id=str(uuid.uuid4()),
            idempotency_key=idempotency_key or '',
            canal=canal,
            external_id=external_id,
            payload={'cliente': cliente_data, 'servicios': [],
                     'giftcards': items},
            cliente_data=cliente_data,
            servicios=[],
            total=total,
            resumen_texto=resumen,
            estado='pendiente',
            # Mismo TTL que las reservas. Acá ni siquiera hay cupo en juego:
            # una propuesta vencida solo obliga a cotizar de nuevo.
            expires_at=timezone.now() + timedelta(hours=24),
        )
        logger.info('[Luna] Propuesta GIFTCARD %s para %s: %s cartas, $%s',
                    propuesta.propuesta_id[:8], external_id, n_cartas, f'{total:,}')
        return {'success': True, 'propuesta_id': propuesta.propuesta_id,
                'resumen_texto': resumen, 'total': total,
                'giftcards_count': n_cartas}
    except Exception as e:  # noqa: BLE001
        logger.exception('Error en preparar_giftcard: %s', e)
        return {'success': False, 'error': 'internal_error',
                'mensaje': f'No se pudo preparar la gift card: {str(e)[:100]}'}


def materializar_giftcards(venta, payload, cliente_comprador):
    """Crea las filas GiftCard de una propuesta aprobada sobre SU venta.

    Espejo de reservation_service.finalize (el camino de la web): por_cobrar,
    vencimiento 365 días, datos de comprador y destinatario. Cada unidad es
    una carta. La señal de Pago las envía por email al confirmarse el pago.
    Devuelve (cantidad creada, monto total): el caller debe sumar ese monto a
    su total ANTES de fijarlo — la señal de GiftCard recalcula desde las
    líneas y pisaría un total puesto a mano (la trampa documentada en el
    paso 4 de crear_reserva).
    """
    from ventas.models import GiftCard

    creadas, monto_total = 0, 0
    hoy = timezone.now().date()
    cliente_data = payload.get('cliente') or {}
    # Los agregados (jugos, tabla) van DENTRO de la carta y solo cuando hay UNA:
    # con varias no habría a cuál asignarlos, y Jorge decidió que esas ventas
    # queden simples (la regla se aplica antes, al agregar el producto).
    incluye = (texto_incluye(payload.get('productos'))
               if cartas_en_payload(payload) == 1 else '')
    for item in payload.get('giftcards') or []:
        for _ in range(max(1, int(item.get('cantidad') or 1))):
            GiftCard.objects.create(
                monto_inicial=item['precio'],
                monto_disponible=item['precio'],
                fecha_emision=hoy,
                fecha_vencimiento=hoy + timedelta(days=365),
                estado='por_cobrar',
                cliente_comprador=cliente_comprador,
                venta_reserva=venta,
                comprador_nombre=cliente_data.get('nombre', ''),
                comprador_email=cliente_data.get('email', ''),
                comprador_telefono=cliente_data.get('telefono', ''),
                destinatario_nombre=item.get('destinatario_nombre', ''),
                mensaje_personalizado=item.get('mensaje', ''),
                servicio_asociado=item.get('experiencia_id', ''),
                detalle_especial=incluye,
            )
            creadas += 1
            monto_total += int(item['precio'])
    if creadas:
        logger.info('[Luna] %s GiftCard(s) creadas para venta %s ($%s)',
                    creadas, venta.id, f'{monto_total:,}')
    return creadas, monto_total
