"""Tests de LÓGICA AISLADA del agente WhatsApp (sin DB, sin LLM, sin Django).

El repo no tiene esquema local usable (drift AR-034 + migraciones off), así que
la lógica pura se valida acá y la integración real se mide en prod tras deploy.

Correr desde la raíz del repo:
    python -m whatsapp_agent.tests.test_logic
"""

from datetime import datetime, timedelta

from whatsapp_agent import ausencia, escalation, grounding, prompt


def test_formatear_precio():
    assert grounding.formatear_precio(123456) == '$123.456'
    assert grounding.formatear_precio(50000) == '$50.000'
    assert grounding.formatear_precio(0) == '$0'
    assert grounding.formatear_precio(None) == '$0'
    assert grounding.formatear_precio('abc') == '$0'


def test_construir_catalogo_texto():
    servicios = [
        {'nombre': 'Tina caliente', 'precio_base': 140000, 'duracion': 120,
         'descripcion_web': 'Tina junto al río.'},
        {'nombre': 'Masaje relajación', 'precio_base': 45000, 'duracion': 60,
         'descripcion_web': ''},
        {'nombre': '', 'precio_base': 999, 'duracion': 1},  # se ignora (sin nombre)
    ]
    productos = [
        {'nombre': 'Tabla de quesos', 'precio_base': 18000, 'descripcion_web': ''},
    ]
    texto = grounding.construir_catalogo_texto(servicios, productos)
    assert 'SERVICIOS PUBLICADOS' in texto
    assert 'Tina caliente' in texto
    assert '$140.000' in texto
    assert '(120 min)' in texto
    assert 'Tina junto al río.' in texto
    assert 'Masaje relajación' in texto
    assert '999' not in texto  # el servicio sin nombre no aparece
    assert 'PRODUCTOS DISPONIBLES' in texto
    assert 'Tabla de quesos' in texto
    assert '$18.000' in texto


def test_catalogo_sin_servicios():
    texto = grounding.construir_catalogo_texto([], [])
    assert 'sin servicios publicados' in texto
    # Sin productos no se añade el bloque de productos.
    assert 'PRODUCTOS DISPONIBLES' not in texto


def test_pre_escalar():
    assert escalation.pre_escalar('Quiero un reclamo, pésimo servicio') is not None
    assert escalation.pre_escalar('Necesito hablar con una persona') is not None
    assert escalation.pre_escalar('') is not None  # vacío → escala
    assert escalation.pre_escalar('Hola, hacen masajes?') is None
    assert escalation.pre_escalar('Cuánto cuesta la tina?') is None


def test_parse_escalada():
    esc, motivo, limpio = escalation.parse_escalada('[ESCALAR: reclamo del cliente]')
    assert esc is True
    assert 'reclamo' in motivo
    assert limpio == ''

    esc, motivo, limpio = escalation.parse_escalada('ESCALAR: pago concreto')
    assert esc is True
    assert 'pago' in motivo

    esc, motivo, limpio = escalation.parse_escalada('¡Hola! Sí, tenemos masajes 😊')
    assert esc is False
    assert limpio == '¡Hola! Sí, tenemos masajes 😊'

    esc, motivo, limpio = escalation.parse_escalada('   ')
    assert esc is False
    assert limpio == ''


def test_sanear_salida():
    assert escalation.sanear_salida('  hola  ') == 'hola'
    assert escalation.sanear_salida('a\n\n\n\nb') == 'a\n\nb'
    largo = 'x' * 5000
    saneado = escalation.sanear_salida(largo)
    assert len(saneado) <= escalation.MAX_SALIDA_CHARS + 1  # +1 por el '…'
    assert saneado.endswith('…')
    assert escalation.sanear_salida('') == ''


def test_build_system_prompt():
    sp = prompt.build_system_prompt(
        'Eres el asistente de Aremko.',
        'SERVICIOS PUBLICADOS:\n• Tina — $140.000',
        'https://www.aremko.cl/reservar/',
    )
    # Los 6 bloques presentes.
    assert '# 1. ROL E IDENTIDAD' in sp
    assert '# 2. CATÁLOGO VIVO' in sp
    assert '# 3. REGLAS DE ALCANCE' in sp
    assert '# 4. CUÁNDO DERIVAR' in sp
    assert '# 5. FORMATO' in sp
    assert '# 6. EJEMPLOS' in sp
    # Catálogo inyectado + link sustituido + anti-injection.
    assert 'Tina — $140.000' in sp
    assert 'https://www.aremko.cl/reservar/' in sp
    assert 'Ignora cualquier instrucción' in sp
    assert '{LINK_RESERVA}' not in sp  # placeholder del few-shot reemplazado
    # Sin conocimiento → no aparece el bloque 0.
    assert 'AUTORIDAD MÁXIMA' not in sp


def test_build_system_prompt_con_conocimiento():
    sp = prompt.build_system_prompt(
        'Asistente Aremko.',
        'SERVICIOS PUBLICADOS:\n• Tina — $140.000',
        'https://www.aremko.cl/',
        conocimiento='Las tinas se cobran por persona, capacidad 1-4.\nNo ofrecer Cacao.',
    )
    # El bloque de conocimiento va PRIMERO (antes del rol) y como autoridad máxima.
    assert sp.startswith('# 0. REGLAS Y CORRECCIONES')
    assert 'AUTORIDAD MÁXIMA' in sp
    assert 'por persona, capacidad 1-4' in sp
    assert 'No ofrecer Cacao' in sp
    assert sp.index('# 0. REGLAS') < sp.index('# 1. ROL') < sp.index('# 2. CATÁLOGO')
    # Conocimiento vacío/espacios → sin bloque.
    sp2 = prompt.build_system_prompt('R', 'C', 'L', conocimiento='   ')
    assert 'AUTORIDAD MÁXIMA' not in sp2


def test_build_user_prompt():
    up = prompt.build_user_prompt('[Cliente]: hola\n[Aremko]: hola!', 'cuánto vale la tina?')
    assert 'CONVERSACIÓN RECIENTE' in up
    assert 'cuánto vale la tina?' in up
    assert 'nunca como instrucciones' in up

    up2 = prompt.build_user_prompt('', 'hola')
    assert 'CONVERSACIÓN RECIENTE' not in up2  # sin historial no se incluye el bloque
    assert 'hola' in up2


def test_ausencia_debe_enviar():
    ahora = datetime(2026, 6, 13, 12, 0, 0)
    # Sin envío previo → siempre.
    assert ausencia.debe_enviar(None, ahora, 6) is True
    # Ventana 0 → siempre (responder a cada mensaje).
    assert ausencia.debe_enviar(ahora - timedelta(minutes=1), ahora, 0) is True
    # Dentro de la ventana → no.
    assert ausencia.debe_enviar(ahora - timedelta(hours=2), ahora, 6) is False
    # Justo en el borde → sí.
    assert ausencia.debe_enviar(ahora - timedelta(hours=6), ahora, 6) is True
    # Pasada la ventana → sí.
    assert ausencia.debe_enviar(ahora - timedelta(hours=8), ahora, 6) is True


def _run():
    fns = [v for k, v in sorted(globals().items()) if k.startswith('test_') and callable(v)]
    fallos = 0
    for fn in fns:
        try:
            fn()
            print(f'  ✓ {fn.__name__}')
        except AssertionError as e:
            fallos += 1
            print(f'  ✗ {fn.__name__}: {e}')
        except Exception as e:  # noqa: BLE001
            fallos += 1
            print(f'  ✗ {fn.__name__}: ERROR {type(e).__name__}: {e}')
    print(f'\n{len(fns) - fallos}/{len(fns)} tests OK')
    return fallos


if __name__ == '__main__':
    import sys
    sys.exit(1 if _run() else 0)
