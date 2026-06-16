"""Lógica pura de la bandeja omnicanal (sin Django) — testeable de forma aislada.

El repo no tiene esquema local usable (drift AR-034 + migraciones off), así que la
lógica pura se valida acá y la integración real se mide en prod tras deploy.
"""


def truthy(value):
    return str(value or '').strip().lower() in ('1', 'true', 'yes', 'si', 'sí', 'on')


def external_id_conversacion(from_igsid, to_igsid, is_echo):
    """IGSID que identifica la conversación = el del CLIENTE (no la cuenta de Aremko).

    En un eco (mensaje saliente que reporta Meta), el cliente es el destinatario
    (`to_igsid`); en un entrante, es el remitente (`from_igsid`). Si el dato del
    cliente viene vacío, cae al `from_igsid`. Devuelve '' si no hay ninguno.
    """
    from_igsid = (from_igsid or '').strip()
    to_igsid = (to_igsid or '').strip()
    elegido = (to_igsid if is_echo else from_igsid) or from_igsid
    return elegido
