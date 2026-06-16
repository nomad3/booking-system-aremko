"""Tests de LÓGICA AISLADA de la bandeja omnicanal (sin DB, sin Django).

Correr desde la raíz del repo:
    python -m inbox_omnicanal.tests.test_logic
"""

from inbox_omnicanal import logic


def test_truthy():
    assert logic.truthy('1') is True
    assert logic.truthy('true') is True
    assert logic.truthy('SI') is True
    assert logic.truthy('sí') is True
    assert logic.truthy('on') is True
    assert logic.truthy('0') is False
    assert logic.truthy('false') is False
    assert logic.truthy('') is False
    assert logic.truthy(None) is False


def test_external_id_conversacion():
    # Entrante (is_echo=False): la conversación es el remitente (cliente).
    assert logic.external_id_conversacion('CLIENTE123', '17841400756478364', False) == 'CLIENTE123'
    # Eco (is_echo=True): la cuenta de Aremko envió → el cliente es el destinatario.
    assert logic.external_id_conversacion('17841400756478364', 'CLIENTE123', True) == 'CLIENTE123'
    # Eco sin destinatario → cae al from.
    assert logic.external_id_conversacion('CLIENTE123', '', True) == 'CLIENTE123'
    # Espacios se recortan.
    assert logic.external_id_conversacion('  CLIENTE123  ', '', False) == 'CLIENTE123'
    # Sin datos → ''.
    assert logic.external_id_conversacion('', '', False) == ''
    assert logic.external_id_conversacion(None, None, True) == ''


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
